"""Live checks of the write gate against Postgres: quarantine rows, permissions, and the box/door match."""
import unittest
import uuid

import psycopg

from ectd_engine.db import migrate, postgres
from ectd_engine.facts import store
from ectd_engine.gate import gate
from tests.test_gate import cand

REGISTRY = {"B1", "B2", "B3"}
P = "T11-"


def fid():
    return P + uuid.uuid4().hex[:10]


class GateLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        migrate.migrate()
        cls.owner = postgres.connect()
        cls.app = store.connect_app()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()
        cls.owner.execute("DELETE FROM facts WHERE fact_id LIKE 'T11-%'")
        cls.owner.execute("DELETE FROM gate_quarantine_rows WHERE fact_id LIKE 'T11-%'")
        cls.owner.commit()
        cls.owner.close()

    def tearDown(self):
        self.app.rollback()

    def quarantine_rows(self, f):
        rows = self.owner.execute(
            "SELECT reason_code, batch FROM gate_quarantine_rows WHERE fact_id = %s", (f,)).fetchall()
        self.owner.commit()
        return rows

    def stored(self, f):
        return store.get(self.app, f)

    def test_accepted_goes_to_store_not_quarantine(self):
        f = fid()
        self.assertIsInstance(gate.submit(cand(fact_id=f), REGISTRY, self.app), gate.Accepted)
        self.assertEqual(str(self.stored(f).value), "0.14")
        self.assertEqual(self.quarantine_rows(f), [])

    def test_each_planted_error_lands_in_quarantine_with_its_code(self):
        cases = [(gate.BATCH_UNKNOWN, dict(batch="B99")), (gate.UNIT_NOT_ALLOWED, dict(unit="mg")),
                 (gate.RANGE_OUT, dict(value="1.4"))]
        for code, over in cases:
            f = fid()
            r = gate.submit(cand(fact_id=f, **over), REGISTRY, self.app)
            self.assertEqual(r.reason_code, code)
            self.assertIsNone(self.stored(f), "quarantined fact must not be in the store")
            self.assertEqual([x[0] for x in self.quarantine_rows(f)], [code])

    def test_missing_unit_quarantined_live(self):
        f = fid()
        c = cand(fact_id=f)
        del c["unit"]
        self.assertEqual(gate.submit(c, REGISTRY, self.app).reason_code, gate.FIELD_MISSING)
        self.assertEqual([x[0] for x in self.quarantine_rows(f)], [gate.FIELD_MISSING])

    def test_duplicate_fact_id_quarantined_not_lost(self):
        f = fid()
        gate.submit(cand(fact_id=f), REGISTRY, self.app)
        r = gate.submit(cand(fact_id=f, value="0.15"), REGISTRY, self.app)
        self.assertEqual(r.reason_code, gate.STORE_REFUSED)
        self.assertEqual(str(self.stored(f).value), "0.14")
        self.assertEqual([x[0] for x in self.quarantine_rows(f)], [gate.STORE_REFUSED])

    def test_fifty_valid_candidates_live(self):
        ids = [fid() for _ in range(50)]
        rs = [gate.submit(cand(fact_id=f, value=str(90 + i % 20) + ".5", test="Assay", batch=f"B{i % 3 + 1}"),
                          REGISTRY, self.app) for i, f in enumerate(ids)]
        self.assertEqual(sum(isinstance(r, gate.Accepted) for r in rs), 50)
        self.assertTrue(all(self.quarantine_rows(f) == [] for f in ids))

    def test_ectd_app_can_call_quarantine_but_not_read_or_write_it(self):
        self.app.execute("SELECT gate_quarantine(%s, 'B1', 'RANGE_OUT', 'direct call', '{}')", (fid(),))
        self.app.commit()
        for sql in ("SELECT * FROM gate_quarantine_rows", "DELETE FROM gate_quarantine_rows",
                    "INSERT INTO gate_quarantine_rows (reason_code, reason_text, candidate) VALUES ('X', 'y', '{}')"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.app.execute(sql)
            self.app.rollback()
        self.owner.execute("DELETE FROM gate_quarantine_rows WHERE reason_text = 'direct call'")
        self.owner.commit()

    def test_quarantine_refuses_blank_reason(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.app.execute("SELECT gate_quarantine(NULL, NULL, 'RANGE_OUT', E'\\t', '{}')")

    def test_db_refuses_tab_and_newline_only_text(self):
        """Box and door match: Python refuses whitespace-only text, and so does the database."""
        from tests_live.test_gate_checks import call_gate
        for col in ("unit", "batch", "test", "condition", "doc_id", "doc_version", "definition"):
            with self.assertRaises(psycopg.errors.IntegrityError, msg=col):
                call_gate(self.app, **{col: "\t\n"})
            self.app.rollback()
        with self.assertRaises(psycopg.errors.IntegrityError):
            call_gate(self.app, fact_id=" \n\t")
        self.app.rollback()


if __name__ == "__main__":
    unittest.main()
