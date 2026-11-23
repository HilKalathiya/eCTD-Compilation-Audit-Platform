"""Tests for the T-072 tasks: ids-only task files, the consistency rules (each refuses a bad task and passes its boundary), outside-limit counts, the graph adapters."""
import copy
import hashlib
import json
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_tasks2 as T
from ectd_engine.summary import plan as P

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evidence" / "T-072" / "tasks"


class IdsOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = T.all_tasks()

    def test_counts(self):
        self.assertEqual((len(self.all["real"]), len(self.all["dev"]), len(self.all["heldout"])), (1, 10, 20))
        ids = [t["task_id"] for items in self.all.values() for t, _ in items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_task_file_holds_no_value_and_no_graph_rows(self):
        for items in self.all.values():
            for t, _ in items:
                text = T.task_json(t).decode("utf-8")
                for banned in ('"value"', '"value_text"', '"text"', "graph_rows", '"limit_text"'):
                    self.assertNotIn(banned, text, t["task_id"])

    def test_the_real_task_has_no_graph_file_and_synthetic_ones_do(self):
        self.assertIsNone(self.all["real"][0][0]["graph_file"])
        self.assertIsNone(self.all["real"][0][1])
        for t, rows in self.all["dev"] + self.all["heldout"]:
            self.assertEqual(t["graph_file"], t["task_id"] + ".graph.json")
            self.assertTrue(all(r["namespace"] == "SYNTHETIC" for r in rows.values()))

    def test_every_task_is_consistent_the_real_one_included(self):
        for t, rows in self.all["dev"] + self.all["heldout"]:
            self.assertEqual(T.consistency_problems(t, rows), [], t["task_id"])
        self.assertEqual(T.consistency_problems(T.real_task(), G.collect()), [])

    def test_the_real_task_ids_all_exist_in_the_real_facts(self):
        rows, t = G.collect(), T.real_task()
        for s in t["spec"]:
            self.assertIn(s["fact_id"], rows)
        for s in t["public"].values():
            self.assertIn(s["fact_id"], rows)
        for g in t["results"]:
            self.assertEqual(MG.stats(rows, g["condition"], g["attribute"])["low"]["fact_id"], g["stat"]["min"])

    def test_the_dev_and_heldout_sets_hold_extrapolation_outside_limit_and_equal_number_cases(self):
        for key in ("dev", "heldout"):
            items = self.all[key]
            self.assertTrue(any(t["extrapolation"] for t, _ in items), key)
            self.assertTrue(any(MG.stats(r, g["condition"], g["attribute"])["outside"] > 0 for t, r in items for g in t["results"]), key)
            self.assertTrue(any(r[t["public"]["shelf"]["fact_id"]]["value_text"] == r[t["public"]["long"]["fact_id"]]["value_text"] for t, r in items), key)
            self.assertTrue(any(g["attribute"] == "Dissolution (15 min)" for t, _ in items for g in t["results"]), key)

    def test_saved_files_equal_what_the_code_makes_now(self):
        for which, items in self.all.items():
            for t, rows in items:
                self.assertEqual((TASKS / which / (t["task_id"] + ".json")).read_bytes(), T.task_json(t), t["task_id"])
                if rows is not None:
                    self.assertEqual((TASKS / which / t["graph_file"]).read_bytes(), T.graph_json(rows), t["task_id"])

    def test_the_hash_list_matches_the_files_and_state_md(self):
        lines = (TASKS / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1 + 2 * 30)
        for line in lines:
            digest, name = line.split("  ")
            self.assertEqual(hashlib.sha256((TASKS / name).read_bytes()).hexdigest(), digest, name)
        state = (ROOT / "STATE.md").read_text(encoding="utf-8")
        for line in lines:
            if line.split("  ")[1].startswith("heldout/"):
                self.assertIn(line.split("  ")[0], state, line)


class Rules(unittest.TestCase):
    """Each rule: a task that breaks it is refused, and the same task exactly at the boundary passes."""

    @classmethod
    def setUpClass(cls):
        cls.base = {t["task_id"]: (t, r) for t, r in T.all_tasks()["dev"]}

    def pick(self, extrapolating):
        for t, r in self.base.values():
            if bool(t["extrapolation"]) == extrapolating:
                return copy.deepcopy(t), copy.deepcopy(r)
        raise AssertionError("no such task")

    def setv(self, t, r, slot, value):
        r[t["public"][slot]["fact_id"]]["value_text"] = str(value)

    def val(self, t, r, slot):
        return int(r[t["public"][slot]["fact_id"]]["value_text"])

    def group_with(self, t, cond):
        return next(g for g in t["results"] if g["condition"] == cond)

    def test_q1e_limit(self):
        self.assertEqual([T.q1e_max_shelf(m) for m in (6, 12, 24, 36, 48)], [12, 24, 36, 48, 60])

    def test_r1_accelerated_rows_stay_within_the_accelerated_duration(self):
        t, r = self.pick(False)
        g = next(g for g in t["results"] if g["condition"] == P.ACCEL)
        accel = self.val(t, r, "accel")
        rows = MG.group_rows(r, g["condition"], g["attribute"])
        self.assertTrue(max(int(x["month"]) for x in rows) <= accel)
        # boundary: a row exactly at the duration is fine; one month later is refused
        rows[-1]["month"] = str(accel)
        self.assertEqual([p for p in T.consistency_problems(t, r) if p.startswith("R1")], [])
        rows[-1]["month"] = str(accel + 1)
        self.assertTrue(any(p.startswith("R1") for p in T.consistency_problems(t, r)))

    def test_r2_long_term_and_intermediate_rows_stay_within_the_long_term_duration(self):
        for cond in (P.LONG, P.INTER):
            for t, r in self.base.values():
                if any(g["condition"] == cond for g in t["results"]):
                    t, r = copy.deepcopy(t), copy.deepcopy(r)
                    g = self.group_with(t, cond)
                    rows = MG.group_rows(r, g["condition"], g["attribute"])
                    rows[-1]["month"] = str(self.val(t, r, "long"))
                    self.assertEqual([p for p in T.consistency_problems(t, r) if p.startswith("R2")], [], cond)
                    rows[-1]["month"] = str(self.val(t, r, "long") + 1)
                    self.assertTrue(any(p.startswith("R2") for p in T.consistency_problems(t, r)), cond)
                    break
            else:
                self.fail("no task with " + cond)

    def test_r3_shelf_life_not_beyond_long_term_without_an_extrapolation_fact(self):
        t, r = self.pick(False)
        self.setv(t, r, "shelf", self.val(t, r, "long"))                 # boundary: equal passes
        self.assertEqual(T.consistency_problems(t, r), [])
        self.setv(t, r, "shelf", self.val(t, r, "long") + 6)             # longer, and no extrapolation fact
        self.assertTrue(any(p.startswith("R3") and "extrapolation fact" in p for p in T.consistency_problems(t, r)))

    def test_r3_extrapolated_shelf_life_stays_within_the_q1e_limit(self):
        t, r = self.pick(True)
        self.assertEqual(T.consistency_problems(t, r), [])
        long_ = self.val(t, r, "long")
        for shelf, ok in ((T.q1e_max_shelf(long_), True), (T.q1e_max_shelf(long_) + 1, False)):
            self.setv(t, r, "shelf", shelf)
            r[t["extrapolation"]]["value_text"] = str(shelf)
            got = [p for p in T.consistency_problems(t, r) if p.startswith("R3")]
            self.assertEqual(got == [], ok, (shelf, got))
            if not ok:
                self.assertIn("Q1E", got[0])

    def test_r3_an_extrapolation_fact_that_names_another_number_is_refused(self):
        t, r = self.pick(True)
        r[t["extrapolation"]]["value_text"] = str(self.val(t, r, "shelf") - 1)
        self.assertTrue(any(p.startswith("R3") for p in T.consistency_problems(t, r)))

    def test_r4_the_long_term_temperature_lies_inside_the_storage_range(self):
        t, r = self.pick(False)
        self.setv(t, r, "st_high", 25)                                   # boundary: 25 is the high end
        self.setv(t, r, "ex_high", 40)
        self.assertEqual([p for p in T.consistency_problems(t, r) if p.startswith("R4")], [])
        self.setv(t, r, "st_high", 24)                                   # the range now stops below 25
        self.assertTrue(any(p.startswith("R4") for p in T.consistency_problems(t, r)))

    def test_r5_the_excursion_range_holds_the_storage_range(self):
        t, r = self.pick(False)
        self.setv(t, r, "ex_low", self.val(t, r, "st_low"))              # boundary: equal ends are fine
        self.setv(t, r, "ex_high", max(self.val(t, r, "ex_high"), self.val(t, r, "st_high")))
        self.assertEqual([p for p in T.consistency_problems(t, r) if p.startswith("R5")], [])
        self.setv(t, r, "ex_low", self.val(t, r, "st_low") + 1)
        self.assertTrue(any(p.startswith("R5") for p in T.consistency_problems(t, r)))

    def test_r6_each_group_needs_three_distinct_months(self):
        t, r = self.pick(False)
        g = t["results"][0]
        rows = MG.group_rows(r, g["condition"], g["attribute"])
        for extra in rows[2:]:
            del r[extra["fact_id"]]
        self.assertTrue(any(p.startswith("R6") for p in T.consistency_problems(t, r)))

    def test_a_missing_public_fact_is_refused(self):
        t, r = self.pick(False)
        del r[t["public"]["long"]["fact_id"]]
        self.assertTrue(T.consistency_problems(t, r)[0].startswith("R0"))

    def test_the_real_task_breaks_none_of_the_rules(self):
        self.assertEqual(T.consistency_problems(T.real_task(), G.collect()), [])


class OutsideCount(unittest.TestCase):
    def test_counts_use_decimal_and_the_limit_text(self):
        ok = [("95.0", "95.0-105.0", False), ("94.99", "95.0-105.0", True), ("105.0", "95.0-105.0", False), ("105.01", "95.0-105.0", True),
              ("0.50", "NMT 0.50", False), ("0.501", "NMT 0.50", True), ("80", "NLT 80", False), ("79.99", "NLT 80", True),
              ("7", "", False), ("7", "weird", False)]
        for value, limit, want in ok:
            self.assertEqual(MG.outside(value, limit), want, (value, limit))

    def test_the_real_data_has_none_outside_and_the_planted_group_has_some(self):
        rows = G.collect()
        for cond, attr in P.STAT_GROUPS:
            self.assertEqual(MG.stats(rows, cond, attr)["outside"], 0, (cond, attr))
        g = P.STAT_GROUPS[0]
        bad = copy.deepcopy(rows)
        first = MG.group_rows(bad, *g)[0]
        first["value_text"] = "94.00" if g[1] == "Assay" else ("0.90" if g[1] == "Degradation product" else "70.00")
        self.assertEqual(MG.stats(bad, *g)["outside"], 1)

    def test_the_dissolution_time_point_is_a_derived_fact(self):
        s = MG.stats(G.collect(), P.LONG, "Dissolution (15 min)")
        self.assertEqual((s["timepoint"]["value_text"], s["timepoint"]["unit"]), ("15", "min"))
        self.assertIsNone(MG.stats(G.collect(), P.LONG, "Assay")["timepoint"])


class Adapters(unittest.TestCase):
    def test_the_memory_graph_refuses_rows_that_are_not_labelled_synthetic(self):
        t, rows = T.synthetic_task("dev", 1)
        MG.MemoryGraph(rows)
        bad = copy.deepcopy(rows)
        next(iter(bad.values())).pop("namespace")
        with self.assertRaises(ValueError):
            MG.MemoryGraph(bad)
        with self.assertRaises(ValueError):
            MG.MemoryGraph(G.collect())

    def test_the_memory_graph_returns_copies(self):
        t, rows = T.synthetic_task("dev", 1)
        g = MG.MemoryGraph(rows)
        got = g.rows()
        next(iter(got.values()))["value_text"] = "999"
        self.assertNotEqual(next(iter(g.rows().values()))["value_text"], "999")

    def test_a_graph_file_must_say_synthetic(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.json"
            p.write_text(json.dumps({"namespace": "NEO4J", "rows": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                MG.load_synthetic(p)

    def test_the_neo4j_reader_gives_the_same_facts_as_the_csv_build(self):
        got, want = MG.Neo4jGraph().rows(), G.collect()
        self.assertEqual({k: v["value_text"] for k, v in got.items()}, {k: v["value_text"] for k, v in want.items()})


if __name__ == "__main__":
    unittest.main()
