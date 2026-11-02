"""Reads the Q3B(R2) threshold table typed twice, accepts it only if both copies agree and every row is quoted from the PDF."""
import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from ectd_engine.knowledge import chunk, cite

ROOT = chunk.ROOT
ENTRY_A = ROOT / "data" / "rules" / "q3b_entry_a.csv"
ENTRY_B = ROOT / "data" / "rules" / "q3b_entry_b.csv"
DOC_ID = "Q3B_R2"
PAGE = 11
COLUMNS = ["kind", "max_daily_dose", "percent", "tdi"]
KINDS = ("reporting", "identification", "qualification")
# The table headings exactly as the PDF prints them (they make the one-row quotes long enough for cite.verify).
HEADINGS = {
    "reporting": "Reporting Thresholds Maximum Daily Dose1 Threshold2,3",
    "identification": "Identification Thresholds Maximum Daily Dose1 Threshold2, 3",
    "qualification": "Qualification Thresholds Maximum Daily Dose1 Threshold2,3",
}
MG = {"mg": Decimal(1), "g": Decimal(1000)}
UG = {"µg": Decimal(1), "μg": Decimal(1), "mg": Decimal(1000), "g": Decimal(1000000)}
NUM = r"(\d+(?:\.\d+)?)"


class Q3BRefused(Exception):
    """The table is not accepted (the message lists exactly what is wrong)."""


@dataclass(frozen=True)
class Row:
    rule_id: str
    doc_id: str
    doc_version: str
    page: int
    kind: str
    dose_low_mg: object
    low_incl: bool
    dose_high_mg: object
    high_incl: bool
    percent: Decimal
    tdi_ug: object
    source_quote: str
    entered_a_sha: str
    entered_b_sha: str
    valid_from: date


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _norm(cell):
    """Only for comparing the two copies: Unicode-equivalent forms (micro sign vs Greek mu) count as equal."""
    return " ".join(unicodedata.normalize("NFKC", cell).split())


def read_entry(path):
    """The rows of one typed copy as a list of {column: text}; the header must be exactly the agreed columns."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = list(csv.reader(f))
    if not lines or [c.strip() for c in lines[0]] != COLUMNS:
        raise Q3BRefused(f"{Path(path).name}: header must be {','.join(COLUMNS)}")
    rows = []
    for n, cells in enumerate(lines[1:], start=2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) != len(COLUMNS):
            raise Q3BRefused(f"{Path(path).name} line {n}: expected {len(COLUMNS)} cells, got {len(cells)}")
        rows.append(dict(zip(COLUMNS, (c.strip() for c in cells))))
    return rows


def compare(rows_a, rows_b):
    """A list of exact differences between the two copies (empty list = they agree)."""
    diffs = []
    maps = []
    for label, rows in (("A", rows_a), ("B", rows_b)):
        m = {}
        for r in rows:
            key = (_norm(r["kind"]), _norm(r["max_daily_dose"]))
            if key in m:
                diffs.append(f"entry_{label.lower()}: duplicate row {key}")
            m[key] = r
        maps.append(m)
    ma, mb = maps
    for key in ma:
        if key not in mb:
            diffs.append(f"row only in entry_a: {key}")
    for key in mb:
        if key not in ma:
            diffs.append(f"row only in entry_b: {key}")
    for key in ma:
        if key in mb:
            for col in ("percent", "tdi"):
                if _norm(ma[key][col]) != _norm(mb[key][col]):
                    diffs.append(f"{key} {col}: entry_a {ma[key][col]!r} != entry_b {mb[key][col]!r}")
    # The order of rows decides the quoted text, so a different order is also a difference.
    if [(_norm(r["kind"]), _norm(r["max_daily_dose"])) for r in rows_a] != [(_norm(r["kind"]), _norm(r["max_daily_dose"])) for r in rows_b] and not diffs:
        diffs.append("rows are in a different order in entry_a and entry_b")
    return diffs


def parse_dose(text):
    """(low_mg, low_incl, high_mg, high_incl) from the dose text as printed; None = no bound on that side."""
    t = _norm(text)
    m = re.fullmatch(rf"([≤<>≥])\s*{NUM}\s*(mg|g)", t)
    if m:
        op, value = m.group(1), Decimal(m.group(2)) * MG[m.group(3)]
        if op in "≤<":
            return None, False, value, op == "≤"
        return value, op == "≥", None, False
    m = re.fullmatch(rf"(>?)\s*{NUM}\s*(mg|g)\s*-\s*{NUM}\s*(mg|g)", t)
    if m:
        low, high = Decimal(m.group(2)) * MG[m.group(3)], Decimal(m.group(4)) * MG[m.group(5)]
        if low >= high:
            raise Q3BRefused(f"dose range {text!r}: lower end is not below the upper end")
        return low, m.group(1) == "", high, True
    raise Q3BRefused(f"cannot read dose text {text!r}")


def parse_percent(text):
    if not re.fullmatch(r"\d+(?:\.\d+)?", text.strip()):
        raise Q3BRefused(f"percent {text!r} is not a plain number")
    return Decimal(text.strip())


def parse_tdi(text):
    """micrograms per day as Decimal, or None when the row has no TDI limit."""
    t = _norm(text)
    if not t:
        return None
    m = re.fullmatch(rf"{NUM}\s*(µg|μg|mg|g)", t)
    if not m:
        raise Q3BRefused(f"cannot read tdi {text!r}")
    return Decimal(m.group(1)) * UG[m.group(2)]


def printed_row(r):
    """The row as the PDF prints it."""
    tdi = f" or {r['tdi']} TDI, whichever is lower" if r["tdi"] else ""
    return f"{r['max_daily_dose']} {r['percent']}%{tdi}"


def _check_partition(rows):
    """For each kind the dose ranges must cover every dose exactly once (no gap, no overlap)."""
    for kind in KINDS:
        mine = sorted((r for r in rows if r.kind == kind),
                      key=lambda r: (r.dose_low_mg is not None, r.dose_low_mg or Decimal(0), r.low_incl))
        if not mine:
            raise Q3BRefused(f"no rows for {kind}")
        if mine[0].dose_low_mg is not None or mine[-1].dose_high_mg is not None:
            raise Q3BRefused(f"{kind}: ranges must start below every dose and end above every dose")
        for a, b in zip(mine, mine[1:]):
            if a.dose_high_mg is None or a.dose_high_mg != b.dose_low_mg or a.high_incl == b.low_incl:
                raise Q3BRefused(f"{kind}: gap or overlap between {a.rule_id} and {b.rule_id}")


@dataclass(frozen=True)
class Table:
    rows: tuple
    files: object = None  # (path_a, path_b) when read from the typed files; None when read from the database

    def check_unchanged(self):
        """Refuse if either typed file changed after it was loaded."""
        if self.files:
            for path, sha in zip(self.files, (self.rows[0].entered_a_sha, self.rows[0].entered_b_sha)):
                if sha_of(path) != sha:
                    raise Q3BRefused(f"{Path(path).name} changed after it was loaded")


def load(entry_a=ENTRY_A, entry_b=ENTRY_B, pdf_dir=None):
    """The accepted table, or Q3BRefused. Accepted only if A and B agree exactly and every row's quote verifies on the PDF."""
    sha_a, sha_b = sha_of(entry_a), sha_of(entry_b)
    rows_a, rows_b = read_entry(entry_a), read_entry(entry_b)
    diffs = compare(rows_a, rows_b)
    if diffs:
        raise Q3BRefused("entry_a and entry_b differ:\n  " + "\n  ".join(diffs))
    out, printed, seq = [], {k: [] for k in KINDS}, {k: 0 for k in KINDS}
    for r in rows_a:
        kind = r["kind"]
        if kind not in KINDS:
            raise Q3BRefused(f"unknown kind {kind!r}")
        printed[kind].append(printed_row(r))
        quote = HEADINGS[kind] + " " + " ".join(printed[kind])
        try:
            cite_ = cite.verify(DOC_ID, PAGE, quote, pdf_dir)
        except cite.CitationRejected as e:
            raise Q3BRefused(f"{kind} row {r['max_daily_dose']!r}: source text does not verify ({e})") from e
        m = re.search(r"\d{4}-\d{2}-\d{2}", cite_.version)
        if not m:
            raise Q3BRefused(f"no date in document version {cite_.version!r}")
        valid_from = date.fromisoformat(m.group(0))
        seq[kind] += 1
        low, low_incl, high, high_incl = parse_dose(r["max_daily_dose"])
        out.append(Row(f"{DOC_ID}@{valid_from}:{kind}:{seq[kind]}", DOC_ID, cite_.version, PAGE, kind, low, low_incl,
                       high, high_incl, parse_percent(r["percent"]), parse_tdi(r["tdi"]), quote, sha_a, sha_b, valid_from))
    _check_partition(out)
    return Table(tuple(out), (Path(entry_a), Path(entry_b)))


def table_from_db(conn):
    """Every stored row (all versions) as a Table."""
    cols = [f for f in Row.__dataclass_fields__]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM rule_thresholds WHERE doc_id = %s ORDER BY rule_id", (DOC_ID,)).fetchall()
    return Table(tuple(Row(*r) for r in rows))


def store(table, conn):
    """Adds the rows; a rule_id that already exists must be identical (rows are never overwritten)."""
    cols = list(Row.__dataclass_fields__)
    for row in table.rows:
        old = conn.execute(f"SELECT {', '.join(cols)} FROM rule_thresholds WHERE rule_id = %s", (row.rule_id,)).fetchone()
        if old is None:
            conn.execute(f"INSERT INTO rule_thresholds ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                         tuple(getattr(row, c) for c in cols))
        elif Row(*old) != row:
            conn.rollback()
            raise Q3BRefused(f"{row.rule_id} is already stored with different content; publish a new doc_version instead")
    conn.commit()


def _as_dose(value):
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("dose must be a Decimal, int or str, never float")
    dose = Decimal(value)
    if dose <= 0:
        raise ValueError("max daily dose must be above 0 mg")
    return dose


def threshold(kind, max_daily_dose_mg, version="latest", table=None):
    """(percent, tdi_ug or None, rule_id) for the dose, using the boundaries exactly as printed."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    dose = _as_dose(max_daily_dose_mg)
    table = table or _default_table()
    table.check_unchanged()
    mine = [r for r in table.rows if r.kind == kind]
    if version == "latest":
        newest = max(r.valid_from for r in mine)
        mine = [r for r in mine if r.valid_from == newest]
    else:
        mine = [r for r in mine if r.doc_version == version]
    hits = [r for r in mine if _inside(r, dose)]
    if len(hits) != 1:
        raise Q3BRefused(f"{len(hits)} {kind} rows match {dose} mg (version {version})")
    return hits[0].percent, hits[0].tdi_ug, hits[0].rule_id


def _inside(r, dose):
    if r.dose_low_mg is not None and not (dose > r.dose_low_mg or (r.low_incl and dose == r.dose_low_mg)):
        return False
    if r.dose_high_mg is not None and not (dose < r.dose_high_mg or (r.high_incl and dose == r.dose_high_mg)):
        return False
    return True


_DEFAULT = []


def _default_table():
    if not _DEFAULT:
        _DEFAULT.append(load())
    return _DEFAULT[0]
