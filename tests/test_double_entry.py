"""Tests that a hand-typed value is accepted only when two blind typings match, and refused otherwise."""
import json
import unittest
from pathlib import Path

from ectd_engine.facts import schema
from ectd_engine.loaders import double_entry, fda_pdf

CFG = json.loads(fda_pdf.TARGETS_PATH.read_text(encoding="utf-8"))
TARGET = CFG["targets"][0]


def enter(a, b):
    return double_entry.enter_twice(TARGET, CFG, lambda: a, lambda: b)


class TestDoubleEntry(unittest.TestCase):
    def test_match_gives_candidate(self):
        c = enter("36", "36")
        self.assertEqual(c["value"], "36")
        self.assertEqual(c["lineage"], "original")
        self.assertIn("typed twice", c["definition"])
        schema.from_json(json.dumps(c))

    def test_locator_is_typed_page_without_box(self):
        c = enter("36", "36")
        self.assertEqual(c["source"]["locator"], f"typed=page={TARGET['page']}")
        self.assertNotIn("box", c["source"]["locator"])

    def test_no_float_in_loader_source(self):
        text = Path(double_entry.__file__).read_text(encoding="utf-8")
        self.assertNotRegex(text, r"[0-9]+\.[0-9]+|float\(")

    def test_mismatch_is_refused(self):
        with self.assertRaisesRegex(double_entry.Refused, "do not match"):
            enter("0.14", "0.014")

    def test_same_number_other_spelling_matches(self):
        self.assertEqual(enter("1.0", "1")["value"], "1.0")

    def test_not_a_number_is_refused(self):
        with self.assertRaisesRegex(double_entry.Refused, "not a number"):
            enter("abc", "abc")

    def test_blank_is_refused(self):
        for a, b in (("", "36"), ("36", "  "), (None, "36")):
            with self.assertRaisesRegex(double_entry.Refused, "blank"):
                enter(a, b)

    def test_second_typing_is_not_asked_until_first_is_taken(self):
        order = []
        double_entry.enter_twice(TARGET, CFG, lambda: order.append(1) or "5", lambda: order.append(2) or "5")
        self.assertEqual(order, [1, 2])


if __name__ == "__main__":
    unittest.main()
