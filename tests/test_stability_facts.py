"""Tests for the stability facts: hand-checked numbers, plus planted errors that must be caught."""
import unittest
from decimal import Decimal

from ectd_engine.stability import facts

D = Decimal
DEMO = "DEMO: redacted (b)(4) in ChemR p.7"
PUBLIC = "FDA ChemR 215341 p.5"


def row(month, value, source=DEMO, attribute="Assay", condition="25C/60%RH", limit="95.0-105.0", line=2):
    return {"condition": condition, "month": str(month), "attribute": attribute, "value": value,
            "unit": "% label claim", "limit": limit, "source": source, "_line": line}


SAMPLE = [row(0, "100.00", line=2), row(3, "99.94", line=3), row(6, "99.88", line=4)]


class FactsOnSample(unittest.TestCase):
    def test_hand_checked_sample(self):
        f = facts.compute_facts(SAMPLE)[("25C/60%RH", "Assay")]
        self.assertEqual(f.n, 3)
        self.assertEqual(f.months, (0, 3, 6))
        self.assertEqual(f.min, D("99.88"))
        self.assertEqual(f.max, D("100.00"))
        self.assertEqual(f.last, D("99.88"))
        self.assertEqual(f.n_outside, 0)
        self.assertEqual(f.n_demo, 3)

    def test_last_is_latest_month_even_if_rows_are_shuffled(self):
        f = facts.compute_facts(list(reversed(SAMPLE)))[("25C/60%RH", "Assay")]
        self.assertEqual(f.last, D("99.88"))

    def test_values_are_decimal(self):
        f = facts.compute_facts(SAMPLE)[("25C/60%RH", "Assay")]
        self.assertIsInstance(f.min, Decimal)
        self.assertIsInstance(f.last, Decimal)

    def test_limit_forms(self):
        self.assertEqual(facts.parse_limit("NMT 0.50"), (None, D("0.50")))
        self.assertEqual(facts.parse_limit("NLT 80"), (D("80"), None))
        self.assertIsNone(facts.parse_limit(""))

    def test_planted_wrong_value_changes_the_facts(self):
        bad = SAMPLE[:2] + [row(6, "88.88", line=4)]
        f = facts.compute_facts(bad)[("25C/60%RH", "Assay")]
        self.assertNotEqual(f.min, D("99.88"))   # the hand-checked min no longer matches
        self.assertEqual(f.n_outside, 1)


class PlantedErrors(unittest.TestCase):
    def test_clean_sample_has_no_problems(self):
        self.assertEqual(facts.check_rows(SAMPLE), [])

    def test_planted_value_outside_limit_is_caught(self):
        bad = SAMPLE[:2] + [row(6, "120.00", line=4)]
        self.assertIn("demo_outside_limit:line 4", facts.check_rows(bad))

    def test_demo_row_labelled_public_is_caught(self):
        bad = SAMPLE[:2] + [row(6, "99.88", source=PUBLIC, line=4)]
        self.assertIn("demo_as_public:line 4", facts.check_rows(bad))

    def test_public_fact_labelled_demo_is_caught(self):
        r = row(36, "36", attribute="expiry_period_proposed", limit="", source=DEMO, line=9)
        self.assertIn("public_as_demo:line 9", facts.check_rows([r]))

    def test_missing_source_is_caught(self):
        self.assertIn("no_source:line 4", facts.check_rows(SAMPLE[:2] + [row(6, "99.88", source="", line=4)]))

    def test_mixed_label_is_caught(self):
        r = row(6, "99.88", source=PUBLIC + " DEMO", line=4)
        self.assertIn("bad_source:line 4", facts.check_rows([r]))

    def test_demo_without_limit_is_caught(self):
        self.assertIn("demo_no_limit:line 4", facts.check_rows([row(6, "99.88", limit="", line=4)]))


class RealCsv(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = facts.load_rows()

    def test_every_row_has_a_source(self):
        for r in self.rows:
            self.assertTrue(r["source"].strip(), "row without source at line %s" % r["_line"])

    def test_csv_has_no_problems(self):
        self.assertEqual(facts.check_rows(self.rows), [])

    def test_public_and_demo_counts(self):
        self.assertEqual(facts.count_sources(self.rows), (4, 60))

    def test_hand_checked_real_facts(self):
        all_facts = facts.compute_facts(self.rows)
        f = all_facts[("40C/75%RH", "Degradation product")]
        self.assertEqual((f.n, f.months, f.min, f.max, f.last), (4, (0, 1, 3, 6), D("0.050"), D("0.170"), D("0.170")))
        f = all_facts[("25C/60%RH", "Assay")]
        self.assertEqual((f.n, f.last, f.n_outside, f.n_demo), (8, D("99.28"), 0, 8))
        f = all_facts[("25C/60%RH", "study_duration_demonstrated")]
        self.assertEqual((f.n, f.last, f.n_demo), (1, D("36"), 0))


if __name__ == "__main__":
    unittest.main()
