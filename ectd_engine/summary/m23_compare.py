"""Independent check that a saved 2.3 HTML says exactly what the task facts say: it reads only the saved file and the task JSON, nothing else.

    python -m ectd_engine.summary.m23_compare <run folder with render_<k>/M23.html and a task json>   (see compare())

It rebuilds the expected paragraphs from the task's numbers with its own small text table, then compares paragraph by paragraph.
It imports no builder, gate, shape or plan code on purpose, so a mistake in those cannot hide here.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

UNIT = {"months": " months", "C": "°C", "%": "%", "% label claim": "% label claim", "% area": "% area", "% dissolved": "% dissolved"}
DEMO = "In illustrative demonstration data, "


class _Paras(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units, self._buf, self._row, self._cell, self._in_body = [], None, None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self._in_body = True
        elif tag == "p" and self._in_body:
            self._buf = []
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._is_th = tag == "th"

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self._buf is not None:
            self.units.append(("p", "".join(self._buf)))
            self._buf = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(("".join(self._cell), self._is_th))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if not any(th for _, th in self._row):
                self.units.append(("row", "\t".join(c for c, _ in self._row)))
            self._row = None


def _with_unit(slot):
    return slot["value"] + UNIT[slot["unit"]]


def expected(task):
    """[(kind, text)] the saved HTML must hold, in order, written only from the task's numbers."""
    out = [("p", DEMO + "the drug product specification lists these tests and acceptance criteria.")]
    out += [("row", f"{s['test']}\t{s['limit_kind']} {_with_unit(s)}") for s in task["spec"]]
    p = task["public"]
    out.append(("p", f"The proposed shelf life is {_with_unit(p['shelf'])} when stored at {_with_unit(p['st_low'])} to {_with_unit(p['st_high'])}. "
                     f"Excursions are permitted from {_with_unit(p['ex_low'])} to {_with_unit(p['ex_high'])}. "
                     f"Stability was demonstrated for {_with_unit(p['long'])} at long-term conditions and {_with_unit(p['accel'])} at accelerated conditions."))
    for g in task["results"]:
        out.append(("p", f"{DEMO}{g['attr_shown']} under {g['cond_word']} conditions ranged from {_with_unit(g['low'])} to {_with_unit(g['high'])}."))
    return out


def numbers(text):
    return re.findall(r"\d+(?:\.\d+)?", text)


def compare(html_path, task):
    """{"ok", "paragraphs", "numbers", "problems"}: every paragraph and every number of the saved HTML against the task facts."""
    parser = _Paras()
    parser.feed(Path(html_path).read_text(encoding="utf-8"))
    got, want = parser.units, expected(task)
    problems = []
    if len(got) != len(want):
        problems.append(f"the file has {len(got)} paragraphs/rows, the task needs {len(want)}")
    for i, (g, w) in enumerate(zip(got, want), 1):
        if g != w:
            problems.append(f"unit {i} differs: file {g[1]!r} / task {w[1]!r}")
    html = Path(html_path).read_text(encoding="utf-8")
    if bool(task["synthetic"]) != ("synthetic test case" in html):
        problems.append("the synthetic marking of the file and of the task do not agree")
    n_got, n_want = [n for _, t in got for n in numbers(t)], [n for _, t in want for n in numbers(t)]
    if n_got != n_want:
        problems.append("the numbers differ in value or order")
    return {"ok": not problems, "paragraphs": len(got), "numbers": len(n_got), "problems": problems}


def main(argv=None):
    """compare.py <render folder> <task json>: prints the result; exit 0 = every paragraph equal, 1 = something differs."""
    args = (argv if argv is not None else sys.argv[1:])
    if len(args) != 2:
        print("usage: m23_compare <render folder or M23.html> <task json>", file=sys.stderr)
        return 2
    p = Path(args[0])
    res = compare(p / "M23.html" if p.is_dir() else p, json.loads(Path(args[1]).read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
