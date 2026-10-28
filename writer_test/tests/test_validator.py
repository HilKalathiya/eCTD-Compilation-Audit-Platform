"""Checks that the validator catches each kind of error and lets a good paragraph through.

    python -m unittest discover tests
"""
import json
import unittest
from pathlib import Path

from writer_test.facts import compute_facts, fmt
from writer_test.validator import render, validate

TASKS = {t["task_id"]: t for t in json.load(
    open(Path(__file__).resolve().parent.parent / "data" / "tasks.json", encoding="utf-8"))["tasks"]}


def setup(task_id):
    return compute_facts(TASKS[task_id])


GOOD_INCREASING = ("Total impurities increased at [[condition]], from [[initial_range]] to "
                   "[[final_range]]. The highest result was [[max_value]]. "
                   "All results remained within the acceptance criterion of [[spec]].")


class FactsTest(unittest.TestCase):
    def test_trends(self):
        self.assertEqual(setup("lt_total_impurities")[1]["trend"], "increasing")
        self.assertEqual(setup("lt_assay")[1]["trend"], "decreasing")
        self.assertEqual(setup("lt_water")[1]["trend"], "no meaningful change")
        self.assertEqual(setup("lt_dissolution")[1]["trend"], "no meaningful change")

    def test_required_result_is_the_one_nearest_the_limit(self):
        self.assertIn("max_value", setup("lt_total_impurities")[2])  # NMT limit
        self.assertIn("min_value", setup("lt_dissolution")[2])       # NLT limit
        self.assertIn("min_value", setup("lt_assay")[2])             # range, low side closer

    def test_oos_detected(self):
        facts, flags, required = setup("acc_impurity_b_oos")
        self.assertFalse(flags["all_within_spec"])
        self.assertEqual("0.18% (Batch B3, Month 6)", facts["oos_results"]["value"])
        self.assertIn("oos_results", required)

    def test_half_up_rounding(self):
        self.assertEqual(fmt(0.125, 2), "0.13")
        self.assertEqual(fmt(2.675, 2), "2.68")


class ValidatorTest(unittest.TestCase):
    def test_good_paragraph_passes(self):
        facts, flags, req = setup("lt_total_impurities")
        self.assertEqual(validate(GOOD_INCREASING, facts, flags, req), [])
        self.assertIn("0.30%", render(GOOD_INCREASING, facts))

    def test_raw_number_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("[[max_value]]", "0.30%")
        self.assertTrue(any("number written" in p for p in validate(bad, facts, flags, req)))

    def test_number_word_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("All results", "All three batches")
        self.assertTrue(any("as a word" in p for p in validate(bad, facts, flags, req)))

    def test_unknown_placeholder_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("[[spec]]", "[[shelf_life]]")
        self.assertTrue(any("unknown" in p for p in validate(bad, facts, flags, req)))

    def test_wrong_trend_fails(self):
        facts, flags, req = setup("lt_assay")  # decreasing
        bad = GOOD_INCREASING.replace("Total impurities", "Assay")
        self.assertTrue(any("trend" in p for p in validate(bad, facts, flags, req)))

    def test_negated_trend_allowed_when_flat(self):
        facts, flags, req = setup("lt_water")
        ok = ("Water content showed no meaningful increase at [[condition]], ranging from [[initial_range]] "
              "initially to [[final_range]]. All results remained within [[spec]], "
              "with a highest result of [[max_value]].")
        self.assertEqual(validate(ok, facts, flags, req), [])

    def test_oos_must_be_stated(self):
        facts, flags, req = setup("acc_impurity_b_oos")
        hidden = GOOD_INCREASING.replace("Total impurities", "Impurity B")
        problems = validate(hidden, facts, flags, req)
        self.assertTrue(any("out of specification" in p for p in problems))
        self.assertTrue(any("claims all results comply" in p for p in problems))

    def test_unit_after_placeholder_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("[[max_value]].", "[[max_value]]%.")
        self.assertTrue(any("unit repeated" in p for p in validate(bad, facts, flags, req)))

    def test_tens_number_word_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("Total impurities", "Total impurities at thirty minutes")
        self.assertTrue(any("as a word" in p for p in validate(bad, facts, flags, req)))

    def test_attribute_name_may_contain_digits(self):
        facts, flags, req = setup("lt_dissolution")
        ok = ("Dissolution at 30 minutes showed no meaningful change at [[condition]], from [[initial_range]] "
              "to [[final_range]]. The lowest result was [[min_value]]. All results remained within the acceptance criterion of [[spec]].")
        self.assertEqual(validate(ok, facts, flags, req), [])

    def test_value_used_as_noun_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("[[final_range]].", "[[final_range]], with a [[mean_change]].")
        self.assertTrue(any("used as a noun" in p for p in validate(bad, facts, flags, req)))

    def test_n_batches_needs_noun(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("at [[condition]]", "at [[condition]] for [[n_batches]]")
        self.assertTrue(any("n_batches" in p for p in validate(bad, facts, flags, req)))

    def test_equal_range_renders_as_one_value(self):
        facts, _, _ = setup("lt_dissolution")
        self.assertEqual(facts["initial_range"]["value"], "92% at Month 0")

    def test_examples_in_prompt_pass_the_validator(self):
        from writer_test import prompt
        facts, flags, req = setup("acc_impurity_b_oos")
        flags = dict(flags, attribute="Related compound D")  # the example's own test name
        self.assertEqual(validate(prompt.EXAMPLE_ASSISTANT_OOS, facts, flags, req), [])

    def test_did_not_meet_counts_as_stating_oos(self):
        facts, flags, req = setup("acc_impurity_b_oos")
        ok = ("Impurity B increased in all [[n_batches]] batches at [[condition]]. The highest result was [[max_value]]. "
              "The result of [[oos_results]] did not meet the acceptance criterion of [[spec]].")
        self.assertEqual(validate(ok, facts, flags, req), [])

    def test_did_not_meet_flagged_when_all_comply(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("All results remained within", "One result did not meet")
        self.assertTrue(any("claims a failure" in p for p in validate(bad, facts, flags, req)))

    # --- wrong-binding checks ---
    def test_role_word_next_to_wrong_fact_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("The highest result was [[max_value]]", "The highest result was [[min_value]]")
        self.assertTrue(any("not the highest result" in p for p in validate(bad, facts, flags, req)))

    def test_lowest_after_max_fact_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("The highest result was", "The lowest result was")
        self.assertTrue(any("not the lowest result" in p for p in validate(bad, facts, flags, req)))

    def test_initial_and_last_words_checked(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("from [[initial_range]] to [[final_range]]", "from [[final_range]] to [[initial_range]]")
        self.assertTrue(any("backwards in time" in p for p in validate(bad, facts, flags, req)))
        bad = GOOD_INCREASING.replace("from [[initial_range]] to [[final_range]]",
                                      "from the initial [[final_range]] to the last [[initial_range]]")
        self.assertTrue(any("initial" in p or "last" in p for p in validate(bad, facts, flags, req)))

    def test_batch_named_in_words_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("All results", "The second batch and all results")
        self.assertTrue(any("batch in words" in p for p in validate(bad, facts, flags, req)))

    def test_ordinary_batches_wording_is_not_flagged(self):
        facts, flags, req = setup("lt_total_impurities")
        ok = GOOD_INCREASING.replace("increased gradually at", "increased gradually across [[n_batches]] batches at")
        self.assertEqual(validate(ok, facts, flags, req), [])

    def test_result_fact_carries_its_own_batch_and_month(self):
        facts, _, _ = setup("lt_total_impurities")
        self.assertEqual(facts["max_value"]["value"], "0.30% (Batch B3, Month 24)")
        self.assertNotIn("max_value_where", facts)

    def test_highest_without_a_result_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("The highest result was [[max_value]].", "Values were highest at the start. The result was [[max_value]].")
        self.assertTrue(any("no result placeholder" in p for p in validate(bad, facts, flags, req)))

    def test_timing_words_fail(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("increased at", "increased early and then levelled off at")
        self.assertTrue(any("timing" in p for p in validate(bad, facts, flags, req)))

    def test_comparison_between_results_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("The highest result was [[max_value]].",
                                      "The highest result [[max_value]] was lower than [[initial_range]].")
        self.assertTrue(any("compares two results" in p for p in validate(bad, facts, flags, req)))

    def test_unregistered_test_name_as_subject_fails(self):
        facts, flags, req = setup("lt_total_impurities")
        bad = GOOD_INCREASING.replace("Total impurities increased", "Related substances increased")
        self.assertTrue(any("sentence starts with 'Related'" in p for p in validate(bad, facts, flags, req)))

    def test_plain_connecting_openers_allowed(self):
        facts, flags, req = setup("lt_total_impurities")
        ok = GOOD_INCREASING.replace("The highest result", "Overall, the highest result".replace("Overall, the", "However, the"))
        self.assertEqual(validate(ok, facts, flags, req), [])

    # --- second round: found by reading the model's own accepted paragraphs ---
    def _bad(self, task, new, old="from [[initial_range]] to [[final_range]]"):
        facts, flags, req = setup(task)
        return validate(GOOD_INCREASING.replace(old, new), facts, flags, req)

    def test_single_result_called_a_range(self):
        bad = self._bad("lt_total_impurities", "from the initial range of [[min_value]] to [[final_range]]")
        self.assertTrue(any("calls the result of one batch a range" in p for p in bad))

    def test_initial_results_of_a_point(self):
        bad = self._bad("lt_assay", "with initial results ranging from [[max_value]] and [[min_value]]",
                        old="from [[initial_range]] to [[final_range]]")
        self.assertTrue(any("calls the result of one batch a range" in p for p in bad))

    def test_change_between_two_single_results(self):
        bad = self._bad("lt_total_impurities", "from [[min_value]] to [[max_value]]")
        self.assertTrue(any("single result" in p for p in bad))
        ok = self._bad("lt_total_impurities", "ranging from [[min_value]] to [[max_value]]")
        self.assertFalse(any("single result" in p for p in ok))

    def test_time_repeated_after_a_range(self):
        for tail in ("[[final_range]] at the last time point", "[[final_range]] at [[duration]]",
                     "[[final_range]] at Month zero"):
            bad = self._bad("lt_total_impurities", "from [[initial_range]] to " + tail)
            self.assertTrue(bad, tail)

    def test_results_at_last_time_point_from_different_months(self):
        bad = self._bad("lt_total_impurities", "ranging from [[min_value]] to [[max_value]] at the last time point")
        self.assertTrue(any("different time points" in p for p in bad))
        facts, flags, req = setup("lt_total_impurities")
        ok = "Total impurities increased at [[condition]]. The highest result was [[max_value]] at the last time point. All results remained within [[spec]]."
        self.assertEqual(validate(ok, facts, flags, req), [])

    def test_span_claim_needs_the_ends_to_span_all_results(self):
        facts, flags, req = setup("lt_dissolution")
        self.assertFalse(flags["ends_span_all"])
        bad = ("Dissolution at 30 minutes showed no meaningful change at [[condition]], ranging from [[initial_range]] "
               "to [[final_range]]. The lowest result was [[min_value]]. All results remained within [[spec]].")
        self.assertTrue(any("some results lie outside" in p for p in validate(bad, facts, flags, req)))
        self.assertEqual(validate(bad.replace("ranging from", "from"), facts, flags, req), [])

    def test_condition_is_not_out_of_specification(self):
        facts, flags, req = setup("acc_impurity_b_oos")
        bad = ("Impurity B increased at [[condition]], from [[initial_range]] to [[final_range]]. The highest result was "
               "[[max_value]]. The result of [[oos_results]] did not meet [[spec]], resulting in the condition being out of specification.")
        self.assertTrue(any("only a result can be" in p for p in validate(bad, facts, flags, req)))

    def test_mean_change_said_twice(self):
        bad = self._bad("lt_total_impurities", "from [[initial_range]] to [[final_range]]. The mean change was a mean change of [[mean_change]]",
                        old="from [[initial_range]] to [[final_range]]")
        self.assertTrue(any("twice" in p for p in bad))

    def test_article_before_placeholders_does_not_hide_a_cross_batch_change(self):
        bad = self._bad("lt_total_impurities", "from the [[max_value]] to the [[min_value]]")
        self.assertTrue(any("single result" in p for p in bad))

    def test_remaining_between_needs_the_ends_to_span_all_results(self):
        facts, flags, req = setup("lt_dissolution")
        bad = ("Dissolution at 30 minutes showed no meaningful change at [[condition]], remaining between [[initial_range]] "
               "and [[final_range]]. The lowest result was [[min_value]]. All results remained within [[spec]].")
        self.assertTrue(any("some results lie outside" in p for p in validate(bad, facts, flags, req)))

    def test_test_name_must_be_complete(self):
        facts, flags, req = setup("lt_dissolution")
        bad = ("Dissolution at [[condition]] showed no meaningful change, from [[initial_range]] to [[final_range]]. "
               "The lowest result was [[min_value]]. All results remained within [[spec]].")
        self.assertTrue(any("names the test only in part" in p for p in validate(bad, facts, flags, req)))
        ok = bad.replace("Dissolution at [[condition]]", "Dissolution at 30 minutes at [[condition]]")
        self.assertEqual(validate(ok, facts, flags, req), [])
        short = bad.replace("Dissolution at [[condition]] showed", "Dissolution showed")
        self.assertEqual(validate(short, facts, flags, req), [])  # short form alone is fine

    def test_ich_codes_allowed(self):
        facts, flags, req = setup("lt_total_impurities")
        ok = GOOD_INCREASING + " The data were evaluated as described in ICH Q1E."
        self.assertEqual(validate(ok, facts, flags, req), [])


if __name__ == "__main__":
    unittest.main()
