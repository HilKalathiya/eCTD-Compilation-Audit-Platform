"""Builds the P.5 HTML from accepted paragraphs; every number is written with a placement record saying which fact it came from."""
import html as htmllib
import re
from dataclasses import dataclass, field

from ectd_engine.render.numbers import NUMBER, find_numbers, uncovered_digits
from ectd_engine.render.plan import CONTENT_PLAN, conditions, parts, required_keys
from ectd_engine.validator.validator import render as plain_render
from ectd_engine.writer.batch_facts import fact_id
from ectd_engine.writer.batch_prompt import opening_sentence
from ectd_engine.writer.spec_facts import render_paragraph

S, M, E = "", "", ""   # private marks: a value starts with S+id+M and ends with E
MARKED = re.compile(S + r"([^" + M + r"]*)" + M + r"(.*?)" + E, re.S)
LEFT_OVER = re.compile(r"\[\[([a-z0-9_]+)\]\]")


class Marked(str):
    """A value with marks around it that still equals its plain text (the writer's wording repair compares the count with "1")."""

    def __eq__(self, other):
        return str.__eq__(MARKED.sub(lambda m: m.group(2), str(self)), other)

    __hash__ = str.__hash__


def wrap_facts(facts):
    """The same facts, with each value (and bare count) marked with its own key, so the renderer can see where it lands."""
    out = {}
    for key, fact in facts.items():
        item = dict(fact, value=Marked(f"{S}{key}{M}{fact['value']}{E}"))
        if "bare" in fact:
            item["bare"] = Marked(f"{S}{key}{M}{fact['bare']}{E}")
        out[key] = item
    return out


def unmark(marked):
    """(clean text, [(id, start, end)]) with the marks taken out."""
    clean, spans, pos = [], [], 0
    length = 0
    for m in MARKED.finditer(marked):
        before = marked[pos:m.start()]
        clean.append(before)
        length += len(before)
        spans.append((m.group(1), length, length + len(m.group(2))))
        clean.append(m.group(2))
        length += len(m.group(2))
        pos = m.end()
    clean.append(marked[pos:])
    return "".join(clean), spans


@dataclass
class Paragraph:
    name: str
    text: str
    placements: list = field(default_factory=list)   # {"id", "label", "offset", "text"}
    batch_ids: tuple = ()
    table_row: bool = False


@dataclass
class Section:
    part: str
    task_id: str
    name: str
    paragraphs: list


@dataclass
class Rejected:
    part: str
    task_id: str
    name: str
    reason: str
    problems: list = field(default_factory=list)


def make_paragraph(name, marked, labels, batch_ids=(), table_row=False):
    """Take the marks out and write one placement for every number that sits inside a marked value."""
    text, spans = unmark(marked)
    found = find_numbers(text, batch_ids, table_row)
    placements = [{"id": key, "label": labels.get(key, ""), "offset": off, "text": tx}
                  for off, tx in found for key, a, b in spans if a <= off and off + len(tx) <= b]
    return Paragraph(name, text, placements, tuple(batch_ids), table_row)


def check_paragraph(p):
    """Problems with one paragraph: a number with no placement, or a placement that is not a number at its offset."""
    problems = []
    for pl in p.placements:
        at = p.text[pl["offset"]:pl["offset"] + len(pl["text"])]
        if at != pl["text"] or not NUMBER.fullmatch(pl["text"]):
            problems.append(f"badplacement:{pl['text']}")
    placed = [(pl["offset"], pl["text"]) for pl in p.placements]
    for off, tx in find_numbers(p.text, p.batch_ids, p.table_row):
        if (off, tx) not in placed:
            problems.append(f"unplaced:{tx}")
    if len(placed) != len(set(placed)):
        problems.append("badplacement:two placements for one number")
    covered = [(pl["offset"], pl["offset"] + len(pl["text"])) for pl in p.placements]
    problems += uncovered_digits(p.text, covered, p.batch_ids, p.table_row)   # second check: every digit, whatever the number regex says
    return problems


def check_section(section):
    """Every problem in a section (one list for all its paragraphs)."""
    return [pr for p in section.paragraphs for pr in check_paragraph(p)]


def finish(part, task_id, name, paragraphs):
    """A Section if its numbers are all placed, else a Rejected with the first problem as the reason."""
    section = Section(part, task_id, name, paragraphs)
    problems = check_section(section)
    return Rejected(part, task_id, name, problems[0], problems) if problems else section


def missing(part, name, flags, facts, marked_text=""):
    """Rejected if a required fact is absent, or the text asks for a fact that is absent; None if all is there."""
    keys = [k for k in required_keys(part, name, conditions(part, flags)) if k not in facts]
    keys += [k for k in LEFT_OVER.findall(marked_text) if k not in keys]
    return keys


def reject_missing(part, task_id, name, keys):
    return Rejected(part, task_id, name, f"missing:{keys[0]}", [f"missing:{k}" for k in keys])


def labels_of(facts):
    return {k: v.get("label", "") for k, v in facts.items()}


def build_p56(task, facts, flags, template):
    """The one P.5.6 section for a task. template = the accepted draft, still with [[placeholders]]."""
    part, name = "3.2.P.5.6", "justification"
    marked = render_paragraph(template, wrap_facts(facts), task["basis"]) if not missing(part, name, flags, facts) else ""
    gone = missing(part, name, flags, facts, marked)
    if gone:
        return [reject_missing(part, task["task_id"], name, gone)]
    return [finish(part, task["task_id"], name, [make_paragraph(name, marked, labels_of(facts))])]


def build_p54(task, facts, flags, table, template):
    """The three P.5.4 sections (opening, table, discussion) for a task."""
    part, tid, ids = "3.2.P.5.4", task["task_id"], tuple(task["batches"])
    out, labels = [], labels_of(facts)
    for name in ("opening", "table", "discussion"):
        keys = missing(part, name, flags, facts)
        if keys:
            out.append(reject_missing(part, tid, name, keys))
            continue
        if name == "opening":
            paras = [make_paragraph(name, opening_sentence(task, wrap_facts(facts)), labels, ids)]
        elif name == "discussion":
            marked = plain_render(template, wrap_facts(facts))
            gone = missing(part, name, flags, facts, marked)
            if gone:
                out.append(reject_missing(part, tid, name, gone))
                continue
            paras = [make_paragraph(name, marked, labels, ids)]
        else:
            paras = []
            for i, (b, value) in enumerate(table["rows"]):
                key = fact_id(b, task["column"])
                cell = f"{S}{key}{M}{value}{E}" if value is not None else "excluded (quarantined)"
                unit = table["unit"] if value is not None else "-"
                paras.append(make_paragraph(f"table:{i}", f"{b}\t{cell}\t{unit}", {key: "stored result of this batch"},
                                            ids, table_row=True))
        out.append(finish(part, tid, name, paras))
    return out


def _inline(text, placements, base=0):
    """HTML for text, with each placed number wrapped in a span that names its source."""
    out, pos = [], 0
    for pl in sorted(placements, key=lambda x: x["offset"]):
        a = pl["offset"] - base
        if a < pos or a + len(pl["text"]) > len(text):
            continue
        out.append(htmllib.escape(text[pos:a]))
        out.append(f'<span class="n" data-src="{htmllib.escape(pl["id"], quote=True)}">{htmllib.escape(pl["text"])}</span>')
        pos = a + len(pl["text"])
    out.append(htmllib.escape(text[pos:]))
    return "".join(out)


def _row_html(p):
    cells, base, parts_ = p.text.split("\t"), 0, []
    for i, cell in enumerate(cells):
        cls = ' class="id"' if i == 0 else ""
        parts_.append(f"<td{cls}>{_inline(cell, p.placements, base)}</td>")
        base += len(cell) + 1
    return "<tr>" + "".join(parts_) + "</tr>"


def section_html(sec):
    if sec.name == "table":
        rows = "".join(_row_html(p) for p in sec.paragraphs)
        return f'<table data-section="table"><tr><th>Batch</th><th>Value</th><th>Unit</th></tr>{rows}</table>'
    p = sec.paragraphs[0]
    return f'<p data-section="{sec.name}">{_inline(p.text, p.placements)}</p>'


def placement_records(sec):
    """The records for placements.jsonl: id, section, paragraph, offset, text (plus what the fact is)."""
    return [{"id": pl["id"], "section": f"{sec.part}/{sec.task_id}/{sec.name}", "paragraph": p.name,
             "offset": pl["offset"], "text": pl["text"], "label": pl["label"]}
            for p in sec.paragraphs for pl in p.placements]


def visible_numbers(doc, batch_ids):
    """Numbers a reader of the finished HTML would see (batch-id table cells and the exempt names left out)."""
    ids = set(batch_ids)

    def id_cell(m):   # a first cell is exempt only if it really is a listed batch id
        return "" if htmllib.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() in ids else m.group(1)

    body = re.sub(r'<td class="id">(.*?)</td>', id_cell, doc, flags=re.S)
    body = re.sub(r"</?span[^>]*>", "", body)
    body = htmllib.unescape(re.sub(r"<[^>]+>", "\n", body))
    return find_numbers(body, batch_ids)


def uncovered_in_html(doc, batch_ids):
    """Second check on the finished HTML: ["uncovered:<context>"] for every digit in a text node that is not inside a
    number span (class n) and not exempt. Does not use the number regex."""
    ids, out, in_span, in_id = set(batch_ids), [], 0, False
    for tok in re.split(r"(<[^>]+>)", doc):
        if tok.startswith("<"):
            if re.match(r'<span class="n"', tok):
                in_span += 1
            elif tok.startswith("</span") and in_span:
                in_span -= 1
            elif tok.startswith('<td class="id"'):
                in_id = True
            elif tok.startswith("</td"):
                in_id = False
        elif tok and not in_span:
            text = htmllib.unescape(tok)
            out += uncovered_digits(text, [], ids, table_first_cell=in_id)
    return out


TITLE = "3.2.P.5 Control of drug product"


def walk(tasks):
    """The one reading order for every output format (HTML and Word). Yields events the plan decides:
    ("part", part, title) ("task", task, None) ("section", Section, None) ("rejected", Rejected, None)
    ("end_task", None, None) ("end_part", None, None). tasks = [{"part", "task_id", "attribute", "batch_ids", "sections"}]."""
    for part in parts():
        yield "part", part, CONTENT_PLAN[part]["title"]
        order = [s["name"] for s in CONTENT_PLAN[part]["sections"]]
        for t in (x for x in tasks if x["part"] == part):
            yield "task", t, None
            by_name = {s.name: s for s in t["sections"]}
            for name in order:
                s = by_name.get(name)
                if isinstance(s, Section):
                    yield "section", s, None
                elif s is not None:
                    yield "rejected", s, None
            yield "end_task", None, None
        yield "end_part", None, None


def build_document(tasks):
    """tasks: [{"part", "task_id", "attribute", "batch_ids", "sections": [Section | Rejected]}] in any order.

    Returns (html, placements, report). The plan decides the order of parts and sections; rejected sections are left out."""
    body, records, rejected, batch_ids, n_sections = [], [], [], set(), 0
    body.append(f"<h1>{TITLE}</h1>")
    for kind, a, b in walk(tasks):
        if kind == "part":
            body.append(f'<section data-part="{a}"><h2>{a} {b}</h2>')
        elif kind == "task":
            batch_ids |= set(a.get("batch_ids", ()))
            body.append(f'<section data-task="{htmllib.escape(a["task_id"], quote=True)}"><h3>{htmllib.escape(a["attribute"])}</h3>')
        elif kind == "section":
            body.append(section_html(a))
            records += placement_records(a)
            n_sections += 1
        elif kind == "rejected":
            rejected.append(a)
        else:
            body.append("</section>")
    doc = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>3.2.P.5</title></head><body>'
           + "".join(body) + "</body></html>")
    n_numbers = len(visible_numbers(doc, batch_ids))
    n_marked = doc.count('data-src="')
    uncovered = uncovered_in_html(doc, batch_ids)
    report = {"numbers": n_numbers, "placements": len(records), "data_src": n_marked, "sections": n_sections,
              "uncovered": len(uncovered), "uncovered_list": uncovered,
              "rejected": rejected, "missing": sum(1 for r in rejected if r.reason.startswith("missing:"))}
    return doc, records, report
