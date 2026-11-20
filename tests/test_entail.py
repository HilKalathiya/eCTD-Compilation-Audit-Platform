"""Tests for the claim gate: a sentence that fits no known writer shape is flagged, a shape with wrong facts is flagged, true sentences pass."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from ectd_engine.review.entail import entail, sentences, stored_quotes
from tools import reread_export

F = {"n_batches": "12", "min_value": "84.33", "max_value": "97.33", "mean_value": "90.46", "n_excluded": "2",
     "limit": "80", "limit_kind": "NLT", "n_outside": "0"}
BAD = dict(F, n_outside="3")

# every sentence form the writer produces, true for F
TRUE_SENTENCES = [
    "Batch analysis results for dissolution of Lek tablets are presented below for 12 batches.",
    "Results for 2 batches (Batches 169 and 171) are shown as excluded (quarantined).",
    "Results for 12 batches ranged from 84.33% (Batch 105) to 97.33% (Batch 26).",
    "Dissolution results for 12 batches showed a range from 84.33% to 97.33%, with a mean of 90.46%.",
    "Residual solvent for 12 batches was found to be within the range 84.33–97.33%, with a mean of 90.46%.",
    "The highest result was 97.33% (Batch 26) and the lowest result was 84.33% (Batch 105).",
    "Results for 2 batches, Batches 169 and 171, were quarantined and are not included.",
    "The acceptance criterion for Dissolution is not less than 80%, which is declared by the author for this demonstration, with no public source.",
    "No result was outside the limit.",
]
# the five true sentences of T-058, checked here against facts that do NOT back them (they must be flagged)
T058_FIVE = [
    "Results for 12 batches ranged from 84.33% to 97.33%.",
    "The results were within the range 84.33–97.33%.",
    "No result was outside the limit.",
    "All results complied.",
    "The highest result was 97.33% (Batch 26) and the lowest result was 84.33% (Batch 105).",
]
OVERCLAIMS = [
    "All batches passed.", "The batches passed testing.", "There was no OOS result.", "No OOS results were found.",
    "No results were out of specification.", "Every result stayed below the limit.", "Results were above the limit.",
    "Two results exceed the limit.", "The method is robust.", "The process is suitable for routine use.",
    "The profile is acceptable.", "There are no issues.", "There are no concerns with the data.", "No new signals were observed.",
    "The data show no trend.", "The batches are comparable.", "Stability is consistent over time.",
    "The product complies with the specification.", "The method “complies” with the guideline.",
    "Results ranged from 80.00% to 99.00%.",
]
OWN_PHRASING = [
    "Dissolution is within specification for all batches.",
    "Results for 12 batches ranged from 84.33% to 97.33%, which is acceptable.",
    "Results for 12 batches ranged from 84.33% to 97.33% and no trend was seen.",
    "Robust results for 12 batches ranged from 84.33% to 97.33%.",
    "All 12 batches met the acceptance criterion.",
    "The product remains stable throughout the study.",
    "No out-of-specification results were recorded.",
    "The mean of the results was 90.46%, well within limits.",
    "Results for 12 batches were reviewed and found satisfactory.",
    "The batches are representative of commercial production.",
    "Quality is assured by the declared specification.",
]
Q = "10 mg - 40 mg 0.15% or 1 µg TDI, whichever is lower"
Q3B = ("The acceptance criterion for Impurity O is not more than 0.15%, set at the ICH Q3B(R2) qualification threshold for an assumed "
       "maximum daily dose of 40 mg: “{}” (ICH Q3B(R2), Step 4 2006-06-02, page 7).")
Q3B_FACTS = {"limit": "0.15", "mdd": "40", "limit_kind": "NMT"}


class ShapeGateTests(unittest.TestCase):
    def test_every_true_sentence_passes(self):
        for s in TRUE_SENTENCES:
            with self.subTest(sentence=s):
                self.assertEqual(entail(s, F), [])

    def test_all_overclaims_are_flagged_with_any_facts(self):
        self.assertEqual((len(OVERCLAIMS), len(set(OVERCLAIMS))), (20, 20))
        for facts in (F, BAD, {}):
            for s in OVERCLAIMS:
                with self.subTest(sentence=s, facts=sorted(facts)):
                    self.assertTrue(entail(s, facts), s)

    def test_the_five_t058_sentences_are_flagged_when_the_facts_do_not_back_them(self):
        for s in T058_FIVE:
            with self.subTest(sentence=s):
                self.assertTrue(entail(s, {}), s)

    def test_ten_more_phrasings_are_flagged(self):
        self.assertGreaterEqual(len(OWN_PHRASING), 10)
        for facts in (F, {}):
            for s in OWN_PHRASING:
                with self.subTest(sentence=s, facts=sorted(facts)):
                    self.assertTrue(entail(s, facts), s)

    def test_unknown_sentence_is_unrecognised_with_a_claim_label(self):
        self.assertEqual(entail("No new signals were observed.", F), ["unrecognised:No new signals were observed.", "claim:no new signals"])
        self.assertEqual(entail("The batches were stored in a warehouse.", F), ["unrecognised:The batches were stored in a warehouse."])

    def test_a_shape_with_a_wrong_number_is_unsupported(self):
        self.assertEqual(entail("Results for 12 batches ranged from 84.33% to 97.34%.", F), ["unsupported:attr_n+ranged"])
        self.assertEqual(entail("Results for 13 batches ranged from 84.33% to 97.33%.", F), ["unsupported:attr_n+ranged"])
        self.assertEqual(entail("The results spanned from 84.33% to 97.33%, with a mean of 90.47%.", F), ["unsupported:results+spanned_from+mean"])
        self.assertEqual(entail("A range of 0.05%.", {"min_value": "0.05", "max_value": "0.05"}), ["unrecognised:A range of 0.05%."])
        self.assertEqual(entail("The results showed a range of 0.05%.", {"min_value": "0.05", "max_value": "0.09"}),
                         ["unsupported:results+range_single"])
        self.assertEqual(entail("The results showed a range of 0.05%.", {"min_value": "0.05", "max_value": "0.05"}), [])

    def test_no_result_outside_needs_n_outside_zero_and_the_count_form_needs_equal_counts(self):
        self.assertEqual(entail("No result was outside the limit.", BAD), ["unsupported:none_outside"])
        self.assertEqual(entail("No result was outside the limit.", {}), ["unsupported:none_outside"])
        self.assertEqual(entail("3 of 12 results were outside the limit.", BAD), [])
        self.assertEqual(entail("2 of 12 results were outside the limit.", BAD), ["unsupported:outside_count"])

    def test_excluded_counts_must_equal_the_facts_and_the_listed_ids(self):
        self.assertEqual(entail("Results for 2 batches, Batches 169, 171 and 172, were quarantined and are not included.", F),
                         ["unsupported:excluded_list"])
        self.assertEqual(entail("Results for 3 batches, Batches 169, 171 and 172, were quarantined and are not included.", F),
                         ["unsupported:excluded_list"])

    def test_when_the_attribute_is_known_the_sentence_must_name_it(self):
        facts = dict(F, attribute="Dissolution")
        self.assertEqual(entail("Dissolution results for 12 batches ranged from 84.33% to 97.33%.", facts), [])
        self.assertEqual(entail("Results for 12 batches ranged from 84.33% to 97.33%.", facts), [])
        self.assertEqual(entail("Everything is perfect for 12 batches ranged from 84.33% to 97.33%.", facts), ["unsupported:attr_n+ranged"])
        self.assertEqual(entail("Impurity O results for 12 batches ranged from 84.33% to 97.33%.", facts), ["unsupported:attr_n+ranged"])

    def test_a_claim_word_hidden_in_the_attribute_slot_is_flagged(self):
        self.assertEqual(entail("Robust results for 12 batches ranged from 84.33% to 97.33%.", F), ["unsupported:attr_n+ranged"])

    def test_the_q3b_quote_passes_only_when_it_is_exactly_a_stored_quote(self):
        self.assertEqual(entail(Q3B.format(Q), Q3B_FACTS, quotes=[Q]), [])
        self.assertEqual(entail(Q3B.format(Q), Q3B_FACTS, quotes=[]), ["unsupported:criterion_q3b"])
        self.assertEqual(entail(Q3B.format(Q + ", and it complies"), Q3B_FACTS, quotes=[Q]), ["unsupported:criterion_q3b"])
        self.assertEqual(entail(Q3B.format(Q), dict(Q3B_FACTS, limit="0.16"), quotes=[Q]), ["unsupported:criterion_q3b"])
        self.assertTrue(stored_quotes())   # the real Q3B rows load

    def test_headings_and_table_rows_are_gated_too(self):
        self.assertEqual(entail("Dissolution", {}, kind="h"), [])
        self.assertEqual(entail("3.2.P.5.4 Batch analyses", {}, kind="h"), [])
        self.assertEqual(entail("No new signals", {}, kind="h"), ["unrecognised:No new signals", "claim:no new signals"])
        self.assertEqual(entail("26\t97.33\t%", {"x": "97.33"}, kind="row"), [])
        self.assertEqual(entail("26\t97.34\t%", {"x": "97.33"}, kind="row"), ["unrecognised:26 97.34 %"])
        self.assertTrue(entail("26\tAll results complied.\t%", {"x": "97.33"}, kind="row"))
        self.assertEqual(entail("327\texcluded (quarantined)\t-", {}, kind="row"), [])

    def test_sentences_split_on_full_stops_but_not_inside_numbers(self):
        self.assertEqual(sentences("Mean was 0.7% overall. Next."), ["Mean was 0.7% overall.", "Next."])


class RereadToolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "P5.docx"
        self.placed = [{"id": "limit", "section": "S/j", "text": "80"}, {"id": "n_batches", "section": "S/j", "text": "12"},
                       {"id": "min_value", "section": "S/j", "text": "84.33"}, {"id": "max_value", "section": "S/j", "text": "97.33"}]
        self.para = ("The acceptance criterion for Dissolution is not less than 80%, which is declared by the author for this "
                     "demonstration, with no public source. Results for 12 batches ranged from 84.33% to 97.33%. "
                     "No result was outside the limit.")

    def write(self, para):
        doc = Document()
        doc.add_paragraph(para)
        doc.save(str(self.path))

    def test_clean_paragraph_has_no_flag_and_numbers_match(self):
        self.write(self.para)
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual((rep["problems"], rep["flags"]), ([], []))
        self.assertEqual(rep["numbers"], 4)

    def test_planted_unrecognised_sentence_is_flagged(self):
        self.write(self.para + " No new signals were observed.")
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual([f["flag"] for f in rep["flags"]], ["unrecognised:No new signals were observed.", "claim:no new signals"])

    def test_planted_claim_contradicted_by_the_stored_numbers_is_flagged(self):
        self.placed[2]["text"] = "79.5"   # lowest result is below the NLT 80 limit, so "no result outside" is false
        self.write(self.para.replace("84.33", "79.5"))
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual([f["flag"] for f in rep["flags"]], ["unsupported:none_outside"])

    def test_planted_changed_number_is_caught(self):
        self.write(self.para.replace("84.33", "84.34"))
        rep = reread_export.reread(self.path, self.placed, set())
        self.assertEqual(rep["problems"], ["changed number #2: file has '84.34', placement says '84.33'"])
        self.assertEqual([f["flag"] for f in rep["flags"]], ["unsupported:attr_n+ranged"])


if __name__ == "__main__":
    unittest.main()
