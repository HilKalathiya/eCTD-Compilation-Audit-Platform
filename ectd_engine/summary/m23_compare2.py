"""Independent T-072 check of a saved 2.3 HTML against the task and the graph rows it was rendered from; it imports no builder, gate, shape, plan or loop code.

    python -m ectd_engine.summary.m23_compare2 <M23.html or render folder> <task json> <graph snapshot json>

It works every expected number out of the graph rows with its own code (lowest, highest, outside-limit count, time point), then checks: every number
equals its fact and is followed by its unit, every digit sits inside a number span, the numbers appear in the order of their place in the sentence,
each fact appears the right number of times, the demo label is where it belongs, and every claim about results outside the limit agrees with the count.
"""
import json
import re
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

UNIT = {"months": " months", "C": "°C", "%": "%", "% label claim": "% label claim", "% area": "% area", "% dissolved": "% dissolved", "min": " min"}
DEMO = "In illustrative demonstration data, "


class _Doc(HTMLParser):
    """Paragraphs ('p', text, [(data-src, offset, number text)]) and table rows ('row', text, spans) of the body; header rows are skipped."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units, self.title, self._body = [], "", False
        self._buf = self._row = self._cell = self._span = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "body":
            self._body = True
        elif tag == "p" and self._body:
            self._buf = {"text": "", "spans": []}
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._th = {"text": "", "spans": []}, tag == "th"
        elif tag == "span" and a.get("class") == "n":
            self._span = [a.get("data-src", ""), ""]

    def handle_data(self, data):
        tgt = self._cell if self._cell is not None else self._buf
        if tgt is None:
            return
        if self._span is not None:
            self._span[1] += data
        tgt["text"] += data

    def handle_endtag(self, tag):
        tgt = self._cell if self._cell is not None else self._buf
        if tag == "span" and self._span is not None and tgt is not None:
            src, num = self._span
            tgt["spans"].append((src, len(tgt["text"]) - len(num), num))
            self._span = None
        elif tag == "p" and self._buf is not None:
            self.units.append(("p", self._buf["text"], self._buf["spans"]))
            self._buf = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append((self._cell, self._th))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if not any(th for _, th in self._row):
                text, spans, base = [], [], 0
                for c, _ in self._row:
                    spans += [(s, o + base, n) for s, o, n in c["spans"]]
                    text.append(c["text"])
                    base += len(c["text"]) + 1
                self.units.append(("row", "\t".join(text), spans))
            self._row = None


def _own_limit(text):
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$", text or "")
    if m:
        return Decimal(m.group(1)), Decimal(m.group(2))
    m = re.match(r"^\s*NMT\s+(\d+(?:\.\d+)?)\s*$", text or "")
    if m:
        return None, Decimal(m.group(1))
    m = re.match(r"^\s*NLT\s+(\d+(?:\.\d+)?)\s*$", text or "")
    return (Decimal(m.group(1)), None) if m else None


def _group(rows, cond, attr):
    return [r for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo" and r["condition"] == cond and r["attribute"] == attr]


def own_fact(rows, fid):
    """(value text, unit) of a stored or derived fact, worked out here; raises KeyError if the graph does not hold it."""
    if fid.startswith("M23-STAT|"):
        cond, attr, which = fid[len("M23-STAT|"):].split("|")
        grp = _group(rows, cond, attr)
        if which == "timepoint":
            return re.search(r"\((\d+) min\)", attr).group(1), "min"
        pick = (min if which == "min" else max)(grp, key=lambda r: Decimal(r["value_text"]))
        return pick["value_text"], pick["unit"]
    return rows[fid]["value_text"], rows[fid]["unit"]


def own_outside(rows, cond, attr):
    n = 0
    for r in _group(rows, cond, attr):
        lim = _own_limit(r.get("limit_text", ""))
        v = Decimal(r["value_text"])
        if lim and ((lim[0] is not None and v < lim[0]) or (lim[1] is not None and v > lim[1])):
            n += 1
    return n


def compare(html_path, task, rows):
    """{"ok", "paragraphs", "numbers", "problems"}."""
    html = Path(html_path).read_text(encoding="utf-8")
    doc = _Doc()
    doc.feed(html)
    units, problems = doc.units, []
    found = [s for _, _, spans in units for s, _, _ in spans]
    # expected ids, each as many times as the document should hold it
    want = [s["fact_id"] for s in task["spec"]] + [task["public"][k]["fact_id"] for k in ("shelf", "st_low", "st_high", "ex_low", "ex_high", "long", "accel")]
    for g in task["results"]:
        want += [g["stat"]["min"], g["stat"]["max"]] + ([g["stat"]["timepoint"]] * 2 if "timepoint" in g["stat"] else [])
    if sorted(found) != sorted(want):
        problems.append("the facts in the file are not the facts the task asks for (a missing, extra or repeated number)")
    n_par = 1 + len(task["spec"]) + 1 + 2 * len(task["results"])
    if len(units) != n_par:
        problems.append(f"the file has {len(units)} paragraphs/rows, the task needs {n_par}")
    for kind, text, spans in units:
        for src, off, num in spans:
            try:
                value, unit = own_fact(rows, src)
            except (KeyError, AttributeError, ValueError):
                problems.append(f"{src} is not a fact of the graph")
                continue
            if num != value:
                problems.append(f"{src}: the file says {num}, the graph says {value}")
            if text[off + len(num):off + len(num) + len(UNIT[unit])] != UNIT[unit]:
                problems.append(f"{src}: the unit after {num} is not {UNIT[unit].strip()!r}")
        covered = {i for _, off, num in spans for i in range(off, off + len(num))}
        problems += [f"digit outside any number span: ...{text[max(0, i - 10):i + 10]}..." for i, ch in enumerate(text) if ch.isdigit() and i not in covered]
    pubs = {task["public"][k]["fact_id"]: k for k in task["public"]}
    ps = [u for u in units if u[0] == "p"]
    if ps:
        if not ps[0][1].startswith(DEMO):
            problems.append("the specification sentence lacks the demo label")
    for u in ps[1:2]:                                                     # the public paragraph
        order = [pubs.get(s) for s, _, _ in u[2]]
        if u[1].startswith(DEMO):
            problems.append("the public paragraph carries the demo label")
        if order[:3] not in (["shelf", "st_low", "st_high"], ["st_low", "st_high", "shelf"]) or order[3:] != ["ex_low", "ex_high", "long", "accel"]:
            problems.append(f"the numbers of the public paragraph are in the wrong places: {order}")
    for g, (a, b) in zip(task["results"], [(ps[2 + 2 * i], ps[3 + 2 * i]) for i in range(len(task["results"]))] if len(ps) == 2 + 2 * len(task["results"]) else []):
        tp = [g["stat"]["timepoint"]] if "timepoint" in g["stat"] else []
        if [s for s, _, _ in a[2]] != tp + [g["stat"]["min"], g["stat"]["max"]]:
            problems.append(f"{g['condition']} | {g['attribute']}: the range sentence holds its numbers in the wrong places")
        if [s for s, _, _ in b[2]] != tp:
            problems.append(f"{g['condition']} | {g['attribute']}: the claim sentence holds numbers it should not")
        for p in (a, b):
            if not p[1].startswith(DEMO):
                problems.append(f"{g['condition']} | {g['attribute']}: a demo sentence lacks the demo label")
        count = own_outside(rows, g["condition"], g["attribute"])
        says_none = bool(re.search(r"no results outside the limit|no .+ result under .+ was outside the limit|within the specification limits", b[1]))
        says_some = "had results outside the limit" in b[1]
        if says_none == says_some:
            problems.append(f"{g['condition']} | {g['attribute']}: the claim sentence says neither or both of 'none outside' and 'some outside'")
        elif says_none and count != 0 or says_some and count == 0:
            problems.append(f"{g['condition']} | {g['attribute']}: the claim disagrees with the graph (results outside the limit: {count})")
    if bool(task["synthetic"]) != ("synthetic test case" in html):
        problems.append("the synthetic marking of the file and of the task do not agree")
    return {"ok": not problems, "paragraphs": len(units), "numbers": len(found), "problems": problems}


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 3:
        print("usage: m23_compare2 <M23.html or render folder> <task json> <graph snapshot json>", file=sys.stderr)
        return 2
    p = Path(args[0])
    res = compare(p / "M23.html" if p.is_dir() else p, json.loads(Path(args[1]).read_text(encoding="utf-8")),
                  json.loads(Path(args[2]).read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
