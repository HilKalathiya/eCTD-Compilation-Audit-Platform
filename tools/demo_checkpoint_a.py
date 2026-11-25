"""One command that shows Checkpoint A: CSV -> facts -> stats -> Gemma draft -> gates -> HTML + Word -> two planted errors that must be rejected.

    python tools/demo_checkpoint_a.py --out evidence/T-075/demo/run1 --log evidence/T-075/demo/run1_console.txt      (needs Ollama + gemma4:e4b)
    python tools/demo_checkpoint_a.py --out <new folder> --mock                                                       (scripted model, no Gemma)

Exit 0 only if steps 1-4 pass AND both planted errors (steps 5 and 6) are rejected. A planted error that is accepted = exit 1.
The test data is the SYNTHETIC / DEMO task m23d_dev_01 (invented numbers, labelled); the public Lek CSV row in step 1 is real public data.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ectd_engine.loaders import lek                                    # noqa: E402
from ectd_engine.stats import q1e                                      # noqa: E402
from ectd_engine.summary import crosscheck as X                        # noqa: E402
from ectd_engine.summary import m23_graph as MG                        # noqa: E402
from ectd_engine.summary import m23_loop4 as L                         # noqa: E402
from ectd_engine.summary import m23_rules4 as R                        # noqa: E402
from ectd_engine.summary import m23_tasks4 as T4                       # noqa: E402
from ectd_engine.review import shapes as S                             # noqa: E402

DEMO_SET, DEMO_INDEX = "dev", 1                                        # task m23d_dev_01: clean data, a few facts of every kind
PH_FIELD = re.compile(r"\{(s|test|attr|cond|kind)\}")
DIGIT = re.compile(r"\d")


class Say:
    """Prints a line and (with --log) also saves it, so the saved console file is written by this script itself."""

    def __init__(self, log_path=None):
        self.fh = open(log_path, "w", encoding="utf-8") if log_path else None

    def __call__(self, text=""):
        print(text, flush=True)
        if self.fh:
            self.fh.write(text + "\n")
            self.fh.flush()

    def close(self):
        if self.fh:
            self.fh.close()


class ScriptedModel:
    """--mock: a scripted model that answers each unit with the correct pattern and the slot names (what the real model is asked to do)."""

    def __init__(self, units):
        self.units = {u["unit_id"]: u for u in units}

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": compose(self.units[context["unit_id"]]), "seconds": 0.0, "output_tokens": 0}


def compose(unit):
    """The correct slot-only draft for a unit (first allowed pattern of each kind that fits the data)."""
    lines = []
    for j, kind in enumerate(unit["expect"]):
        shapes = S.M23D_SHAPES[kind]
        if kind == "claim":
            shapes = [x for x in shapes if x[3] == ("zero" if unit["outside"] == 0 else "some")]
        if kind == "study" and unit["study_blockers"]:
            shapes = [x for x in shapes if x[3] is None]
        _, template, slots, _ = shapes[0]
        plain = iter([s for s in slots if s != "attr"])

        def sub(m, j=j, kind=kind):
            f = m.group(1)
            if f == "s":
                return "[[" + (unit["rows"][j - 1][2] if kind == "spec_row" else next(plain)) + "]]"
            if f == "attr":
                return unit["attr_template"]
            if f == "cond":
                return unit["names"]["cond"][0]
            if f == "test":
                return unit["rows"][j - 1][0]
            return unit["rows"][j - 1][1]
        lines.append(PH_FIELD.sub(sub, template))
    return "\n".join(lines) if unit["kind"] == "spec" else " ".join(lines)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- the two planted errors (functions, so the sabotage test can swap them for ones that do nothing) ----

def plant_wrong_number(render_dir, work_dir):
    """Copy the rendered folder and change the proposed shelf-life number in the HTML copy only. Returns (copy folder, old text, new text, fact id)."""
    copy = Path(work_dir)
    shutil.copytree(render_dir, copy)
    html = copy / "M23.html"
    text = html.read_text(encoding="utf-8")
    m = re.search(r'<span class="n" data-src="([^"]*expiry_period_proposed[^"]*)">(\d+)</span>', text)
    old, new = m.group(2), str(int(m.group(2)) + 12)
    html.write_text(text[:m.start(2)] + new + text[m.end(2):], encoding="utf-8")
    return copy, old, new, m.group(1)


def plant_digit_draft(good_draft):
    """A draft that is right except that the model typed a number itself."""
    return good_draft + " The shelf life is 36 months."


def main(argv=None, plant_number=plant_wrong_number, plant_draft=plant_digit_draft):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="a NEW folder for this run (never reused)")
    ap.add_argument("--mock", action="store_true", help="scripted model instead of Gemma")
    ap.add_argument("--log", help="also save the console output to this file (written by this script)")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default="http://localhost:11434")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists; use a new folder (runs are never overwritten)", file=sys.stderr)
        return 2
    if args.log and Path(args.log).exists():
        print(f"{args.log} already exists; use a new file", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    say, results = Say(args.log), {}
    try:
        return _run(args, out, say, results, plant_number, plant_draft)
    finally:
        say.close()


def _run(args, out, say, results, plant_number, plant_draft):
    say("CHECKPOINT A DEMO - CSV -> facts -> stats -> draft -> gates -> HTML + Word -> two planted errors")
    say("Model: %s | Output folder: %s" % ("SCRIPTED MOCK (no Gemma)" if args.mock else args.model, out))

    # (1) facts
    say("\n[1/7] FACTS: every number enters as a fact with its source")
    lek_rows = lek.read_rows()
    rownum, row = lek_rows[0]
    cand = lek._candidate(row, next(iter(lek.COLUMNS)), rownum)
    say("  public data: Laboratory.csv (Lek tablets, CC BY 4.0) has %d rows. One fact from it:" % len(lek_rows))
    say("    %s = %s %s  | source: %s, %s" % (cand["fact_id"], cand["value"], cand["unit"], cand["source"]["doc_id"], cand["source"]["locator"]))
    task, rows = T4.synthetic_task4(DEMO_SET, DEMO_INDEX)
    stab = sorted((r for r in rows.values() if r["family"] == "stability" and r["condition"] == "25C/60%RH" and r["attribute"] == "Assay"), key=lambda r: Decimal(r["month"]))
    fact = stab[0]
    say("  DEMO data (invented, labelled %s for the writer: \"%s\"): %d facts in task %s. One fact:" % (fact["namespace"], fact["demo_label"].strip(), len(rows), task["task_id"]))
    say("    %s = %s %s  | source: %s (%s), page/row: %s" % (fact["fact_id"], fact["value_text"], fact["unit"], fact["doc_id"], fact["definition"], fact["locator"] or fact["page"] or "(synthetic, none)"))
    results[1] = len(lek_rows) > 0 and len(rows) > 0

    # (2) stats
    points = [(Decimal(r["month"]), Decimal(r["value_text"])) for r in stab]
    spec_min = Decimal(stab[0]["limit_text"].replace("NLT", "").strip())
    sl = q1e.shelf_life(points, spec_min=spec_min)
    say("\n[2/7] STATS: computed by code (ICH Q1E, Decimal), never by the model")
    say("  Assay at 25C/60%%RH, points (month, %% label claim): %s; limit NLT %s" % (", ".join("(%s, %s)" % p for p in points), spec_min))
    say("  Q1E shelf-life estimate = %s months (the %s 95%% bound crosses the limit); cap %s months" % (sl.months, sl.side, sl.cap_months))
    results[2] = sl.months > 0
    g = MG.stats(rows, "25C/60%RH", "Assay")
    say("  range: lowest %s, highest %s, results outside the limit: %d of %d" % (g["low"]["value_text"], g["high"]["value_text"], g["outside"], g["n"]))

    # (3) Gemma drafts with slots only
    units = T4.units_of4(task, rows)
    if args.mock:
        client = ScriptedModel(units)
    else:
        from ectd_engine.writer.llm import OllamaClient
        client = OllamaClient(args.model, args.base_url, num_ctx=4096, num_predict=600, think=False)
    work = out / "draft"
    res = L.run_world(client, task, work, MG.MemoryGraph(rows), seed=L.SEED, temperature=0.0)
    attempts = [json.loads(x) for x in (work / "attempts.jsonl").read_text(encoding="utf-8").splitlines()] if (work / "attempts.jsonl").exists() else []
    drafts = [a for a in attempts if "unit_id" in a and a.get("passed")]
    say("\n[3/7] DRAFT: the model writes sentences with [[slots]] only; here is the raw draft of one section (unit %s)" % (drafts[0]["unit_id"] if drafts else "none"))
    first = drafts[0]["text"].strip() if drafts else ""
    for line in first.splitlines():
        say("    | " + line)
    digits = bool(DIGIT.search(first))
    say("  digits in this raw draft: %s" % ("YES - PROBLEM" if digits else "none"))
    say("  drafts asked: %d for %d sections (retries after a rejection: %d)" % (len(attempts) - sum(1 for a in attempts if a.get("gate") == "d"), len(res["drafts"]),
                                                                         len([a for a in attempts if "unit_id" in a and not a["passed"]])))
    results[3] = bool(drafts) and not digits

    # (4) gates + crosscheck + render
    say("\n[4/7] GATES + CROSS-CHECK: wording gates (a-i), then an independent check of the saved files")
    results[4] = bool(res["accepted"])
    if res["accepted"]:
        render = work / res["render"]
        c = res["counts"]
        say("  RESULT: ACCEPTED. Cross-check html: %(checked)d numbers checked, %(matched)d MATCH, %(failed)d failed" % c["html"])
        say("          Cross-check docx: %(checked)d numbers checked, %(matched)d MATCH, %(failed)d failed" % c["docx"])
        say("  HTML : %s" % (render / "M23.html"))
        say("  Word : %s" % (render / "M23.docx"))
    else:
        say("  RESULT: REJECTED - %s" % res["reason"])
        say("\nDEMO FAILED at step 4")
        return 1
    ref = (work / "ref" / "p5_placements.jsonl", work / "ref" / "p8")

    # (5) planted wrong number
    say("\n[5/7] PLANT 1: change one number in a COPY of the rendered document")
    copy, old, new, fid = plant_number(render, out / "plant_number")
    say("  changed %s -> %s next to fact %s (copy: %s)" % (old, new, fid, copy / "M23.html"))
    cc = X.run(copy, rows, *ref)
    bad = [r for r in cc["rows"] if r["verdict"] != "MATCH"]
    for r in bad[:4]:
        say("  cross-check says %s: number %s, fact %s, in %s - %s" % (r["verdict"], r["number"], r["fact_id"], r["format"], r["reason"]))
    for p in cc["problems"]:
        say("  cross-check problem: " + p)
    names_fact = any(r["fact_id"] == fid for r in bad)
    names_number = any(r["number"] == new and r["verdict"] == "FAIL" for r in bad)
    say("  in plain words: fact %s owns the number %s; the file now shows %s there, and no fact owns %s" % (fid, old, new, new))
    results[5] = not cc["passed"] and names_fact and names_number
    say("  PLANT 1 %s" % ("REJECTED (good)" if results[5] else "NOT REJECTED (BAD - the check did not catch it)"))

    # (6) planted digit in a draft
    say("\n[6/7] PLANT 2: a draft where the model typed a number itself")
    unit = next(u for u in units if u["unit_id"] == drafts[0]["unit_id"])
    bad_draft = plant_draft(first)
    problems, _ = L.gate_unit(unit, bad_draft, rows, R.links_of(task))
    tags = L.gate_tags(problems)
    say("  draft text: %s" % bad_draft.splitlines()[-1])
    for p in problems[:3]:
        say("  gate says: " + p)
    results[6] = "a" in tags
    say("  PLANT 2 %s (gates fired: %s)" % ("REJECTED by gate (a) (good)" if results[6] else "NOT REJECTED by gate (a) (BAD)", ",".join(sorted(tags)) or "none"))

    # (7) trace
    say("\n[7/7] TRACE: hashes so this run can be found and checked again")
    files = {"M23.html": render / "M23.html", "M23.docx": render / "M23.docx", "attempts.jsonl": work / "attempts.jsonl", "graph_snapshot.json": work / "graph_snapshot.json"}
    hashes = {k: sha(v) for k, v in files.items()}
    run_id = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(hashes.items())).encode()).hexdigest()[:16]
    for k, v in hashes.items():
        say("  sha256 %-20s %s" % (k, v))
    say("  RUN ID: %s (first 16 hex of the sha256 of the four hashes above)" % run_id)
    results[7] = True

    ok = all(results[i] for i in (1, 2, 3, 4)) and results[5] and results[6]
    summary = {"run_id": run_id, "steps_ok": {str(k): v for k, v in sorted(results.items())}, "plant_number_rejected": results[5], "plant_digit_rejected": results[6],
               "mock": args.mock, "hashes": hashes}
    (out / "demo_result.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    say("\nSTEPS 1-4 %s | PLANT 1 %s | PLANT 2 %s" % ("PASS" if all(results[i] for i in (1, 2, 3, 4)) else "FAIL", "rejected" if results[5] else "ACCEPTED (BAD)",
                                                       "rejected" if results[6] else "ACCEPTED (BAD)"))
    say("DEMO %s (exit %d)" % ("PASSED" if ok else "FAILED", 0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
