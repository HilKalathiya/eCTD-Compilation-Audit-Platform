"""Runs the T-074 2.3 writer (a TEMPLATE FILLER) over a set of saved task files with Gemma and scores it. Every run goes in a NEW folder.

    python -m ectd_engine.summary.m23_run4 --set dev --tasks evidence/T-074/tasks --out evidence/T-074/dev/run1
    python -m ectd_engine.summary.m23_run4 --set real --tasks evidence/T-074/tasks --out evidence/T-074/real/run1      (reads Neo4j)

Scores: accepted / rejected / WRONG-BUT-ACCEPTED (accepted, but the independent m23_compare4 finds any problem) plus
 * copy rates, FIXED in T-074: every [[placeholder]], every <blank> of the pattern menu and every attribute / test / condition name is blanked in both the
   draft and the prompt before comparing, so a pattern filled with the unit's own words counts as copied. For a template filler this rate is high by design
   and is reported as "template fill", not as freedom;
 * how many times each gate FIRED on a real model draft (planted drafts are not counted): a, b, c, e, f, g, h, i (review route) per rejected draft, and d per
   rejected render; a gate that never fired is named in the summary;
 * pattern choice: of the units, how many had a wrong-for-the-data pattern (gate f, g or i) in their FIRST draft.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from ectd_engine.summary import m23_compare4 as C
from ectd_engine.summary import m23_loop4 as L
from ectd_engine.summary.m23_run import seconds_from_ns
from ectd_engine.summary.m23_run2 import _sentences, graphs_for, load_tasks

NAMES = ["Degradation product", "Dissolution", "Assay", "Impurity O", "Impurity L", "Total impurities", "Residual solvent",
         "long-term", "intermediate", "accelerated", "NLT", "NMT"]
_NAME = re.compile("|".join(re.escape(n) for n in sorted(NAMES, key=len, reverse=True)))
_PH = re.compile(r"\[\[[a-z_]+\]\]")
_BLANK = re.compile(r"<[^<>\n]*>")
MARK = "<>"
GATES = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
PATTERN_GATES = {"f", "g", "i"}                 # the gates that fire when the model picked a pattern that is wrong for the data


def blank(text):
    """Placeholders, <blanks> of the menu, attribute / test / condition names and the intro words replaced by one mark, so a filled pattern equals its menu line."""
    text = _BLANK.sub(MARK, text)
    text = _PH.sub(MARK, text)
    text = _NAME.sub(MARK, text)
    text = re.sub(re.escape(MARK) + r" \(" + re.escape(MARK) + r"\)", MARK, text)            # "Dissolution ([[tp]])" = the menu's <attribute>
    return re.sub(r"lists (?:these|the) tests", f"lists {MARK} tests", text)


def copy_stats(attempts_path):
    """Both copy rates of the ACCEPTED drafts of one attempts.jsonl (see the module text); planted drafts are skipped."""
    out = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "blanked_sentences_copied": 0}
    for line in Path(attempts_path).read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if "unit_id" not in a or not a.get("passed") or a.get("planted"):
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


def gate_stats(attempts_path):
    """How often each gate fired on real drafts of one attempts.jsonl: {"fired": {gate: rejected drafts}, "units": n, "first_draft_wrong_pattern": n}."""
    fired, units, wrong_first, seen = {g: 0 for g in GATES}, 0, 0, set()
    for line in Path(attempts_path).read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if a.get("planted"):
            continue
        if a.get("gate") == "d":
            fired["d"] += 0 if a["passed"] else 1
            continue
        if "unit_id" not in a:
            continue
        if a["unit_id"] not in seen:
            seen.add(a["unit_id"])
            units += 1
            wrong_first += bool(PATTERN_GATES & set(a.get("gates", [])))
        for g in a.get("gates", []):
            fired[g] += 1
    return {"fired": fired, "units": units, "first_draft_wrong_pattern": wrong_first}


def add_up(into, part):
    for k, v in part.items():
        if isinstance(v, dict):
            add_up(into.setdefault(k, {}), v)
        else:
            into[k] = into.get(k, 0) + v


def run_set(client, tasks, out_dir, only=None, log=print, **kw):
    """Run every task into out_dir/<task id>. Returns the summary dict (also saved as summary.json). tasks = [(task, directory)]."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    results, wrong, started = [], [], time.monotonic_ns()
    copy = {"units": 0, "whole": 0, "sentences": 0, "sentences_copied": 0, "blanked_sentences_copied": 0}
    gates = {"fired": {g: 0 for g in GATES}, "units": 0, "first_draft_wrong_pattern": 0}
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
            add_up(copy, copy_stats(out / task["task_id"] / "attempts.jsonl"))
            add_up(gates, gate_stats(out / task["task_id"] / "attempts.jsonl"))
        drafts = sum(res["drafts"].values())
        results.append({"task_id": task["task_id"], "profile": task.get("profile"), "accepted": res["accepted"], "reason": res["reason"], "drafts": drafts,
                        "units": len(res["drafts"]), "retries": drafts - len(res["drafts"]), "renders": res["renders"], "review_route": res.get("review_route"),
                        "compare_ok": None if cmp_ is None else cmp_["ok"], "compare_problems": [] if cmp_ is None else cmp_["problems"],
                        "pattern": {} if cmp_ is None else cmp_["pattern"]})
        log("%s [%s]: %s after %d draft(s) for %d unit(s)%s%s" % (task["task_id"], task.get("profile"), "ACCEPTED" if res["accepted"] else "REJECTED", drafts,
                                                                  len(res["drafts"]), "" if res["accepted"] else " - " + res["reason"],
                                                                  "  WRONG-BUT-ACCEPTED" if task["task_id"] in wrong else ""))
    never = [g for g in GATES if gates["fired"][g] == 0]
    summary = {"tasks": len(results), "accepted": sum(r["accepted"] for r in results), "rejected": [r["task_id"] for r in results if not r["accepted"]],
               "wrong_but_accepted": wrong, "drafts": sum(r["drafts"] for r in results), "units": sum(r["units"] for r in results),
               "retries": sum(r["retries"] for r in results), "copy": copy, "gates": gates, "gates_never_fired": never,
               "review_route_tasks": sum(bool(r["review_route"]) for r in results), "review_route_accepted": sum(bool(r["review_route"]) and r["accepted"] for r in results),
               "seconds": seconds_from_ns(time.monotonic_ns() - started), "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    log("\n%d/%d accepted, %d rejected, %d wrong-but-accepted, %d drafts for %d units. Template fill (copy): %d of %d accepted drafts whole; %d of %d sentences "
        "byte-identical to the prompt (exact); %d of %d after blanking placeholders, <blanks> and names. Gates fired on real drafts: %s; never fired: %s. "
        "First draft chose a pattern wrong for the data in %d of %d units. Review route: %d tasks, %d accepted. Saved in %s" % (
            summary["accepted"], summary["tasks"], len(summary["rejected"]), len(wrong), summary["drafts"], summary["units"], copy["whole"], copy["units"],
            copy["sentences_copied"], copy["sentences"], copy["blanked_sentences_copied"], copy["sentences"], gates["fired"], never or "none",
            gates["first_draft_wrong_pattern"], gates["units"], summary["review_route_tasks"], summary["review_route_accepted"], out))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=["real", "dev", "heldout"])
    ap.add_argument("--tasks", required=True, help="the folder written by m23_tasks4 (it holds real/, dev/, heldout/)")
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
