"""The one entry point for the P.8.3 writer: writes every task to a folder and audits what was accepted; the direct run and the skill both call it."""
import json
from pathlib import Path

from ectd_engine.stability import facts as F
from ectd_engine.stability import loop, reread


def run_p83(client, out_dir, csv_path=F.DEFAULT_CSV, max_drafts=loop.MAX_DRAFTS, seed=loop.SEED, temperature=0.0,
            only=None, meta=None, log=print):
    """Write all P.8.3 tasks. Files in out_dir: tasks.json, drafts.jsonl, results.jsonl, sections/, summary.json.

    Returns the summary: counts, wrong_accepted (accepted but the CSV recount disagrees), seed, temperature."""
    out = Path(out_dir)
    (out / "sections").mkdir(parents=True, exist_ok=True)
    rows = F.load_rows(csv_path)
    problems = F.check_rows(rows)
    if problems:
        raise ValueError("stability data is not clean: " + "; ".join(problems[:5]))
    tasks = loop.make_tasks(F.p83_facts(rows))
    if only:
        tasks = [t for t in tasks if t["task_id"] in set(only)]
    raw = reread.read_rows(csv_path)
    (out / "tasks.json").write_text(json.dumps({"seed": seed, "temperature": temperature, "meta": meta or {},
                                                "tasks": [loop.task_view(t) for t in tasks]}, indent=1, ensure_ascii=False), encoding="utf-8")
    accepted, wrong, rejected_ids = 0, [], []
    with open(out / "drafts.jsonl", "w", encoding="utf-8") as dlog, open(out / "results.jsonl", "w", encoding="utf-8") as rlog:
        for t in tasks:
            res = loop.run_task(client, t, max_drafts, temperature, seed)
            bad = reread.reread(res["rendered"], t, raw) if res["accepted"] else []
            for d in res["drafts"]:
                dlog.write(json.dumps({"task_id": t["task_id"], **d}, ensure_ascii=False) + "\n")
            rlog.write(json.dumps({"task_id": t["task_id"], "accepted": res["accepted"], "rendered": res["rendered"],
                                   "reread_problems": bad, "drafts": res["drafts"]}, ensure_ascii=False) + "\n")
            if res["accepted"]:
                accepted += 1
                (out / "sections" / (t["task_id"] + ".md")).write_text(loop.write_section(t, res), encoding="utf-8")
                log("%s: ACCEPTED after %d draft(s)%s" % (t["task_id"], len(res["drafts"]), "  WRONG: " + "; ".join(bad) if bad else ""))
                if bad:
                    wrong.append(t["task_id"])
            else:
                rejected_ids.append(t["task_id"])
                log("%s: REJECTED after %d draft(s): %s" % (t["task_id"], len(res["drafts"]), "; ".join(res["drafts"][-1]["problems"])))
    summary = {"tasks": len(tasks), "accepted": accepted, "rejected": rejected_ids, "wrong_accepted": wrong,
               "seed": seed, "temperature": temperature, "max_drafts": max_drafts, "meta": meta or {}}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    log("\n%d/%d accepted, %d wrong accepted. Saved in %s" % (accepted, len(tasks), len(wrong), out))
    return summary
