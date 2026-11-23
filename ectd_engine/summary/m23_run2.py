"""Runs the T-072 2.3 writer over a set of saved task files with Gemma and scores it: accepted, rejected, wrong-but-accepted, copy rate. Every run goes in a NEW folder.

    python -m ectd_engine.summary.m23_run2 --set dev --tasks evidence/T-072/tasks --out evidence/T-072/dev/run1
    python -m ectd_engine.summary.m23_run2 --set real --tasks evidence/T-072/tasks --out evidence/T-072/real/run1      (reads Neo4j)

Synthetic tasks read their own labelled graph file; the real task reads Neo4j. The cross-check makes its OWN second read of the graph (for Neo4j:
the cross-check's own query; for a synthetic task: its graph file loaded again). A task is WRONG-BUT-ACCEPTED when it was accepted but the independent
m23_compare2 (saved HTML vs the graph rows) finds any difference. Copy rate: how many accepted drafts are byte-identical to text that was in their prompt.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from ectd_engine.summary import crosscheck as X
from ectd_engine.summary import m23_compare2 as C
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_loop2 as L
from ectd_engine.summary.m23_run import seconds_from_ns

_PH = re.compile(r"\[\[[a-z_]+\]\]")


def load_tasks(tasks_dir, which):
    """[(task dict, directory)] of one set, in name order (the graph files are not tasks and are skipped)."""
    d = Path(tasks_dir) / which
    return [(json.loads(p.read_text(encoding="utf-8")), d) for p in sorted(d.glob("*.json")) if not p.name.endswith(".graph.json")]


def graphs_for(task, directory):
    """(graph for rendering, the cross-check's own rows). A synthetic task: its graph file, read twice. The real task: Neo4j, read twice with two queries."""
    if task["synthetic"]:
        path = Path(directory) / task["graph_file"]
        return MG.load_synthetic(path), json.loads(path.read_text(encoding="utf-8"))["rows"]
    from ectd_engine.graph import facts_graph
    graph = MG.Neo4jGraph()
    driver = facts_graph.connect()
    try:
        with driver.session() as session:
            check = X.read_graph(session)
    finally:
        driver.close()
    return graph, check


def _sentences(text):
    return [s for s in re.split(r"(?<=\.)\s+|\n", text.strip()) if s]


def copy_stats(attempts_path):
    """Copy rate of the ACCEPTED drafts in one attempts.jsonl, against the text of the prompt each was written from.

    whole = the whole draft is a piece of the prompt, byte for byte; sentence = a sentence (or line) of the draft is a piece of the prompt, byte for byte;
    skeleton = the same after every [[placeholder]] is blanked in both (the same wording with other slot names counts)."""
    accepted = []
    for line in Path(attempts_path).read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if "unit_id" in a and a.get("passed"):
            accepted.append(a)
    out = {"units": len(accepted), "whole": 0, "sentences": 0, "sentences_copied": 0, "skeleton_sentences_copied": 0}
    for a in accepted:
        prompt = "\n".join(m["content"] for m in a["messages"])
        blank = _PH.sub("[[]]", prompt)
        draft = a["text"].strip()
        out["whole"] += draft in prompt
        for s in _sentences(draft):
            out["sentences"] += 1
            out["sentences_copied"] += s in prompt
            out["skeleton_sentences_copied"] += _PH.sub("[[]]", s) in blank
    return out


def run_set(client, tasks, out_dir, only=None, log=print, **kw):
    """Run every task into out_dir/<task id>. Returns the summary dict (also saved as summary.json). tasks = [(task, directory)]."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    results, wrong, started = [], [], time.monotonic_ns()
    copy = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "skeleton_sentences_copied": 0}
    for task, directory in tasks:
        if only and task["task_id"] not in only:
            continue
        graph, check = graphs_for(task, directory)
        res = L.run_world(client, task, out / task["task_id"], graph, check_rows=check, **kw)
        cmp_ = None
        if res["accepted"]:
            cmp_ = C.compare(out / task["task_id"] / res["render"] / "M23.html", task,
                             json.loads((out / task["task_id"] / "graph_snapshot_check.json").read_text(encoding="utf-8")))
            if not cmp_["ok"]:
                wrong.append(task["task_id"])
        if (out / task["task_id"] / "attempts.jsonl").exists():
            for k, v in copy_stats(out / task["task_id"] / "attempts.jsonl").items():
                copy[k] += v
        drafts = sum(res["drafts"].values())
        results.append({"task_id": task["task_id"], "accepted": res["accepted"], "reason": res["reason"], "drafts": drafts, "units": len(res["drafts"]),
                        "retries": drafts - len(res["drafts"]), "renders": res["renders"], "compare_ok": None if cmp_ is None else cmp_["ok"]})
        log("%s: %s after %d draft(s) for %d unit(s)%s%s" % (task["task_id"], "ACCEPTED" if res["accepted"] else "REJECTED", drafts, len(res["drafts"]),
                                                              "" if res["accepted"] else " - " + res["reason"], "  WRONG-BUT-ACCEPTED" if task["task_id"] in wrong else ""))
    summary = {"tasks": len(results), "accepted": sum(r["accepted"] for r in results), "rejected": [r["task_id"] for r in results if not r["accepted"]],
               "wrong_but_accepted": wrong, "drafts": sum(r["drafts"] for r in results), "units": sum(r["units"] for r in results),
               "retries": sum(r["retries"] for r in results), "copy": copy, "seconds": seconds_from_ns(time.monotonic_ns() - started), "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    log("\n%d/%d accepted, %d rejected, %d wrong-but-accepted, %d drafts for %d units. Copy: %d of %d accepted drafts whole, %d of %d sentences "
        "byte-identical to the prompt (%d by skeleton). Saved in %s" % (
            summary["accepted"], summary["tasks"], len(summary["rejected"]), len(wrong), summary["drafts"], summary["units"], copy["whole"], copy["units"],
            copy["sentences_copied"], copy["sentences"], copy["skeleton_sentences_copied"], out))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=["real", "dev", "heldout"])
    ap.add_argument("--tasks", required=True, help="the folder written by m23_tasks2 (it holds real/, dev/, heldout/)")
    ap.add_argument("--out", required=True, help="a NEW folder for this run")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--only", nargs="*", help="task ids to run (default: the whole set)")
    args = ap.parse_args(argv)
    if Path(args.out).exists():
        print(f"{args.out} already exists; use a new folder (runs are never overwritten)", file=sys.stderr)
        return 2
    from ectd_engine.writer.llm import OllamaClient
    client = OllamaClient(args.model, args.base_url, num_ctx=4096, num_predict=600, think=False)
    summary = run_set(client, load_tasks(args.tasks, args.set), args.out, only=args.only, seed=L.SEED, temperature=0.0)
    return 0 if summary["accepted"] == summary["tasks"] and not summary["wrong_but_accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
