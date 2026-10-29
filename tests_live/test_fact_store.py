"""Live checks that facts can only enter Postgres through the gate, and that numbers stay exact."""
import unittest
import uuid
from decimal import Decimal

import psycopg

from ectd_engine.db import postgres
from ectd_engine.facts import store
from ectd_engine.facts.schema import Fact, SourcePointer


def make_fact(**over):
    base = dict(fact_id="T9-" + uuid.uuid4().hex[:10], value=Decimal("0.140"), unit="%", batch="B1",
                test="Impurity A", condition="25C/60%RH", month=6,
                source=SourcePointer("DOC-1", "v1", "row=12"), lineage="original", definition="live test fact")
    base.update(over)
    return Fact(**base)


class FactStoreLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = postgres.connect()
        cls.app = store.connect_app()
        cls.ids = []

    @classmethod
    def tearDownClass(cls):
        cls.app.close()
        cls.owner.execute("DELETE FROM facts WHERE fact_id LIKE 'T9-%'")
        cls.owner.commit()
        cls.owner.close()

    def tearDown(self):
        self.app.rollback()

    def _put(self, **over):
        f = make_fact(**over)
        store.put(self.app, f)
        return f

    def test_round_trip_keeps_trailing_zero(self):
        f = self._put()
        got = store.get(self.app, f.fact_id)
        self.assertEqual(got, f)
        self.assertEqual(str(got.value), "0.140")

    def test_get_missing_is_none(self):
        self.assertIsNone(store.get(self.app, "T9-nope"))

    def test_planted_direct_insert_denied(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as cm:
            self.app.execute(
                "INSERT INTO facts (fact_id, value, value_text, unit, batch, test, condition, doc_id, "
                "doc_version, locator, lineage, definition) VALUES ('T9-x', 1, '1', 'u', 'b', 't', 'c', "
                "'d', 'v', 'row=1', 'original', 'x')")
        print("\nINSERT ->", str(cm.exception).strip())

    def test_planted_update_denied(self):
        f = self._put()
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as cm:
            self.app.execute("UPDATE facts SET value_text = '9', value = 9 WHERE fact_id = %s", (f.fact_id,))
        print("\nUPDATE ->", str(cm.exception).strip())

    def test_planted_delete_denied(self):
        f = self._put()
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as cm:
            self.app.execute("DELETE FROM facts WHERE fact_id = %s", (f.fact_id,))
        print("\nDELETE ->", str(cm.exception).strip())

    def test_planted_truncate_denied(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.app.execute("TRUNCATE facts")

    def test_planted_duplicate_id_refused(self):
        f = self._put()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            store.put(self.app, f)
        self.app.rollback()
        self.assertEqual(store.get(self.app, f.fact_id), f)

    def test_planted_value_text_mismatch_refused(self):
        s = make_fact().source
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.app.execute(
                "SELECT gate_insert_fact('T9-bad', 0.14, '0.140', 'u', 'b', 't', 'c', 6, %s, %s, %s, 'original', 'x')",
                (s.doc_id, s.doc_version, s.locator))

    def test_facts_table_has_no_float_columns(self):
        self.assertEqual([r for r in postgres.float_columns(self.owner) if r[0] == "facts"], [])

    def test_app_role_cannot_create_tables(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.app.execute("CREATE TABLE t9_sneaky (x int)")


if __name__ == "__main__":
    unittest.main()
