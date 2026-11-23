"""Planted-error tests for the closed citation list: a number hidden in a guideline-shaped token must FAIL in the 2.3 crosscheck, the P.8.3 validator and the P.5 digit check."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from docx import Document

from ectd_engine.graph import summary_graph as G
from ectd_engine.references import registry as R
from ectd_engine.render.numbers import find_numbers, uncovered_digits
from ectd_engine.stability import facts as F, mock_writer as W
from ectd_engine.summary import build, crosscheck
from ectd_engine.validator import stability as V
from ectd_engine.validator import validator as VV

ANCHOR = "at accelerated conditions."
HIDDEN = ["per Q48.", "ICH Q36 applies.", "(see 36.0.P.8)", "Q3B(R7)", "3.2.P.8.9", "Q1A(R2)36", "Q 36"]
CITATIONS = ["ICH Q1A(R2)", "Q3B(R2)", "section 3.2.P.8.3", "2.3.P.5"]
FACTS = F.p83_facts(F.load_rows())
DRAFT = W.draft_paragraph(FACTS)


def _append_to_docx(path, old, new):
    doc = Document(str(path))
    hit = 0
    for p in doc.paragraphs:
        if old in p.text:
            text = p.text.replace(old, new, 1)
            for run in p.runs[1:]:
                run.text = ""
            p.runs[0].text = text
            hit += 1
    assert hit == 1, f"{old!r} found {hit} times"
    doc.save(str(path))


def digit_left(text):
    """The digit test the placeholder validators (validator, batch, spec) run: citations removed, then any digit left?"""
    return bool(re.search(r"\d", VV.ALLOWED_TOKENS.sub(" ", VV.PLACEHOLDER.sub(" ", text))))


class Hidden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = G.collect()
        cls.base = Path(tempfile.mkdtemp()) / "run"
        build.write_run(cls.base, cls.facts)

    def crosscheck(self, sentence):
        folder = Path(tempfile.mkdtemp()) / "copy"
        shutil.copytree(self.base, folder)
        html = (folder / "M23.html").read_text(encoding="utf-8")
        assert html.count(ANCHOR + "</p>") == 1
        (folder / "M23.html").write_text(html.replace(ANCHOR + "</p>", f"{ANCHOR} {sentence}</p>"), encoding="utf-8")
        _append_to_docx(folder / "M23.docx", ANCHOR, f"{ANCHOR} {sentence}")
        return crosscheck.run(folder, self.facts)

    def test_control_unchanged_copy_passes(self):
        folder = Path(tempfile.mkdtemp()) / "copy"
        shutil.copytree(self.base, folder)
        self.assertTrue(crosscheck.run(folder, self.facts)["passed"])

    def assert_hidden_fails_everywhere(self, sentence):
        r = self.crosscheck(sentence)
        self.assertFalse(r["passed"], sentence)
        self.assertTrue(any(x["verdict"] == "FAIL" and x["fact_id"].startswith("unplaced:") for x in r["rows"]), sentence)
        self.assertFalse(V.paragraph_ok(DRAFT + " " + sentence, FACTS), sentence)           # P.8.3 validator
        self.assertTrue(re.search(r"\d", re.sub(r"\[\[.*?\]\]", " ", sentence)))             # sanity: it does hold a digit
        self.assertTrue(find_numbers(sentence) and uncovered_digits(sentence, []), sentence)  # P.5 digit checks
        self.assertTrue(digit_left(sentence), sentence)                                       # placeholder validators' digit check

    def test_hidden_per_q48(self):
        self.assert_hidden_fails_everywhere(HIDDEN[0])

    def test_hidden_ich_q36(self):
        self.assert_hidden_fails_everywhere(HIDDEN[1])

    def test_hidden_section_36_0_p_8(self):
        self.assert_hidden_fails_everywhere(HIDDEN[2])

    def test_hidden_q3b_r7(self):
        self.assert_hidden_fails_everywhere(HIDDEN[3])

    def test_hidden_section_3_2_p_8_9(self):
        self.assert_hidden_fails_everywhere(HIDDEN[4])

    def test_hidden_glued_q1a_r2_36(self):
        self.assert_hidden_fails_everywhere(HIDDEN[5])

    def test_hidden_q_space_36(self):
        self.assert_hidden_fails_everywhere(HIDDEN[6])

    def test_brain_case_shelf_life_48_is_one_unplaced_row_and_the_30_real_numbers_still_match(self):
        r = self.crosscheck("a shelf life of 48 months is supported")
        bad = [x for x in r["rows"] if x["verdict"] == "FAIL" and x["format"] == "html"]
        self.assertEqual([(x["fact_id"], x["number"]) for x in bad], [("unplaced:48", "48")])
        self.assertEqual(sum(1 for x in r["rows"] if x["format"] == "html" and x["verdict"] == "MATCH"), 30)
        self.assertEqual(sum(1 for x in r["rows"] if x["format"] == "docx" and x["verdict"] == "MATCH"), 30)

    # ---- real citations still pass ----
    def check_citation(self, sentence):
        self.assertEqual(find_numbers(sentence), [], sentence)
        self.assertEqual(uncovered_digits(sentence, []), [], sentence)
        self.assertFalse(digit_left(sentence), sentence)
        r = self.crosscheck(sentence)
        self.assertTrue(r["passed"], [x for x in r["rows"] if x["verdict"] == "FAIL"])

    def test_pass_ich_q1a_r2(self):
        self.check_citation(CITATIONS[0])

    def test_pass_q3b_r2(self):
        self.check_citation(CITATIONS[1])

    def test_pass_section_3_2_p_8_3(self):
        self.check_citation(CITATIONS[2])

    def test_pass_2_3_p_5(self):
        self.check_citation(CITATIONS[3])


class RegistryIsFullMatchOnly(unittest.TestCase):
    def test_prefix_and_suffix_tricks_are_not_exempt(self):
        for text in ("Q1", "Q100", "Q101", "Q140", "Q10x", "Q1A(R2)3", "3.2.P.8.30", "3.2.P.8.3.1", "13.2.P.8.3", "Q1E5"):
            self.assertTrue(find_numbers(text), text)           # a digit is left over, so it must be placed
            self.assertTrue(uncovered_digits(text, []), text)
        for text in ("Q10", "Q14", "Q1E", "3.2.P.8.3"):
            self.assertEqual(find_numbers(text), [], text)

    def test_every_entry_is_a_whole_token_and_nothing_else_matches(self):
        for tok in R.registry():
            m = R.ALLOWED_TOKENS.search(tok)
            self.assertTrue(m and m.group(0) == tok, tok)
        self.assertNotIn("Q1", R.registry())
        self.assertIn("Q3B(R2)", R.registry())
        self.assertIn("3.2.P.8.3", R.registry())
        self.assertIn("2.3.P.8", R.registry())

    def test_sections_come_from_the_plans(self):
        from ectd_engine.render.plan import CONTENT_PLAN
        from ectd_engine.summary.plan import SUMMARY_PLAN
        reg = set(R.registry())
        self.assertTrue(set(CONTENT_PLAN) <= reg and set(SUMMARY_PLAN) <= reg)

    def test_the_old_shapes_are_gone(self):
        src = (Path(__file__).resolve().parent.parent / "ectd_engine" / "validator" / "validator.py").read_text(encoding="utf-8")
        self.assertNotIn(r"Q\d+", src)


if __name__ == "__main__":
    unittest.main()
