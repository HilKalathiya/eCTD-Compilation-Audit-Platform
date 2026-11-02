"""Tests for the double-entry Q3B threshold table: the real files load, and every planted error is refused."""
import shutil
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from ectd_engine.db import migrate, postgres
from ectd_engine.knowledge import cite
from ectd_engine.rules import q3b
from tests.test_migrate import require_database


def real():
    return q3b.load()


class CopyCase(unittest.TestCase):
    """Works on temporary copies of the two entry files (the real ones are never touched)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.a = self.tmp / "a.csv"
        self.b = self.tmp / "b.csv"
        shutil.copy(q3b.ENTRY_A, self.a)
        shutil.copy(q3b.ENTRY_B, self.b)

    def edit(self, path, old, new):
        text = path.read_bytes().decode("utf-8")
        self.assertIn(old, text)
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

    def refused(self, *needles):
        with self.assertRaises(q3b.Q3BRefused) as cm:
            q3b.load(self.a, self.b)
        for n in needles:
            self.assertIn(n, str(cm.exception))


class RealFilesTests(unittest.TestCase):
    def test_loads_ten_rows(self):
        t = real()
        self.assertEqual(len(t.rows), 10)
        self.assertEqual({r.kind for r in t.rows}, set(q3b.KINDS))

    def test_every_source_quote_verifies_on_page_11(self):
        for r in real().rows:
            c = cite.verify("Q3B_R2", 11, r.source_quote)
            self.assertEqual(c.page, 11, r.rule_id)

    def test_boundaries_exactly_as_printed(self):
        t = real()
        cases = [  # (kind, dose mg, percent, tdi_ug)
            ("reporting", "0.001", "0.1", None), ("reporting", "1000", "0.1", None), ("reporting", "1000.001", "0.05", None),
            ("identification", "0.999", "1.0", "5"), ("identification", "1", "0.5", "20"), ("identification", "10", "0.5", "20"),
            ("identification", "10.001", "0.2", "2000"), ("identification", "2000", "0.2", "2000"),
            ("identification", "2000.001", "0.10", None),
            ("qualification", "9.999", "1.0", "50"), ("qualification", "10", "0.5", "200"), ("qualification", "100", "0.5", "200"),
            ("qualification", "100.001", "0.2", "3000"), ("qualification", "2000", "0.2", "3000"),
            ("qualification", "2000.001", "0.15", None),
        ]
        for kind, dose, pct, tdi in cases:
            got = q3b.threshold(kind, dose, table=t)
            self.assertEqual(got[0], D(pct), (kind, dose))
            self.assertEqual(got[1], None if tdi is None else D(tdi), (kind, dose))
            self.assertTrue(got[2].startswith("Q3B_R2@"))

    def test_percent_keeps_printed_digits(self):
        self.assertEqual(str(q3b.threshold("identification", "5000", table=real())[0]), "0.10")

    def test_float_and_bad_dose_refused(self):
        with self.assertRaises(TypeError):
            q3b.threshold("reporting", 1.5, table=real())
        with self.assertRaises(ValueError):
            q3b.threshold("reporting", "0", table=real())


class PlantedErrorTests(CopyCase):
    def test_copies_agree_loads(self):
        self.assertEqual(len(q3b.load(self.a, self.b).rows), 10)

    def test_row_only_in_a_refused(self):
        with open(self.a, "ab") as f:
            f.write("\nqualification,> 5 g,0.15,\n".encode("utf-8"))
        self.refused("row only in entry_a", "> 5 g")

    def test_row_only_in_b_refused(self):
        self.edit(self.a, "reporting,> 1 g,0.05,\n", "")
        self.refused("row only in entry_b")

    def test_percent_0_1_vs_0_15_refused(self):
        self.edit(self.b, "reporting,≤ 1 g,0.1,", "reporting,≤ 1 g,0.15,")
        self.refused("percent", "'0.1'", "'0.15'")

    def test_less_equal_vs_less_refused(self):
        self.edit(self.b, "≤ 1 g", "< 1 g")
        self.refused("row only in entry_a", "row only in entry_b")

    def test_tdi_difference_refused(self):
        self.edit(self.b, "5 µg", "50 µg")
        self.refused("tdi")

    def test_wrong_value_in_both_copies_fails_the_pdf_check(self):
        # Both people make the same typo: the copies agree, but the PDF does not say it.
        self.edit(self.a, "reporting,≤ 1 g,0.1,", "reporting,≤ 1 g,0.2,")
        self.edit(self.b, "reporting,≤ 1 g,0.1,", "reporting,≤ 1 g,0.2,")
        self.refused("does not verify")

    def test_edited_entry_b_after_load_refused(self):
        t = q3b.load(self.a, self.b)
        q3b.threshold("reporting", "1", table=t)
        self.edit(self.b, "0.15", "0.16")
        with self.assertRaises(q3b.Q3BRefused) as cm:
            q3b.threshold("reporting", "1", table=t)
        self.assertIn("changed after it was loaded", str(cm.exception))

    def test_dropped_row_in_both_copies_refused(self):
        for p in (self.a, self.b):
            text = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
            p.write_bytes(text.replace("qualification,10 mg - 100 mg,0.5,200 µg\n", "").encode("utf-8"))
        self.refused("does not verify")

    def test_gap_between_ranges_refused(self):
        from dataclasses import replace
        rows = list(real().rows)
        i = next(n for n, r in enumerate(rows) if r.kind == "reporting" and r.dose_low_mg is not None)
        q3b._check_partition(rows)  # the real table is fine
        rows[i] = replace(rows[i], low_incl=True)  # 1 g would now be in two rows
        with self.assertRaises(q3b.Q3BRefused):
            q3b._check_partition(rows)
        rows[i] = replace(rows[i], low_incl=False, dose_low_mg=D("1001"))  # doses just above 1 g in no row
        with self.assertRaises(q3b.Q3BRefused):
            q3b._check_partition(rows)

    def test_bad_header_refused(self):
        self.edit(self.a, "kind,max_daily_dose", "kind,dose")
        self.refused("header")


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        require_database()
        migrate.migrate()
        self.conn = postgres.connect()
        self.addCleanup(self.conn.close)

    def test_store_and_read_back_same_answers(self):
        t = real()
        q3b.store(t, self.conn)
        q3b.store(t, self.conn)  # second time is a no-op
        db = q3b.table_from_db(self.conn)
        self.assertEqual(len(db.rows), 10)
        for kind, dose in (("reporting", "1000"), ("identification", "10"), ("qualification", "2000.001")):
            self.assertEqual(q3b.threshold(kind, dose, table=db), q3b.threshold(kind, dose, table=t))

    def test_rows_cannot_be_changed_or_deleted(self):
        q3b.store(real(), self.conn)
        for sql in ("UPDATE rule_thresholds SET percent = 9", "DELETE FROM rule_thresholds"):
            with self.assertRaises(Exception) as cm:
                self.conn.execute(sql)
            self.assertIn("append-only", str(cm.exception))
            self.conn.rollback()

    def test_same_version_with_other_content_refused(self):
        t = real()
        q3b.store(t, self.conn)
        from dataclasses import replace
        changed = q3b.Table((replace(t.rows[0], percent=D("0.2")),) + t.rows[1:])
        with self.assertRaises(q3b.Q3BRefused):
            q3b.store(changed, self.conn)


if __name__ == "__main__":
    unittest.main()
