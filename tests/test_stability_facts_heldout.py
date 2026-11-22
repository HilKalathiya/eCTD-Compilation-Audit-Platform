"""Tests for the held-out source label rule in stability/facts.py: it matches the two allowed labels only and rejects near-misses."""
import unittest

from ectd_engine.stability import facts as F

GOOD = ["DEMO: synthetic held-out set T-065", "DEMO: synthetic held-out set T-067"]
NEAR_MISSES = [
    "DEMO: synthetic held-out set T-066",          # a withdrawn set must stay refused
    "DEMO: synthetic held-out set T-064",
    "DEMO: synthetic held-out set T-068",
    "DEMO: synthetic held-out set T-0650",
    "DEMO: synthetic held-out set T-65",
    "DEMO: synthetic held-out set T-065 extra",
    "DEMO: synthetic held-out set T-065\n",        # `$` would let this through; the pattern ends with \Z
    "DEMO: synthetic held-out set T-067\nDEMO",
    "demo: synthetic held-out set T-065",
    "DEMO: synthetic heldout set T-065",
    "XDEMO: synthetic held-out set T-065",
    "DEMO: synthetic held-out set T-065.",
]


def demo_row(source):
    return {"condition": "Cool 15C", "month": "3", "attribute": "Friability", "value": "0.3", "unit": "%", "limit": "NMT 1.0",
            "source": source, "_line": 2}


class HeldoutSourceLabel(unittest.TestCase):
    def test_the_two_allowed_labels_match(self):
        for s in GOOD:
            self.assertIsNotNone(F.HELDOUT_SOURCE.match(s), s)
            self.assertEqual(F.source_kind(s, heldout=True), "demo", s)

    def test_near_misses_do_not_match_the_pattern(self):
        for s in NEAR_MISSES:
            self.assertIsNone(F.HELDOUT_SOURCE.match(s), repr(s))

    def test_near_misses_are_refused_by_source_kind_and_check_rows(self):
        for s in NEAR_MISSES:
            if s.strip() in GOOD:
                continue   # source_kind strips outer white space first, so a bare trailing newline is the same label
            self.assertIsNone(F.source_kind(s, heldout=True), repr(s))
            self.assertEqual(F.check_rows([demo_row(s)], heldout=True), ["bad_source:line 2"], repr(s))

    def test_the_label_is_refused_unless_the_caller_asks_for_heldout(self):
        for s in GOOD:
            self.assertIsNone(F.source_kind(s), s)
            self.assertEqual(F.check_rows([demo_row(s)]), ["bad_source:line 2"])

    def test_a_good_label_with_heldout_gives_a_clean_row(self):
        for s in GOOD:
            self.assertEqual(F.check_rows([demo_row(s)], heldout=True), [])


if __name__ == "__main__":
    unittest.main()
