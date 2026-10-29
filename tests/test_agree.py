"""Tests that the agreement check only trusts independent originals and that drift is caught."""
import unittest
from dataclasses import replace
from decimal import Decimal

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.gate.agree import ReviewItem, SingleSource, Verified, agree, drift


def fact(fid, value, doc, lineage="original", test="Assay", month=3):
    return Fact(fid, Decimal(value), "mg", "B1", test, "25C/60RH", month,
                SourcePointer(doc, "v1", "row=1"), lineage, "def")


class AgreeTests(unittest.TestCase):
    def test_decimal_point_slip_is_conflict(self):
        r = agree([fact("a", "0.14", "d1"), fact("b", "0.014", "d2")])
        self.assertIsInstance(r, ReviewItem)
        self.assertEqual(r.kind, "conflict")
        self.assertEqual(set(r.values), {Decimal("0.14"), Decimal("0.014")})
        self.assertEqual({s.doc_id for s in r.sources}, {"d1", "d2"})

    def test_original_plus_copy_is_single(self):
        self.assertIsInstance(agree([fact("a", "1.5", "d1"), fact("b", "1.5", "d2", "copy")]), SingleSource)

    def test_original_plus_unknown_is_single(self):
        self.assertIsInstance(agree([fact("a", "1.5", "d1"), fact("b", "1.5", "d2", "unknown")]), SingleSource)

    def test_same_doc_twice_is_single(self):
        self.assertIsInstance(agree([fact("a", "1.5", "d1"), fact("b", "1.5", "d1")]), SingleSource)

    def test_two_docs_equal_decimals_verified(self):
        r = agree([fact("a", "1.0", "d1"), fact("b", "1.00", "d2")])
        self.assertIsInstance(r, Verified)
        self.assertEqual(r.routes, ("d1", "d2"))

    def test_copy_with_other_value_does_not_cause_conflict(self):
        self.assertIsInstance(agree([fact("a", "1.5", "d1"), fact("b", "9.9", "d2", "copy")]), SingleSource)

    def test_mixed_keys_raise(self):
        for other in (fact("b", "1.5", "d2", test="Water"), fact("b", "1.5", "d2", month=6)):
            with self.assertRaises(ValueError):
                agree([fact("a", "1.5", "d1"), other])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            agree([])


class DriftTests(unittest.TestCase):
    def test_changed_value_is_review_item(self):
        r = drift(fact("a", "0.14", "d1"), Decimal("0.15"))
        self.assertEqual(r.kind, "source changed")
        self.assertEqual(r.values, (Decimal("0.14"), Decimal("0.15")))

    def test_same_value_none(self):
        self.assertIsNone(drift(fact("a", "0.14", "d1"), Decimal("0.140")))


if __name__ == "__main__":
    unittest.main()
