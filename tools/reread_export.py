"""Second, independent reader: opens the saved P5.docx as a zip (no python-docx), checks its numbers against placements.jsonl read from disk, and flags unsupported claims."""
import argparse
import csv
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.render.numbers import BATCH_RUN, ID_TOKEN, find_numbers, uncovered_digits  # noqa: E402
from ectd_engine.review.entail import entail  # noqa: E402
from ectd_engine.review.layout import check_headings, check_row, expected_headings  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEAD = "Batch\tValue\tUnit"


def _par_text(p):
    out = []
    for el in p.iter():
        if el.tag == W + "t":
            out.append(el.text or "")
        elif el.tag == W + "tab":
            out.append("\t")
        elif el.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def read_units(docx_path):
    """In file order: ("p", text) per paragraph, ("row", "a\tb\tc") per table row. Read straight from word/document.xml."""
    with zipfile.ZipFile(docx_path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    units = []
    for el in body:
        if el.tag == W + "p":
            style = el.find(W + "pPr/" + W + "pStyle")
            is_head = style is not None and style.get(W + "val", "").startswith(("Heading", "Title"))
            units.append(("h" if is_head else "p", _par_text(el)))
        elif el.tag == W + "tbl":
            for tr in el.findall(W + "tr"):
                cells = ["\n".join(_par_text(p) for p in tc.findall(W + "p")) for tc in tr.findall(W + "tc")]
                units.append(("row", "\t".join(cells)))
    return units


def read_placements(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def batch_ids_from_disk():
    """Batch ids the P.5.4 tasks list (read from the task files on disk, not from the writer)."""
    from tools.render_doc import RUN54, tasks_of
    ids = set()
    for t in tasks_of(RUN54).values():
        ids |= set(t.get("batches", ()))
    return ids


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def facts_for(text, placed):
    """{fact id: value text} from the placements of this paragraph. If n_outside is not placed but the limit and the
    lowest/highest result are, work it out from them (0 = none outside, 1 = at least one outside)."""
    facts = {pl["id"]: pl["text"] for pl in placed}
    lim, lo, hi = _dec(facts.get("limit")), _dec(facts.get("min_value")), _dec(facts.get("max_value"))
    if "n_outside" not in facts and lim is not None and lo is not None and hi is not None:
        if "not less than" in text:
            facts["n_outside"] = "0" if lo >= lim else "1"
        elif "not more than" in text:
            facts["n_outside"] = "0" if hi <= lim else "1"
    return facts


def plan_from_disk():
    """What the document must contain, read from the task files and the content plan: {"title", "tasks": [{"part", "task_id",
    "attribute", "column", "unit", "batches"}]} in the order the writer used (P.5.4 tasks, then P.5.6 tasks)."""
    from ectd_engine.render.html import TITLE
    from tools.render_doc import RUN54, RUN56, accepted_text, load_jsonl, tasks_of
    tasks = []
    for part, folders in (("3.2.P.5.4", (RUN54,)), ("3.2.P.5.6", (RUN56, RUN56 / "synthetic"))):
        for folder in folders:
            by_id = tasks_of(folder)
            for res in load_jsonl(folder / "results.jsonl"):
                if accepted_text(res) is None:
                    continue
                t = by_id[res["task_id"]]
                tasks.append({"part": part, "task_id": t["task_id"], "attribute": t["attribute"], "column": t["column"],
                              "unit": t.get("unit", "%"), "batches": list(t.get("batches", ()))})
    return {"title": TITLE, "tasks": tasks}


def reread(docx_path, placements, batch_ids, plan=None):
    """Returns a report dict: number counts, problems, and one row per flag.
    With a plan (see plan_from_disk) every heading must equal the planned one at its position ("heading:<text>") and every
    table row must match its own task and placement ("row:<batch id>")."""
    units = read_units(docx_path)
    found, uncovered, flags, pos, unknown, attribute = [], [], [], 0, [], ""
    headings, n_tasks = [], 0
    for i, (kind, text) in enumerate(units):
        if kind == "h":
            headings.append(text)
        if kind == "h" and not text.startswith("3.2.P"):
            attribute = text   # the attribute heading: the sentences under it must be about this attribute
            n_tasks += 1
        data_row = kind == "row" and text != HEAD
        for run in BATCH_RUN.finditer(text):   # every id after "Batch"/"Batches" must be on the list of the task files
            unknown += [f"unknown batch id:{t.group(0)}" for t in ID_TOKEN.finditer(run.group(1))
                        if t.group(0) != "and" and any(c.isdigit() for c in t.group(0)) and t.group(0) not in batch_ids]
        if data_row and text.split("\t", 1)[0] not in batch_ids:
            unknown.append(f"unknown batch id:{text.split(chr(9), 1)[0]}")
        nums = find_numbers(text, batch_ids, data_row)
        uncovered += uncovered_digits(text, [(o, o + len(t)) for o, t in nums], batch_ids, data_row)
        placed = placements[pos:pos + len(nums)]
        pos += len(nums)
        found += [t for _, t in nums]
        facts = dict(facts_for(text, placed), attribute=attribute)
        section = placed[0]["section"] if placed else ""
        if plan and kind == "h":
            continue   # headings are checked as a whole list below
        if plan and data_row:
            task = plan["tasks"][n_tasks - 1] if 0 < n_tasks <= len(plan["tasks"]) else None
            for flag in check_row(text.split("\t"), placed[0] if placed else None, task):
                flags.append({"unit": i, "section": section, "flag": flag, "text": text})
            continue
        for flag in entail(text, facts, kind=kind):
            flags.append({"unit": i, "section": section, "flag": flag, "text": text})
    if plan:
        flags += [{"unit": "", "section": "", "flag": f, "text": ""}
                  for f in check_headings(headings, expected_headings(plan["title"], plan["tasks"]))]
    placed_text = [r["text"] for r in placements]
    problems = []
    if len(found) != len(placed_text):
        problems.append(f"numbers!=placements: {len(found)} in file, {len(placed_text)} placed")
    for i, (a, b) in enumerate(zip(found, placed_text)):
        if a != b:
            problems.append(f"changed number #{i}: file has {a!r}, placement says {b!r}")
            break
    problems += uncovered + unknown
    return {"numbers": len(found), "placements": len(placed_text), "uncovered": len(uncovered), "paragraphs": len(units),
            "flags": flags, "problems": problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="folder holding P5.docx and placements.jsonl")
    ap.add_argument("--out", required=True, help="folder for report.txt and flags.csv")
    args = ap.parse_args(argv)
    src, out = Path(args.folder), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = reread(src / "P5.docx", read_placements(src / "placements.jsonl"), batch_ids_from_disk(), plan_from_disk())
    with open(out / "flags.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["unit", "section", "flag", "text"])
        w.writeheader()
        w.writerows(rep["flags"])
    ok = not rep["problems"] and rep["numbers"] == rep["placements"]
    lines = ["== DOCX re-read (zip + ElementTree, placements read from disk) ==", f"text units {rep['paragraphs']}",
             f"numbers {rep['numbers']}", f"placements {rep['placements']}", f"uncovered {rep['uncovered']}",
             f"reviewer flags {len(rep['flags'])} (see flags.csv)"]
    lines += [f"  problem: {p}" for p in rep["problems"]]
    lines.append("RESULT docx numbers == placements" if ok else "RESULT MISMATCH")
    text = "\n".join(lines) + "\n"
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
