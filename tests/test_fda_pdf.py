"""Tests that the Kerendia PDF loader gives every fact a page and a box, and fails loudly on planted errors."""
import copy
import json
import re
import unittest

import fitz

from ectd_engine.facts import schema
from ectd_engine.gate import gate
from ectd_engine.loaders import fda_pdf

CFG = json.loads(fda_pdf.TARGETS_PATH.read_text(encoding="utf-8"))
DOC = fitz.open(fda_pdf.ROOT / CFG["pdf"])


class TestLoadedFacts(unittest.TestCase):
    def test_every_fact_has_page_and_box_inside_page(self):
        cands = fda_pdf.build(CFG, DOC)
        self.assertTrue(0 < len(cands) <= 10)
        for c in cands:
            m = re.fullmatch(r"page=(\d+);box=([\d.]+),([\d.]+),([\d.]+),([\d.]+)", c["source"]["locator"])
            self.assertIsNotNone(m, c["source"]["locator"])
            page = DOC[int(m.group(1)) - 1].rect
            x0, y0, x1, y1 = (float(g) for g in m.groups()[1:])
            self.assertTrue(0 <= x0 < x1 <= page.width and 0 <= y0 < y1 <= page.height, c["fact_id"])
            self.assertEqual(c["lineage"], "original")
            schema.from_json(json.dumps(c))  # contract holds

    def test_box_really_holds_the_expected_word(self):
        for t, c in zip(CFG["targets"], fda_pdf.build(CFG, DOC)):
            nums = re.findall(r"[\d.]+", c["source"]["locator"].split("box=")[1])
            rect = fitz.Rect(*(float(n) for n in nums))
            self.assertEqual(DOC[t["page"] - 1].get_textbox(rect).strip(), t["expected"])

    def test_values_without_a_range_rule_are_quarantined(self):
        class Conn:
            def execute(self, *a, **k): return self
            def commit(self): pass
            def rollback(self): pass
        units, ranges = gate.load_rules()
        results = fda_pdf.load(Conn(), None, CFG, DOC, (units, {}))
        self.assertTrue(all(isinstance(r, gate.Quarantined) and r.reason_code == gate.TEST_UNKNOWN for _, r in results))

    def test_all_eight_facts_pass_the_gate(self):
        class Conn:
            def execute(self, *a, **k): return self
            def commit(self): pass
            def rollback(self): pass
        results = fda_pdf.load(Conn(), None, CFG, DOC)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(isinstance(r, gate.Accepted) for _, r in results), [r for _, r in results])

    def test_pdf_has_no_blank_pages_list_is_ints(self):
        self.assertEqual(fda_pdf.no_text_pages(DOC), [])


class TestPlantedErrors(unittest.TestCase):
    def _cfg(self, **change):
        cfg = copy.deepcopy(CFG)
        cfg["targets"][0].update(change)
        return cfg

    def test_mistyped_expected_text_is_loud(self):
        with self.assertRaisesRegex(fda_pdf.NotFound, "not found at page 3"):
            fda_pdf.build(self._cfg(expected="63"), DOC)

    def test_wrong_page_is_loud(self):
        with self.assertRaisesRegex(fda_pdf.NotFound, "not found at page 4"):
            fda_pdf.build(self._cfg(page=4), DOC)

    def test_page_outside_document_is_loud(self):
        with self.assertRaisesRegex(fda_pdf.NotFound, "not found at page 999"):
            fda_pdf.build(self._cfg(page=999), DOC)

    def test_wrong_label_is_loud(self):
        with self.assertRaisesRegex(fda_pdf.NotFound, "not found at page 3"):
            fda_pdf.build(self._cfg(label=["nowhere"]), DOC)

    def test_vague_label_matching_twice_is_loud(self):
        with self.assertRaisesRegex(fda_pdf.NotFound, "found 2 times"):
            fda_pdf.build(self._cfg(page=4, expected="20", label=["dose"]), DOC)

    def test_non_number_expected_is_refused(self):
        cfg = self._cfg(expected="months", label=["shall"])
        with self.assertRaisesRegex(ValueError, "not a number"):
            fda_pdf.build(cfg, DOC)


if __name__ == "__main__":
    unittest.main()
