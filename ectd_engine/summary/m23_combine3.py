"""Combines saved T-073 run folders into ONE summary (accepted, rejected, wrong-but-accepted, both copy rates), re-running only the independent check; it calls no model.

    python -m ectd_engine.summary.m23_combine3 --tasks evidence/T-073/tasks --set heldout --out evidence/T-073/heldout/combined_summary.json \
        --part evidence/T-073/heldout/run1 m23c_held_01 ... m23c_held_19 --part evidence/T-073/heldout/run2 m23c_held_20

Each --part is a run folder followed by the task ids taken from it. The summary says for every task which folder it came from. Used when a run was cut short
(T-073: heldout/run1 was killed by low memory at task 20; held_20 was run alone into heldout/run2). An existing output file is refused.
"""
import argparse
import json
import sys
from pathlib import Path

from ectd_engine.summary import m23_compare3 as C
from ectd_engine.summary.m23_run3 import copy_stats
from ectd_engine.summary.m23_run2 import load_tasks


def combine(tasks_dir, which, parts):
    """The summary dict for the listed (run folder, task id) pairs, in the given order."""
    by_id = {t["task_id"]: t for t, _ in load_tasks(tasks_dir, which)}
    results, wrong = [], []
    copy = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "blanked_sentences_copied": 0}
    for folder, ids in parts:
        for tid in ids:
            d = Path(folder) / tid
            res = json.loads((d / "result.json").read_text(encoding="utf-8"))
            task, cmp_ = by_id[tid], None
            if res["accepted"]:
                cmp_ = C.compare(d / res["render"] / "M23.html", task, json.loads((d / "graph_snapshot_check.json").read_text(encoding="utf-8")))
                if not cmp_["ok"]:
                    wrong.append(tid)
            for k, v in copy_stats(d / "attempts.jsonl").items():
                copy[k] += v
            drafts = sum(res["drafts"].values())
            results.append({"task_id": tid, "from": str(folder).replace("\\", "/"), "profile": task.get("profile"), "accepted": res["accepted"],
                            "reason": res["reason"], "drafts": drafts, "units": len(res["drafts"]), "retries": drafts - len(res["drafts"]),
                            "compare_ok": None if cmp_ is None else cmp_["ok"], "compare_problems": [] if cmp_ is None else cmp_["problems"]})
    return {"tasks": len(results), "accepted": sum(r["accepted"] for r in results), "rejected": [r["task_id"] for r in results if not r["accepted"]],
            "wrong_but_accepted": wrong, "drafts": sum(r["drafts"] for r in results), "units": sum(r["units"] for r in results),
            "retries": sum(r["retries"] for r in results), "copy": copy, "sources": [[str(f).replace("\\", "/"), list(i)] for f, i in parts],
            "results": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--set", required=True, choices=["real", "dev", "heldout"])
    ap.add_argument("--out", required=True, help="a NEW json file")
    ap.add_argument("--part", nargs="+", action="append", required=True, help="run folder, then task ids")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists; use a new file", file=sys.stderr)
        return 2
    s = combine(args.tasks, args.set, [(p[0], p[1:]) for p in args.part])
    out.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    c = s["copy"]
    print("%d/%d accepted, %d rejected, %d wrong-but-accepted, %d drafts for %d units (%d retries). Copy: %d of %d accepted drafts whole; %d of %d sentences "
          "byte-identical to the prompt (exact); %d of %d after blanking names (blanked)." % (
              s["accepted"], s["tasks"], len(s["rejected"]), len(s["wrong_but_accepted"]), s["drafts"], s["units"], s["retries"], c["whole"], c["units"],
              c["sentences_copied"], c["sentences"], c["blanked_sentences_copied"], c["sentences"]))
    return 0 if s["accepted"] == s["tasks"] and not s["wrong_but_accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
