"""Planted-error tests for summary/crosscheck.py: each planted change to a COPY of the saved 2.3 output must make it FAIL on the right fact, and the clean control must PASS."""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import build, crosscheck

ROOT = Path(__file__).resolve().parent.parent
SHELF = G.stab_id("20-25C CRT", "expiry_period_proposed", "36")
LONG = G.stab_id("25C/60%RH", "study_duration_demonstrated", "36")
ST_LOW = G.stab_id("20-25C CRT", "storage_low", "36")
SPEC_DISS = G.spec_id("dissolution_av")
ASSAY_LO = "M23-STAT|25C/60%RH|Assay|min"
ASSAY_HI = "M23-STAT|25C/60%RH|Assay|max"
LABEL = G.LABEL


def _rewrite_docx(path, old, new):
    doc = Document(str(path))
    paragraphs = list(doc.paragraphs) + [p for t in doc.tables for row in t.rows for c in row.cells for p in c.paragraphs]
    hit = 0
    for p in paragraphs:
        if old in p.text:
            text = p.text.replace(old, new, 1)
            for run in p.runs[1:]:
                run.text = ""
            p.runs[0].text = text
            hit += 1
    assert hit == 1, f"{old!r} found {hit} times in the docx"
    doc.save(str(path))


class Planted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = G.collect()
        cls.base = Path(tempfile.mkdtemp()) / "run"
        build.write_run(cls.base, cls.facts)

    def copy_run(self):
        folder = Path(tempfile.mkdtemp()) / "copy"
        shutil.copytree(self.base, folder)
        return folder

    def plant(self, html=None, docx=None, place=None, swap=None):
        """A copy of the saved run with one change. html/docx = (old, new) text; place = {fact id: new placement text};
        swap = (id1, id2) exchanged in the placements and in the HTML spans."""
        folder = self.copy_run()
        if html:
            text = (folder / "M23.html").read_text(encoding="utf-8")
            assert text.count(html[0]) == 1, f"{html[0]!r} found {text.count(html[0])} times in the html"
            (folder / "M23.html").write_text(text.replace(*html), encoding="utf-8")
        if docx:
            _rewrite_docx(folder / "M23.docx", *docx)
        recs = [json.loads(x) for x in (folder / "placements.jsonl").read_text(encoding="utf-8").splitlines()]
        for r in recs:
            if place and r["id"] in place:
                r["text"] = place[r["id"]]
        if swap:
            a, b = swap
            for r in recs:
                r["id"] = b if r["id"] == a else a if r["id"] == b else r["id"]
            text = (folder / "M23.html").read_text(encoding="utf-8")
            text = text.replace(f'data-src="{a}"', "data-src=\"@@\"").replace(f'data-src="{b}"', f'data-src="{a}"').replace('data-src="@@"', f'data-src="{b}"')
            (folder / "M23.html").write_text(text, encoding="utf-8")
        (folder / "placements.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        return folder

    def failing_ids(self, result):
        return {r["fact_id"] for r in result["rows"] if r["verdict"] == "FAIL"}

    def reasons(self, result):
        return " | ".join(r["reason"] for r in result["rows"] if r["verdict"] == "FAIL")

    # ---- the clean control: it must PASS, or the failures below prove nothing ----
    def test_control_clean_output_passes(self):
        r = crosscheck.run(self.base, self.facts)
        self.assertTrue(r["passed"], self.reasons(r))
        self.assertEqual(r["counts"]["html"], {"checked": 30, "matched": 30, "failed": 0, "uncovered": 0})
        self.assertEqual(r["counts"]["docx"], {"checked": 30, "matched": 30, "failed": 0, "uncovered": 0})
        self.assertTrue(all(x["v32_saved"] and x["v32_graph"] and x["v23"] == x["v32_graph"] == x["v32_saved"] for x in r["rows"]))

    # ---- (a)-(h): each must FAIL ----
    def test_a_shelf_life_36_changed_to_24_while_p8_says_36(self):
        folder = self.plant(html=('>36</span> months when stored', '>24</span> months when stored'),
                            docx=("is 36 months when stored", "is 24 months when stored"), place={SHELF: "24"})
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {SHELF})
        self.assertIn("differs from the graph value", self.reasons(r))
        self.assertIn("differs from the saved 3.2 value", self.reasons(r))

    def test_b_storage_20_25_changed_to_15_25(self):
        folder = self.plant(html=('>20</span>°C to', '>15</span>°C to'),
                            docx=("stored at 20°C to", "stored at 15°C to"), place={ST_LOW: "15"})
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {ST_LOW})    # 15 also equals the excursion limit, but it is tied to the storage fact

    def test_c_one_spec_limit_changed_in_the_table(self):
        folder = self.plant(html=(f'data-src="{SPEC_DISS}">80</span>', f'data-src="{SPEC_DISS}">75</span>'),
                            docx=("NLT 80%", "NLT 75%"), place={SPEC_DISS: "75"})
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {SPEC_DISS})

    def test_d_right_value_tied_to_the_wrong_fact_id(self):
        # shelf life and long-term duration are both 36: the values stay right, only the ids are swapped
        folder = self.plant(swap=(SHELF, LONG))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {SHELF, LONG})
        self.assertIn("number is not at the place of this fact in the sentence", self.reasons(r))

    def test_e_right_value_wrong_unit_months_to_weeks(self):
        folder = self.plant(html=('>36</span> months when stored', '>36</span> weeks when stored'),
                            docx=("is 36 months when stored", "is 36 weeks when stored"))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertIn(SHELF, self.failing_ids(r))
        shelf = [x["reason"] for x in r["rows"] if x["fact_id"] == SHELF]
        self.assertTrue(all("unit after the number" in why for why in shelf))
        # "weeks" is one letter shorter, so the later numbers of that paragraph moved: they fail only on their offset
        others = {x["reason"] for x in r["rows"] if x["verdict"] == "FAIL" and x["fact_id"] != SHELF}
        self.assertEqual(others, {"placement offset differs"})

    def test_f_extra_number_in_prose_with_no_placement(self):
        folder = self.plant(html=("at accelerated conditions.</p>", "at accelerated conditions. See note 12.</p>"),
                            docx=("at accelerated conditions.", "at accelerated conditions. See note 12."))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertIn("number has no placement", self.reasons(r))
        self.assertTrue(any(x["number"] == "12" and x["verdict"] == "FAIL" for x in r["rows"]))

    def test_g_demo_sentence_with_the_label_removed(self):
        old = LABEL + "Assay under long-term conditions"
        folder = self.plant(html=(old, "Assay under long-term conditions"), docx=(old, "Assay under long-term conditions"))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {ASSAY_LO, ASSAY_HI})
        self.assertIn("without the demo label", self.reasons(r))

    def test_h_graph_value_changed_after_rendering_stale_2_3(self):
        stale = copy.deepcopy(self.facts)
        stale[SHELF]["value_text"] = "48"
        r = crosscheck.run(self.base, stale)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {SHELF})
        self.assertIn("differs from the graph value", self.reasons(r))

    # ---- more plants that must FAIL ----
    def test_html_changed_without_touching_the_placements(self):
        folder = self.plant(html=('>36</span> months when stored', '>24</span> months when stored'))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertIn(SHELF, self.failing_ids(r))

    def test_a_loose_digit_with_no_number_span_is_found(self):
        folder = self.plant(html=("Excursions are permitted", "Excursions (rule 7x) are permitted"),
                            docx=("Excursions are permitted", "Excursions (rule 7x) are permitted"))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])

    def test_a_fake_span_around_a_loose_number_does_not_hide_it(self):
        folder = self.plant(html=("Excursions are permitted", 'Excursions <span class="n" data-src="x">12</span> are permitted'),
                            docx=("Excursions are permitted", "Excursions 12 are permitted"))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])

    def test_a_graph_fact_that_the_saved_3_2_does_not_state_fails(self):
        r = crosscheck.run(self.base, self.facts, p8_dir=Path(tempfile.mkdtemp()))
        self.assertFalse(r["passed"])
        self.assertIn("the saved 3.2 does not state this fact", self.reasons(r))

    def test_a_fact_missing_from_the_graph_fails(self):
        thin = {k: v for k, v in self.facts.items() if k != SPEC_DISS}
        r = crosscheck.run(self.base, thin)
        self.assertFalse(r["passed"])
        self.assertEqual(self.failing_ids(r), {SPEC_DISS})

    def test_the_docx_alone_is_checked_too(self):
        folder = self.plant(docx=("NLT 80%", "NLT 75%"))
        r = crosscheck.run(folder, self.facts)
        self.assertFalse(r["passed"])
        self.assertTrue(all(x["format"] == "docx" for x in r["rows"] if x["verdict"] == "FAIL" and x["number"]))
        self.assertIn("do not hold the same numbers", " ".join(r["problems"]))

    def test_outputs_are_written_once_and_never_overwritten(self):
        folder = self.copy_run()
        r = crosscheck.run(folder, self.facts)
        crosscheck.write_outputs(r, folder)
        self.assertIn("RESULT: PASS", (folder / "summary.md").read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            crosscheck.write_outputs(r, folder)


class Independence(unittest.TestCase):
    def test_crosscheck_does_not_import_the_builder_or_the_plan(self):
        code = ("import sys, ectd_engine.summary.crosscheck\n"
                "bad = [m for m in ('ectd_engine.summary.build', 'ectd_engine.summary.plan', 'ectd_engine.graph.summary_graph') if m in sys.modules]\n"
                "print(bad)\nsys.exit(1 if bad else 0)")
        out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_crosscheck_source_names_neither_module(self):
        src = (ROOT / "ectd_engine" / "summary" / "crosscheck.py").read_text(encoding="utf-8")
        code_lines = [ln for ln in src.splitlines() if re.match(r"\s*(from|import)\s", ln)]
        for ln in code_lines:
            self.assertNotRegex(ln, r"summary\.(build|plan)|summary_graph|import build|import plan")


if __name__ == "__main__":
    unittest.main()
