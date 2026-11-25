"""One command that shows Checkpoint A: the stability CSV -> facts -> stats -> Gemma draft -> gates -> HTML + Word -> two planted errors that must be rejected.

    python tools/demo_checkpoint_a.py --out evidence/T-076/demo/run1 --log evidence/T-076/demo/run1_console.txt      (needs Ollama + gemma4:e4b)
    python tools/demo_checkpoint_a.py --out <new folder> --mock                                                       (scripted model, no Gemma)
    python tools/demo_checkpoint_a.py --out <new folder> --mock --synthetic                                           (the old invented test task, labelled)

Default mode: ONE connected chain. data/stability/finerenone_stability.csv -> facts (read in memory, no database) -> stats computed by code from THOSE
rows -> Gemma writes [[slots]] only -> gates + cross-check on the saved HTML and Word files -> a check that every number in the files traces to a
fact whose source is a line of that CSV -> two planted errors that must be rejected.
Exit 0 only if steps 1-4 pass AND both planted errors (steps 5 and 6) are rejected. A planted error that is accepted = exit 1.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ectd_engine.graph import summary_graph as G                       # noqa: E402
from ectd_engine.stats import q1e                                      # noqa: E402
from ectd_engine.stability import facts as SF                          # noqa: E402
from ectd_engine.summary import crosscheck as X                        # noqa: E402
from ectd_engine.summary import m23_graph as MG                        # noqa: E402
from ectd_engine.summary import m23_loop4 as L                         # noqa: E402
from ectd_engine.summary import m23_rules4 as R                        # noqa: E402
from ectd_engine.summary import m23_tasks4 as T4                       # noqa: E402
from ectd_engine.summary import plan as P                              # noqa: E402
from ectd_engine.review import shapes as S                             # noqa: E402

CSV_PATH = SF.DEFAULT_CSV
STAB_DOC = G.STAB_DOC
DEMO_SET, DEMO_INDEX = "dev", 1                                        # --synthetic only: task m23d_dev_01
SPEC_FROM_CSV = [("Dissolution (15 min)", "dissolution_av", "Dissolution", G.spec_id("dissolution_av")),
                 ("Degradation product", "degradation_product", "Degradation product", G.spec_id("degradation_product"))]      # the cross-check only reads spec ids that start with M23-SPEC-LEK-; the source fields say it is the CSV
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


# ---- the CSV world: facts read from the CSV in memory, no database ---------------------------------------------------------------------

class CsvGraph:
    """An in-memory graph filled from the stability CSV only. Same interface as the other graphs (namespace, rows()); it has no write path."""
    namespace = "CSV (in memory, from finerenone_stability.csv)"

    def __init__(self, rows):
        self._rows = {k: dict(r) for k, r in rows.items()}

    def rows(self):
        return {k: dict(r) for k, r in self._rows.items()}


def csv_lines(path=CSV_PATH):
    """{line number: row dict} read straight from the file with the csv module (line 1 is the header). Independent of the fact builder."""
    with open(path, newline="", encoding="utf-8") as fh:
        return {i: r for i, r in enumerate(csv.DictReader(fh), start=2)}


def build_csv_world(path=CSV_PATH):
    """(task, rows): every fact comes from the CSV. Stability rows: G.collect_stability. The ONE specification row (Dissolution) is read from the
    'limit' column of the CSV's first Dissolution row (NLT 80), with that CSV line as its source; the Lek specification file is NOT used."""
    rows = G.collect_stability(path)
    lines = csv_lines(path)
    task = T4.real_task4()
    task_spec = []
    # (CSV attribute, spec attribute, name of the test in the table, id): the one-sided limits of the CSV (NLT / NMT). Assay has a two-sided range: no spec row, range sentence only.
    for csv_attr, spec_attr, test, fid in SPEC_FROM_CSV:
        n, line = next((i, r) for i, r in lines.items() if r["attribute"] == csv_attr)
        kind, value = line["limit"].split()
        spec = dict(G.collect_spec()[G.spec_id("dissolution_av")])
        stab = rows[G.stab_id(line["condition"], line["attribute"], line["month"])]
        spec.update(fact_id=fid, attribute=spec_attr, test=test, unit=stab["unit"] if csv_attr != "Dissolution (15 min)" else "%", value_text=value, limit_kind=kind,
                    doc_id=stab["doc_id"], doc_version=stab["doc_version"], locator=f"row={n}", page=stab["page"], basis="csv limit column", derived="yes",
                    demo_label=G.LABEL, definition=f"limit column of stability row {n} of {STAB_DOC}; source text: {line['source']}")
        rows[fid] = spec
        task_spec.append({"attribute": spec_attr, "slot": "spec_" + spec_attr, "fact_id": fid})
        for g in task["results"]:
            if g["attribute"] == csv_attr:
                g["spec_fact"] = fid
    task.update(task_id="m23d_csv", set="csv", note="Facts read from finerenone_stability.csv (public rows and DEMO rows).", spec=task_spec)
    return task, rows


def trace_one(fid, rows, lines):
    """(ok, text): does this fact id lead back to a line of the CSV whose own cells hold the same value? Read from the CSV file, not from the graph."""
    try:
        r = MG.fact(rows, fid)
    except KeyError:
        return False, "no such fact"
    if r.get("doc_id") != STAB_DOC:
        return False, f"source is {r.get('doc_id')!r}, not the CSV"
    loc = r.get("locator", "")
    m = re.fullmatch(r"row=(\d+)", loc)
    if m:
        n = int(m.group(1))
        line = lines.get(n)
        if line is None:
            return False, f"CSV has no line {n}"
        if r["unit"] == "min" and fid.endswith("|timepoint"):                       # the dissolution time point is written in the attribute cell
            ok = f"({r['value_text']} min)" in line["attribute"]
        elif r["family"] == "spec":                                                   # the specification limit is written in the limit cell
            ok = line["limit"].split() == [r["limit_kind"], r["value_text"]]
        else:
            ok = all(line[c] == r[k] for c, k in (("value", "value_text"), ("attribute", "attribute"), ("condition", "condition"), ("month", "month")))
        return ok, f"CSV line {n}"
    m = re.fullmatch(r"typed=page=(\d+)", loc)
    if m:                                                                              # storage temperature typed inside the condition text
        idx = 0 if r["attribute"] == "storage_low" else 1
        ok = any(re.findall(r"\d+", l["condition"])[idx] == r["value_text"] for l in lines.values()
                 if l["condition"] == r["condition"] and l["attribute"] == "expiry_period_proposed" and l["month"] == r["month"])
        return ok, "the condition text of the shelf-life line"
    return False, f"locator {loc!r} is not a CSV line"


def trace_numbers(cc_rows, rows, lines):
    """(traced, untraced, total) over every checked number of the cross-check (html and docx rows). A number with no fact id is untraced."""
    nums = [r for r in cc_rows if r["number"]]
    bad = []
    for r in nums:
        ok, why = trace_one(r["fact_id"], rows, lines) if r["fact_id"] else (False, "no fact owns this number")
        if not ok:
            bad.append((r["format"], r["number"], r["fact_id"], why))
    return len(nums) - len(bad), bad, len(nums)


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
    ap.add_argument("--synthetic", action="store_true", help="use the old SYNTHETIC invented task instead of the CSV (clearly labelled)")
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


def _facts_and_stats(args, say, results):
    """Steps 1 and 2. Returns (task, rows, lines, stab, links) for the chosen mode."""
    lines = None
    if args.synthetic:
        from ectd_engine.loaders import lek
        say("\n[1/7] FACTS (SYNTHETIC mode: invented numbers, NOT the CSV): every number enters as a fact with its source")
        lek_rows = lek.read_rows()
        rownum, row = lek_rows[0]
        cand = lek._candidate(row, next(iter(lek.COLUMNS)), rownum)
        say("  public data: Laboratory.csv (Lek tablets, CC BY 4.0) has %d rows. One fact from it:" % len(lek_rows))
        say("    %s = %s %s  | source: %s, %s" % (cand["fact_id"], cand["value"], cand["unit"], cand["source"]["doc_id"], cand["source"]["locator"]))
        task, rows = T4.synthetic_task4(DEMO_SET, DEMO_INDEX)
        stab = sorted((r for r in rows.values() if r["family"] == "stability" and r["condition"] == P.LONG and r["attribute"] == "Assay"), key=lambda r: Decimal(r["month"]))
        fact = stab[0]
        say("  SYNTHETIC data (invented, labelled %s for the writer: \"%s\"): %d facts in task %s. One fact:" % (fact["namespace"], fact["demo_label"].strip(), len(rows), task["task_id"]))
        say("    %s = %s %s  | source: %s (%s), page/row: %s" % (fact["fact_id"], fact["value_text"], fact["unit"], fact["doc_id"], fact["definition"], fact["locator"] or fact["page"] or "(synthetic, none)"))
        results[1] = len(lek_rows) > 0 and len(rows) > 0
        spec_lo, spec_hi = Decimal(stab[0]["limit_text"].replace("NLT", "").strip()), None
    else:
        say("\n[1/7] FACTS: the CSV is read into facts in memory (no database); every fact keeps its CSV line and the page of its source")
        task, rows = build_csv_world()
        lines = csv_lines()
        raw = CSV_PATH.read_text(encoding="utf-8").splitlines()
        say("  CSV: %s has %d data lines -> %d facts (stored rows + 2 storage temperatures read from the condition text + %d specification limits read from the limit column)"
            % (CSV_PATH.relative_to(ROOT).as_posix(), len(lines), len(rows), len(SPEC_FROM_CSV)))
        pub = rows[P.PUBLIC_REFS["shelf"]]
        say("  PUBLIC fact: %s = %s %s" % (pub["fact_id"], pub["value_text"], pub["unit"]))
        say("    source: %s, %s (CSV line text: \"%s\"), FDA review page %s, kind=%s" % (pub["doc_id"], pub["locator"], raw[int(pub["locator"][4:]) - 1], pub["page"], pub["kind"]))
        stab = sorted(MG.group_rows(rows, P.LONG, "Assay"), key=lambda r: Decimal(r["month"]))
        fact = next(r for r in stab if r["month"] == "12")
        say("  DEMO fact: %s = %s %s   label the writer must show: \"%s\"" % (fact["fact_id"], fact["value_text"], fact["unit"], fact["demo_label"].strip()))
        say("    source: %s, %s (CSV line text: \"%s\"), (b)(4) redacted in FDA review page %s, kind=%s" % (fact["doc_id"], fact["locator"], raw[int(fact["locator"][4:]) - 1], fact["page"], fact["kind"]))
        results[1] = len(rows) > 0 and pub["kind"] == "public" and fact["kind"] == "demo" and bool(fact["page"])
        spec_lo, spec_hi = MG.parse_limit(stab[0]["limit_text"])

    points = [(Decimal(r["month"]), Decimal(r["value_text"])) for r in stab]
    sl = q1e.shelf_life(points, spec_min=spec_lo, spec_max=spec_hi)
    say("\n[2/7] STATS: computed by code (ICH Q1E, Decimal) from those same rows, never by the model")
    say("  inputs: Assay at 25C/60%%RH, %d rows (%s), points (month, %% label claim): %s" % (
        len(points), ", ".join(r["locator"] for r in stab) if not args.synthetic else "synthetic", ", ".join("(%s, %s)" % p for p in points)))
    say("  limits from the rows: lower %s, upper %s" % (spec_lo, spec_hi if spec_hi is not None else "none"))
    say("  result: Q1E shelf-life estimate = %s months (the %s 95%% bound crosses the limit); cap %s months" % (sl.months, sl.side, sl.cap_months))
    results[2] = sl.months > 0
    g = MG.stats(rows, P.LONG, "Assay")
    say("  range of the same rows: lowest %s, highest %s, results outside the limit: %d of %d" % (g["low"]["value_text"], g["high"]["value_text"], g["outside"], g["n"]))
    links = R.links_of(task)
    if links.get((P.LONG, "Dissolution (15 min)")):
        say("  Dissolution at 25C/60%%RH against its limit (%s): %d of %d outside" % (R.spec_limit_text(rows, links[(P.LONG, "Dissolution (15 min)")]),
            R.outside_count(rows, links, P.LONG, "Dissolution (15 min)"), len(MG.group_rows(rows, P.LONG, "Dissolution (15 min)"))))
    return task, rows, lines, links


def _run(args, out, say, results, plant_number, plant_draft):
    say("CHECKPOINT A DEMO - %s -> facts -> stats -> draft -> gates -> HTML + Word -> two planted errors" % ("SYNTHETIC task (invented numbers)" if args.synthetic else "stability CSV"))
    say("Model: %s | Output folder: %s" % ("SCRIPTED MOCK (no Gemma)" if args.mock else args.model, out))
    if args.synthetic:
        say("*** SYNTHETIC MODE: the numbers are invented test data, not the CSV. The default mode (no --synthetic) uses the CSV. ***")
    task, rows, lines, links = _facts_and_stats(args, say, results)

    # (3) Gemma drafts with slots only
    units = T4.units_of4(task, rows)
    if args.mock:
        client = ScriptedModel(units)
    else:
        from ectd_engine.writer.llm import OllamaClient
        client = OllamaClient(args.model, args.base_url, num_ctx=4096, num_predict=600, think=False)
    work = out / "draft"
    graph = MG.MemoryGraph(rows) if args.synthetic else CsvGraph(rows)
    run_kw = {}
    if not args.synthetic:                                   # the saved 3.2 stand-in files are written from the CSV facts, before any draft is asked
        run_kw["ref"] = T4.write_reference4(task, rows, out / "ref")
        run_kw["check_rows"] = build_csv_world()[1]          # the cross-check reads the CSV a second, separate time
    res = L.run_world(client, task, work, graph, seed=L.SEED, temperature=0.0, **run_kw)
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

    # (4) gates + crosscheck + render + source trace
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
    ref = run_kw.get("ref") or (work / "ref" / "p5_placements.jsonl", work / "ref" / "p8")
    trace = None
    if not args.synthetic:
        cc0 = X.run(render, rows, *ref)
        traced, bad, total = trace_numbers(cc0["rows"], rows, lines)
        fmt = {f: len([r for r in cc0["rows"] if r["number"] and r["format"] == f]) for f in ("html", "docx")}
        total_checked = c["html"]["checked"] + c["docx"]["checked"]
        say("  SOURCE TRACE: every number in the saved HTML and Word file -> its fact id -> that fact's source line in finerenone_stability.csv (re-read from the file)")
        say("    numbers in the files (html %d + docx %d) = %d | traced to a CSV line, value equal: %d | not traced: %d | cross-check total: %d"
            % (fmt["html"], fmt["docx"], total, traced, len(bad), total_checked))
        for b in bad[:5]:
            say("    NOT TRACED: %s number %s fact %s: %s" % b)
        trace = {"numbers": total, "traced": traced, "untraced": len(bad), "crosscheck_total": total_checked, "html": fmt["html"], "docx": fmt["docx"]}
        results[4] = results[4] and not bad and traced == total_checked and total > 0
        say("  SOURCE TRACE %s" % ("OK: all %d of %d numbers trace to the CSV" % (traced, total_checked) if results[4] else "FAILED"))

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

    # (7) fingerprint
    say("\n[7/7] RUN FINGERPRINT: hashes so this run can be found and checked again (a fingerprint of the files, not a ledger entry)")
    files = {"M23.html": render / "M23.html", "M23.docx": render / "M23.docx", "attempts.jsonl": work / "attempts.jsonl", "graph_snapshot.json": work / "graph_snapshot.json"}
    if not args.synthetic:
        files["finerenone_stability.csv"] = CSV_PATH
    hashes = {k: sha(v) for k, v in files.items()}
    fingerprint = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(hashes.items())).encode()).hexdigest()[:16]
    for k, v in hashes.items():
        say("  sha256 %-26s %s" % (k, v))
    say("  RUN FINGERPRINT: %s (first 16 hex of the sha256 of the %d hashes above)" % (fingerprint, len(hashes)))
    results[7] = True

    ok = all(results[i] for i in (1, 2, 3, 4)) and results[5] and results[6]
    summary = {"run_fingerprint": fingerprint, "steps_ok": {str(k): v for k, v in sorted(results.items())}, "plant_number_rejected": results[5],
               "plant_digit_rejected": results[6], "mock": args.mock, "synthetic": args.synthetic, "source_trace": trace, "hashes": hashes}
    (out / "demo_result.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    say("\nSTEPS 1-4 %s | PLANT 1 %s | PLANT 2 %s" % ("PASS" if all(results[i] for i in (1, 2, 3, 4)) else "FAIL", "rejected" if results[5] else "ACCEPTED (BAD)",
                                                       "rejected" if results[6] else "ACCEPTED (BAD)"))
    say("DEMO %s (exit %d)" % ("PASSED" if ok else "FAILED", 0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
