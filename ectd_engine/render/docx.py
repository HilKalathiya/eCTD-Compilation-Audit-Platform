"""Builds P5.docx (Word) from the same plan, sections and placements as the HTML, then re-opens the SAVED file and checks its numbers again."""
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph as WordParagraph

from ectd_engine.render.html import TITLE, placement_records, walk
from ectd_engine.render.numbers import find_numbers, uncovered_digits

TABLE_HEAD = ("Batch", "Value", "Unit")


def _units(doc):
    """What a reader of the saved .docx sees, in order: ("p", text) for each paragraph, ("row", "a\\tb\\tc") for each table row."""
    out = []
    for el in doc.element.body.iterchildren():
        if el.tag.endswith("}p"):
            out.append(("p", WordParagraph(el, doc).text))
        elif el.tag.endswith("}tbl"):
            for row in Table(el, doc).rows:
                out.append(("row", "\t".join(c.text for c in row.cells)))
    return out


def build_docx(tasks, path):
    """Write the document to path. Returns what reread() needs: the placement records, what we meant to write, the batch ids,
    the rejected sections and the section count. Same walk() as the HTML, so the order and headings come from the plan."""
    doc = Document()
    doc.add_heading(TITLE, level=1)
    expected, records, rejected, batch_ids, n_sections = [("p", TITLE)], [], [], set(), 0
    for kind, a, b in walk(tasks):
        if kind == "part":
            doc.add_heading(f"{a} {b}", level=2)
            expected.append(("p", f"{a} {b}"))
        elif kind == "task":
            batch_ids |= set(a.get("batch_ids", ()))
            doc.add_heading(a["attribute"], level=3)
            expected.append(("p", a["attribute"]))
        elif kind == "section":
            n_sections += 1
            records += placement_records(a)
            if a.name == "table":
                table = doc.add_table(rows=1, cols=3)
                table.style = "Table Grid"
                for cell, head in zip(table.rows[0].cells, TABLE_HEAD):
                    cell.text = head
                expected.append(("row", "\t".join(TABLE_HEAD)))
                for p in a.paragraphs:
                    cells = p.text.split("\t")
                    for cell, text in zip(table.add_row().cells, cells):
                        cell.text = text
                    expected.append(("row", p.text))
            else:
                doc.add_paragraph(a.paragraphs[0].text)
                expected.append(("p", a.paragraphs[0].text))
        elif kind == "rejected":
            rejected.append(a)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return {"records": records, "expected": expected, "batch_ids": batch_ids, "rejected": rejected, "sections": n_sections}


def reread(path, built):
    """Open the saved .docx again and check it. Does not look at the objects that wrote it, only at the file.

    Checks: (1) the numbers found in the file, in order, equal the placements; (2) every digit is inside a found number or exempt;
    (3) the file's text units equal what was meant to be written (catches a deleted row or a changed word).
    Returns a report dict; "problems" is empty when the file is clean."""
    units = _units(Document(str(path)))
    ids, found, uncovered = set(built["batch_ids"]), [], []
    for kind, text in units:
        is_row = kind == "row"
        head = is_row and text == "\t".join(TABLE_HEAD)
        data_row = is_row and not head
        nums = find_numbers(text, ids, data_row)
        found += [tx for _, tx in nums]
        uncovered += uncovered_digits(text, [(o, o + len(tx)) for o, tx in nums], ids, data_row)
    placed = [r["text"] for r in built["records"]]
    problems = []
    if len(found) != len(placed):
        problems.append(f"numbers!=placements: {len(found)} in file, {len(placed)} placed")
    for i, (f, p) in enumerate(zip(found, placed)):
        if f != p:
            problems.append(f"changed number #{i}: file has {f!r}, placement says {p!r}")
            break
    problems += uncovered
    if units != built["expected"]:
        n_rows = sum(1 for k, _ in units if k == "row")
        n_exp = sum(1 for k, _ in built["expected"] if k == "row")
        if n_rows != n_exp:
            problems.append(f"table rows: {n_rows} in file, {n_exp} written")
        else:
            problems.append("text differs from what was written")
    rejected = built["rejected"]
    return {"numbers": len(found), "placements": len(placed), "uncovered": len(uncovered), "uncovered_list": uncovered,
            "sections": built["sections"], "rejected": rejected,
            "missing": sum(1 for r in rejected if r.reason.startswith("missing:")), "problems": problems}
