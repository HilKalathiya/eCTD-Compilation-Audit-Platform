"""Tests for the T-073 tasks: ids-only files, rules R0-R8 on every task, the quotas of the dev and held-out sets, the saved bytes and hashes."""
import json
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_rules as R
from ectd_engine.summary import m23_tasks2 as T2
from ectd_engine.summary import m23_tasks3 as T

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evidence" / "T-073" / "tasks"


def stats(items):
    """(tasks with a result outside the limit, tasks that extrapolate, tasks where extrapolation was refused, tasks with significant change and no outside result)."""
    outside = sum(1 for t, r in items if any(R.outside_count(r, c, a) for c, a in R.groups_in(r)))
    sig_only = sum(1 for t, r in items if any(R.significant_change(r, a) for a in {x for _, x in R.groups_in(r)})
                   and not any(R.outside_count(r, c, a) for c, a in R.groups_in(r)))
    return outside, sum(1 for t, _ in items if t["extrapolation"]), sum(1 for t, _ in items if t["extrapolation_refused"]), sig_only


class Tasks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = T.all_tasks3()

    def test_counts_and_ids(self):
        self.assertEqual((len(self.all["real"]), len(self.all["dev"]), len(self.all["heldout"])), (1, 10, 20))
        ids = [t["task_id"] for items in self.all.values() for t, _ in items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("m23c_") for i in ids))
        old = {t["task_id"] for items in T2.all_tasks().values() for t, _ in items}
        self.assertFalse(old & set(ids), "T-073 must use new task ids")

    def test_a_task_file_holds_no_value_and_no_graph_rows(self):
        for items in self.all.values():
            for t, _ in items:
                text = T2.task_json(t).decode("utf-8")
                for banned in ('"value"', '"value_text"', '"text"', "graph_rows", '"limit_text"'):
                    self.assertNotIn(banned, text, t["task_id"])

    def test_labels_never_say_demonstrated(self):
        for items in self.all.values():
            for t, _ in items:
                for s in t["public"].values():
                    self.assertNotIn("demonstrated", s["label"])

    def test_every_task_is_consistent_the_real_one_included(self):
        for t, rows in self.all["dev"] + self.all["heldout"]:
            self.assertEqual(T.consistency_problems3(t, rows), [], t["task_id"])
            self.assertEqual(R.limit_problems(rows), [], t["task_id"])
        self.assertEqual(T.consistency_problems3(T.real_task3(), G.collect()), [])

    def test_every_synthetic_task_has_a_long_term_group_and_the_spec_fact_of_its_dissolution_limit(self):
        for t, rows in self.all["dev"] + self.all["heldout"]:
            self.assertTrue(any(g["condition"] == T.P.LONG for g in t["results"]), t["task_id"])
            if any(g["attribute"] == "Dissolution (15 min)" for g in t["results"]):
                self.assertIn(G.spec_id("dissolution_av"), {s["fact_id"] for s in t["spec"]}, t["task_id"])

    def test_the_heldout_set_meets_the_quotas_of_the_card(self):
        outside, extrap, refused, sig_only = stats(self.all["heldout"])
        self.assertGreaterEqual(outside, 6)
        self.assertGreaterEqual(extrap, 3)
        self.assertGreaterEqual(refused, 3)
        self.assertGreaterEqual(sig_only, 1)             # significant change with nothing outside the limit: a rule of its own

    def test_the_dev_set_holds_every_kind_of_case(self):
        outside, extrap, refused, sig_only = stats(self.all["dev"])
        self.assertTrue(outside >= 1 and extrap >= 1 and refused >= 1 and sig_only >= 1)

    def test_the_task_bytes_never_change(self):
        again = T.all_tasks3()
        for key in ("real", "dev", "heldout"):
            for (a, ra), (b, rb) in zip(self.all[key], again[key]):
                self.assertEqual(T2.task_json(a), T2.task_json(b))
                if ra is not None:
                    self.assertEqual(T2.graph_json(ra), T2.graph_json(rb))

    def test_saved_task_files_are_the_ones_the_code_makes_and_their_hashes_hold(self):
        lines = (TASKS / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1 + 2 * 10 + 2 * 20)    # the real task has no graph file: 1 + 20 + 40 = 61
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(T2.sha256((TASKS / name).read_bytes()), digest, name)
        for key, items in self.all.items():
            for t, rows in items:
                self.assertEqual((TASKS / key / (t["task_id"] + ".json")).read_bytes(), T2.task_json(t))
                if rows is not None:
                    self.assertEqual((TASKS / key / t["graph_file"]).read_bytes(), T2.graph_json(rows))

    def test_the_refusals_are_recorded_in_the_task_with_their_reasons(self):
        for t, rows in self.all["dev"] + self.all["heldout"]:
            if t["profile"] in ("clean", "extrap"):
                self.assertIsNone(t["extrapolation_refused"], t["task_id"])
            else:
                self.assertTrue(t["extrapolation_refused"]["reasons"], t["task_id"])
                self.assertEqual(t["extrapolation_refused"]["reasons"], R.extrapolation_blockers(rows))


if __name__ == "__main__":
    unittest.main()
