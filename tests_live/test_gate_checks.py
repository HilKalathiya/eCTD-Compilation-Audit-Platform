"""Live checks that the database refuses bad facts by itself, with no Python Fact in the way."""
import ast
import unittest
import uuid
from pathlib import Path

import psycopg

from ectd_engine.db import postgres
from ectd_engine.facts import store

SCHEMA = Path(__file__).resolve().parents[1] / "ectd_engine" / "facts" / "schema.py"
GOOD = dict(fact_id=None, value="0.140", value_text="0.140", unit="%", batch="B1", test="Impurity A",
            condition="25C/60%RH", month=6, doc_id="DOC-1", doc_version="v1", locator="row=12",
            lineage="original", definition="gate test")
ORDER = ["fact_id", "value", "value_text", "unit", "batch", "test", "condition", "month",
         "doc_id", "doc_version", "locator", "lineage", "definition"]

# every check in schema.py, and the table constraint(s) that repeat it in the database
_NEED_TEXT_CONSTRAINTS = {
    "doc_id": "facts_doc_id_nonblank", "doc_version": "facts_doc_version_nonblank",
    "locator": "facts_locator_nonblank", "fact_id": "facts_fact_id_nonblank",
    "unit": "facts_unit_nonblank", "test": "facts_test_nonblank", "batch": "facts_batch_nonblank",
    "condition": "facts_condition_nonblank",
}
# the other `raise ValueError` checks, by class: SourcePointer locator form; Fact type/finite/plain/month/source/lineage
_OTHER_RAISES = {
    "SourcePointer": ["facts_locator_form"],
    "Fact": [None, "facts_value_finite", "facts_value_plain_text", "facts_month_nonneg", None, "facts_lineage_allowed"],
}
# None = Python-only check (type checks the database cannot see: value is a Decimal, source is a SourcePointer)
_EXTRA_DB_ONLY = {"facts_definition_nonblank"}  # stricter than Python on purpose (T-010 card)


def call_gate(conn, **over):
    d = dict(GOOD, fact_id="T10-" + uuid.uuid4().hex[:10])
    d.update(over)
    return conn.execute("SELECT gate_insert_fact(" + ",".join(["%s"] * 13) + ")", [d[k] for k in ORDER])


class GateChecksLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = postgres.connect()
        cls.app = store.connect_app()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()
        cls.owner.execute("DELETE FROM facts WHERE fact_id LIKE 'T10-%'")
        cls.owner.commit()
        cls.owner.close()

    def tearDown(self):
        self.app.rollback()

    def refused(self, label, **over):
        with self.assertRaises(psycopg.errors.IntegrityError) as cm:
            call_gate(self.app, **over)
        print(f"\nREFUSED {label} -> {ascii(str(cm.exception).splitlines()[0])}")

    def test_valid_fact_accepted(self):
        call_gate(self.app)
        self.app.commit()

    def test_empty_batch_refused(self):
        self.refused("empty batch", batch="")

    def test_blank_unit_refused(self):
        self.refused("blank unit", unit="  ")

    def test_nan_refused(self):
        self.refused("NaN", value="NaN", value_text="NaN")

    def test_infinity_refused(self):
        self.refused("Infinity", value="Infinity", value_text="Infinity")

    def test_negative_month_refused(self):
        self.refused("month -1", month=-1)

    def test_bad_lineage_refused(self):
        self.refused("lineage guess", lineage="guess")

    def test_exponent_value_text_refused(self):
        self.refused("value_text 1E+2", value="100", value_text="1E+2")

    def test_arabic_digits_refused(self):
        self.refused("value_text arabic digits", value="0.14", value_text="٠.١٤")

    def test_bad_locator_refused(self):
        self.refused("locator anything", locator="anything")

    def test_locator_trailing_newline_refused(self):
        self.refused("locator row=1 + newline", locator="row=1\n")

    def test_table_itself_refuses_without_gate(self):
        """Even the table owner (no gate) cannot store a blank batch: the rule is in the table."""
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.owner.execute(
                "INSERT INTO facts (fact_id, value, value_text, unit, batch, test, condition, doc_id, "
                "doc_version, locator, lineage, definition) VALUES ('T10-own', 1, '1', 'u', ' ', 't', 'c', "
                "'d', 'v', 'row=1', 'original', 'x')")
        self.owner.rollback()

    def test_schema_checks_have_matching_constraints(self):
        """Drift guard: every check in schema.py's __post_init__ must map to a table constraint."""
        tree = ast.parse(SCHEMA.read_text(encoding="utf-8"))
        need, raises = set(), {}
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__"]:
                for node in ast.walk(fn):
                    if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_need_text"
                            and isinstance(node.args[0], ast.Constant)):
                        need.add(node.args[0].value)
                raises[cls.name] = sum(isinstance(n, ast.Raise) for n in ast.walk(fn))
        self.assertEqual(need, set(_NEED_TEXT_CONSTRAINTS), "schema.py non-blank checks changed; update the mapping and 002 SQL")
        self.assertEqual(raises, {k: len(v) for k, v in _OTHER_RAISES.items()},
                         "schema.py has a new/removed check; update the mapping and 002 SQL")
        expected = set(_NEED_TEXT_CONSTRAINTS.values()) | {c for v in _OTHER_RAISES.values() for c in v if c}
        have = {r[0] for r in self.owner.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'facts'::regclass AND contype = 'c'")}
        self.assertEqual(expected - have, set(), "constraint missing in the database")
        self.assertEqual(have - expected - _EXTRA_DB_ONLY - {"facts_check"}, set(), "unmapped constraint in the database")


if __name__ == "__main__":
    unittest.main()
