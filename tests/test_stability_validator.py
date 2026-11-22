"""Tests the P.8.3 validator and the mock writer: clean drafts pass, and each planted error is rejected."""
import unittest

from ectd_engine.stability import facts as F, mock_writer as W
from ectd_engine.validator import stability as V

FACTS = F.p83_facts(F.load_rows())
DRAFT = W.draft_paragraph(FACTS)
DEG = "°"


def codes(text):
    return [(r.status, r.code) for r in V.check_paragraph(text, FACTS) if r.status != "ok"]


class CleanDraft(unittest.TestCase):
    def test_mock_draft_passes(self):
        self.assertEqual(codes(DRAFT), [])
        self.assertTrue(V.paragraph_ok(DRAFT, FACTS))

    def test_draft_is_deterministic_and_has_demo_label(self):
        self.assertEqual(DRAFT, W.draft_paragraph(FACTS))
        self.assertIn("illustrative demonstration data", DRAFT)

    def test_empty_paragraph_is_not_ok(self):
        self.assertFalse(V.paragraph_ok("", FACTS))


class PlantedErrors(unittest.TestCase):
    def reject(self, bad, status):
        self.assertNotEqual(bad, DRAFT, "mutation changed nothing")
        got = codes(bad)
        self.assertTrue(got, "planted error was accepted")
        self.assertIn(status, [s for s, _ in got])
        self.assertFalse(V.paragraph_ok(bad, FACTS))

    def test_changed_demo_number(self):
        self.reject(DRAFT.replace("ranged from 99.28 to 100.00", "ranged from 99.29 to 100.00", 1), "unsupported")

    def test_changed_count(self):
        self.reject(DRAFT.replace("over 8 time points", "over 9 time points", 1), "unsupported")

    def test_changed_storage_number(self):
        self.reject(DRAFT.replace("20" + DEG + "C to 25" + DEG + "C", "20" + DEG + "C to 30" + DEG + "C", 1), "unsupported")

    def test_changed_excursion_number(self):
        self.reject(DRAFT.replace("from 15" + DEG, "from 10" + DEG, 1), "unsupported")

    def test_claim_48_months(self):
        self.reject(DRAFT.replace("shelf life is 36 months", "shelf life is 48 months", 1), "unsupported")

    def test_claim_48_months_new_sentence(self):
        self.reject(DRAFT + " The shelf life is 48 months.", "unrecognised")

    def test_dropped_demo_label(self):
        bad = DRAFT.replace("In illustrative demonstration data, ", "", 1)
        self.reject(bad, "demo_unlabelled")

    def test_no_significant_change_without_fact(self):
        self.reject(DRAFT + " No significant change was observed.", "unsupported")

    def test_no_significant_change_with_fact_is_allowed(self):
        facts = dict(FACTS, no_significant_change=True)
        r = V.check_sentence("No significant change was observed.", facts)
        self.assertEqual(r.status, "ok")

    def test_unknown_sentence_is_unrecognised(self):
        self.reject(DRAFT + " The product is very stable.", "unrecognised")

    def test_unknown_condition_name(self):
        self.reject(DRAFT.replace("at 25C/60%RH ranged", "at 5C/60%RH ranged", 1), "unrecognised")

    def test_outside_limit_claim_without_fact(self):
        bad = DRAFT.replace("had none of its 8 results outside the limit", "had 2 of its 8 results outside the limit", 1)
        self.reject(bad, "unsupported")


if __name__ == "__main__":
    unittest.main()
