"""Builds 2.3.P.5 and 2.3.P.8 (HTML and Word) from graph facts; every number is written with the id of the graph fact it came from. No model."""
import json
import re
from decimal import Decimal
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph as WordParagraph

from ectd_engine.graph.summary_graph import spec_id
from ectd_engine.render import html as H
from ectd_engine.render.numbers import find_numbers, uncovered_digits
from ectd_engine.summary.plan import ATTR_SHOWN, COND_WORD, SUMMARY_PLAN, TITLE, UNIT_TEXT, stat_id

_REF = re.compile(r"\[\[([a-z_]+)\]\]")


class Refused(Exception):
    """A fact is missing or does not fit its place; the message starts with the reason code."""


def _mark(fact_id, text):
    return f"{H.S}{fact_id}{H.M}{text}{H.E}"


def _fact(facts, fact_id):
    if fact_id not in facts:
        raise Refused(f"missing:{fact_id}")
    return facts[fact_id]


def _with_unit(row):
    """The value (marked with its id) and then its unit written the way the plan says; an unlisted unit stops the build."""
    if row["unit"] not in UNIT_TEXT:
        raise Refused(f"unit_not_listed:{row['unit']}")
    return _mark(row["fact_id"], row["value_text"]) + UNIT_TEXT[row["unit"]]


def _label(rows, demo):
    """The demo label of these facts, or '' for public facts. A DEMO fact without a label, or a public one with a label, is refused."""
    labels = {r["demo_label"] for r in rows}
    if len(labels) != 1:
        raise Refused("label_mixed")
    label = labels.pop()
    if demo and not label:
        raise Refused("demo_fact_without_label")
    if not demo and label:
        raise Refused("public_sentence_holds_demo_fact")
    return label


def _section(part, task_id, name, paragraphs, refused):
    return H.Rejected(part, task_id, name, refused, [refused]) if refused else H.finish(part, task_id, name, paragraphs)


def _template(part, spec, facts):
    refs = {k: _fact(facts, v) for k, v in spec["refs"].items()}
    _label(list(refs.values()), False)
    text = _REF.sub(lambda m: _with_unit(refs[m.group(1)]), spec["text"])
    labels = {r["fact_id"]: r["test"] for r in refs.values()}
    return [H.make_paragraph(spec["name"], text, labels)]


def _spec_intro(part, spec, facts):
    rows = [_fact(facts, spec_id(a)) for a in SUMMARY_PLAN["2.3.P.5"]["sections"][1]["attributes"]]
    return [H.make_paragraph(spec["name"], _label(rows, True) + spec["text"], {})]


def _spec_table(part, spec, facts):
    out = []
    for attr in spec["attributes"]:
        row = _fact(facts, spec_id(attr))
        _label([row], True)
        out.append(H.make_paragraph(f"row:{attr}", f"{row['test']}\t{row['limit_kind']} {_with_unit(row)}",
                                    {row["fact_id"]: "specification limit"}, table_row=True))
    return out


def _results(part, spec, facts, cond, attr):
    rows = [r for r in facts.values() if r["family"] == "stability" and r["kind"] == "demo"
            and r["condition"] == cond and r["attribute"] == attr]
    if not rows:
        raise Refused(f"missing:{cond}|{attr}")
    lo = min(rows, key=lambda r: Decimal(r["value_text"]))
    hi = max(rows, key=lambda r: Decimal(r["value_text"]))
    if len({r["unit"] for r in rows}) != 1:
        raise Refused("unit_mixed")
    label = _label(rows, True)
    lo_id, hi_id = stat_id(cond, attr, "min"), stat_id(cond, attr, "max")
    low, high = dict(lo, fact_id=lo_id), dict(hi, fact_id=hi_id)   # a derived result: the placement id names the statistic, the value is the stored row's text
    text = (f"{label}{ATTR_SHOWN[attr]} under {COND_WORD[cond]} conditions ranged from {_with_unit(low)} to {_with_unit(high)}.")
    return [H.make_paragraph("results", text, {lo_id: "lowest stored result", hi_id: "highest stored result"})]


def build_sections(facts):
    """{part: [Section | Rejected]} in plan order. Nothing is left out silently: a refusal becomes a Rejected the report counts."""
    out = {}
    for part, spec in SUMMARY_PLAN.items():
        items = []
        for sec in spec["sections"]:
            kind, name = sec["kind"], sec["name"]
            try:
                if kind == "results":
                    for cond, attr in sec["groups"]:
                        try:
                            items.append(_section(part, f"{cond}|{attr}", name, _results(part, sec, facts, cond, attr), None))
                        except Refused as e:
                            items.append(_section(part, f"{cond}|{attr}", name, None, str(e)))
                    continue
                paras = {"template": _template, "spec_intro": _spec_intro, "spec_table": _spec_table}[kind](part, sec, facts)
                items.append(_section(part, name, name, paras, None))
            except Refused as e:
                items.append(_section(part, name, name, None, str(e)))
        out[part] = items
    return out


def walk(sections):
    """The one reading order for both formats: ("part", part, title) ("section", Section) ("rejected", Rejected) ("end_part", None)."""
    for part, spec in SUMMARY_PLAN.items():
        yield "part", part, spec["title"]
        for s in sections[part]:
            yield ("section" if isinstance(s, H.Section) else "rejected"), s, None
        yield "end_part", None, None


def _section_html(sec, head):
    if sec.name == "spec_table":
        cols = "".join(f"<th>{c}</th>" for c in head)
        return f'<table data-section="spec_table"><tr>{cols}</tr>{"".join(H._row_html(p) for p in sec.paragraphs)}</table>'
    return "".join(f'<p data-section="{sec.name}">{H._inline(p.text, p.placements)}</p>' for p in sec.paragraphs)


def build_html(sections):
    """(html text, placement records, rejected list)."""
    body, records, rejected = [f"<h1>{TITLE}</h1>"], [], []
    for kind, a, b in walk(sections):
        if kind == "part":
            body.append(f'<section data-part="{a}"><h2>{a} {b}</h2>')
        elif kind == "section":
            head = next((s.get("head") for s in SUMMARY_PLAN[a.part]["sections"] if s["name"] == a.name), None)
            body.append(_section_html(a, head))
            records += H.placement_records(a)
        elif kind == "rejected":
            rejected.append(a)
        else:
            body.append("</section>")
    doc = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title></head><body>'
           + "".join(body) + "</body></html>")
    return doc, records, rejected


def build_docx(sections, path):
    """Write the Word file from the same walk. Returns nothing; verify_docx reopens the saved file."""
    doc = Document()
    doc.add_heading(TITLE, level=1)
    for kind, a, b in walk(sections):
        if kind == "part":
            doc.add_heading(f"{a} {b}", level=2)
        elif kind == "section":
            if a.name == "spec_table":
                head = next(s["head"] for s in SUMMARY_PLAN[a.part]["sections"] if s["name"] == a.name)
                table = doc.add_table(rows=1, cols=len(head))
                table.style = "Table Grid"
                for cell, text in zip(table.rows[0].cells, head):
                    cell.text = text
                for p in a.paragraphs:
                    for cell, text in zip(table.add_row().cells, p.text.split("\t")):
                        cell.text = text
            else:
                for p in a.paragraphs:
                    doc.add_paragraph(p.text)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def saved_units(path):
    """What a reader of the saved .docx sees, in order: ("p", text) per paragraph, ("row", "a\\tb") per table row."""
    doc, out = Document(str(path)), []
    for el in doc.element.body.iterchildren():
        if el.tag.endswith("}p"):
            out.append(("p", WordParagraph(el, doc).text))
        elif el.tag.endswith("}tbl"):
            out += [("row", "\t".join(c.text for c in row.cells)) for row in Table(el, doc).rows]
    return out


def verify_docx(path, records):
    """Problems found when the saved .docx is read again (empty list = its numbers equal the placements, in order, and no digit is loose)."""
    found, loose = [], []
    for _, text in saved_units(path):
        nums = find_numbers(text)
        found += [t for _, t in nums]
        loose += uncovered_digits(text, [(o, o + len(t)) for o, t in nums])
    placed = [r["text"] for r in records]
    problems = [] if found == placed else [f"docx numbers {len(found)} != placements {len(placed)} or changed"]
    return problems + loose


def write_run(out_dir, facts, docx=True):
    """Build everything and save it in a NEW folder (an existing folder is refused). Returns the report dict."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new run folder (runs are never overwritten)")
    sections = build_sections(facts)
    doc, records, rejected = build_html(sections)
    out.mkdir(parents=True)
    (out / "M23.html").write_text(doc, encoding="utf-8")
    with open(out / "placements.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    uncovered = H.uncovered_in_html(doc, ())
    report = {"numbers": len(H.visible_numbers(doc, ())), "placements": len(records), "data_src": doc.count('data-src="'),
              "uncovered": len(uncovered), "uncovered_list": uncovered, "rejected": [(r.task_id, r.reason) for r in rejected],
              "docx_problems": []}
    if docx:
        build_docx(sections, out / "M23.docx")
        report["docx_problems"] = verify_docx(out / "M23.docx", records)
    lines = [f"numbers {report['numbers']}", f"placements {report['placements']}", f"data-src spans {report['data_src']}",
             f"uncovered digits {report['uncovered']}", f"rejected sections {len(rejected)}"]
    lines += [f"  rejected: {t}: {why}" for t, why in report["rejected"]]
    lines += [f"  docx problem: {p}" for p in report["docx_problems"]]
    (out / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
