"""Reads the stability CSV and computes facts (counts, min, max, last, outside-limit) per condition and attribute; code, not a model, makes every number."""
import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "stability" / "finerenone_stability.csv"
COLUMNS = ["condition", "month", "attribute", "value", "unit", "limit", "source"]

PUBLIC_SOURCE = re.compile(r"^FDA ChemR 215341 p\.(\d+)$")
DEMO_SOURCE = re.compile(r"^DEMO: redacted \(b\)\(4\) in ChemR p\.(\d+)$")
# The only things the FDA review says in public (shelf life, storage, how long each condition ran).
# Any other attribute (assay, impurity, dissolution...) is hidden in the review, so it can only be DEMO.
PUBLIC_ATTRIBUTES = {"study_duration_demonstrated", "expiry_period_proposed"}

_NUM = r"(\d+(?:\.\d+)?)"
_RANGE = re.compile(r"^" + _NUM + r"-" + _NUM + r"$")
_NMT = re.compile(r"^NMT " + _NUM + r"$")
_NLT = re.compile(r"^NLT " + _NUM + r"$")


@dataclass(frozen=True)
class Fact:
    """Facts for one condition x attribute."""
    condition: str
    attribute: str
    n: int
    months: tuple
    min: Decimal
    max: Decimal
    last: Decimal
    n_outside: int
    n_demo: int


def load_rows(path=DEFAULT_CSV):
    """Read the CSV into a list of dicts; each gets '_line' (file line number) for error messages."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for i, row in enumerate(reader, start=2):
            row["_line"] = i
            rows.append(row)
    return rows


def parse_limit(text):
    """'95.0-105.0' -> (95.0, 105.0); 'NMT x' -> (None, x); 'NLT x' -> (x, None); '' -> None."""
    text = (text or "").strip()
    if not text:
        return None
    m = _RANGE.match(text)
    if m:
        return Decimal(m.group(1)), Decimal(m.group(2))
    m = _NMT.match(text)
    if m:
        return None, Decimal(m.group(1))
    m = _NLT.match(text)
    if m:
        return Decimal(m.group(1)), None
    raise ValueError("unknown limit format: " + text)


def is_outside(value, limit):
    """True when value breaks the limit (limit = (low, high) or None)."""
    if limit is None:
        return False
    low, high = limit
    return (low is not None and value < low) or (high is not None and value > high)


def source_kind(source):
    """'public', 'demo' or None (anything else is not an allowed source)."""
    source = (source or "").strip()
    if PUBLIC_SOURCE.match(source):
        return "public"
    if DEMO_SOURCE.match(source):
        return "demo"
    return None


def check_rows(rows):
    """Return a list of problems ('<code>:line N'); an empty list means the data is clean."""
    problems = []
    for row in rows:
        at = "line %s" % row.get("_line", "?")
        if not (row.get("source") or "").strip():
            problems.append("no_source:" + at)
            continue
        kind = source_kind(row["source"])
        if kind is None:
            problems.append("bad_source:" + at)
            continue
        is_public_attr = row.get("attribute") in PUBLIC_ATTRIBUTES
        if kind == "public" and not is_public_attr:
            problems.append("demo_as_public:" + at)
        if kind == "demo" and is_public_attr:
            problems.append("public_as_demo:" + at)
        try:
            value = Decimal(row["value"])
            limit = parse_limit(row.get("limit"))
            int(row["month"])
        except (InvalidOperation, ValueError, TypeError, KeyError):
            problems.append("bad_field:" + at)
            continue
        if kind == "demo" and limit is None:
            problems.append("demo_no_limit:" + at)
        if kind == "demo" and is_outside(value, limit):
            problems.append("demo_outside_limit:" + at)
    return problems


def compute_facts(rows):
    """Group rows by (condition, attribute) and compute n, months, min, max, last, n_outside, n_demo."""
    groups = {}
    for row in rows:
        groups.setdefault((row["condition"], row["attribute"]), []).append(row)
    facts = {}
    for (cond, attr), grp in groups.items():
        grp = sorted(grp, key=lambda r: int(r["month"]))
        values = [Decimal(r["value"]) for r in grp]
        outside = sum(1 for r, v in zip(grp, values) if is_outside(v, parse_limit(r["limit"])))
        demo = sum(1 for r in grp if source_kind(r["source"]) == "demo")
        facts[(cond, attr)] = Fact(
            condition=cond, attribute=attr, n=len(grp),
            months=tuple(int(r["month"]) for r in grp),
            min=min(values), max=max(values), last=values[-1],
            n_outside=outside, n_demo=demo,
        )
    return facts


def count_sources(rows):
    """(n_public_rows, n_demo_rows)."""
    kinds = [source_kind(r["source"]) for r in rows]
    return kinds.count("public"), kinds.count("demo")
