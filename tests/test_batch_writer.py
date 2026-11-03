"""Tests for the P.5.4 batch writer: facts from a fake store, the table, the prompt, each validator rule (with a planted error), the loop."""
import json
import re
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.loaders import lek
from ectd_engine.validator import batch as bv
from ectd_engine.writer import batch_facts as bf
from ectd_engine.writer.batch_loop import BatchMockClient, run_batch_task, write_batch_section
from ectd_engine.writer.batch_prompt import build_messages, opening_sentence

ROOT = Path(__file__).resolve().parent.parent
TASKS = json.loads((ROOT / "data" / "tasks" / "p54_tasks.json").read_text(encoding="utf-8"))["tasks"]


def make_store(values, column="impurities_total"):
    """values: {batch: '0.12' or None (= quarantined)}. Returns (get, known_batches)."""
    facts = {}
    for i, (b, v) in enumerate(values.items(), start=2):
        if v is not None:
            fid = bf.fact_id(b, column)
            facts[fid] = Fact(fid, Decimal(v), "%", b, "Total impurities", "batch release", None,
                              SourcePointer("Laboratory.csv", "v1", f"row={i}"), "original", "test fact")
    return facts.get, set(values)


def make_task(ids, decimals=2):
    return {"task_id": "t", "section": "3.2.P.5.4", "product": "Lek tablets", "attribute": "Total impurities",
            "column": "impurities_total", "unit": "%", "decimals": decimals, "batches": list(ids)}


def compute(values, decimals=2):
    get, known = make_store(values)
    return bf.compute_batch_facts(make_task(list(values), decimals), get, known)


GOOD = ("Total impurities results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of "
        "[[mean_value]]. The highest result was [[max_value]] and the lowest result was [[min_value]].")
GOOD_EX = GOOD + " Results for [[n_excluded]], [[excluded_batches]], were quarantined and are not included."


class FactsTests(unittest.TestCase):
    def test_counts_extremes_ties_and_mean(self):
        facts, flags, required, table = compute({"1": "0.30", "2": "0.10", "3": "0.10", "4": "0.20"})
        self.assertEqual(facts["n_batches"]["value"], "four batches")
        self.assertEqual(facts["min_value"]["value"], "0.10% (Batches 2 and 3)")
        self.assertEqual(facts["max_value"]["value"], "0.30% (Batch 1)")
        self.assertEqual(facts["value_range"]["value"], "0.10–0.30%")
        self.assertEqual(facts["mean_value"]["value"], "0.18%")  # 0.175 -> half up
        self.assertNotIn("n_excluded", facts)
        self.assertEqual(required, ["n_batches", "min_value", "max_value", "mean_value"])

    def test_mean_rounds_half_up_not_to_even(self):
        facts = compute({"1": "0.12", "2": "0.13"})[0]  # 0.125 -> 0.13 (half-even would give 0.12)
        self.assertEqual(facts["mean_value"]["value"], "0.13%")

    def test_source_values_are_never_rounded(self):
        with self.assertRaises(ValueError):
            compute({"1": "0.123", "2": "0.1"}, decimals=2)  # 3 places would have to be rounded to show

    def test_excluded_batches_become_facts(self):
        facts, flags, required, table = compute({"1": "0.10", "2": None, "3": "0.20", "4": None})
        self.assertEqual(facts["n_excluded"]["value"], "two batches")
        self.assertEqual(facts["excluded_batches"]["value"], "Batches 2 and 4")
        self.assertEqual(facts["n_batches"]["value"], "two batches")
        self.assertIn("n_excluded", required)
        self.assertEqual(flags["excluded"], ["2", "4"])
        self.assertEqual(facts["mean_value"]["value"], "0.15%")  # excluded batches are not in the mean

    def test_all_equal_gives_both_roles(self):
        facts = compute({"1": "0.05", "2": "0.05"})[0]
        self.assertEqual(facts["min_value"]["roles"], {"min", "max"})
        self.assertEqual(facts["value_range"]["value"], "0.05%")

    def test_unknown_batch_is_a_loud_error_not_an_exclusion(self):
        get, known = make_store({"1": "0.10", "2": "0.20"})
        with self.assertRaises(bf.UnknownBatch):
            bf.compute_batch_facts(make_task(["1", "2", "3"]), get, known)

    def test_no_result_at_all_is_an_error(self):
        with self.assertRaises(ValueError):
            compute({"1": None, "2": None})

    def test_unsorted_or_duplicate_ids_are_refused(self):
        get, known = make_store({"2": "0.1", "10": "0.2"})
        with self.assertRaises(ValueError):
            bf.compute_batch_facts(make_task(["10", "2"]), get, known)  # a text sort would put 10 first
        with self.assertRaises(ValueError):
            bf.compute_batch_facts(make_task(["2", "2"]), get, known)

    def test_wrong_unit_is_refused(self):
        get, known = make_store({"1": "0.1"})
        task = make_task(["1"])
        task["unit"] = "mg"
        with self.assertRaises(ValueError):
            bf.compute_batch_facts(task, get, known)

    def test_numeric_id_order(self):
        self.assertEqual(sorted(["10", "2", "1", "60"], key=bf.id_key), ["1", "2", "10", "60"])

    def test_no_float_and_no_round_in_the_new_files(self):
        for rel in ("ectd_engine/writer/batch_facts.py", "ectd_engine/writer/batch_prompt.py",
                    "ectd_engine/writer/batch_loop.py", "ectd_engine/validator/batch.py", "tests/test_batch_writer.py",
                    "tests/test_mutation_batch.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?<![\w.])(float|round)\(", src), rel)


class TableTests(unittest.TestCase):
    def test_table_rows_and_excluded_cell(self):
        table = compute({"1": "0.10", "2": None, "3": "0.2"})[3]
        text = bf.render_table(table)
        self.assertIn("| 1 | 0.10 | % |", text)
        self.assertIn("| 2 | excluded (quarantined) | - |", text)
        self.assertIn("| 3 | 0.2 | % |", text)  # shown exactly as stored

    def test_table_is_not_in_the_prompt(self):
        facts, flags, required, table = compute({"1": "0.10", "2": None, "3": "0.20", "4": "0.17"})
        messages = build_messages(make_task(["1", "2", "3", "4"]), facts, flags)
        user = messages[-1]["content"]
        self.assertNotIn("| Batch |", "".join(m["content"] for m in messages))
        self.assertNotIn("| excluded (quarantined) |", "".join(m["content"] for m in messages))  # that cell exists only in the table
        self.assertNotIn("0.17", user)  # a middle value: it is in the table, not in any fact
        self.assertIn("[[min_value]]", user)

    def test_opening_sentence_is_code_text(self):
        facts = compute({"1": "0.10", "2": None})[0]
        s = opening_sentence(make_task(["1", "2"]), facts)
        self.assertIn("one batch", s)
        self.assertIn("Batch 2", s)


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.facts, self.flags, self.required, self.table = compute({"1": "0.10", "2": "0.30", "3": "0.20"})
        self.facts_ex, self.flags_ex, self.required_ex, self.table_ex = compute({"1": "0.10", "2": "0.30", "3": None})

    def check(self, text, expect, excluded=False):
        f, fl, rq = (self.facts_ex, self.flags_ex, self.required_ex) if excluded else (self.facts, self.flags, self.required)
        problems = bv.validate(text, f, fl, rq)
        self.assertTrue(any(expect in p for p in problems), f"{expect!r} not found in {problems}")

    def test_correct_text_is_accepted(self):
        self.assertEqual(bv.validate(GOOD, self.facts, self.flags, self.required), [])
        self.assertEqual(bv.validate(GOOD_EX, self.facts_ex, self.flags_ex, self.required_ex), [])
        for text in ("The mean result for [[n_batches]] was [[mean_value]]. The lowest result was [[min_value]] and the "
                     "highest result was [[max_value]].",
                     "Total impurities were determined for [[n_batches]]. The results covered the range [[value_range]], "
                     "with a mean of [[mean_value]]. The highest result was [[max_value]] and the lowest result was [[min_value]]."):
            self.assertEqual(bv.validate(text, self.facts, self.flags, self.required), [], text)

    def test_compliance_words_rejected_without_spec(self):
        for w in ("All results complied with the specification.", "All batches met the acceptance criteria.",
                  "The results are acceptable.", "All batches passed.", "No result was out of specification.",
                  "The results did not meet the limit.", "All results conform to requirements.", "No result exceeded the limit."):
            self.check(GOOD + " " + w, "compliance")

    def test_compliance_words_allowed_when_a_spec_fact_exists(self):
        facts = dict(self.facts, spec={"value": "NMT 0.50%", "label": "acceptance criterion", "roles": set()})
        flags = dict(self.flags, has_spec=True)
        text = GOOD + " All results remained within the acceptance criterion."
        self.assertEqual(bv.validate(text, facts, flags, self.required), [])

    def test_batch_count_words(self):
        for w in ("Several batches were tested.", "The data cover a single batch.", "Both batches were tested."):
            self.check(GOOD + " " + w, "batch count")

    def test_batch_in_words_and_typed_ids(self):
        self.check(GOOD.replace("The highest", "In the second batch the highest"), "names a batch in words")
        self.check(GOOD + " Batch 2 was highest.", "types batch ID")

    def test_noun_repeated(self):
        self.check(GOOD.replace("[[n_batches]]", "[[n_batches]] batches"), "noun repeated")

    def test_exclusion_iff_excluded(self):
        self.check(GOOD, "omits exclusion", excluded=True)
        self.check(GOOD + " One batch was excluded as it was quarantined.", "invented exclusion")
        self.check(GOOD_EX.replace("[[n_excluded]], [[excluded_batches]],", "[[n_batches]], [[excluded_batches]],"),
                   "exclusion", excluded=True)
        self.check(GOOD_EX + " The results apply to all batches.", "claims all batches", excluded=True)

    def test_invented_exclusion_placeholder_is_unknown(self):
        self.check(GOOD_EX, "unknown placeholders")  # the task has nothing excluded, so no such fact exists

    def test_count_flip(self):
        flipped = GOOD_EX.replace("[[n_excluded]]", "\0").replace("[[n_batches]]", "[[n_excluded]]").replace("\0", "[[n_batches]]")
        self.check(flipped, "exclusion", excluded=True)

    def test_min_max_roles_and_range_order(self):
        self.check(GOOD.replace("[[min_value]] to [[max_value]]", "[[max_value]] to [[min_value]]"), "backwards")
        self.check(GOOD.replace("highest result was [[max_value]]", "highest result was [[min_value]]"), "is next to")
        self.check(GOOD.replace("highest", "TMP").replace("lowest", "highest").replace("TMP", "lowest"), "is next to")

    def test_mean_is_not_a_range(self):
        self.check(GOOD.replace("to [[max_value]],", "to [[mean_value]],"), "range")
        self.check(GOOD.replace("with a mean of", "with a mean range of"), "range")
        self.check(GOOD.replace("with a mean of [[mean_value]]", "with [[mean_value]]"), "not called the mean")
        self.check(GOOD.replace("highest result was [[max_value]]", "highest result was [[mean_value]]"), "is next to")
        self.check(GOOD.replace("with a mean of [[mean_value]]", "with a [[mean_value]]"), "noun")

    def test_other_checks(self):
        self.check(GOOD.replace("[[mean_value]]", "0.20%"), "number written outside")
        self.check(GOOD.replace("[[mean_value]]", "[[mean_value_where]]"), "unknown placeholders")
        self.check(GOOD.replace("[[mean_value]]", "[[mean_value]] percent"), "unit repeated")
        self.check(GOOD.replace("Total impurities", "Dissolution", 1), "another test")
        self.check(GOOD + " The results showed low variability.", "statistic")
        self.check(GOOD + " This is due to degradation.", "cause")
        self.check("Total impurities were measured.", "missing required facts")
        self.check("# Heading\n" + GOOD, "headings")

    def test_rendered_text_re_read(self):
        self.assertEqual(bv.verify_render(bv.render(GOOD_EX, self.facts_ex), self.table_ex), [])
        rendered = bv.render(GOOD, self.facts)
        self.assertEqual(bv.verify_render(rendered, self.table), [])
        self.assertTrue(bv.verify_render(rendered.replace("0.30%", "0.31%"), self.table))
        self.assertTrue(bv.verify_render(rendered.replace("(Batch 2)", "(Batch 3)"), self.table))
        self.assertTrue(bv.verify_render(rendered.replace("three batches", "four batches"), self.table))
        self.assertTrue(bv.verify_render(rendered.replace("0.20%", "0.21%"), self.table))  # the mean
        ex = bv.render(GOOD_EX, self.facts_ex)
        self.assertTrue(bv.verify_render(ex.replace("Batch 3", "Batch 2"), self.table_ex))


class LoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = bf.LoaderStore()

    def test_task_file_shape(self):
        self.assertEqual(len(TASKS), 6)
        self.assertEqual(sorted(t["column"] for t in TASKS[:5]), sorted(lek.COLUMNS))
        for t in TASKS:
            bf.check_task(t)
            self.assertEqual(len(t["batches"]), 12)
            self.assertEqual(t["batches"], sorted(t["batches"], key=bf.id_key))
        self.assertEqual({tuple(t["batches"]) for t in TASKS[:5]}, {tuple(TASKS[0]["batches"])})

    def test_exclusions_come_from_the_real_loader(self):
        n_ex = {t["task_id"]: bf.compute_batch_facts(t, self.store.get, self.store.known_batches)[1]["n_excluded"] for t in TASKS}
        self.assertEqual([n_ex[t["task_id"]] for t in TASKS[:5]], [0, 0, 0, 0, 0])
        self.assertEqual(n_ex[TASKS[5]["task_id"]], 1)
        # quarantine is per attribute: batch 60 is fine for dissolution
        t = dict(TASKS[0], batches=["1", "60"])
        self.assertEqual(bf.compute_batch_facts(t, self.store.get, self.store.known_batches)[1]["n_excluded"], 0)

    def test_mock_model_accepted_on_all_six_after_a_rejected_first_draft(self):
        client = BatchMockClient()
        for t in TASKS:
            res = run_batch_task(client, t, self.store.get, self.store.known_batches)
            self.assertTrue(res["accepted"], res["drafts"])
            self.assertEqual([d["passed"] for d in res["drafts"]], [False, True])
            section = write_batch_section(t, res)
            self.assertIn("| Batch | Value | Unit |", section)
            self.assertNotIn("[[", section)
        self.assertIn("excluded (quarantined)", section)  # last task is the quarantine task

    def test_model_that_always_claims_compliance_is_rejected(self):
        class Bad:
            def chat(self, messages, temperature, seed, context=None, schema=None):
                return {"text": "All results complied with the specification. They were acceptable."}
        res = run_batch_task(Bad(), TASKS[0], self.store.get, self.store.known_batches)
        self.assertFalse(res["accepted"])
        self.assertEqual(len(res["drafts"]), 4)
        self.assertIsNone(res["rendered"])

    def test_empty_reply_is_a_problem(self):
        class Empty:
            def chat(self, messages, temperature, seed, context=None, schema=None):
                return {"text": ""}
        res = run_batch_task(Empty(), TASKS[0], self.store.get, self.store.known_batches, max_drafts=2)
        self.assertEqual(res["drafts"][0]["problems"], ["empty output"])


if __name__ == "__main__":
    unittest.main()
