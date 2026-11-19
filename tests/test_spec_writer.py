"""Tests for the P.5.6 spec-justification writer: facts, quote handling, each validator rule (with a planted error), the loop, the runner."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ectd_engine.validator import spec as sv
from ectd_engine.writer import spec_facts as sf
from ectd_engine.writer.spec_loop import SpecMockClient, mock_text, run_spec_task, write_spec_section
from ectd_engine.writer.spec_prompt import build_messages
from tests.test_mutation_spec import FILE, fixed_tasks, live_data

ROOT = Path(__file__).resolve().parent.parent
REAL, SYN = FILE["tasks"], FILE["synthetic"]


class SpecWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = fixed_tasks()  # 0-4 real, 5-9 planted variants (quotes from the live PDF check)
        cls.by_id = {t["task_id"]: t for t in cls.tasks}

    def ctx(self, task_id):
        t = self.by_id[task_id]
        return (t,) + sf.compute_spec_facts(t)

    def check(self, task_id, text):
        t, facts, flags, required = self.ctx(task_id)
        return sv.validate(text, facts, flags, required)

    # ---- facts
    def test_task_file_matches_live_data(self):
        live = live_data()["40"]
        for t in REAL:
            j = live[t["column"]]
            self.assertEqual(sf.task_from_justification(j, t["column"], t.get("mdd"), t["task_id"]), t)

    def test_stale_task_is_refused(self):
        bad = dict(REAL[1], max="0.17")
        with self.assertRaisesRegex(ValueError, "max is '0.17'"):
            sf.resolve_quote(bad, live_data())

    def test_facts_for_each_basis(self):
        _, facts, flags, required = self.ctx("p56_impurity_o")
        self.assertEqual(facts["limit_kind"]["value"], "not more than")
        self.assertEqual(facts["limit"]["value"], "0.5%")
        self.assertEqual(facts["mdd"]["value"], "40 mg")
        self.assertEqual(facts["n_batches"]["value"], "985 batches")
        self.assertTrue(facts["q3b_quote"]["value"].startswith("“Qualification Thresholds"))
        self.assertNotIn("n_outside", facts)
        self.assertEqual(required, ["limit_kind", "limit", "basis", "n_batches", "min_value", "max_value", "mdd", "q3b_quote"])
        _, facts, _, required = self.ctx("p56_dissolution")
        self.assertEqual(facts["limit_kind"]["value"], "not less than")
        self.assertNotIn("mdd", facts)
        self.assertNotIn("q3b_quote", facts)
        _, facts, _, required = self.ctx("syn_dissolution_outside")
        self.assertEqual(facts["n_outside"]["value"], "two batches")
        self.assertIn("n_outside", required)

    def test_malformed_tasks_fail_loudly(self):
        t = self.by_id["p56_impurity_o"]
        for change, msg in [({"n_outside": 986}, "n_outside"), ({"basis": "typed"}, "basis"), ({"limit_kind": "MAX"}, "limit_kind"),
                            ({"min": "1", "max": "0.5"}, "min must not be above max"), ({"q3b_quote": ""}, "needs mdd and the quote")]:
            with self.assertRaisesRegex(ValueError, msg):
                sf.compute_spec_facts(dict(t, **change))
        with self.assertRaisesRegex(ValueError, "must not carry"):
            sf.compute_spec_facts(dict(self.by_id["p56_dissolution"], mdd="40"))

    def test_other_dose_uses_its_own_q3b_row(self):
        self.assertEqual(self.by_id["syn_impurity_l_mdd5"]["limit"], "1.0")
        self.assertEqual(self.by_id["syn_impurity_o_mdd500_outside"]["limit"], "0.2")

    # ---- validator rules, each with a planted error
    GOOD_Q = ("The acceptance criterion for Impurity O is [[limit_kind]] [[limit]], set at [[basis]] for an assumed maximum daily "
              "dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. "
              "No result was outside the limit.")
    GOOD_D = ("The acceptance criterion for Dissolution is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] "
              "ranged from [[min_value]] to [[max_value]]. No result was outside the limit.")

    def test_correct_paragraphs_pass(self):
        self.assertEqual(self.check("p56_impurity_o", self.GOOD_Q), [])
        self.assertEqual(self.check("p56_dissolution", self.GOOD_D), [])

    def test_declared_limit_must_not_look_sourced(self):
        for extra in ["The limit is in line with ICH guidance.", "The limit is per the pharmacopoeia.", "The limit is qualified by toxicology data."]:
            self.assertTrue(self.check("p56_dissolution", self.GOOD_D + " " + extra), extra)

    def test_ich_in_text_is_seen_even_though_digits_are_allowed(self):
        p = self.check("p56_dissolution", self.GOOD_D + " The limit is in line with ICH Q3B(R2).")
        self.assertTrue(any("sourced one" in x for x in p), p)

    def test_q3b_dose_must_be_called_an_assumption_in_its_own_sentence(self):
        self.assertTrue(any("assumption" in x for x in self.check("p56_impurity_o", self.GOOD_Q.replace("assumed ", ""))))
        moved = self.GOOD_Q.replace("assumed ", "") + " The dose is only an assumption."
        self.assertTrue(any("assumption" in x for x in self.check("p56_impurity_o", moved)))

    def test_q3b_quote_is_never_typed(self):
        p = self.check("p56_impurity_o", self.GOOD_Q + " The table says qualification thresholds maximum daily dose threshold.")
        self.assertTrue(any("typed quote" in x for x in p), p)
        p = self.check("p56_impurity_o", self.GOOD_Q + " Whichever is lower applies.")
        self.assertTrue(any("typed quote" in x for x in p), p)

    def test_q3b_qualification_threshold_wording_is_allowed_but_qualified_is_not(self):
        self.assertEqual(self.check("p56_impurity_o", self.GOOD_Q.replace("The acceptance criterion", "The qualification threshold criterion")), [])
        self.assertTrue(any("safety or qualification" in x for x in self.check("p56_impurity_o", self.GOOD_Q + " The impurity is qualified.")))

    def test_compliance_wording_only_when_nothing_is_outside(self):
        t, facts, flags, required = self.ctx("syn_dissolution_outside")
        base = ("The acceptance criterion for Dissolution is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] "
                "ranged from [[min_value]] to [[max_value]]. [[n_outside]] had results outside the limit.")
        self.assertEqual(sv.validate(base, facts, flags, required), [])
        self.assertTrue(any("compliance wording" in x for x in sv.validate(base + " All other results were within the limit.", facts, flags, required)))
        self.assertTrue(any("missing required" in x for x in sv.validate(base.replace(" [[n_outside]] had results outside the limit.", " Results were outside the limit."), facts, flags, required)))
        self.assertTrue(any("invented failure" in x for x in self.check("p56_dissolution", self.GOOD_D + " Some results were outside the limit.")))

    def test_limit_direction_comes_only_from_the_placeholder(self):
        p = self.check("p56_dissolution", self.GOOD_D.replace("[[limit_kind]]", "not more than"))
        self.assertTrue(any("limit direction" in x for x in p), p)
        p = self.check("p56_dissolution", self.GOOD_D.replace("[[limit_kind]] [[limit]]", "[[limit_kind]] [[max_value]]"))
        self.assertTrue(any("limit direction" in x for x in p), p)

    def test_typed_numbers_and_unknown_facts_are_rejected(self):
        self.assertTrue(any("number written" in x for x in self.check("p56_dissolution", self.GOOD_D.replace("[[max_value]]", "102.67%"))))
        self.assertTrue(any("unknown placeholders" in x for x in self.check("p56_dissolution", self.GOOD_D.replace("[[limit]]", "[[mdd]]"))))

    # ---- re-read of the finished text
    def test_reread_catches_a_changed_limit_basis_or_quote(self):
        for tid, text in [("p56_impurity_o", self.GOOD_Q), ("p56_dissolution", self.GOOD_D)]:
            t, facts, _, _ = self.ctx(tid)
            r = sv.render(text, facts)
            self.assertEqual(sv.verify_render(r, t), [], tid)
            self.assertTrue(sv.verify_render(r.replace("0.5%", "0.6%").replace("80%", "70%"), t))
            flipped = r.replace("not more than", "not less than") if t["limit_kind"] == "NMT" else r.replace("not less than", "not more than")
            self.assertTrue(sv.verify_render(flipped, t))
        t, facts, _, _ = self.ctx("p56_impurity_o")
        r = sv.render(self.GOOD_Q, facts)
        self.assertTrue(sv.verify_render(r.replace("Q3B(R2) qualification", "Q1B(R2) qualification"), t))
        self.assertTrue(sv.verify_render(r.replace("TDI", "TDX", 1), t))

    # ---- prompt and loop
    def test_prompt_never_shows_the_quote(self):
        t, facts, flags, _ = self.ctx("p56_impurity_o")
        user = build_messages(t, facts, flags)[-1]["content"]
        self.assertNotIn("Qualification Thresholds", user)
        self.assertIn("[[mdd]]", user)

    def test_mock_text_is_correct_for_every_task(self):
        for t in self.tasks:
            _, facts, flags, required = self.ctx(t["task_id"])
            self.assertEqual(sv.validate(mock_text(flags), facts, flags, required), [], t["task_id"])

    def test_loop_rejects_the_overclaim_then_accepts_the_correct_draft(self):
        client = SpecMockClient()
        for t in self.tasks:
            res = run_spec_task(client, t)
            self.assertTrue(res["accepted"], t["task_id"])
            self.assertEqual(len(res["drafts"]), 2)
            self.assertFalse(res["drafts"][0]["passed"])
            self.assertTrue(any("sourced one" in p or "safety" in p or "compliance" in p for p in res["drafts"][0]["problems"]))
        sect = write_spec_section(t, res)
        self.assertIn("| Attribute | Limit |", sect)

    def test_loop_gives_up_after_max_drafts_when_the_model_keeps_overclaiming(self):
        class Bad:
            def chat(self, messages, temperature, seed, context=None, schema=None):
                return {"text": "The limit is qualified by toxicology data and is safe.", "seconds": 0, "output_tokens": 9}
        res = run_spec_task(Bad(), self.by_id["p56_dissolution"])
        self.assertFalse(res["accepted"])
        self.assertEqual(len(res["drafts"]), 4)
        self.assertIsNone(res["rendered"])

    # ---- T-048: the outside-count sentence is required
    def test_outside_sentence_is_required_when_none_outside(self):
        task = next(t for t in self.tasks if not t["n_outside"])
        good = mock_text(sf.compute_spec_facts(task)[1])
        self.assertEqual(self.check(task["task_id"], good), [])
        bad = good.replace(" No result was outside the limit.", " All results were within the limit.")
        self.assertNotEqual(bad, good)  # planted: the sentence is swapped for a compliance claim
        self.assertTrue(any("outside-count sentence" in p for p in self.check(task["task_id"], bad)))

    def test_outside_sentence_is_required_when_some_outside(self):
        task = next(t for t in self.tasks if t["n_outside"])
        good = mock_text(sf.compute_spec_facts(task)[1])
        self.assertEqual(self.check(task["task_id"], good), [])
        bad = good.replace("[[n_outside]] had results outside the limit.", "The count was [[n_outside]].")
        self.assertNotEqual(bad, good)  # planted: [[n_outside]] is there but nothing says the results were outside
        self.assertEqual([p for p in self.check(task["task_id"], bad) if "outside-count" in p].__len__(), 1)

    def test_prompt_asks_for_exactly_three_sentences_and_shows_both_patterns(self):
        t, facts, flags, _ = self.ctx("p56_dissolution")
        text = " ".join(m["content"] for m in build_messages(t, facts, flags))
        self.assertIn("exactly 3 sentences", text)
        self.assertIn("[[n_outside]] of [[n_batches]] results were outside the limit.", text)
        self.assertIn("set at [[basis]] for an assumed maximum daily dose of [[mdd]]", text)
        self.assertIn("which is [[basis]].", text)

    def test_synthetic_windows_all_have_batches_outside_and_are_marked(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("writer_run", ROOT / "tools" / "writer_run.py")
        wr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wr)
        store = wr.LoaderStore()
        from ectd_engine.specs import load, p56
        sp = load.load()
        live = {r.attribute: j for r, j in zip(sp.rows, p56.compute(sp, store))}
        syn = wr.make_synthetic_p56_windows(store.get, store.known_batches, live, 6)
        self.assertEqual(len(syn), 6)
        for t in syn:
            self.assertTrue(t["synthetic"])
            self.assertEqual(t["basis"], "declared")
            self.assertGreaterEqual(t["n_outside"], 1)

    def test_runner_accepts_all_five_with_the_mock_model(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "writer_run.py"), "--kind", "p56", "--backend", "mock", "--out", d],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("5/5 accepted", p.stdout)
            self.assertEqual(len(list((Path(d) / "p56_mock_gemma4-e4b" / "sections").glob("*.md"))), 5)


if __name__ == "__main__":
    unittest.main()
