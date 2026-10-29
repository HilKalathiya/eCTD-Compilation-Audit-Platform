"""Reads Laboratory.csv (Lek tablet batches) and sends every number through the gate as a sourced fact."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ectd_engine.gate import gate

CSV_PATH = Path(__file__).resolve().parents[2] / "Laboratory.csv"
DOC_ID = "Laboratory.csv"
DOC_VERSION = "v1"
CONDITION = "batch release"
CROSS_FIELD = "CROSS_FIELD"

# csv column -> (test name, definition); "resodual_solvent" is the real (misspelled) header
COLUMNS = {
    "dissolution_av": ("Dissolution", "Average dissolution of the batch"),
    "impurity_o": ("Impurity O", "Impurity O of the batch"),
    "impurity_l": ("Impurity L", "Impurity L of the batch"),
    "impurities_total": ("Total impurities", "Total impurities of the batch"),
    "resodual_solvent": ("Residual solvent", "Residual solvent of the batch"),
}
PARTS = ("impurity_o", "impurity_l", "impurities_total")


def _dec(text):
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None


def _part_exceeds_total(row):
    """True when impurity O or L is larger than the total; unreadable cells are left to the gate."""
    o, l, t = (_dec(row[c]) for c in ("impurity_o", "impurity_l", "impurities_total"))
    if None in (o, l, t) or not (o.is_finite() and l.is_finite() and t.is_finite()):
        return False
    return o > t or l > t


def _candidate(row, col, rownum):
    test, definition = COLUMNS[col]
    return {"fact_id": f"LEK-{row['batch']}-{col}", "value": row[col], "unit": "%", "batch": row["batch"],
            "test": test, "condition": CONDITION, "month": None,
            "source": {"doc_id": DOC_ID, "doc_version": DOC_VERSION, "locator": f"row={rownum}"},
            "lineage": "original", "definition": definition}


def read_rows(path=CSV_PATH):
    """Return [(row_number, row_dict)]; row_number is the spreadsheet row (header = row 1). Wrong header = loud error."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        missing = [c for c in ("batch", *COLUMNS) if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Laboratory.csv header is missing column(s): {', '.join(missing)}")
        return [(i, row) for i, row in enumerate(reader, start=2)]


def load(conn, graph=None, path=CSV_PATH, rules=None):
    """Submit every row through gate.submit; return (accepted, quarantined, bad_batches)."""
    rows = read_rows(path)
    registry = {row["batch"] for _, row in rows}  # register batches
    rules = rules or gate.load_rules()
    accepted = quarantined = 0
    bad_batches = set()
    for rownum, row in rows:
        split = _part_exceeds_total(row)
        for col in COLUMNS:
            cand = _candidate(row, col, rownum)
            if split and col in PARTS:
                gate.quarantine(conn, cand, gate.Quarantined(CROSS_FIELD, "part > total"))
                quarantined += 1
                bad_batches.add(row["batch"])
                continue
            if isinstance(gate.submit(cand, registry, conn, rules, graph), gate.Accepted):
                accepted += 1
            else:
                quarantined += 1
    return accepted, quarantined, bad_batches


class _Dry:
    """Stand-in for the database and the graph: records calls, stores nothing."""

    def execute(self, sql, params=()):
        return self

    def commit(self):
        pass

    def rollback(self):
        pass

    def run(self, *a, **k):
        return self

    def consume(self):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="count only; nothing is stored")
    args = ap.parse_args(argv)
    if not args.dry_run:
        ap.error("only --dry-run is allowed for now (no live load yet)")
    dry = _Dry()
    a, q, b = load(dry, dry)
    print(f"accepted {a}, quarantined {q} ({len(b)} batches)")


if __name__ == "__main__":
    main()
