"""Checks a real-model P.5.4 run: re-reads every accepted section against the Lek facts, lists rejects by rule, makes the blind sheet for Hil.

    python tools/audit_p54.py --run evidence/T-042/run/p54_ollama_gemma4-e4b --out evidence/T-042
    python tools/audit_p54.py --score --run <same folder> --out evidence/T-042      # after Hil filled hil_label in blind.csv
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.validator.batch import verify_render  # noqa: E402
from ectd_engine.validator.validator import sentences  # noqa: E402
from ectd_engine.writer.batch_facts import fact_id  # noqa: E402

BLIND_SEED = 7
BLIND_N = 25
LABELS = {"right", "wrong"}


class AuditError(Exception):
    """A missing or unusable input; the audit stops with a clear message instead of reporting 0 wrong."""


def load_run(run_dir):
    """Return (tasks by id, results list) from a writer_run --audit folder."""
    run = Path(run_dir)
    if not (run / "tasks.json").is_file() or not (run / "results.jsonl").is_file():
        raise AuditError(f"{run}: tasks.json or results.jsonl is missing (was it made with writer_run.py --audit?)")
    tasks = {t["task_id"]: t for t in json.loads((run / "tasks.json").read_text(encoding="utf-8"))["tasks"]}
    results = [json.loads(line) for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not results:
        raise AuditError(f"{run}: results.jsonl is empty")
    return tasks, results


def table_from_store(task, get_fact, known_batches):
    """The raw table again, straight from the stored facts (not from the writer's own table)."""
    rows = []
    for b in task["batches"]:
        f = get_fact(fact_id(b, task["column"]))
        if f is None and b not in known_batches:
            raise AuditError(f"{task['task_id']}: batch {b} is not in the batch registry")
        rows.append((b, None if f is None else str(f.value)))
    return {"unit": task["unit"], "decimals": task["decimals"], "rows": rows}


def reread(task, result, get_fact, known_batches):
    """Problems found when the finished text of an accepted section is compared with the stored facts (empty = right)."""
    table = table_from_store(task, get_fact, known_batches)
    problems = []
    if [list(r) for r in result["table"]["rows"]] != [list(r) for r in table["rows"]]:
        problems.append("the table saved with the section differs from the stored facts")
    problems += verify_render(result["rendered"], table)
    return problems


def rule_of(problem):
    """The rule behind a validator message, without the details (so the same rule is counted together)."""
    p = re.sub(r"^re-read of finished text: .*", "re-read of finished text", problem)
    p = re.sub(r"'[^']*'", "'..'", p)
    p = re.sub(r"\[\[[a-z_]+\]\]", "[[..]]", p)
    p = re.split(r" \(|: ", p)[0]
    return re.sub(r"\d+", "N", p).strip()


def bad_sentence(text, problem):
    """The sentence a rule fired on (found by the quoted word, else the first sentence)."""
    sents = sentences(text) or [text]
    for q in re.findall(r"'([^']+)'", problem):
        for s in sents:
            if re.search(re.escape(q), s, re.I):
                return s
    return sents[0]


def audit(tasks, results, get_fact, known_batches):
    """Return the audit rows and the summary numbers."""
    rows, rules, examples, all_rules, all_examples = [], Counter(), {}, Counter(), {}
    for r in results:
        task = tasks[r["task_id"]]
        drafts = r["drafts"]
        for d in drafts:
            for p in d["problems"]:
                all_rules[rule_of(p)] += 1
                all_examples.setdefault(rule_of(p), []).append((r["task_id"], bad_sentence(d["text"], p)))
        row = {"task_id": r["task_id"], "attribute": task["attribute"], "n_excluded": r["flags"]["n_excluded"],
               "accepted": r["accepted"], "drafts": len(drafts), "reread": "", "final_rules": "", "all_rules": ""}
        row["all_rules"] = " | ".join(sorted({rule_of(p) for d in drafts for p in d["problems"]}))
        if r["accepted"]:
            row["reread"] = "right" if not reread(task, r, get_fact, known_batches) else "wrong"
        else:
            last = drafts[-1]
            fr = sorted({rule_of(p) for p in last["problems"]})
            row["final_rules"] = " | ".join(fr)
            for p in last["problems"]:
                rules[rule_of(p)] += 1
                examples.setdefault(rule_of(p), []).append((r["task_id"], bad_sentence(last["text"], p)))
        rows.append(row)
    acc = [x for x in rows if x["accepted"]]
    summary = {"total": len(rows), "accepted": len(acc), "rejected": len(rows) - len(acc),
               "wrong": sum(1 for x in acc if x["reread"] == "wrong"),
               "drafts_accepted": sum(x["drafts"] for x in acc), "drafts_all": sum(x["drafts"] for x in rows),
               "with_excluded": sum(1 for x in rows if x["n_excluded"]),
               "final_rules": rules, "examples": examples, "all_rules": all_rules, "all_examples": all_examples,
               "first_try": sum(1 for x in acc if x["drafts"] == 1)}
    return rows, summary


def pick_blind(results, n=BLIND_N, seed=BLIND_SEED):
    """n random accepted sections, in random order."""
    acc = sorted((r for r in results if r["accepted"]), key=lambda r: r["task_id"])
    return random.Random(seed).sample(acc, min(n, len(acc)))


def facts_text(table):
    return "; ".join(f"batch {b} = " + ("excluded (quarantined)" if t is None else f"{t} {table['unit']}") for b, t in table["rows"])


def write_outputs(out_dir, rows, summary, results, tasks):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["task_id", "attribute", "n_excluded", "accepted", "drafts", "reread", "final_rules", "all_rules"]
    with open(out / "audit.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    picked = pick_blind(results)
    with open(out / "blind.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "attribute", "facts", "text", "hil_label"])
        for i, r in enumerate(picked, start=1):
            w.writerow([f"B{i:02d}", tasks[r["task_id"]]["attribute"], facts_text(r["table"]), r["rendered"], ""])
    with open(out / "blind_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "task_id"])
        for i, r in enumerate(picked, start=1):
            w.writerow([f"B{i:02d}", r["task_id"]])
    s = summary
    L = ["# T-042 audit summary: P.5.4 batch writer with the real model", "",
         f"- windows: {s['total']} ({s['with_excluded']} with an excluded batch)",
         f"- accepted: {s['accepted']} / {s['total']}; rejected: {s['rejected']}",
         f"- accepted on the first draft: {s['first_try']}",
         f"- drafts per accepted section: {s['drafts_accepted']} drafts / {s['accepted']} sections",
         f"- drafts per window (all): {s['drafts_all']} / {s['total']}",
         f"- independent re-read of accepted sections: wrong = {s['wrong']}", "",
         "## Rejected final drafts, by rule (a draft can break several rules)"]
    if not s["final_rules"]:
        L.append("- none")
    for rule, n in s["final_rules"].most_common():
        L.append(f"- {n}x {rule}")
        for tid, sent in s["examples"][rule][:3]:
            L.append(f"    - {tid}: \"{sent}\"")
    L += ["", "## Every rule that fired on any draft (including drafts later fixed)"]
    for rule, n in s["all_rules"].most_common():
        L.append(f"- {n}x {rule}")
        for tid, sent in s["all_examples"][rule][:3]:
            L.append(f"    - {tid}: \"{sent}\"")
    L += ["", f"Blind sheet: {len(picked)} accepted sections in blind.csv; Hil fills hil_label with right or wrong."]
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def score(out_dir, rows):
    """Compare Hil's labels with the re-read. Missing or odd labels stop with an error; they are never counted as right."""
    out = Path(out_dir)
    if not (out / "blind.csv").is_file() or not (out / "blind_key.csv").is_file():
        raise AuditError(f"{out}: blind.csv or blind_key.csv is missing; run the audit first")
    with open(out / "blind.csv", newline="", encoding="utf-8") as f:
        sheet = list(csv.DictReader(f))
    with open(out / "blind_key.csv", newline="", encoding="utf-8") as f:
        key = {r["blind_id"]: r["task_id"] for r in csv.DictReader(f)}
    if not sheet:
        raise AuditError("blind.csv has no rows")
    unlabelled = [r["blind_id"] for r in sheet if (r.get("hil_label") or "").strip().lower() not in LABELS]
    if unlabelled:
        raise AuditError(f"hil_label is empty or not 'right'/'wrong' for {len(unlabelled)} row(s): {', '.join(unlabelled)}")
    reread = {x["task_id"]: x["reread"] for x in rows}
    hil_wrong, differ = [], []
    for r in sheet:
        label = r["hil_label"].strip().lower()
        tid = key[r["blind_id"]]
        if label == "wrong":
            hil_wrong.append(r["blind_id"])
        if label != reread.get(tid):
            differ.append((r["blind_id"], tid, label, reread.get(tid)))
    return {"n": len(sheet), "hil_wrong": hil_wrong, "differ": differ}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="folder made by writer_run.py --kind p54 --audit")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "T-042"))
    ap.add_argument("--score", action="store_true", help="compare Hil's blind labels with the re-read")
    args = ap.parse_args(argv)
    try:
        from ectd_engine.writer.batch_facts import LoaderStore
        store = LoaderStore()
        tasks, results = load_run(args.run)
        rows, summary = audit(tasks, results, store.get, store.known_batches)
        if args.score:
            sc = score(args.out, rows)
            print(f"Hil labelled {sc['n']} sections: wrong = {len(sc['hil_wrong'])} {sc['hil_wrong']}; "
                  f"differs from the re-read = {len(sc['differ'])}")
            for d in sc["differ"]:
                print(f"  {d[0]} ({d[1]}): Hil says {d[2]}, re-read says {d[3]}")
            return 0 if not sc["hil_wrong"] and not sc["differ"] else 1
        print(write_outputs(args.out, rows, summary, results, tasks))
        return 0 if summary["wrong"] == 0 else 1
    except AuditError as e:
        print(f"AUDIT ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
