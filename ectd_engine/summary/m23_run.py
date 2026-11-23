"""Runs the 2.3 writer over a set of saved task files with Gemma (or a fake model) and scores it; every run goes in a NEW folder.

    python -m ectd_engine.summary.m23_run --set dev --tasks evidence/T-071/tasks --out evidence/T-071/dev/run1
    python -m ectd_engine.summary.m23_run --set real --tasks evidence/T-071/tasks --out evidence/T-071/real/run1 --neo4j

Per task: <out>/<task id>/ (attempts.jsonl with every draft and its messages, render_<k>/ HTML + Word + placements + crosscheck.csv, result.json).
At the end: <out>/summary.json with accepted / rejected / wrong-but-accepted. A task counts as WRONG-BUT-ACCEPTED when it was accepted
but the independent comparison (m23_compare: saved HTML vs the task's own numbers) finds any difference.
"""
import argparse
import json
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ectd_engine.summary import crosscheck as X
from ectd_engine.summary import m23_compare as C
from ectd_engine.summary import m23_loop as L


def seconds_from_ns(ns):
    """Whole seconds from a count of nanoseconds, rounded half up with Decimal (not the built-in rounding, which sends 2.5 s to 2; here it must give 3)."""
    return int((Decimal(ns) / Decimal(1_000_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def load_tasks(tasks_dir, which):
    """The saved task files of one set, in name order."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((Path(tasks_dir) / which).glob("*.json"))]


def run_set(client, tasks, out_dir, rows=None, only=None, log=print, **kw):
    """Run every task into out_dir/<task id>. Returns the summary dict (also saved as summary.json)."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    if rows is not None:
        (out / "graph_snapshot.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    results, wrong, started = [], [], time.monotonic_ns()
    for t in tasks:
        if only and t["task_id"] not in only:
            continue
        res = L.run_world(client, t, out / t["task_id"], rows=rows if not t["synthetic"] else None, **kw)
        cmp_ = C.compare(out / t["task_id"] / res["render"] / "M23.html", t) if res["accepted"] else None
        if cmp_ and not cmp_["ok"]:
            wrong.append(t["task_id"])
        drafts = sum(res["drafts"].values())
        results.append({"task_id": t["task_id"], "accepted": res["accepted"], "reason": res["reason"], "drafts": drafts,
                        "units": len(res["drafts"]), "retries": drafts - len(res["drafts"]), "renders": res["renders"],
                        "compare_ok": None if cmp_ is None else cmp_["ok"]})
        log("%s: %s after %d draft(s) for %d unit(s)%s%s" % (t["task_id"], "ACCEPTED" if res["accepted"] else "REJECTED", drafts, len(res["drafts"]),
                                                              "" if res["accepted"] else " - " + res["reason"], "  WRONG-BUT-ACCEPTED" if t["task_id"] in wrong else ""))
    summary = {"tasks": len(results), "accepted": sum(r["accepted"] for r in results),
               "rejected": [r["task_id"] for r in results if not r["accepted"]], "wrong_but_accepted": wrong,
               "drafts": sum(r["drafts"] for r in results), "units": sum(r["units"] for r in results),
               "retries": sum(r["retries"] for r in results), "seconds": seconds_from_ns(time.monotonic_ns() - started), "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    log("\n%d/%d accepted, %d rejected, %d wrong-but-accepted, %d drafts for %d units. Saved in %s" % (
        summary["accepted"], summary["tasks"], len(summary["rejected"]), len(wrong), summary["drafts"], summary["units"], out))
    return summary


def neo4j_rows():
    """The real graph facts read from Neo4j now (run_set saves them as graph_snapshot.json in the run folder)."""
    from ectd_engine.graph import facts_graph
    driver = facts_graph.connect()
    try:
        with driver.session() as s:
            return X.read_graph(s)
    finally:
        driver.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=["real", "dev", "heldout"])
    ap.add_argument("--tasks", required=True, help="the folder written by m23_tasks (it holds real/, dev/, heldout/)")
    ap.add_argument("--out", required=True, help="a NEW folder for this run")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--only", nargs="*", help="task ids to run (default: the whole set)")
    ap.add_argument("--neo4j", action="store_true", help="real set only: read the graph facts from Neo4j now instead of the task file")
    args = ap.parse_args(argv)
    if Path(args.out).exists():
        print(f"{args.out} already exists; use a new folder (runs are never overwritten)", file=sys.stderr)
        return 2
    from ectd_engine.writer.llm import OllamaClient
    client = OllamaClient(args.model, args.base_url, num_ctx=4096, num_predict=600, think=False)
    rows = None
    if args.neo4j:
        if args.set != "real":
            print("--neo4j is only for the real set", file=sys.stderr)
            return 2
        rows = neo4j_rows()
    summary = run_set(client, load_tasks(args.tasks, args.set), args.out, rows=rows, only=args.only, seed=L.SEED, temperature=0.0)
    return 0 if summary["accepted"] == summary["tasks"] and not summary["wrong_but_accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
