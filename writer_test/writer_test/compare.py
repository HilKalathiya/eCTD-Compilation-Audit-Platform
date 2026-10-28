"""Blind comparison of the local model against another model's paragraphs.

1. Run:  python -m writer_test.run --model gemma4:e4b --export-prompts
2. Paste each file from outputs/<run>/prompts/ into the other model (for example
   the Claude app) and save only its paragraph as reference/<task_id>.txt
3. Run:  python -m writer_test.compare --run outputs/ollama_gemma4-e4b

The validator checks both sides. You then rate both paragraphs without
knowing which model wrote which; names are revealed at the end. Each rating
is saved as soon as you give it, so you can stop (type q) and carry on later.
"""
import argparse
import csv
import json
import random
from pathlib import Path

from .facts import compute_facts
from .validator import render, validate

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["task_id", "local_writing", "local_judgement", "ref_writing", "ref_judgement", "ref_validator_problems"]

GUIDE = """
How to score (you do not know which model wrote A or B):
  Writing quality      5 = could go into a submission as is
                       4 = needs a small polish
                       3 = correct but clumsy
                       2 = awkward, needs rewriting
                       1 = broken or wrong English
  Scientific judgement 5 = picks what matters (trend, the result nearest the limit,
                           compliance) and says nothing wrong or misleading
                       3 = correct, but misses or buries something important
                       1 = wrong or misleading
Type q to stop; your ratings so far are kept and the next run continues.
"""


class Stop(Exception):
    pass


def ask(prompt):
    while True:
        v = input(prompt).strip().lower()
        if v in {"1", "2", "3", "4", "5"}:
            return int(v)
        if v == "q":
            raise Stop
        print("  enter a number from 1 to 5, or q to stop")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="folder written by writer_test.run")
    ap.add_argument("--reference", default=str(ROOT / "reference"))
    ap.add_argument("--reference-name", default="Claude")
    ap.add_argument("--data", default=str(ROOT / "data" / "tasks.json"))
    args = ap.parse_args()

    tasks = {t["task_id"]: t for t in json.load(open(args.data, encoding="utf-8"))["tasks"]}
    winners = {}
    for line in open(Path(args.run) / "drafts.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if d["passed"]:
            winners[d["task_id"]] = d["text"]

    out = Path(args.run) / "blind_ratings.csv"
    rows = list(csv.DictReader(open(out, encoding="utf-8"))) if out.exists() else []
    done = {r["task_id"] for r in rows}
    if not out.exists():
        with open(out, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    todo = [t for t in tasks if t in winners and t not in done
            and (Path(args.reference) / f"{t}.txt").exists()]
    if not todo and not rows:
        print("No pairs found. Check the --run folder and the reference/ files.")
        return
    if todo:
        print(GUIDE)
    rng = random.Random()
    try:
        for task_id in todo:
            facts, flags, required = compute_facts(tasks[task_id])
            ref_text = (Path(args.reference) / f"{task_id}.txt").read_text(encoding="utf-8").strip()
            ref_problems = validate(ref_text, facts, flags, required)
            pair = [("local", render(winners[task_id], facts)), (args.reference_name, render(ref_text, facts))]
            rng.shuffle(pair)
            print(f"\n=== {task_id} ===")
            for label, (_, text) in zip("AB", pair):
                print(f"\n[{label}] {text}")
            scores = {}
            for label, (who, _) in zip("AB", pair):
                scores[who] = (ask(f"\n{label} writing quality (1-5): "), ask(f"{label} scientific judgement (1-5): "))
            row = {"task_id": task_id,
                   "local_writing": scores["local"][0], "local_judgement": scores["local"][1],
                   "ref_writing": scores[args.reference_name][0], "ref_judgement": scores[args.reference_name][1],
                   "ref_validator_problems": "; ".join(ref_problems)}
            with open(out, "a", newline="", encoding="utf-8") as f:  # saved at once, so stopping loses nothing
                csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
            rows.append(row)
            print("  saved.")
    except (Stop, KeyboardInterrupt, EOFError):
        print(f"\nStopped. {len(rows)} section(s) rated so far; run the same command to continue.")

    if not rows:
        return
    mean = lambda k: sum(float(r[k]) for r in rows) / len(rows)
    print(f"\nRated {len(rows)} sections (scores 1-5):")
    print(f"  local:  writing {mean('local_writing'):.2f}, judgement {mean('local_judgement'):.2f}")
    print(f"  {args.reference_name}: writing {mean('ref_writing'):.2f}, judgement {mean('ref_judgement'):.2f}")
    print(f"  {args.reference_name} paragraphs failing the validator: "
          f"{sum(1 for r in rows if r['ref_validator_problems'])} of {len(rows)}")
    print(f"Saved in {out}")


if __name__ == "__main__":
    main()
