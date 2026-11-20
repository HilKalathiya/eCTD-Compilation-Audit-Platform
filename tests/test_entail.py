"""Tests for the claim checker: unsupported claims are flagged, supported ones are not, and the Word re-read tool is planted-error tested."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from ectd_engine.review.entail import entail, sentences, stored_quotes
from tools import reread_export

CLEAN = {"n_outside": "0", "n_batches": "12"}
BAD = {"n_outside": "3", "n_batches": "12"}


class EntailTests(unittest.TestCase):
    def test_planted_no_new_signals_is_flagged(self):
        self.assertEqual(entail("No new signals were observed.", CLEAN), ["unsupported:no new signals"])

    def test_planted_all_results_complied_with_results_outside_is_flagged(self):
        self.assertEqual(entail("All results complied.", BAD), ["unsupported:all results"])

    def test_true_claims_are_not_flagged(self):
        self.assertEqual(entail("All results complied.", CLEAN), [])
        self.assertEqual(entail("No result was outside the limit.", CLEAN), [])
        self.assertEqual(entail("3 of 12 results were outside the limit.", BAD), [])

    def test_a_claim_with_no_fact_is_flagged_not_passed(self):
        self.assertEqual(entail("No result was outside the limit.", {}), ["unsupported:no result"])
        self.assertEqual(entail("The batches are consistent.", CLEAN), ["unsupported:consistent"])

    def test_wrong_count_is_flagged(self):
        self.assertEqual(entail("2 of 12 results were outside the limit.", BAD), ["unsupported:outside"])

    def test_sentences_without_claim_words_are_ignored_and_only_a_stored_quote_is_skipped(self):
        self.assertEqual(entail("Results for 12 batches were measured. Mean was 90%.", CLEAN), [])
        said = "The source says “results must stay within 80”."
        self.assertEqual(entail(said, {}, quotes=["results must stay within 80"]), [])   # exactly a stored quote
        self.assertEqual(entail(said, {}, quotes=["something else"]), ["unsupported:within"])
        self.assertTrue(stored_quotes())   # the real Q3B rows load, so real quotes can be skipped

    def test_only_the_unsupported_sentence_is_flagged(self):
        text = "No result was outside the limit. Impurities are stable."
        self.assertEqual(entail(text, CLEAN), ["unsupported:stable"])
        self.assertEqual(sentences("Mean was 0.7% overall. Next."), ["Mean was 0.7% overall.", "Next."])


RANGE = {"n_outside": "0", "n_batches": "12", "min_value": "84.33", "max_value": "97.33"}

# 20 different bad sentences: none is backed by a fact in RANGE (or in BAD), so every one must be flagged.
OVERCLAIMS = [
    "All batches passed.",
    "The batches passed testing.",
    "There was no OOS result.",
    "No OOS results were found.",
    "No results were out of specification.",
    "Every result stayed below the limit.",
    "Results were above the limit.",
    "Two results exceed the limit.",
    "The method is robust.",
    "The process is suitable for routine use.",
    "The profile is acceptable.",
    "There are no issues.",
    "There are no concerns with the data.",
    "No new signals were observed.",
    "The data show no trend.",
    "The batches are comparable.",
    "Stability is consistent over time.",
    "The product complies with the specification.",
    "The method “complies” with the guideline.",
    "Results ranged from 80.00% to 99.00%.",
]
TRUE_SENTENCES = [
    "Results for 12 batches ranged from 84.33% to 97.33%.",
    "The results were within the range 84.33–97.33%.",
    "No result was outside the limit.",
    "All results complied.",
    "The highest result was 97.33% (Batch 26) and the lowest result was 84.33% (Batch 105).",
]


class OverclaimTests(unittest.TestCase):
    def test_all_20_overclaims_are_flagged(self):
        self.assertEqual(len(OVERCLAIMS), 20)
        self.assertEqual(len(set(OVERCLAIMS)), 20)
        for facts in (RANGE, BAD, {}):
            for s in OVERCLAIMS:
                with self.subTest(sentence=s, facts=sorted(facts)):
                    self.assertTrue(entail(s, facts), s)

    def test_5_true_sentences_are_not_flagged(self):
        self.assertEqual(len(TRUE_SENTENCES), 5)
        for s in TRUE_SENTENCES:
            with self.subTest(sentence=s):
                self.assertEqual(entail(s, RANGE), [])

    def test_range_rule_needs_the_placed_min_and_max(self):
        self.assertEqual(entail("Results ranged from 84.33% to 97.34%.", RANGE), ["unsupported:ranged"])
        self.assertEqual(entail("Results were within the range 84.30–97.33%.", RANGE), ["unsupported:within"])
        self.assertEqual(entail("Results ranged from 84.33% to 97.33%.", {}), ["unsupported:ranged"])
        self.assertEqual(entail("A range of 0.05%.", {"min_value": "0.05", "max_value": "0.05"}), [])
        self.assertEqual(entail("A range of 0.05%.", {"min_value": "0.05", "max_value": "0.09"}), ["unsupported:range"])

    def test_a_quoted_claim_is_checked_unless_it_is_the_stored_quote(self):
        self.assertEqual(entail("It says “complies”.", RANGE, quotes=[]), ["unsupported:complies"])
        self.assertEqual(entail("It says “complies”.", RANGE, quotes=["complies"]), [])


class RereadToolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "P5.docx"
        self.placed = [{"id": "limit", "section": "S/j", "text": "80"}, {"id": "min_value", "section": "S/j", "text": "84.33"},
                       {"id": "max_value", "section": "S/j", "text": "97.33"}]
        self.para = ("The acceptance criterion is not less than 80%. Results ranged from 84.33% to 97.33%. "
                     "No result was outside the limit.")

    def write(self, para):
        doc = Document()
        doc.add_paragraph(para)
        doc.save(str(self.path))

    def test_clean_paragraph_has_no_flag_and_numbers_match(self):
        self.write(self.para)
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual((rep["problems"], rep["flags"]), ([], []))
        self.assertEqual(rep["numbers"], 3)

    def test_planted_unsupported_sentence_is_flagged(self):
        self.write(self.para + " No new signals were observed.")
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual([f["flag"] for f in rep["flags"]], ["unsupported:no new signals"])

    def test_planted_claim_contradicted_by_the_stored_numbers_is_flagged(self):
        self.placed[1]["text"] = "79.5"   # lowest result is below the NLT 80 limit, so "no result outside" is false
        self.write(self.para.replace("84.33", "79.5"))
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual([f["flag"] for f in rep["flags"]], ["unsupported:no result"])

    def test_planted_changed_number_is_caught(self):
        self.write(self.para.replace("84.33", "84.34"))
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual(rep["problems"], ["changed number #1: file has '84.34', placement says '84.33'"])


if __name__ == "__main__":
    unittest.main()
