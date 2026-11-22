"""Compares two P.8.3 run folders (direct vs skill): a verdict per task, draft diffs, and a non-zero exit if any verdict differs."""
import argparse
import difflib
import json
import sys
from pathlib import Path


def load(folder):
    """{task_id: result dict} from a run folder's results.jsonl, plus its summary.json (or {})."""
    folder = Path(folder)
    results = {}
    with open(folder / "results.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                results[r["task_id"]] = r
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8")) if (folder / "summary.json").exists() else {}
    return results, summary


def verdict(r):
    """Short verdict of one task result: what happened on every draft (timings are ignored)."""
    if r is None:
        return "MISSING"
    steps = ["pass" if d["passed"] else "fail[" + ",".join(p.split(":")[0] if p.startswith("sentence") else p for p in d["problems"]) + "]"
             for d in r["drafts"]]
    return ("ACCEPTED" if r["accepted"] else "REJECTED") + " " + " > ".join(steps)


def compare(direct, skill):
    """List of rows {task_id, direct, skill, same, text_same, diff}. A task counts as same only if the verdicts match exactly."""
    rows = []
    for tid in sorted(set(direct) | set(skill)):
        a, b = direct.get(tid), skill.get(tid)
        va, vb = verdict(a), verdict(b)
        ta = [d["text"] for d in a["drafts"]] if a else []
        tb = [d["text"] for d in b["drafts"]] if b else []
        diff = []
        for i in range(max(len(ta), len(tb))):
            x, y = (ta[i] if i < len(ta) else ""), (tb[i] if i < len(tb) else "")
            if x != y:
                diff += ["draft %d:" % (i + 1)] + list(difflib.unified_diff(x.split(". "), y.split(". "), "direct", "skill", lineterm="", n=0))
        rows.append({"task_id": tid, "direct": va, "skill": vb, "same": va == vb and a is not None and b is not None
                     and a["accepted"] == b["accepted"], "text_same": not diff, "diff": diff})
    return rows


def render_md(rows, sum_a, sum_b):
    """The compare.md text."""
    bad = [r for r in rows if not r["same"]]
    same_run = all(sum_a.get(k) == sum_b.get(k) for k in ("seed", "temperature", "max_drafts"))
    out = ["# P.8.3 direct vs skill", "",
           "Seed / temperature / max drafts: direct %s / %s / %s; skill %s / %s / %s (%s)." % (
               sum_a.get("seed"), sum_a.get("temperature"), sum_a.get("max_drafts"),
               sum_b.get("seed"), sum_b.get("temperature"), sum_b.get("max_drafts"), "same" if same_run else "DIFFERENT"),
           "", "**%d of %d tasks have the same verdict. Draft text identical in %d.**" % (
               len(rows) - len(bad), len(rows), sum(1 for r in rows if r["text_same"])), "",
           "| task | direct | skill | same verdict | same text |", "|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s |" % (r["task_id"], r["direct"], r["skill"], "yes" if r["same"] else "**NO**",
                                                    "yes" if r["text_same"] else "no"))
    diffs = [r for r in rows if r["diff"]]
    out += ["", "## Draft differences", ""] if diffs else ["", "No draft differences.", ""]
    for r in diffs:
        out += ["### " + r["task_id"], "```"] + r["diff"] + ["```", ""]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("direct")
    ap.add_argument("skill")
    ap.add_argument("--out", default=None, help="write the report here (compare.md)")
    args = ap.parse_args(argv)
    a, sa = load(args.direct)
    b, sb = load(args.skill)
    rows = compare(a, b)
    text = render_md(rows, sa, sb)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    bad = [r["task_id"] for r in rows if not r["same"]]
    print("%d tasks compared, %d with a different verdict%s" % (len(rows), len(bad), ": " + ", ".join(bad) if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
