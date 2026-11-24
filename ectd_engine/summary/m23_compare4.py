"""Independent T-074 check of a saved 2.3 HTML against the task and the graph rows it was rendered from; it imports no builder, gate, rule, shape, plan or loop code.

    python -m ectd_engine.summary.m23_compare4 <M23.html or render folder> <task json> <graph snapshot json>

Everything is worked out here with its own code from the rows: the limit of each group (ONE spec fact named in the task, or the group's own single limit when
the task names none), the outside-limit count, significant change, "demonstrated" and extrapolation rules, and the human review route. It then checks the saved file:
 * the facts in the file are exactly the facts the task asks for (in review no shelf, storage or shelf-life number; a group with no spec fact has one sentence);
 * the sections come in the expected order (specification, review marker only when needed, public, results), every number equals its fact and unit;
 * every claim sentence agrees with the count in both directions and carries the link to its outside-limit-count fact; no claim sentence for an unlinked group;
 * "demonstrated" only for clean data and linked to all long-term / intermediate counts; a shelf life beyond the data only when nothing blocks it;
 * R7: every stored row of a linked group carries the limit of its spec fact;
 * review route: the marker "HUMAN REVIEW REQUIRED:" is there exactly when a long-term / intermediate result is outside its limit, is linked to those counts,
   and no shelf-life sentence is anywhere in the file.
"""
import json
import re
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

UNIT = {"months": " months", "C": "°C", "%": "%", "% label claim": "% label claim", "% area": "% area", "% dissolved": "% dissolved", "min": " min"}
DEMO = "In illustrative demonstration data, "
LONG, INTER, ACCEL = "25C/60%RH", "30C/75%RH", "40C/75%RH"
MARK = "HUMAN REVIEW REQUIRED:"
NONE_SAYS = r"no results outside the limit|no .+ result under .+ was outside the limit|within the specification limits"


class _Doc(HTMLParser):
    """Units of the body in order: dicts {"kind": "p"|"row", "section", "text", "spans": [(data-src, offset, number)], "claims": [(start, end, [ids])]}."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units, self._body, self._buf, self._row, self._cell, self._span, self._claim, self._table = [], False, None, None, None, None, None, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "body":
            self._body = True
        elif tag == "table":
            self._table = a.get("data-section", "")
        elif tag == "p" and self._body:
            self._buf = {"kind": "p", "section": a.get("data-section", ""), "text": "", "spans": [], "claims": []}
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._th = {"text": "", "spans": []}, tag == "th"
        elif tag == "span" and a.get("class") == "n":
            self._span = [a.get("data-src", ""), ""]
        elif tag == "span" and a.get("class") == "claim" and self._buf is not None:
            self._claim = (len(self._buf["text"]), [i for i in (a.get("data-src") or "").split(";") if i])

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
        elif tag == "span" and self._claim is not None and self._buf is not None:
            self._buf["claims"].append((self._claim[0], len(self._buf["text"]), self._claim[1]))
            self._claim = None
        elif tag == "p" and self._buf is not None:
            self.units.append(self._buf)
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
                self.units.append({"kind": "row", "section": self._table, "text": "\t".join(text), "spans": spans, "claims": []})
            self._row = None


def _lim(text):
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


def _limit(rows, link, cond, attr):
    """The limit of a group: its spec fact's, else the single readable limit of its own rows; None = unknown."""
    if link:
        s = rows.get(link)
        return _lim(f"{s['limit_kind']} {s['value_text']}") if s else None
    got = {_lim(r.get("limit_text", "")) for r in _group(rows, cond, attr)}
    return next(iter(got)) if len(got) == 1 and None not in got else None


def _outside(rows, link, cond, attr):
    """Count of results outside the limit; None when the limit is unknown (never 0 by default)."""
    lim = _limit(rows, link, cond, attr)
    if lim is None:
        return None
    return sum(1 for r in _group(rows, cond, attr)
               if (lim[0] is not None and Decimal(r["value_text"]) < lim[0]) or (lim[1] is not None and Decimal(r["value_text"]) > lim[1]))


def _significant(rows, links, attr):
    grp = _group(rows, ACCEL, attr)
    if not grp:
        return None
    if attr == "Assay":
        zero = [r for r in grp if r["month"] != "" and Decimal(r["month"]) == 0]
        if not zero:
            return True
        v0 = Decimal(zero[0]["value_text"])
        return any(abs(Decimal(r["value_text"]) - v0) * 20 >= v0 for r in grp)            # 5% or more: |v - v0| >= v0 / 20
    n = _outside(rows, links.get((ACCEL, attr)), ACCEL, attr)
    return True if n is None else n > 0


def _own_fact(rows, fid):
    if fid.startswith("M23-STAT|"):
        cond, attr, which = fid[len("M23-STAT|"):].split("|")
        if which == "timepoint":
            return re.search(r"\((\d+) min\)", attr).group(1), "min"
        pick = (min if which == "min" else max)(_group(rows, cond, attr), key=lambda r: Decimal(r["value_text"]))
        return pick["value_text"], pick["unit"]
    return rows[fid]["value_text"], rows[fid]["unit"]


def _derived(rows, links, fid):
    cond, attr, which = fid[len("M23-STAT|"):].split("|")
    if which == "outside_limit_count":
        n = _outside(rows, links.get((cond, attr)), cond, attr)
        if n is None:
            raise ValueError("unknown limit")
        return str(n)
    if which == "significant_change" and cond == ACCEL:
        s = _significant(rows, links, attr)
        if s is None:
            raise KeyError(fid)
        return "1" if s else "0"
    raise KeyError(fid)


def compare(html_path, task, rows):
    """{"ok", "paragraphs", "numbers", "problems", "review", "pattern"}: every check of the module text; pattern = what the chosen sentences say per group."""
    html = Path(html_path).read_text(encoding="utf-8")
    doc = _Doc()
    doc.feed(html)
    units, problems = doc.units, []
    links = {(g["condition"], g["attribute"]): g.get("spec_fact") for g in task["results"]}
    pubs = {task["public"][k]["fact_id"]: k for k in task["public"]}
    groups = sorted({(r["condition"], r["attribute"]) for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo"})
    li = [(c, a) for c, a in groups if c != ACCEL]
    # ---- own rules ----
    failing = []
    for c, a in li:
        n = _outside(rows, links.get((c, a)), c, a)
        if n:
            failing.append((c, a))
    review = bool(failing)
    unknown_li = [(c, a) for c, a in li if _outside(rows, links.get((c, a)), c, a) is None]
    clean = any(c == LONG for c, _ in li) and not failing and not unknown_li
    attrs = sorted({a for _, a in groups})
    sig = {a: _significant(rows, links, a) for a in attrs}
    ok_extrap = clean and all(v is False for v in sig.values())
    li_ids = {f"M23-STAT|{c}|{a}|outside_limit_count" for c, a in li}
    sig_ids = {f"M23-STAT|{ACCEL}|{a}|significant_change" for a in attrs if sig[a] is not None}
    # ---- R7 ----
    for (cond, attr), link in sorted(links.items()):
        if link:
            spec = rows.get(link)
            if spec is None:
                problems.append(f"R7: {cond} | {attr}: the spec fact {link} is not in the graph")
            elif any(_lim(r.get("limit_text", "")) != _lim(f"{spec['limit_kind']} {spec['value_text']}") for r in _group(rows, cond, attr)):
                problems.append(f"R7: {cond} | {attr}: a stored limit is not the limit of {link}")
            if link not in {s["fact_id"] for s in task["spec"]}:
                problems.append(f"R7: {link} is not in the specification table")
        elif task["synthetic"]:
            problems.append(f"R7: {cond} | {attr} has no spec fact")
    # ---- the facts and the sections ----
    want = [s["fact_id"] for s in task["spec"]] + [task["public"][k]["fact_id"] for k in ("ex_low", "ex_high", "long", "accel")]
    if not review:
        want += [task["public"][k]["fact_id"] for k in ("shelf", "st_low", "st_high")]
    for g in task["results"]:
        tp = [g["stat"]["timepoint"]] * (2 if links.get((g["condition"], g["attribute"])) else 1) if "timepoint" in g["stat"] else []
        want += [g["stat"]["min"], g["stat"]["max"]] + tp
    found = [s for u in units for s, _, _ in u["spans"]]
    if sorted(found) != sorted(want):
        problems.append("the facts in the file are not the facts the task asks for (a missing, extra or repeated number; in review no shelf life or storage number)")
    plan = ["spec_intro"] + ["spec_table"] * len(task["spec"]) + (["review"] if review else []) + ["public"]
    for g in task["results"]:
        plan += ["results"] * (2 if links.get((g["condition"], g["attribute"])) else 1)
    if [u["section"] for u in units] != plan:
        problems.append(f"the sections are {[u['section'] for u in units]} but the data need {plan}")
        return {"ok": False, "paragraphs": len(units), "numbers": len(found), "problems": problems, "review": review, "pattern": {}}
    for u in units:
        for src, off, num in u["spans"]:
            try:
                value, unit = _own_fact(rows, src)
            except (KeyError, AttributeError, ValueError):
                problems.append(f"{src} is not a fact of the graph")
                continue
            if num != value:
                problems.append(f"{src}: the file says {num}, the graph says {value}")
            if u["text"][off + len(num):off + len(num) + len(UNIT[unit])] != UNIT[unit]:
                problems.append(f"{src}: the unit after {num} is not {UNIT[unit].strip()!r}")
        covered = {i for _, off, num in u["spans"] for i in range(off, off + len(num))}
        problems += [f"digit outside any number span: ...{u['text'][max(0, i - 10):i + 10]}..." for i, ch in enumerate(u["text"]) if ch.isdigit() and i not in covered]
        for a, b, ids in u["claims"]:
            for i in ids:
                try:
                    _derived(rows, links, i)
                except (KeyError, ValueError, IndexError):
                    problems.append(f"a claim links {i}, which is not a derived fact of the graph")
    # ---- specification and review ----
    if not units[0]["text"].startswith(DEMO):
        problems.append("the specification sentence lacks the demo label")
    marks = [u for u in units if u["section"] == "review"]
    for u in marks:
        ids = {i for _, _, x in u["claims"] for i in x}
        if not u["text"].startswith(MARK) or "HUMAN REVIEW REQUIRED: " not in u["text"]:
            problems.append("the review section does not start with 'HUMAN REVIEW REQUIRED:'")
        if len(u["claims"]) != 1 or (u["claims"][0][0], u["claims"][0][1]) != (0, len(u["text"])):
            problems.append("the review marker is not one claim over the whole text")
        if ids != {f"M23-STAT|{c}|{a}|outside_limit_count" for c, a in failing}:
            problems.append("the review marker is not linked to exactly the outside-limit counts that caused it")
        if u["spans"]:
            problems.append("the review marker holds a number")
    if any(MARK in u["text"] for u in units if u["section"] != "review"):
        problems.append("a review marker sits outside the review section")
    # ---- the public paragraph ----
    pub = next(u for u in units if u["section"] == "public")
    order = [pubs.get(s) for s, _, _ in pub["spans"]]
    if pub["text"].startswith(DEMO):
        problems.append("the public paragraph carries the demo label")
    if review:
        if order != ["ex_low", "ex_high", "long", "accel"]:
            problems.append(f"in review the public paragraph must hold only excursion and study numbers: {order}")
        if "shelf life" in pub["text"] or "stored at" in pub["text"]:
            problems.append("review route: a shelf-life or storage sentence was written")
    elif order[:3] not in (["shelf", "st_low", "st_high"], ["st_low", "st_high", "shelf"]) or order[3:] != ["ex_low", "ex_high", "long", "accel"]:
        problems.append(f"the numbers of the public paragraph are in the wrong places: {order}")
    for u in units:
        if u["section"] != "public" and re.search(r"proposed shelf life", u["text"]):
            problems.append("a shelf-life sentence sits outside the public paragraph")
    shelf, long_ = (Decimal(rows[task["public"][k]["fact_id"]]["value_text"]) for k in ("shelf", "long"))
    pos = 0
    for sent in re.split(r"(?<=\.)\s+", pub["text"]):
        s = pub["text"].index(sent, pos)
        e = pos = s + len(sent)
        link = [ids for a, b, ids in pub["claims"] if a <= s and e <= b]
        if re.search(r"\bdemonstrated\b", sent):
            if not clean:
                problems.append("a sentence says 'demonstrated' but a long-term / intermediate result is outside its limit, its limit is unknown, or no long-term result exists")
            if not link or set(link[0]) != li_ids:
                problems.append("a 'demonstrated' sentence does not link the outside-limit counts of all long-term and intermediate groups")
        if "proposed shelf life" in sent and shelf > long_:
            if not ok_extrap:
                problems.append("the shelf life goes beyond the long-term data but the graph does not allow that extrapolation")
            if not link or set(link[0]) != li_ids | sig_ids:
                problems.append("a shelf life beyond the data does not link the outside-limit counts and the significant-change facts")
    # ---- the results ----
    rs = [u for u in units if u["section"] == "results"]
    pattern, k = {}, 0
    for g in task["results"]:
        key = (g["condition"], g["attribute"])
        tp = [g["stat"]["timepoint"]] if "timepoint" in g["stat"] else []
        a = rs[k]
        k += 1
        if [s for s, _, _ in a["spans"]] != tp + [g["stat"]["min"], g["stat"]["max"]]:
            problems.append(f"{key[0]} | {key[1]}: the range sentence holds its numbers in the wrong places")
        if not a["text"].startswith(DEMO):
            problems.append(f"{key[0]} | {key[1]}: a demo sentence lacks the demo label")
        if a["claims"]:
            problems.append(f"{key[0]} | {key[1]}: the range sentence carries a claim link")
        if not links.get(key):
            pattern[key] = "range_only"
            continue
        b = rs[k]
        k += 1
        if [s for s, _, _ in b["spans"]] != tp:
            problems.append(f"{key[0]} | {key[1]}: the claim sentence holds numbers it should not")
        if not b["text"].startswith(DEMO):
            problems.append(f"{key[0]} | {key[1]}: a demo sentence lacks the demo label")
        want_id = f"M23-STAT|{key[0]}|{key[1]}|outside_limit_count"
        if len(b["claims"]) != 1 or b["claims"][0][2] != [want_id] or (b["claims"][0][0], b["claims"][0][1]) != (0, len(b["text"])):
            problems.append(f"{key[0]} | {key[1]}: the claim sentence does not carry the link to {want_id}")
        count = _outside(rows, links[key], *key)
        says_none = bool(re.search(NONE_SAYS, b["text"]))
        says_some = "had results outside the limit" in b["text"]
        pattern[key] = "none" if says_none else "some" if says_some else "?"
        if says_none == says_some:
            problems.append(f"{key[0]} | {key[1]}: the claim sentence says neither or both of 'none outside' and 'some outside'")
        elif count is None or (says_none and count != 0) or (says_some and count == 0):
            problems.append(f"{key[0]} | {key[1]}: the claim disagrees with the graph (results outside the limit: {count})")
    if bool(task["synthetic"]) != ("synthetic test case" in html):
        problems.append("the synthetic marking of the file and of the task do not agree")
    return {"ok": not problems, "paragraphs": len(units), "numbers": len(found), "problems": problems, "review": review, "pattern": {f"{c}|{a}": v for (c, a), v in pattern.items()}}


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 3:
        print("usage: m23_compare4 <M23.html or render folder> <task json> <graph snapshot json>", file=sys.stderr)
        return 2
    p = Path(args[0])
    res = compare(p / "M23.html" if p.is_dir() else p, json.loads(Path(args[1]).read_text(encoding="utf-8")),
                  json.loads(Path(args[2]).read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
