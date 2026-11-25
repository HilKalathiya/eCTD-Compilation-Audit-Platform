"""A test kit for a person who is not on the team: they change up to 10 things in a copy of the document or the CSV, and the real checks must find them.

    python tools/classmate_kit.py prepare --out evidence/T-076/classmate/kit1 [--run <demo run folder>]
    python tools/classmate_kit.py score --dir evidence/T-076/classmate/kit1

prepare: copies the saved HTML, Word file and CSV into <out>/for_classmate/ (this is all the classmate gets), writes simple instructions, and keeps the trusted
copies and facts in <out>/trusted/. The classmate lists what they changed in <out>/answers.csv.
score, in TWO separate steps: (1) run_checks() looks ONLY at the edited files and the trusted copies and never opens answers.csv; (2) match_answers() then
reads answers.csv and says, for each change they listed: caught (located) / not located (only the file fingerprint changed) / missed, and by which check.
"""
import argparse
import csv
import difflib
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ectd_engine.review import shapes as S                             # noqa: E402
from ectd_engine.stability import facts as SF                          # noqa: E402
from ectd_engine.summary import crosscheck as X                        # noqa: E402
from ectd_engine.summary import m23_compare4 as C4                     # noqa: E402
from ectd_engine.summary import m23_graph as MG                        # noqa: E402
from ectd_engine.summary import m23_rules4 as R                        # noqa: E402
from ectd_engine.summary import m23_tasks4 as T4                       # noqa: E402
from ectd_engine.summary import plan as P                              # noqa: E402
from tools import demo_checkpoint_a as D                               # noqa: E402

FILES = {"csv": "finerenone_stability.csv", "html": "M23.html", "docx": "M23.docx"}
ANSWER_COLUMNS = ["n", "file", "csv_line", "near", "original_text", "new_text", "kind"]
SENTENCE_SPLIT = re.compile(r"(?<=\.)\s+(?=[A-Z])")
FINGERPRINT = "file fingerprint"

INSTRUCTIONS = """TEST THE CHECKER - for a person who is not on the team (about 15 minutes)

You have three files. Together they are a small regulatory document and the data table behind it.
  M23.html                    the document (open it in a browser to read it; edit it with Notepad)
  M23.docx                    the same document as a Word file (edit it in Word)
  finerenone_stability.csv    the data table (edit it in Notepad, NOT in Excel: Excel changes the file)

WHAT TO DO
1. Make up to 10 changes. Try to fool the checker: change a number, flip a claim ("had no results outside the limit" <-> "had results outside the limit"),
   change a unit, delete a sentence, remove the words "In illustrative demonstration data,", change a number in the CSV, and so on.
   You may change the document, the CSV, or both. Make each change small and different. Save each file under its own name.
2. Write down EVERY change in answers.csv (the file next to the folder for_classmate). One line per change:
     n            1, 2, 3 ...
     file         html, docx or csv
     csv_line     only for csv: the line number in the CSV file (line 1 is the header)
     near         a few words of the sentence or table row around the change, so a person can find it
     original_text  what it said before
     new_text     what it says now (leave empty if you deleted it)
     kind         number, claim, unit, deleted, label or other
3. Give the whole folder back. Do not tell the person who runs the checker what you changed before the check has run.
Nothing you do can break anything: these are copies.
"""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- prepare ---------------------------------------------------------------------------------------------------------------------------

def prepare(out, run=None):
    """Make the kit folder. Returns the folder. Refuses an existing folder. Without run, a fresh scripted-mock demo run is made first."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (kits are never overwritten)")
    out.mkdir(parents=True)
    if run is None:
        run = out / "source_run"
        code = D.main(["--out", str(run), "--mock"])
        if code != 0:
            raise RuntimeError("the demo run that feeds the kit did not pass")
    run = Path(run)
    result = json.loads((run / "draft" / "result.json").read_text(encoding="utf-8"))
    summary = json.loads((run / "demo_result.json").read_text(encoding="utf-8"))
    if not result["accepted"] or summary["synthetic"]:
        raise ValueError("the run must be an accepted CSV-mode run (not --synthetic)")
    if summary["hashes"]["finerenone_stability.csv"] != sha256(D.CSV_PATH):
        raise ValueError("the CSV has changed since that run was made; make a new run")
    render = run / "draft" / result["render"]
    give, keep = out / "for_classmate", out / "trusted"
    give.mkdir()
    for name in ("M23.html", "M23.docx"):
        shutil.copyfile(render / name, give / name)
    shutil.copyfile(D.CSV_PATH, give / FILES["csv"])
    (give / "INSTRUCTIONS.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    shutil.copytree(render, keep / "render")
    shutil.copytree(run / "ref", keep / "ref")
    shutil.copyfile(run / "draft" / "graph_snapshot.json", keep / "rows.json")
    shutil.copyfile(D.CSV_PATH, keep / FILES["csv"])
    task, _ = D.build_csv_world()
    (keep / "task.json").write_text(json.dumps(task, indent=1, sort_keys=True), encoding="utf-8")
    (keep / "fingerprints.json").write_text(json.dumps({k: sha256(give / v) for k, v in FILES.items()}, indent=1), encoding="utf-8")
    with open(out / "answers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(ANSWER_COLUMNS)
        for i in range(1, 11):
            w.writerow([i, "", "", "", "", "", ""])
    return out


# ---- score step 1: the checks (never opens answers.csv) --------------------------------------------------------------------------------

def _finding(check, file, text, line=None, tokens=(), require="any", group=None):
    return {"check": check, "file": file, "text": text, "line": line, "tokens": list(tokens), "require": require, "group": group}


def _trusted(keep):
    keep = Path(keep)
    return (json.loads((keep / "task.json").read_text(encoding="utf-8")), json.loads((keep / "rows.json").read_text(encoding="utf-8")),
            (keep / "ref" / "p5_placements.jsonl", keep / "ref" / "p8"))


def _line_of(rows, fid):
    """The CSV line a trusted fact came from, or None."""
    try:
        m = re.fullmatch(r"row=(\d+)", MG.fact(rows, fid).get("locator", ""))
    except KeyError:
        return None
    return int(m.group(1)) if m else None


def csv_checks(edited, rows, task, keep):
    """Checks on the edited CSV: the data rules (check_rows), and the TRUSTED rendered document cross-checked against facts rebuilt from the edited CSV."""
    out = []
    try:
        lines = SF.load_rows(edited)
        problems = SF.check_rows(lines)
    except Exception as e:                                                # noqa: BLE001 - any unreadable file is a finding, not a crash
        return [_finding("csv_rules", "csv", f"the CSV cannot be read: {type(e).__name__}")]
    flagged = set()
    for p in problems:
        code, _, at = p.partition(":line ")
        out.append(_finding("csv_rules", "csv", f"{code} (line {at})", line=int(at) if at.isdigit() else None))
        if at.isdigit():
            flagged.add(int(at))
    source = Path(edited)
    with tempfile.TemporaryDirectory(prefix="kit_csv_") as tmp:
        if flagged:                                                       # keep checking the other lines: the flagged ones are already found
            source = Path(tmp) / FILES["csv"]
            kept = Path(edited).read_text(encoding="utf-8").splitlines(keepends=True)
            source.write_text("".join(ln for i, ln in enumerate(kept, start=1) if i not in flagged), encoding="utf-8")
            if len(lines) == len(flagged):
                return out
        try:
            _, rows2 = D.build_csv_world(source)
        except Exception as e:                                            # noqa: BLE001
            return out + [_finding("csv_rebuild", "csv", f"the CSV cannot be turned into facts: {type(e).__name__}: {e}")]
        try:
            out += _csv_vs_document(rows, rows2, task, keep, flagged)
        except Exception as e:                                            # noqa: BLE001 - e.g. a flagged line held a fact the document needs
            out.append(_finding("csv_rebuild", "csv", f"the document cannot be checked against the edited CSV: {type(e).__name__}: {e}"))
    return out


def _csv_vs_document(rows, rows2, task, keep, flagged):
    """The TRUSTED saved document cross-checked against facts rebuilt from the edited CSV (lines the data rules already flagged are left out)."""
    out = []
    p5, p8 = Path(keep) / "ref" / "p5_placements.jsonl", Path(keep) / "ref" / "p8"
    cc = X.run(Path(keep) / "render", rows2, p5, p8)
    for r in cc["rows"]:
        if r["verdict"] != "MATCH":
            out.append(_finding("csv_vs_document", "csv", f"the saved document shows {r['number'] or '(nothing)'} for {r['fact_id']}: {r['reason']}",
                                line=_line_of(rows, r["fact_id"])))
    for p in C4.compare(Path(keep) / "render" / "M23.html", task, rows2)["problems"]:
        out.append(_finding("csv_vs_claims", "csv", p, group=_group_of_problem(p)))
    return out


def _group_of_problem(text):
    m = re.match(r"^(\S+) \| ([^:]+):", text)
    return (m.group(1), m.group(2)) if m else None


def _units_info(task, rows):
    """(expected labels in document order, {(cond word, shown attribute): (condition, attribute)}, names for the sentence patterns)."""
    units = T4.units_of4(task, rows)
    expected, where, names = [], {}, {"test": [], "kind": ["NLT", "NMT"], "attr": [], "cond": []}
    for u in units:
        for key in ("test", "attr", "cond"):
            names[key] += [w for w in u["names"].get(key, []) if w not in names[key]]
        if u["kind"] == "result":
            where[(u["names"]["cond"][0], u["names"]["attr"][0])] = (u["condition"], u["attribute"])
            expected += [f"{k}|{u['names']['cond'][0]}|{u['names']['attr'][0]}" for k in u["expect"]]
        else:
            expected += [k for k in u["expect"] if k != "spec_row"]
    return expected, where, names


def _label(kind, sentence, where):
    """kind + the group the sentence names (for range / claim sentences)."""
    if kind in ("range", "claim"):
        for (cond, attr), _ in sorted(where.items(), key=lambda kv: -len(kv[0][1])):
            if cond in sentence and attr in sentence:
                return f"{kind}|{cond}|{attr}"
    return kind or "?"


def wording_checks(fmt, units, task, rows):
    """The sentence patterns of the writer's gate (c)/(e) applied to the SAVED text: every sentence must fit one allowed pattern, the sentences must be
    the expected ones in order, and a claim must agree with the outside-limit count. Works for html and docx alike."""
    expected, where, names = _units_info(task, rows)
    links = R.links_of(task)
    out, got = [], []
    for kind, text in units:
        if kind != "p":
            continue
        for s in SENTENCE_SPLIT.split(text.strip()):
            if not s:
                continue
            c = S.m23d_classify(s, names)
            label = _label(c[0], s, where) if c else "?"
            got.append(label)
            words = [w for w in list(names["cond"]) + [a.split(" (")[0] for a in names["attr"]] if w in s]
            if c is None:
                out.append(_finding("wording", fmt, f"a sentence fits no allowed pattern: \"{s[:70]}\"", tokens=words or s.split()[:3], require="all" if words else "any"))
                continue
            if c[0] == "claim" and "|" in label:
                grp = where[tuple(label.split("|")[1:])]
                try:
                    n = R.outside_count(rows, links, *grp)
                except R.LimitUnknown:
                    n = None
                if (c[2] == "zero" and n != 0) or (c[2] == "some" and n == 0):
                    out.append(_finding("wording", fmt, f"a claim disagrees with the data (results outside the limit: {n}): \"{s[:70]}\"", tokens=words, require="all"))
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, expected, got, autojunk=False).get_opcodes():
        for lab in (expected[i1:i2] if tag in ("delete", "replace") else []):
            if got and lab in got[j1:j2]:
                continue
            parts = lab.split("|")
            toks = [parts[1], parts[2].split(" (")[0]] if len(parts) == 3 else {"shelf": ["shelf life"], "excursion": ["xcursion"], "study": ["demonstrated"], "spec_intro": ["specification"]}.get(lab, [lab])
            if tag == "delete" or all(g == "?" for g in got[j1:j2]):
                out.append(_finding("wording", fmt, f"an expected sentence is missing or empty: {lab}", tokens=toks, require="all" if len(parts) == 3 else "any"))
        if tag == "insert":
            out.append(_finding("wording", fmt, "an extra sentence was added", tokens=[]))
    return out


def doc_checks(for_dir, keep, task, rows):
    """Checks on the edited HTML and Word file against the TRUSTED facts: the cross-check (every number and its unit), compare4 (claims, label, links), wording."""
    out = []
    p5, p8 = Path(keep) / "ref" / "p5_placements.jsonl", Path(keep) / "ref" / "p8"
    with tempfile.TemporaryDirectory(prefix="kit_") as tmp:
        work = Path(tmp) / "render"
        shutil.copytree(Path(keep) / "render", work)
        for fmt in ("html", "docx"):
            shutil.copyfile(Path(for_dir) / FILES[fmt], work / FILES[fmt])
        try:
            cc = X.run(work, rows, p5, p8)
            for r in cc["rows"]:
                if r["verdict"] != "MATCH":
                    fact = rows.get(r["fact_id"], {})
                    toks = [t for t in (r["number"], r["v23"], fact.get("value_text", "")) if t]
                    out.append(_finding("crosscheck", r["format"], f"number {r['number'] or '(missing)'} next to {r['fact_id']}: {r['reason']}", tokens=toks))
            for p in cc["problems"]:
                out.append(_finding("crosscheck", "doc", p))
        except Exception as e:                                            # noqa: BLE001
            out.append(_finding("crosscheck", "doc", f"the cross-check could not read the files: {type(e).__name__}"))
        try:
            for p in C4.compare(work / "M23.html", task, rows)["problems"]:
                g = _group_of_problem(p)
                out.append(_finding("compare4", "html", p, tokens=group_words(g) if g else [], require="all"))
        except Exception as e:                                            # noqa: BLE001
            out.append(_finding("compare4", "html", f"the HTML could not be checked: {type(e).__name__}"))
        for fmt, reader in (("html", lambda: X.read_html(work / "M23.html")[0]), ("docx", lambda: X.read_docx(work / "M23.docx"))):
            try:
                out += wording_checks(fmt, reader(), task, rows)
            except Exception as e:                                        # noqa: BLE001
                out.append(_finding("wording", fmt, f"the {fmt} file could not be read for the wording check: {type(e).__name__}"))
    return out


def group_words(group):
    """The words a person would use for a group (condition, attribute): ['long-term', 'Assay']."""
    return [P.COND_WORD.get(group[0], group[0]), P.ATTR_SHOWN.get(group[1], group[1]).split(" (")[0]]


def run_checks(for_dir, keep):
    """STEP 1. {"findings": [...], "changed": {file: bool}}. Looks only at the edited files and the trusted folder; never opens answers.csv."""
    task, rows, _ = _trusted(keep)
    want = json.loads((Path(keep) / "fingerprints.json").read_text(encoding="utf-8"))
    changed, findings = {}, []
    for k, name in FILES.items():
        p = Path(for_dir) / name
        changed[k] = (not p.exists()) or sha256(p) != want[k]
        if changed[k]:
            findings.append(_finding(FINGERPRINT, k, f"{name} is not the file that was handed out (its sha256 differs); this says nothing about WHERE"))
    if changed["csv"]:
        findings += csv_checks(Path(for_dir) / FILES["csv"], rows, task, keep)
    if changed["html"] or changed["docx"]:
        findings += doc_checks(for_dir, keep, task, rows)
    return {"findings": findings, "changed": changed}


# ---- score step 2: match the checks to the classmate's list ---------------------------------------------------------------------------

def _has(blob, token):
    return re.search(r"(?<![\w.])" + re.escape(token.lower()) + r"(?![\w]|\.\d)", blob) is not None


def read_answers(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("file") or "").strip()]


def match_answers(checks, answers, keep):
    """STEP 2. For each listed change: {"n", "file", "result", "by", ...}; result is CAUGHT / NOT LOCATED / MISSED. Also lists findings that no change explains."""
    trusted_lines = D.csv_lines(Path(keep) / FILES["csv"])
    findings, used, results = checks["findings"], set(), []
    for a in answers:
        f = a["file"].strip().lower()
        blob = " ".join((a.get("near") or "", a.get("original_text") or "", a.get("new_text") or "")).lower()
        hits = []
        for i, fd in enumerate(findings):
            if fd["check"] == FINGERPRINT or fd["file"] != f:
                continue
            if f == "csv":
                line = int(a["csv_line"]) if (a.get("csv_line") or "").strip().isdigit() else None
                grp = (trusted_lines[line]["condition"], trusted_lines[line]["attribute"]) if line in trusted_lines else None
                ok = (fd["line"] is not None and fd["line"] == line) or (fd["group"] is not None and grp is not None and tuple(fd["group"]) == grp)
            else:
                toks = fd["tokens"]
                ok = bool(toks) and (all if fd["require"] == "all" else any)(_has(blob, t) for t in toks)
            if ok:
                hits.append(i)
        used.update(hits)
        fp = any(fd["check"] == FINGERPRINT and fd["file"] == f for fd in findings)
        by = sorted({findings[i]["check"] for i in hits})
        result = "CAUGHT" if hits else "NOT LOCATED" if fp else "MISSED"
        results.append({"n": a["n"], "file": f, "near": a.get("near", ""), "kind": a.get("kind", ""), "result": result,
                        "by": by if hits else ([FINGERPRINT] if fp else []), "evidence": [findings[i]["text"] for i in hits][:2]})
    extra = [fd for i, fd in enumerate(findings) if i not in used and fd["check"] != FINGERPRINT]
    return {"results": results, "unexplained_findings": [f"{fd['check']} ({fd['file']}): {fd['text']}" for fd in extra]}


def report_text(matched):
    r = matched["results"]
    lines = ["CLASSMATE TEST - result for each change the person listed", ""]
    for x in r:
        lines.append(f"  #{x['n']:>2} [{x['file']:<4}] {x['kind'] or '-':<8} {x['near'][:38]:<38} -> {x['result']:<11} by: {', '.join(x['by']) or 'nothing'}")
    c = {k: sum(1 for x in r if x["result"] == k) for k in ("CAUGHT", "NOT LOCATED", "MISSED")}
    lines += ["", f"  TOTAL {len(r)} changes: CAUGHT (a content check names the place) {c['CAUGHT']} | NOT LOCATED (only the file fingerprint changed) {c['NOT LOCATED']} | MISSED {c['MISSED']}"]
    for x in r:
        if x["result"] != "CAUGHT":
            lines.append(f"  NOT CAUGHT: #{x['n']} {x['file']} {x['near']!r}: {x['result']}")
    for u in matched["unexplained_findings"][:6]:
        lines.append(f"  finding that no listed change explains: {u}")
    return "\n".join(lines)


def score(kit):
    """Run step 1, then read answers.csv (step 2). Writes score_<time>.json next to the kit; prints the report. Returns the matched dict."""
    kit = Path(kit)
    checks = run_checks(kit / "for_classmate", kit / "trusted")                 # step 1: answers.csv is not touched here
    matched = match_answers(checks, read_answers(kit / "answers.csv"), kit / "trusted")   # step 2
    stamp = time.strftime("%Y%m%d_%H%M%S")
    (kit / f"score_{stamp}.json").write_text(json.dumps({"changed_files": checks["changed"], "findings": checks["findings"], **matched}, indent=1), encoding="utf-8")
    print(report_text(matched))
    return matched


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--out", required=True)
    p.add_argument("--run", help="an accepted CSV-mode demo run folder (default: make a fresh scripted-mock one inside the kit)")
    s = sub.add_parser("score")
    s.add_argument("--dir", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "prepare":
        print(f"kit ready: {prepare(args.out, args.run)}\n  give the person ONLY the folder for_classmate/ ; they fill answers.csv ; then run: python tools/classmate_kit.py score --dir {args.out}")
        return 0
    m = score(args.dir)
    return 0 if all(x["result"] == "CAUGHT" for x in m["results"]) else 1


if __name__ == "__main__":
    sys.exit(main())
