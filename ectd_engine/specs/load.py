"""Reads the Lek specification file and turns every acceptance criterion into a gated fact with a traced basis."""
import csv
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.gate import gate
from ectd_engine.loaders import lek
from ectd_engine.rules import q3b

SPEC_CSV = Path(__file__).resolve().parents[2] / "data" / "specs" / "lek_spec.csv"
COLUMNS = ["attribute", "limit_kind", "value", "unit", "basis", "basis_note"]
BATCH = "SPEC"  # the one "batch" all specification facts belong to
CONDITION = "specification limit"
MDD_ID = "ASSUMPTION-MDD"
DEFAULT_MDD = Decimal("40")  # highest Lek strength, taken once a day
BASES = ("q3b_qualification", "declared")
LIMIT_KINDS = ("NMT", "NLT")
SOURCE_WORDS = re.compile(r"q3b|\bich\b|guideline|fda|pharmacopo", re.IGNORECASE)


class SpecRefused(Exception):
    """The specification is not accepted (the message names the attribute and the reason)."""


@dataclass(frozen=True)
class SpecRow:
    attribute: str
    test: str
    limit_kind: str
    unit: str
    basis: str
    basis_note: str
    fact: Fact
    rule_id: object = None  # Q3B rule id for q3b rows, None for declared rows
    q3b_row: object = None


@dataclass(frozen=True)
class Spec:
    mdd: Fact
    rows: tuple
    csv_sha: str


class Recorder:
    """Stands in for the database: keeps every fact that the gate hands to gate_insert_fact."""

    def __init__(self):
        self.facts = []

    def execute(self, sql, params=()):
        if "gate_insert_fact" in sql:
            p = params
            self.facts.append(Fact(fact_id=p[0], value=Decimal(p[2]), unit=p[3], batch=p[4], test=p[5], condition=p[6],
                                   month=p[7], source=SourcePointer(p[8], p[9], p[10]), lineage=p[11], definition=p[12]))
        return self

    def commit(self):
        pass

    def rollback(self):
        pass


def spec_fact_id(attribute):
    return f"SPEC-LEK-{attribute}"


def read_spec(path=SPEC_CSV):
    """[(csv_row_number, {column: text})]; header must be exactly the agreed columns. The file is only read."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = list(csv.reader(f))
    if not lines or [c.strip() for c in lines[0]] != COLUMNS:
        raise SpecRefused(f"{Path(path).name}: header must be {','.join(COLUMNS)}")
    out = []
    for n, cells in enumerate(lines[1:], start=2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) != len(COLUMNS):
            raise SpecRefused(f"{Path(path).name} line {n}: expected {len(COLUMNS)} cells, got {len(cells)}")
        out.append((n, dict(zip(COLUMNS, (c.strip() for c in cells)))))
    return out


def q3b_limit(mdd, table):
    """(limit %, rule_id, Q3B row, text) for the qualification threshold at this maximum daily dose.

    The limit is the percent or the TDI (as a percent of the dose), whichever is lower, as Q3B prints it."""
    if not isinstance(mdd, Decimal):
        raise TypeError("mdd must be a Decimal")
    percent, tdi_ug, rule_id = q3b.threshold("qualification", mdd, table=table)
    row = next(r for r in table.rows if r.rule_id == rule_id)
    value, how = percent, f"{percent}%"
    if tdi_ug is not None:
        with localcontext() as ctx:
            ctx.prec = 50
            tdi_pct = tdi_ug / (mdd * 1000) * 100
        how += f" or {tdi_ug} ug TDI (= {format(tdi_pct.normalize(), 'f')}%), whichever is lower"
        if tdi_pct < percent:
            value = Decimal(format(tdi_pct.normalize(), "f"))
    return value, rule_id, row, how


def _candidate(fact_id, value, unit, test, source, lineage, definition):
    return {"fact_id": fact_id, "value": format(value, "f"), "unit": unit, "batch": BATCH, "test": test,
            "condition": CONDITION, "month": None, "source": source, "lineage": lineage, "definition": definition}


def _submit(cand, conn, rules):
    res = gate.submit(cand, {BATCH}, conn, rules)
    if not isinstance(res, gate.Accepted):
        raise SpecRefused(f"{cand['fact_id']}: the gate refused it ({res.reason_code}: {res.reason_text})")
    return res.fact


def load(conn=None, path=SPEC_CSV, mdd=DEFAULT_MDD, table=None, rules=None):
    """The Spec: the MDD assumption plus one gated fact per attribute. Any problem raises SpecRefused."""
    conn = conn if conn is not None else Recorder()
    table = table or q3b.load()
    rules = rules or gate.load_rules()
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    version = f"lek_spec.csv sha256:{sha[:12]}"
    mdd_fact = _submit(_candidate(
        MDD_ID, mdd, "mg", "Maximum daily dose",
        {"doc_id": "lek_spec.csv", "doc_version": version, "locator": "row=0"}, "unknown",
        "ASSUMPTION (not a source value): highest Lek strength taken once a day"), conn, rules)
    rows, seen = [], set()
    for n, r in read_spec(path):
        attr = r["attribute"]
        if attr not in lek.COLUMNS:
            raise SpecRefused(f"row {n}: unknown attribute {attr!r}")
        if attr in seen:
            raise SpecRefused(f"row {n}: attribute {attr!r} appears twice")
        seen.add(attr)
        if r["limit_kind"] not in LIMIT_KINDS:
            raise SpecRefused(f"{attr}: limit_kind {r['limit_kind']!r} must be one of {LIMIT_KINDS}")
        if r["basis"] not in BASES:
            raise SpecRefused(f"{attr}: basis {r['basis']!r} must be one of {BASES}")
        if not r["unit"]:
            raise SpecRefused(f"{attr}: unit is blank")
        test = lek.COLUMNS[attr][0]
        fid = spec_fact_id(attr)
        if r["basis"] == "q3b_qualification":
            if r["value"]:
                raise SpecRefused(f"{attr}: a q3b row must not carry a typed value ({r['value']!r}); code computes it")
            if attr not in ("impurity_o", "impurity_l"):
                raise SpecRefused(f"{attr}: Q3B qualification limits apply to individual impurities only")
            if r["limit_kind"] != "NMT" or r["unit"] != "%":
                raise SpecRefused(f"{attr}: a Q3B limit is NMT in %")
            value, rule_id, q_row, how = q3b_limit(mdd, table)
            source = {"doc_id": q_row.doc_id, "doc_version": q_row.doc_version, "locator": f"typed=page={q_row.page}"}
            definition = (f"Q3B qualification threshold at an assumed maximum daily dose of {mdd} mg "
                          f"({rule_id}): {how}")
            fact = _submit(_candidate(fid, value, r["unit"], test, source, "original", definition), conn, rules)
            rows.append(SpecRow(attr, test, r["limit_kind"], r["unit"], r["basis"], r["basis_note"], fact, rule_id, q_row))
        else:
            if SOURCE_WORDS.search(r["basis_note"]):
                raise SpecRefused(f"{attr}: a declared row must not claim a source (note: {r['basis_note']!r})")
            if not r["value"]:
                raise SpecRefused(f"{attr}: declared row has a blank value")
            try:
                value = Decimal(r["value"])
            except InvalidOperation:
                raise SpecRefused(f"{attr}: value {r['value']!r} is not a number") from None
            if not value.is_finite():
                raise SpecRefused(f"{attr}: value {r['value']!r} is not a finite number")
            source = {"doc_id": "lek_spec.csv", "doc_version": version, "locator": f"row={n}"}
            definition = f"DECLARED by the author, no source: {r['basis_note']}"
            fact = _submit(_candidate(fid, value, r["unit"], test, source, "unknown", definition), conn, rules)
            rows.append(SpecRow(attr, test, r["limit_kind"], r["unit"], r["basis"], r["basis_note"], fact))
    missing = [a for a in lek.COLUMNS if a not in seen]
    if missing:
        raise SpecRefused("missing spec row(s): " + ", ".join(missing))
    order = list(lek.COLUMNS)
    rows.sort(key=lambda s: order.index(s.attribute))
    return Spec(mdd_fact, tuple(rows), sha)
