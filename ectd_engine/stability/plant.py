"""Retry test with a real model: three tasks get a planted bad first draft, then we see whether the model fixes it from the feedback.

    python -m ectd_engine.stability.plant --data evidence/T-065/heldout.csv --out evidence/T-065/retry/run1 --model gemma4:e4b
"""
import argparse
import json
import sys
from pathlib import Path

from ectd_engine.stability import facts as F, loop
from ectd_engine.stability.runner import run_p83

LABEL = "In illustrative demonstration data, "


def typed_digit(task):
    """Draft 1 types a digit instead of a placeholder."""
    return loop.mock_text(task).replace("[[min]]", "2.5")


def no_label(task):
    """Draft 1 drops the demonstration label from the second sentence."""
    first, second = loop.mock_text(task).split(". " + LABEL, 1)
    return first + ". " + second


def invented_conclusion(task):
    """Draft 1 adds a conclusion nobody may write."""
    return loop.mock_text(task) + " The product is stable and no significant change was observed."


PLANTS = {"typed_digit": typed_digit, "no_label": no_label, "invented_conclusion": invented_conclusion}


def choose(tasks):
    """3 (task id, plant name) pairs, fixed by the task ids: two tasks with results outside the limit and one without."""
    demo = sorted((t for t in tasks if t["kind"] == "demo"), key=lambda t: t["task_id"])
    out = [t for t in demo if "n_outside" in t["slots"]]
    inside = [t for t in demo if "n_outside" not in t["slots"]]
    return [(out[0]["task_id"], "typed_digit"), (out[1]["task_id"], "no_label"), (inside[0]["task_id"], "invented_conclusion")]


class PlantedFirstClient:
    """Gives the planned bad text as draft 1 of the chosen tasks (no model call), then asks the real model for every later draft."""

    def __init__(self, real, plan):
        self.real, self.plan, self.seen = real, plan, set()

    def chat(self, messages, temperature, seed, context=None, schema=None):
        tid = context["task_id"]
        if tid in self.plan and tid not in self.seen:
            self.seen.add(tid)
            return {"text": self.plan[tid], "seconds": 0, "output_tokens": 0, "planted": True}
        return self.real.chat(messages, temperature, seed, context=context, schema=schema)


def run_retry(real_client, out_dir, csv_path, seed=loop.SEED, temperature=0.0, max_drafts=loop.MAX_DRAFTS, heldout=True, log=print):
    """Run the 3 planted tasks into out_dir; write retry.json (one entry per task) and return it."""
    rows = F.load_rows(csv_path)
    tasks = [t for t in loop.make_tasks(F.p83_facts(rows, heldout)) if not (heldout and t["kind"] == "public")]
    by_id = {t["task_id"]: t for t in tasks}
    chosen = choose(tasks)
    plan = {tid: PLANTS[name](by_id[tid]) for tid, name in chosen}
    run_p83(PlantedFirstClient(real_client, plan), out_dir, csv_path=csv_path, max_drafts=max_drafts, seed=seed, temperature=temperature,
            only=[tid for tid, _ in chosen], meta={"retry_test": True, "planted": dict(chosen)}, log=log, heldout=heldout)
    results = {}
    with open(Path(out_dir) / "results.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            results[r["task_id"]] = r
    report = []
    for tid, name in chosen:
        r = results[tid]
        first = r["drafts"][0]
        planted_rejected = bool(first.get("planted")) and not first["passed"]
        report.append({"task_id": tid, "planted_error": name, "planted_draft": first["text"], "planted_problems": first["problems"],
                       "planted_was_rejected": planted_rejected, "drafts_used": len(r["drafts"]), "accepted": r["accepted"],
                       "fixed_by_model": planted_rejected and r["accepted"], "final_text": r["rendered"],
                       "reread_problems": r["reread_problems"]})
    (Path(out_dir) / "retry.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for e in report:
        log("%s [%s]: planted draft rejected=%s; %s after %d draft(s)" % (
            e["task_id"], e["planted_error"], e["planted_was_rejected"], "FIXED" if e["fixed_by_model"] else "NOT FIXED", e["drafts_used"]))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--seed", type=int, default=loop.SEED)
    args = ap.parse_args(argv)
    from ectd_engine.writer.llm import OllamaClient
    report = run_retry(OllamaClient(args.model, args.base_url, 4096, 600, think=False), args.out, args.data, seed=args.seed)
    return 0 if all(e["planted_was_rejected"] for e in report) else 1


if __name__ == "__main__":
    sys.exit(main())
