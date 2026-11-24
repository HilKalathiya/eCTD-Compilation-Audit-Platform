"""Independent T-073 check of a saved 2.3 HTML: everything of m23_compare2 plus the claim rules, worked out here with its OWN code (it imports only m23_compare2, which imports nothing).

    python -m ectd_engine.summary.m23_compare3 <M23.html or render folder> <task json> <graph snapshot json>

Extra checks (all recomputed from the graph rows, never from the loop's or the rules module's functions):
 * R7: each stability group's stored limit equals the limit of the specification fact the table shows (Dissolution <-> dissolution_av);
 * every <span class="claim" data-src="ids"> holds ids this file can work out, and a result claim carries exactly the outside-limit-count id of its group;
 * a sentence with "demonstrated" sits in a claim span that links ALL long-term / intermediate outside-limit counts, there is a long-term group and every count is 0;
 * a shelf life beyond the long-term data sits in a claim span linking those counts and the significant-change fact of every attribute, and nothing blocks it
   (no outside result at long-term / intermediate, no significant change at accelerated, an accelerated group for every attribute).
Significant change is read from ICH Q1A(R2) p15 (chunk Q1A_R2:p15-c1/c2): Assay 5% or more from the initial value; degradation product / dissolution outside the limit.
"""
import json
import re
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from ectd_engine.summary import m23_compare2 as C2

SPEC_OF = {"Dissolution (15 min)": "dissolution_av"}
LONG, INTER, ACCEL = "25C/60%RH", "30C/75%RH", "40C/75%RH"


class _Paras(HTMLParser):
    """Paragraph texts of the body with their claim spans: [(text, [(start, end, [ids])])]."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras, self._text, self._claims, self._stack, self._body = [], None, None, [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "body":
            self._body = True
        elif tag == "p" and self._body:
            self._text, self._claims, self._stack = "", [], []
        elif tag == "span" and self._text is not None:
            self._stack.append((a.get("class"), len(self._text), [i for i in (a.get("data-src") or "").split(";") if i]))   # ids may hold spaces, so they are joined with ";"

    def handle_data(self, data):
        if self._text is not None:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "span" and self._stack:
            cls, start, ids = self._stack.pop()
            if cls == "claim":
                self._claims.append((start, len(self._text), ids))
        elif tag == "p" and self._text is not None:
            self.paras.append((self._text, self._claims))
            self._text = None


def _group(rows, cond, attr):
    return [r for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo" and r["condition"] == cond and r["attribute"] == attr]


def _limit_of(rows, attr, row):
    if attr in SPEC_OF:
        spec = rows.get("M23-SPEC-LEK-" + SPEC_OF[attr])
        return None if spec is None else f"{spec['limit_kind']} {spec['value_text']}"
    return row.get("limit_text", "")


def _outside(rows, cond, attr):
    n = 0
    for r in _group(rows, cond, attr):
        lim = C2._own_limit(_limit_of(rows, attr, r))
        v = Decimal(r["value_text"])
        n += bool(lim and ((lim[0] is not None and v < lim[0]) or (lim[1] is not None and v > lim[1])))
    return n


def _significant(rows, attr):
    grp = _group(rows, ACCEL, attr)
    if not grp:
        return None
    if attr == "Assay":
        zero = [r for r in grp if r["month"] != "" and Decimal(r["month"]) == 0]
        if not zero:
            return True
        v0 = Decimal(zero[0]["value_text"])
        return any(abs(Decimal(r["value_text"]) - v0) * 20 >= v0 for r in grp)            # 5% or more: |v - v0| >= v0 / 20
    return _outside(rows, ACCEL, attr) > 0


def _derived(rows, fid):
    cond, attr, which = fid[len("M23-STAT|"):].split("|")
    if which == "outside_limit_count":
        return str(_outside(rows, cond, attr))
    if which == "significant_change" and cond == ACCEL:
        s = _significant(rows, attr)
        if s is None:
            raise KeyError(fid)
        return "1" if s else "0"
    raise KeyError(fid)


def _groups(rows):
    return sorted({(r["condition"], r["attribute"]) for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo"})


def compare(html_path, task, rows):
    """{"ok", "paragraphs", "numbers", "problems"}: the T-072 check plus the claim rules."""
    res = C2.compare(html_path, task, rows)
    problems = list(res["problems"])
    doc = _Paras()
    doc.feed(Path(html_path).read_text(encoding="utf-8"))
    li = [(c, a) for c, a in _groups(rows) if c != ACCEL]
    li_ids = {f"M23-STAT|{c}|{a}|outside_limit_count" for c, a in li}
    attrs = sorted({a for _, a in _groups(rows)})
    sig_ids = {f"M23-STAT|{ACCEL}|{a}|significant_change" for a in attrs if _significant(rows, a) is not None}
    # R7
    for cond, attr in _groups(rows):
        for r in _group(rows, cond, attr):
            if attr in SPEC_OF and _limit_of(rows, attr, r) is None:
                problems.append(f"R7: {attr} has no specification fact in the graph to take its limit from")
                break
            if C2._own_limit(_limit_of(rows, attr, r)) != C2._own_limit(r.get("limit_text", "")):
                problems.append(f"R7: {cond} | {attr}: the stored limit {r.get('limit_text')!r} is not the limit of the specification table")
                break
    # every claim span: ids workable, and what the wording says
    for text, claims in doc.paras:
        for a, b, ids in claims:
            for i in ids:
                try:
                    _derived(rows, i)
                except (KeyError, ValueError, IndexError):
                    problems.append(f"a claim links {i}, which is not a derived fact of the graph")
    # result claims
    ps = [p for p in doc.paras]
    n = len(task["results"])
    result_paras = ps[2:2 + 2 * n]
    for k, g in enumerate(task["results"]):
        if len(result_paras) < 2 * n:
            problems.append("claim paragraphs missing")
            break
        text, claims = result_paras[2 * k + 1]
        want = f"M23-STAT|{g['condition']}|{g['attribute']}|outside_limit_count"
        if len(claims) != 1 or claims[0][2] != [want] or (claims[0][0], claims[0][1]) != (0, len(text)):
            problems.append(f"{g['condition']} | {g['attribute']}: the claim sentence does not carry the link to {want}")
            continue
        count = _outside(rows, g["condition"], g["attribute"])
        says_none = bool(re.search(r"no results outside the limit|no .+ result under .+ was outside the limit|within the specification limits", text))
        says_some = "had results outside the limit" in text
        if says_none and count != 0 or says_some and count == 0 or says_none == says_some:
            problems.append(f"{g['condition']} | {g['attribute']}: the claim disagrees with the count against the specification limit ({count})")
    # "demonstrated" and extrapolation, in the public paragraph (and nowhere else)
    shelf = Decimal(rows[task["public"]["shelf"]["fact_id"]]["value_text"])
    long_ = Decimal(rows[task["public"]["long"]["fact_id"]]["value_text"])
    clean = any(c == LONG for c, _ in li) and all(_outside(rows, c, a) == 0 for c, a in li)
    ok_extrap = clean and all(_significant(rows, a) is False for a in attrs)
    for text, claims in ps:
        pos = 0
        for sent in re.split(r"(?<=\.)\s+", text):
            s = text.index(sent, pos)
            e, pos = s + len(sent), s + len(sent)
            link = [ids for a, b, ids in claims if a <= s and e <= b]
            if re.search(r"\bdemonstrated\b", sent):
                if not clean:
                    problems.append("a sentence says 'demonstrated' but the graph holds a result outside the limit at long-term / intermediate conditions "
                                    "or no long-term result")
                if not link or set(link[0]) != li_ids:
                    problems.append("a 'demonstrated' sentence does not link the outside-limit counts of all long-term and intermediate groups")
            if "proposed shelf life" in sent and shelf > long_:
                if not ok_extrap:
                    problems.append("the shelf life goes beyond the long-term data but the graph does not allow that extrapolation")
                if not link or set(link[0]) != li_ids | sig_ids:
                    problems.append("a shelf life beyond the data does not link the outside-limit counts and the significant-change facts")
    return {"ok": not problems, "paragraphs": res["paragraphs"], "numbers": res["numbers"], "problems": problems}


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 3:
        print("usage: m23_compare3 <M23.html or render folder> <task json> <graph snapshot json>", file=sys.stderr)
        return 2
    p = Path(args[0])
    res = compare(p / "M23.html" if p.is_dir() else p, json.loads(Path(args[1]).read_text(encoding="utf-8")),
                  json.loads(Path(args[2]).read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
