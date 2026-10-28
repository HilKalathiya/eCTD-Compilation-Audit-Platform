"""Run the writer pipeline on every test task and report pass rate and speed.

    python -m writer_test.run --model gemma4:e4b
    python -m writer_test.run --backend mock          # no model, checks the harness
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from .facts import compute_facts
from .llm import MockClient, OllamaClient, OpenAIClient
from .prompt import build_messages, data_table, opening_sentence
from .rendercheck import verify_render
from .validator import render, validate

ROOT = Path(__file__).resolve().parent.parent


def make_client(args):
    if args.backend == "mock":
        return MockClient()
    if args.backend == "openai":
        return OpenAIClient(args.model, args.base_url or "http://localhost:8080/v1", args.num_predict)
    return OllamaClient(args.model, args.base_url or "http://localhost:11434", args.num_ctx, args.num_predict,
                        think=args.think == "on")


def write_section(task, facts, paragraph):
    return "\n\n".join([
        f"### {task['section']} Stability data: {task['attribute']}, {facts['condition']['value']}",
        opening_sentence(task, facts),
        data_table(task),
        render(paragraph, facts),
        "_Values in the paragraph were inserted by code from computed facts; the model wrote only the words._",
    ]) + "\n"


def run_task(client, task, args, log):
    facts, flags, required = compute_facts(task)
    messages = build_messages(task, facts, flags)
    drafts = []
    for i in range(args.max_drafts):
        # First draft is conservative; later drafts sample more widely for variety.
        temperature = args.temperature if i == 0 else args.retry_temperature
        reply = client.chat(messages, temperature, seed=1000 + i,
                            context={"task_id": task["task_id"], "flags": flags})
        if not reply["text"]:
            problems = ["empty output" + (" (the model spent its tokens thinking; use --think off or raise "
                                          "--num-predict)" if reply.get("thinking_chars") else "")]
        else:
            problems = validate(reply["text"], facts, flags, required)
            if not problems:  # second, independent route: re-read the finished text against the raw table
                problems = ["re-read of finished text: " + p
                            for p in verify_render(render(reply["text"], facts), task)]
        record = {"task_id": task["task_id"], "draft": i + 1, "passed": not problems,
                  "problems": problems, **reply}
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.flush()
        drafts.append(record)
        status = "PASS" if not problems else "fail: " + "; ".join(problems)
        print(f"  draft {i + 1}: {reply['seconds']:.1f}s, {reply['output_tokens']} tokens, {status}")
        if not problems:
            print(f"    {render(reply['text'], facts)}")  # the paragraph as it will appear, values filled in
            break
    winner = next((d for d in drafts if d["passed"]), None)
    return facts, flags, drafts, winner


def audit_data(task, facts):
    """The raw table on one line, so the person labelling does not need another file open."""
    from .facts import fmt
    head = "Months " + ", ".join(str(m) for m in task["months"])
    rows = [f"{b}: " + ", ".join(fmt(v, task["decimals"]) for v in vals) for b, vals in task["batches"].items()]
    return f"{task['attribute']} | {facts['spec']['value']} | {head} | " + " | ".join(rows)


def run_audit(client, tasks, args, out):
    """Many drafts per section, none thrown away. A person then reads every ACCEPTED paragraph and
    marks it right or wrong: the only unbiased test of whether the checks let a wrong paragraph through.

    Every draft is saved the moment it is written (audit_<time>.jsonl), and the spreadsheet gets a new
    name each run, so a file left open in Excel can never make a finished run lose its results."""
    import csv
    stamp = time.strftime("%Y%m%d_%H%M%S")
    live = out / f"audit_{stamp}.jsonl"
    rows = []
    with open(live, "w", encoding="utf-8") as log:
        for task in tasks:
            facts, flags, required = compute_facts(task)
            messages = build_messages(task, facts, flags)
            for i in range(args.audit):
                reply = client.chat(messages, 0.9, seed=2000 + i, context={"task_id": task["task_id"], "flags": flags})
                text = reply["text"]
                problems = validate(text, facts, flags, required) if text else ["empty output"]
                if not problems:
                    problems = [f"re-read: {p}" for p in verify_render(render(text, facts), task)]
                row = {"task_id": task["task_id"], "draft": i + 1, "accepted": "yes" if not problems else "no",
                       "why_rejected": "; ".join(problems), "finished_text": render(text, facts) if text else "",
                       "data (to check against)": audit_data(task, facts),
                       "raw_draft": text,
                       "human_verdict (ok / wrong / awkward)": "", "human_note": ""}
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
            print(f"  {task['task_id']}: {sum(r['accepted'] == 'yes' for r in rows if r['task_id'] == task['task_id'])}"
                  f" of {args.audit} accepted")
    path = out / f"audit_{stamp}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows the degree sign
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    acc = sum(r["accepted"] == "yes" for r in rows)
    print(f"\n{acc} of {len(rows)} drafts accepted. Open {path}, read every row with accepted = yes and "
          f"fill the human_verdict column. Pass mark: no 'wrong' among at least 100 accepted paragraphs (so use --audit 20 or more).")


def summarise(results, args, wall):
    n = len(results)
    first_pass = sum(1 for r in results if r["drafts"][0]["passed"])
    any_pass = sum(1 for r in results if r["winner"])
    per_section = [sum(d["seconds"] for d in r["drafts"]) for r in results]
    all_drafts = [d for r in results for d in r["drafts"]]
    gen_rates = [d["output_tokens"] / d["output_seconds"] for d in all_drafts if d["output_seconds"] > 0]
    pre_rates = [d["prompt_tokens"] / d["prompt_seconds"] for d in all_drafts if d["prompt_seconds"] > 0]
    reasons = {}
    for d in all_drafts:
        for p in d["problems"]:
            key = p.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    lines = [
        f"# Writer test: {args.backend} / {args.model}",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        f"| Sections | {n} |",
        f"| Passed on the first draft | {first_pass} of {n} |",
        f"| Passed within {args.max_drafts} drafts | {any_pass} of {n} |",
        f"| Drafts per section (mean) | {statistics.mean(len(r['drafts']) for r in results):.1f} |",
        f"| Seconds per section (mean) | {statistics.mean(per_section):.0f} |",
        f"| Seconds per section (slowest) | {max(per_section):.0f} |",
        f"| Generation speed (tokens/s, median) | {statistics.median(gen_rates):.1f} |" if gen_rates else
        "| Generation speed (tokens/s) | not reported by this backend |",
        f"| Prompt reading speed (tokens/s, median) | {statistics.median(pre_rates):.1f} |" if pre_rates else
        "| Prompt reading speed (tokens/s) | not reported by this backend |",
        f"| Total wall time | {wall / 60:.1f} min |",
        "",
        "Why drafts failed:",
        "",
    ] + ([f"- {k}: {v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])] or ["- none"])
    lines += ["", "Per section:", "", "| Task | Drafts | Passed | Seconds |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['task_id']} | {len(r['drafts'])} | {'yes' if r['winner'] else 'NO'} | "
              f"{sum(d['seconds'] for d in r['drafts']):.0f} |" for r in results]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["ollama", "openai", "mock"], default="ollama")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-drafts", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--retry-temperature", type=float, default=0.7)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=600)
    ap.add_argument("--think", choices=["off", "on"], default="off",
                    help="hidden reasoning for thinking models (Ollama only); off is faster")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("--data", default=str(ROOT / "data" / "tasks.json"))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--audit", type=int, default=0, metavar="N",
                    help="write N drafts per section at a high temperature, no early stop, to audit by hand")
    ap.add_argument("--export-prompts", action="store_true",
                    help="also write each prompt as text, to paste into another model for comparison")
    args = ap.parse_args()

    tasks = json.load(open(args.data, encoding="utf-8"))["tasks"]
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["task_id"] in wanted]
    tag = f"{args.backend}_{args.model}".replace(":", "-").replace("/", "-")
    out = Path(args.out) / tag
    (out / "sections").mkdir(parents=True, exist_ok=True)
    client = make_client(args)

    if args.audit:
        return run_audit(client, tasks, args, out)

    results, t0 = [], time.time()
    with open(out / "drafts.jsonl", "w", encoding="utf-8") as log:
        for task in tasks:
            print(f"{task['task_id']}:")
            facts, flags, drafts, winner = run_task(client, task, args, log)
            results.append({"task_id": task["task_id"], "drafts": drafts, "winner": winner})
            if winner:
                (out / "sections" / f"{task['task_id']}.md").write_text(
                    write_section(task, facts, winner["text"]), encoding="utf-8")
            if args.export_prompts:
                (out / "prompts").mkdir(exist_ok=True)
                msgs = build_messages(task, facts, flags)
                text = "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in msgs)
                (out / "prompts" / f"{task['task_id']}.txt").write_text(text, encoding="utf-8")
    summary = summarise(results, args, time.time() - t0)
    (out / "summary.md").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    print(f"Results saved in {out}")


if __name__ == "__main__":
    main()
