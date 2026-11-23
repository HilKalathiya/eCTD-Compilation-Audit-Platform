"""Independent cross-check of the SAVED 2.3 files (HTML and Word) against the 3.2 facts; it never imports the builder or the plan.

Every number found in a saved file starts as FAIL. It becomes MATCH only if all of these hold: it sits at its placement's offset, its
text equals the graph value (read fresh) AND the value in the saved 3.2 output, the unit right after it is the graph unit, its sentence
talks about that very fact, and a DEMO fact sits in a sentence that starts with the demo label. Any digit left over is a failure.

    python -m ectd_engine.summary.crosscheck evidence/T-068/run1            # reads Neo4j now and saves graph_snapshot.json
    python -m ectd_engine.summary.crosscheck <run folder> --snapshot <graph_snapshot.json>   # no database
"""
import argparse
import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from ectd_engine.render.numbers import find_numbers, uncovered_digits

ROOT = Path(__file__).resolve().parents[2]
P5_PLACEMENTS = ROOT / "evidence" / "T-056" / "placements.jsonl"      # the saved 3.2.P.5 (P.5.6 limits)
P8_SECTIONS = ROOT / "evidence" / "T-064" / "direct" / "sections"      # the saved 3.2.P.8.3 paragraphs
PREFIX = "M23-"
LABEL = "In illustrative demonstration data, "
NUM = r"\d+(?:\.\d+)?"
# What may follow a number for each graph unit (this is a separate copy of the table on purpose).
UNIT_AFTER = {"months": " months", "C": "°C", "%": "%", "% label claim": "% label claim", "% area": "% area",
              "% dissolved": "% dissolved"}
COND_WORD = {"25C/60%RH": "long-term", "30C/75%RH": "intermediate", "40C/75%RH": "accelerated"}
ATTR_SHOWN = {"Assay": "Assay", "Degradation product": "Degradation product", "Dissolution (15 min)": "Dissolution"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_READ = ("MATCH (f) WHERE (f:StabFact OR f:SpecFact) AND f.fact_id STARTS WITH $prefix RETURN properties(f) AS p")


# ---------- reading the saved files ----------

class _HtmlUnits(HTMLParser):
    """Text units of the saved HTML in order: ("h"|"p"|"row", text), plus every number span as (data-src, text)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units, self.spans = [], []
        self._body, self._kind, self._buf, self._cells, self._cell, self._span = False, None, None, None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "body":
            self._body = True
        elif not self._body:
            return
        elif tag in ("h1", "h2", "h3", "p"):
            self._kind, self._buf = ("h" if tag[0] == "h" else "p"), []
        elif tag == "tr":
            self._cells = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag == "span" and a.get("class") == "n":
            self._span = [a.get("data-src", ""), ""]

    def handle_data(self, data):
        if not self._body:
            return
        if self._span is not None:
            self._span[1] += data
        if self._cell is not None:
            self._cell.append(data)
        elif self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "span" and self._span is not None:
            self.spans.append(tuple(self._span))
            self._span = None
        elif tag in ("td", "th") and self._cell is not None:
            self._cells.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.units.append(("row", "\t".join(self._cells)))
            self._cells = None
        elif tag in ("h1", "h2", "h3", "p") and self._buf is not None:
            self.units.append((self._kind, "".join(self._buf)))
            self._buf = None


def read_html(path):
    """(units, spans) of a saved HTML file."""
    parser = _HtmlUnits()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    return parser.units, parser.spans


def _par_text(p):
    return "".join("\t" if el.tag == W + "tab" else (el.text or "") for el in p.iter() if el.tag in (W + "t", W + "tab"))


def read_docx(path):
    """Units of a saved .docx read straight from word/document.xml (no python-docx): ("h"|"p"|"row", text)."""
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    units = []
    for el in body:
        if el.tag == W + "p":
            style = el.find(W + "pPr/" + W + "pStyle")
            head = style is not None and style.get(W + "val", "").startswith(("Heading", "Title"))
            units.append(("h" if head else "p", _par_text(el)))
        elif el.tag == W + "tbl":
            for tr in el.findall(W + "tr"):
                units.append(("row", "\t".join("\n".join(_par_text(p) for p in tc.findall(W + "p")) for tc in tr.findall(W + "tc"))))
    return units


def read_placements(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------- the facts: graph (fresh) and saved 3.2 ----------

def read_graph(session):
    """{fact_id: properties} straight from Neo4j, read now."""
    return {rec["p"]["fact_id"]: dict(rec["p"]) for rec in session.run(_READ, prefix=PREFIX)}


def _graph_fact(rows, fid):
    """(value text, unit, meta) for a fact id, or None. A STAT id is the lowest/highest stored result of one condition x attribute."""
    if fid.startswith(PREFIX + "STAT|"):
        try:
            cond, attr, which = fid[len(PREFIX + "STAT|"):].split("|")
        except ValueError:
            return None
        grp = [r for r in rows.values() if r.get("family") == "stability" and r.get("kind") == "demo"
               and r["condition"] == cond and r["attribute"] == attr]
        if not grp or which not in ("min", "max"):
            return None
        pick = (min if which == "min" else max)(grp, key=lambda r: Decimal(r["value_text"]))
        return pick["value_text"], pick["unit"], {"kind": "demo", "stat": (cond, attr, which)}
    r = rows.get(fid)
    if r is None:
        return None
    return r["value_text"], r["unit"], {"kind": r["kind"], "attribute": r["attribute"], "condition": r["condition"],
                                        "test": r["test"], "limit_kind": r.get("limit_kind", "")}


def p5_limits(path=P5_PLACEMENTS):
    """{attribute: set of limit texts} from the real (w*) sections of the saved 3.2.P.5.6; the synthetic s* sections are ignored."""
    out = {}
    for r in read_placements(path):
        m = re.match(r"^3\.2\.P\.5\.6/w\d+_(.+)/justification$", r["section"])
        if m and r["id"] == "limit":
            out.setdefault(m.group(1), set()).add(r["text"])
    return out


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def _saved32(fid, meta, p5, p8_dir):
    """The value the saved 3.2 output states for this fact, as text; None if the 3.2 does not state it (or states two different ones)."""
    p8_dir = Path(p8_dir)
    if "stat" in meta:
        cond, attr, which = meta["stat"]
        f = p8_dir / f"demo_{_slug(cond)}_{_slug(attr)}.md"
        m = re.search(rf"ranged from ({NUM}) to ({NUM}) over", f.read_text(encoding="utf-8")) if f.exists() else None
        return m.group(1 if which == "min" else 2) if m else None
    if fid.startswith(PREFIX + "SPEC-LEK-"):
        found = p5.get(meta["attribute"], set())
        return next(iter(found)) if len(found) == 1 else None
    pub = p8_dir / "p83_public.md"
    text = pub.read_text(encoding="utf-8") if pub.exists() else ""
    deg = "°C"
    pats = {
        "expiry_period_proposed": (rf"shelf life is ({NUM}) months when stored at {NUM}{deg} to {NUM}{deg}", 1),
        "storage_low": (rf"shelf life is {NUM} months when stored at ({NUM}){deg} to {NUM}{deg}", 1),
        "storage_high": (rf"shelf life is {NUM} months when stored at {NUM}{deg} to ({NUM}){deg}", 1),
        "excursion_permitted_low": (rf"Excursions are permitted from ({NUM}){deg} to {NUM}{deg}", 1),
        "excursion_permitted_high": (rf"Excursions are permitted from {NUM}{deg} to ({NUM}){deg}", 1),
    }
    attr = meta["attribute"]
    if attr == "study_duration_demonstrated":
        pat = rf"demonstrated for ({NUM}) months at long-term conditions and ({NUM}) months at accelerated conditions"
        group = {"25C/60%RH": 1, "40C/75%RH": 2}.get(meta["condition"])
        m = re.search(pat, text)
        return m.group(group) if m and group else None
    if attr in pats:
        m = re.search(pats[attr][0], text)
        return m.group(1) if m else None
    return None


def _context(fid, meta, unit):
    """(regex, group name): the sentence (or table row) this fact must sit in, and which group is the number. None if unknown."""
    after = re.escape(UNIT_AFTER.get(unit, "?"))
    deg = "°C"
    if "stat" in meta:
        cond, attr, which = meta["stat"]
        if cond not in COND_WORD or attr not in ATTR_SHOWN:
            return None
        rx = (rf"^(?:{re.escape(LABEL)})?{re.escape(ATTR_SHOWN[attr])} under {COND_WORD[cond]} conditions ranged from "
              rf"(?P<min>{NUM}){after} to (?P<max>{NUM}){after}\.$")
        return re.compile(rx), which
    if fid.startswith(PREFIX + "SPEC-LEK-"):
        return re.compile(rf"^{re.escape(meta['test'])}\t{re.escape(meta['limit_kind'])} (?P<n>{NUM}){after}$"), "n"
    attr, cond = meta["attribute"], meta["condition"]
    rx = {
        "expiry_period_proposed": rf"The proposed shelf life is (?P<n>{NUM}) months when stored at",
        "storage_low": rf"when stored at (?P<n>{NUM}){deg} to {NUM}{deg}",
        "storage_high": rf"when stored at {NUM}{deg} to (?P<n>{NUM}){deg}",
        "excursion_permitted_low": rf"Excursions are permitted from (?P<n>{NUM}){deg} to {NUM}{deg}",
        "excursion_permitted_high": rf"Excursions are permitted from {NUM}{deg} to (?P<n>{NUM}){deg}",
    }.get(attr)
    if attr == "study_duration_demonstrated":
        rx = {"25C/60%RH": rf"demonstrated for (?P<n>{NUM}) months at long-term conditions",
              "40C/75%RH": rf"conditions and (?P<n>{NUM}) months at accelerated conditions"}.get(cond)
    return (re.compile(rx), "n") if rx else None


# ---------- checking one saved file ----------

def check_units(units, placements, rows, p5, p8_dir, spans=None, fmt=""):
    """Rows for every number and every loose digit of one saved file. Each row starts as FAIL."""
    found, loose = [], []
    for i, (kind, text) in enumerate(units):
        nums = find_numbers(text)
        found += [(i, off, tx) for off, tx in nums]
        loose += [(i, d) for d in uncovered_digits(text, [(o, o + len(t)) for o, t in nums])]
    # Pair each number with a placement by its value (first unused one at or after the last pair, so equal values keep their
    # order). A number no placement carries is "unplaced" and takes nothing, so it cannot shift the pairing of the others.
    pairs, used, j = [], set(), 0
    for _, off, tx in found:
        idx = next((q for q in list(range(j, len(placements))) + list(range(0, j))
                    if q not in used and placements[q]["text"] == tx), None)
        if idx is not None:
            used.add(idx)
            j = idx + 1
        pairs.append(idx)
    span_left = {}
    for s in (spans or []):
        span_left[s] = span_left.get(s, 0) + 1
    out = []
    for k, (i, off, tx) in enumerate(found):
        kind, text = units[i]
        row = {"format": fmt, "number": tx, "fact_id": "", "v23": tx, "v32_graph": "", "v32_saved": "", "unit": "",
               "verdict": "FAIL", "reason": ""}
        why = []
        pl = placements[pairs[k]] if pairs[k] is not None else None
        if pl is None:
            row["fact_id"] = "unplaced:" + tx
            why.append("number has no placement")
        else:
            fid = row["fact_id"] = pl["id"]
            if pl["offset"] != off:
                why.append("placement offset differs")
            if spans is not None:
                if span_left.get((fid, tx), 0) > 0:
                    span_left[(fid, tx)] -= 1
                else:
                    why.append("html span differs from the placement")
            g = _graph_fact(rows, fid)
            if g is None:
                why.append("fact id not in the graph")
            else:
                value, unit, meta = g
                row["v32_graph"], row["unit"] = value, unit
                saved = _saved32(fid, meta, p5, p8_dir)
                row["v32_saved"] = saved or ""
                if tx != value:
                    why.append("2.3 value differs from the graph value")
                if saved is None:
                    why.append("the saved 3.2 does not state this fact")
                elif tx != saved:
                    why.append("2.3 value differs from the saved 3.2 value")
                want = UNIT_AFTER.get(unit)
                if want is None:
                    why.append("unit not known")
                elif not text[off + len(tx):].startswith(want):
                    why.append(f"unit after the number is not {want.strip()!r}")
                ctx = _context(fid, meta, unit)
                m = ctx[0].search(text) if ctx else None
                if m is None:
                    why.append("sentence is not about this fact")
                elif m.start(ctx[1]) != off:
                    why.append("number is not at the place of this fact in the sentence")
                para = text if kind == "p" else next((t for kd, t in reversed(units[:i]) if kd == "p"), "")
                if meta["kind"] == "demo" and not para.startswith(LABEL):
                    why.append("DEMO fact without the demo label")
                if meta["kind"] != "demo" and para.startswith(LABEL):
                    why.append("public fact in a demo-labelled sentence")
        row["reason"] = "; ".join(why)
        row["verdict"] = "FAIL" if why else "MATCH"
        out.append(row)
    for k in range(len(placements)):
        if k in used:
            continue
        out.append({"format": fmt, "number": "", "fact_id": placements[k]["id"], "v23": "", "v32_graph": "", "v32_saved": "", "unit": "",
                    "verdict": "FAIL", "reason": "placement without a number in the file"})
    for i, d in loose:
        out.append({"format": fmt, "number": "", "fact_id": "", "v23": "", "v32_graph": "", "v32_saved": "", "unit": "",
                    "verdict": "FAIL", "reason": d})
    return out


def run(run_dir, graph_rows, p5_path=P5_PLACEMENTS, p8_dir=P8_SECTIONS):
    """Check M23.html and M23.docx in a run folder. Returns {"rows", "passed", "counts", "problems"}; passed only if every row is MATCH."""
    d = Path(run_dir)
    placements, p5 = read_placements(d / "placements.jsonl"), p5_limits(p5_path)
    html_units, spans = read_html(d / "M23.html")
    docx_units = read_docx(d / "M23.docx")
    rows = (check_units(html_units, placements, graph_rows, p5, p8_dir, spans, "html")
            + check_units(docx_units, placements, graph_rows, p5, p8_dir, None, "docx"))
    problems = []
    nums = lambda units: [t for _, u in units for _, t in find_numbers(u)]   # noqa: E731
    if nums(html_units) != nums(docx_units):
        problems.append("the HTML and the Word file do not hold the same numbers")
    if not rows:
        problems.append("no numbers found")
    counts = {}
    for fmt in ("html", "docx"):
        mine = [r for r in rows if r["format"] == fmt]
        counts[fmt] = {"checked": sum(1 for r in mine if r["number"]), "matched": sum(1 for r in mine if r["verdict"] == "MATCH"),
                       "failed": sum(1 for r in mine if r["verdict"] == "FAIL" and not r["reason"].startswith("uncovered")),
                       "uncovered": sum(1 for r in mine if r["reason"].startswith("uncovered"))}
    passed = bool(rows) and all(r["verdict"] == "MATCH" for r in rows) and not problems
    return {"rows": rows, "passed": passed, "counts": counts, "problems": problems}


COLUMNS = ["format", "number", "fact_id", "v23", "v32_graph", "v32_saved", "unit", "verdict", "reason"]


def write_outputs(result, out_dir):
    """crosscheck.csv and summary.md in the run folder; an existing file is refused (never overwritten)."""
    d = Path(out_dir)
    for name in ("crosscheck.csv", "summary.md"):
        if (d / name).exists():
            raise FileExistsError(f"{d / name} already exists")
    with open(d / "crosscheck.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(result["rows"])
    lines = ["# 2.3 vs 3.2 cross-check", "", "RESULT: " + ("PASS" if result["passed"] else "FAIL"), ""]
    for fmt, c in result["counts"].items():
        lines.append(f"- {fmt}: numbers checked {c['checked']}, matched {c['matched']}, failed {c['failed']}, uncovered digits {c['uncovered']}")
    lines += [f"- problem: {p}" for p in result["problems"]]
    (d / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--snapshot", help="graph rows saved earlier (a json file); without it Neo4j is read now and the rows are saved")
    args = ap.parse_args(argv)
    d = Path(args.run_dir)
    if args.snapshot:
        rows = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    else:
        from ectd_engine.graph import facts_graph
        driver = facts_graph.connect()
        try:
            with driver.session() as s:
                rows = read_graph(s)
        finally:
            driver.close()
        (d / "graph_snapshot.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    result = run(d, rows)
    write_outputs(result, d)
    print((d / "summary.md").read_text(encoding="utf-8"))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
