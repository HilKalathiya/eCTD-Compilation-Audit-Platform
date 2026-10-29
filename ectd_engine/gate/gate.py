"""Checks each candidate fact (contract, unit, range); good ones go to the store, bad ones to quarantine."""
import json
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import psycopg

from ectd_engine.facts import schema, store

RULES = Path(__file__).resolve().parent / "rules"

# reason codes written to the quarantine table
FIELD_MISSING = "FIELD_MISSING"
CONTRACT_INVALID = "CONTRACT_INVALID"
BATCH_UNKNOWN = "BATCH_UNKNOWN"
TEST_UNKNOWN = "TEST_UNKNOWN"
UNIT_NOT_ALLOWED = "UNIT_NOT_ALLOWED"
RANGE_OUT = "RANGE_OUT"
STORE_REFUSED = "STORE_REFUSED"
REASON_CODES = (FIELD_MISSING, CONTRACT_INVALID, BATCH_UNKNOWN, TEST_UNKNOWN, UNIT_NOT_ALLOWED, RANGE_OUT, STORE_REFUSED)

_FIELDS = ("fact_id", "value", "unit", "batch", "test", "condition", "month", "source", "lineage", "definition")
_SOURCE_FIELDS = ("doc_id", "doc_version", "locator")


@dataclass(frozen=True)
class Accepted:
    fact: schema.Fact


@dataclass(frozen=True)
class Quarantined:
    reason_code: str
    reason_text: str


def load_rules(rules_dir=RULES):
    """Read units and the plausible ranges; the two range files are typed separately and must agree."""
    units = json.loads((rules_dir / "units.json").read_text(encoding="utf-8"))
    ranges = json.loads((rules_dir / "ranges.json").read_text(encoding="utf-8"))
    check = json.loads((rules_dir / "ranges_check.json").read_text(encoding="utf-8"))
    if ranges != check:
        raise ValueError("ranges.json and ranges_check.json disagree; fix the rule files before using the gate")
    return units, ranges


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _contract(candidate):
    """Return a Fact if the candidate has every field and passes the Fact rules, else a Quarantined."""
    if not isinstance(candidate, dict):
        return Quarantined(CONTRACT_INVALID, "candidate is not a dict")
    gaps = [k for k in _FIELDS if k != "month" and _blank(candidate.get(k))]
    if "month" not in candidate:
        gaps.append("month")
    src = candidate.get("source")
    if isinstance(src, dict):
        gaps += [f"source.{k}" for k in _SOURCE_FIELDS if _blank(src.get(k))]
    if gaps:
        return Quarantined(FIELD_MISSING, "missing or blank: " + ", ".join(gaps))
    try:
        return schema.from_json(json.dumps(candidate))
    except (ValueError, TypeError, KeyError) as e:
        return Quarantined(CONTRACT_INVALID, str(e))


def _unit(fact, units):
    """Return the fact in the test's allowed unit, converted by the table only, or a Quarantined."""
    rule = units.get(fact.test)
    if rule is None:
        return Quarantined(TEST_UNKNOWN, f"no unit rule for test {fact.test!r}")
    if fact.unit == rule["unit"]:
        return fact
    factor = rule["conversions"].get(fact.unit)
    if factor is None:
        return Quarantined(UNIT_NOT_ALLOWED, f"unit {fact.unit!r} for {fact.test!r}: allowed {rule['unit']!r}, no conversion in table")
    new = Decimal(format(fact.value * Decimal(factor), "f"))
    note = f" [converted from {fact.value} {fact.unit} by x{factor}]"
    return replace(fact, value=new, unit=rule["unit"], definition=fact.definition + note)


def _range(fact, ranges):
    rule = ranges.get(fact.test)
    if rule is None:
        return Quarantined(TEST_UNKNOWN, f"no range rule for test {fact.test!r}")
    lo, hi = Decimal(rule["min"]), Decimal(rule["max"])
    if not lo <= fact.value <= hi:
        return Quarantined(RANGE_OUT, f"{fact.test} {fact.value} {fact.unit} is outside {lo} to {hi}")
    return fact


def quarantine(conn, candidate, q):
    """Write the rejected candidate and its reason through gate_quarantine (the only door in)."""
    fid = candidate.get("fact_id") if isinstance(candidate, dict) else None
    batch = candidate.get("batch") if isinstance(candidate, dict) else None
    conn.execute(
        "SELECT gate_quarantine(%s, %s, %s, %s, %s)",
        (fid if isinstance(fid, str) else None, batch if isinstance(batch, str) else None,
         q.reason_code, q.reason_text, json.dumps(candidate, default=repr)),
    )
    conn.commit()


def submit(candidate, batch_registry, conn, rules=None):
    """Check a candidate in order: contract, batch, unit, range. Accepted -> store.put; else quarantine."""
    units, ranges = rules or load_rules()
    result = _contract(candidate)
    if isinstance(result, schema.Fact) and result.batch not in batch_registry:
        result = Quarantined(BATCH_UNKNOWN, f"batch {result.batch!r} is not in the batch registry")
    if isinstance(result, schema.Fact):
        result = _unit(result, units)
    if isinstance(result, schema.Fact):
        result = _range(result, ranges)
    if isinstance(result, schema.Fact):
        try:
            store.put(conn, result)
        except psycopg.errors.IntegrityError as e:
            conn.rollback()
            result = Quarantined(STORE_REFUSED, str(e).splitlines()[0])
        else:
            return Accepted(result)
    quarantine(conn, candidate, result)
    return result
