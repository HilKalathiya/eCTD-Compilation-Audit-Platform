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
# Held-out test data (T-065) is made up by code and never comes from the FDA review. It is only accepted when a caller asks for heldout=True.
HELDOUT_SOURCE = re.compile(r"^DEMO: synthetic held-out set T-06[57]\Z")  # T-065 and T-067 only; \Z (not $) so a trailing newline is refused too
# The only things the FDA review says in public (shelf life, storage, how long each condition ran).
# Any other attribute (assay, impurity, dissolution...) is hidden in the review, so it can only be DEMO.
PUBLIC_ATTRIBUTES = {"study_duration_demonstrated", "expiry_period_proposed", "excursion_permitted_low", "excursion_permitted_high"}

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


def source_kind(source, heldout=False):
    """'public', 'demo' or None (anything else is not an allowed source). heldout=True also allows the synthetic held-out source."""
    source = (source or "").strip()
    if PUBLIC_SOURCE.match(source):
        return "public"
    if DEMO_SOURCE.match(source) or (heldout and HELDOUT_SOURCE.match(source)):
        return "demo"
    return None


def check_rows(rows, heldout=False):
    """Return a list of problems ('<code>:line N'); an empty list means the data is clean.

    heldout=True (T-065 only): the synthetic held-out source is allowed and demo results may fall outside their limit
    (the held-out set needs some). Every other check stays on. The default is the strict check."""
    problems = []
    for row in rows:
        at = "line %s" % row.get("_line", "?")
        if not (row.get("source") or "").strip():
            problems.append("no_source:" + at)
            continue
        kind = source_kind(row["source"], heldout)
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
        if kind == "demo" and not heldout and is_outside(value, limit):
            problems.append("demo_outside_limit:" + at)
    return problems


def compute_facts(rows, heldout=False):
    """Group rows by (condition, attribute) and compute n, months, min, max, last, n_outside, n_demo."""
    groups = {}
    for row in rows:
        groups.setdefault((row["condition"], row["attribute"]), []).append(row)
    facts = {}
    for (cond, attr), grp in groups.items():
        grp = sorted(grp, key=lambda r: int(r["month"]))
        values = [Decimal(r["value"]) for r in grp]
        outside = sum(1 for r, v in zip(grp, values) if is_outside(v, parse_limit(r["limit"])))
        demo = sum(1 for r in grp if source_kind(r["source"], heldout) == "demo")
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


def p83_facts(rows, heldout=False):
    """Facts the P.8.3 paragraph may use: 'public' (shelf life, storage, excursions, study length) and 'demo' (per condition x attribute)."""
    f = compute_facts(rows, heldout)
    crt = [c for (c, a) in f if a == "expiry_period_proposed"]
    m = re.match(r"^(\d+)-(\d+)C CRT$", crt[0]) if crt else None
    public = {
        "shelf_life_months": f[(crt[0], "expiry_period_proposed")].last,
        "storage_low": Decimal(m.group(1)),
        "storage_high": Decimal(m.group(2)),
        "excursion_low": f[("15-30C excursion", "excursion_permitted_low")].last,
        "excursion_high": f[("15-30C excursion", "excursion_permitted_high")].last,
        "long_term_months": f[("25C/60%RH", "study_duration_demonstrated")].last,
        "accel_months": f[("40C/75%RH", "study_duration_demonstrated")].last,
    }
    demo = {k: v for k, v in f.items() if v.n_demo > 0}
    return {"public": public, "demo": demo}
