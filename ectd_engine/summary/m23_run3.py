"""Runs the T-073 2.3 writer over a set of saved task files with Gemma and scores it: accepted, rejected, wrong-but-accepted, and TWO copy rates. Every run goes in a NEW folder.

    python -m ectd_engine.summary.m23_run3 --set dev --tasks evidence/T-073/tasks --out evidence/T-073/dev/run1
    python -m ectd_engine.summary.m23_run3 --set real --tasks evidence/T-073/tasks --out evidence/T-073/real/run1      (reads Neo4j)

Same method as m23_run2 (synthetic tasks read their labelled graph file; the real task reads Neo4j; the cross-check reads the graph a second time).
WRONG-BUT-ACCEPTED = accepted, but the independent m23_compare3 (saved HTML vs the graph rows, claim rules recomputed there) finds any problem.
Copy rates, per accepted draft against the text of the prompt it was written from (system message, unit message, and the rejected drafts sent back):
  exact  = sentences (or lines) that are a piece of the prompt byte for byte;
  blanked = the same after every [[placeholder]] AND every attribute / test / condition name is blanked in both the draft and the prompt.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from ectd_engine.summary import m23_compare3 as C
from ectd_engine.summary import m23_loop3 as L
from ectd_engine.summary.m23_run import seconds_from_ns
from ectd_engine.summary.m23_run2 import _PH, _sentences, graphs_for, load_tasks

# names that identify an attribute, a test or a condition in the text (blanked for the second copy rate)
NAMES = ["Degradation product", "Dissolution", "Assay", "Impurity O", "Impurity L", "Total impurities", "Residual solvent",
         "long-term", "intermediate", "accelerated"]
_NAME = re.compile("|".join(re.escape(n) for n in sorted(NAMES, key=len, reverse=True)))


def blank(text):
    """Placeholders and attribute / test / condition names replaced by fixed marks."""
    return _NAME.sub("<name>", _PH.sub("[[]]", text))


def copy_stats(attempts_path):
    """Both copy rates of the ACCEPTED drafts of one attempts.jsonl (see the module text)."""
    out = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "blanked_sentences_copied": 0}
    for line in Path(attempts_path).read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if "unit_id" not in a or not a.get("passed"):
            continue
        out["units"] += 1
        prompt = "\n".join(m["content"] for m in a["messages"])
        bprompt, draft = blank(prompt), a["text"].strip()
        out["whole"] += draft in prompt
        for s in _sentences(draft):
            out["sentences"] += 1
            out["sentences_copied"] += s in prompt
            out["blanked_sentences_copied"] += blank(s) in bprompt
    return out


def run_set(client, tasks, out_dir, only=None, log=print, **kw):
    """Run every task into out_dir/<task id>. Returns the summary dict (also saved as summary.json). tasks = [(task, directory)]."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    results, wrong, started = [], [], time.monotonic_ns()
    copy = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "blanked_sentences_copied": 0}
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
        results.append({"task_id": task["task_id"], "profile": task.get("profile"), "accepted": res["accepted"], "reason": res["reason"], "drafts": drafts,
                        "units": len(res["drafts"]), "retries": drafts - len(res["drafts"]), "renders": res["renders"],
                        "compare_ok": None if cmp_ is None else cmp_["ok"], "compare_problems": [] if cmp_ is None else cmp_["problems"]})
        log("%s [%s]: %s after %d draft(s) for %d unit(s)%s%s" % (task["task_id"], task.get("profile"), "ACCEPTED" if res["accepted"] else "REJECTED", drafts,
                                                                  len(res["drafts"]), "" if res["accepted"] else " - " + res["reason"],
                                                                  "  WRONG-BUT-ACCEPTED" if task["task_id"] in wrong else ""))
    summary = {"tasks": len(results), "accepted": sum(r["accepted"] for r in results), "rejected": [r["task_id"] for r in results if not r["accepted"]],
               "wrong_but_accepted": wrong, "drafts": sum(r["drafts"] for r in results), "units": sum(r["units"] for r in results),
               "retries": sum(r["retries"] for r in results), "copy": copy, "seconds": seconds_from_ns(time.monotonic_ns() - started), "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    log("\n%d/%d accepted, %d rejected, %d wrong-but-accepted, %d drafts for %d units. Copy: %d of %d accepted drafts whole; %d of %d sentences "
        "byte-identical to the prompt (exact); %d of %d after blanking names (blanked). Saved in %s" % (
            summary["accepted"], summary["tasks"], len(summary["rejected"]), len(wrong), summary["drafts"], summary["units"], copy["whole"], copy["units"],
            copy["sentences_copied"], copy["sentences"], copy["blanked_sentences_copied"], copy["sentences"], out))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=["real", "dev", "heldout"])
    ap.add_argument("--tasks", required=True, help="the folder written by m23_tasks3 (it holds real/, dev/, heldout/)")
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
