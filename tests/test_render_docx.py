"""Tests for the Word writer: same content as the HTML, and the saved .docx is re-read and caught if anyone changes it."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from ectd_engine.render.docx import build_docx, reread
from ectd_engine.render.html import build_document, build_p54, build_p56
from tests.test_render import TASK54, TASK56, TEXT54, TEXT56, facts54, facts56


def items():
    facts, flags, _, table = facts54()
    f56, fl56 = facts56()
    return [
        {"part": "3.2.P.5.6", "task_id": "t1", "attribute": "Dissolution", "batch_ids": [],
         "sections": build_p56(TASK56, f56, fl56, TEXT56)},
        {"part": "3.2.P.5.4", "task_id": "b1", "attribute": "Dissolution", "batch_ids": ["26", "105"],
         "sections": build_p54(TASK54, facts, flags, table, TEXT54)},
    ]


class DocxTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "P5.docx"
        self.built = build_docx(items(), self.path)

    def edit(self, fn):
        """Open the saved file, let fn change it, save it back (a person editing the Word file)."""
        doc = Document(str(self.path))
        fn(doc)
        doc.save(str(self.path))

    def test_clean_file_numbers_equal_placements(self):
        rep = reread(self.path, self.built)
        self.assertEqual(rep["problems"], [])
        self.assertEqual(rep["numbers"], rep["placements"])
        self.assertGreater(rep["numbers"], 0)
        self.assertEqual((rep["uncovered"], rep["missing"]), (0, 0))

    def test_same_placements_as_the_html(self):
        _, records, report = build_document(items())
        self.assertEqual(self.built["records"], records)
        self.assertEqual(reread(self.path, self.built)["numbers"], report["numbers"])

    def test_headings_come_from_the_plan_in_plan_order_and_the_table_is_a_real_table(self):
        doc = Document(str(self.path))
        heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
        self.assertLess(heads.index("3.2.P.5.4 Batch analyses"), heads.index("3.2.P.5.6 Justification of specification"))
        self.assertEqual(len(doc.tables), 1)
        self.assertEqual([c.text for c in doc.tables[0].rows[0].cells], ["Batch", "Value", "Unit"])
        self.assertEqual(len(doc.tables[0].rows), 3)   # header + batches 26 and 105

    def test_planted_changed_number_in_a_paragraph_is_caught(self):
        def change(doc):
            p = next(p for p in doc.paragraphs if "84.33" in p.text)   # the P.5.6 paragraph
            p.runs[0].text = p.runs[0].text.replace("84.33", "84.34")
        self.edit(change)
        self.assertTrue(any("changed number" in x for x in reread(self.path, self.built)["problems"]))

    def test_planted_changed_number_in_a_table_cell_is_caught(self):
        def change(doc):
            doc.tables[0].rows[1].cells[1].paragraphs[0].runs[0].text = "97.34"
        self.edit(change)
        self.assertTrue(any("changed number" in x for x in reread(self.path, self.built)["problems"]))

    def test_planted_deleted_table_row_is_caught(self):
        def drop(doc):
            row = doc.tables[0].rows[2]._tr
            row.getparent().remove(row)
        self.edit(drop)
        problems = reread(self.path, self.built)["problems"]
        self.assertTrue(any(x.startswith("numbers!=placements") for x in problems))
        self.assertTrue(any(x.startswith("table rows") for x in problems))

    def test_planted_bare_number_is_caught(self):
        self.edit(lambda doc: doc.add_paragraph("About 0.7% was lost."))
        rep = reread(self.path, self.built)
        self.assertEqual(rep["numbers"], rep["placements"] + 1)
        self.assertTrue(any(x.startswith("numbers!=placements") for x in rep["problems"]))

    def test_planted_digits_the_number_finder_misses_are_caught(self):
        # the finder reads "5" but not the superscript two, so only the second (digit by digit) check can see it
        self.edit(lambda doc: doc.add_paragraph("Lost 5² units."))
        rep = reread(self.path, self.built)
        self.assertEqual(rep["uncovered"], 1)
        self.assertEqual([x for x in rep["problems"] if x.startswith("uncovered:")], ["uncovered:Lost 5² units."])

    def test_planted_batch_id_not_on_the_list_is_caught(self):
        # a listed batch id (26) in text is exempt: only the text change shows, no number problem
        self.edit(lambda doc: doc.add_paragraph("Batch 26 was retested."))
        self.assertEqual(reread(self.path, self.built)["problems"], ["text differs from what was written"])
        # an id that is not on the list (99) is a number nobody placed
        self.edit(lambda doc: doc.paragraphs[-1].runs[0].__setattr__("text", "Batch 99 was retested."))
        self.assertEqual(reread(self.path, self.built)["problems"],
                         ["numbers!=placements: 12 in file, 11 placed", "text differs from what was written"])

    def test_a_rejected_section_is_left_out_and_counted(self):
        f, fl = facts56()
        del f["limit"]
        bad = [{"part": "3.2.P.5.6", "task_id": "t1", "attribute": "Dissolution", "batch_ids": [],
                "sections": build_p56(TASK56, f, fl, TEXT56)}]
        built = build_docx(bad, self.path)
        rep = reread(self.path, built)
        self.assertEqual((rep["placements"], rep["missing"]), (0, 1))
        self.assertEqual(rep["problems"], [])


if __name__ == "__main__":
    unittest.main()
