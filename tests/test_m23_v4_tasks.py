"""Tests for the T-074 rules (every limit from one spec fact, review route, unknown limits) and the T-074 task generator, each check with a planted case that must fail."""
import copy
import inspect
import json
import unittest

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_rules4 as R
from ectd_engine.summary import m23_tasks2 as T
from ectd_engine.summary import m23_tasks4 as T4
from ectd_engine.summary import plan as P

LONG, INTER, ACCEL = P.LONG, P.INTER, P.ACCEL


def dev(i):
    return T4.synthetic_task4("dev", i)


def by_profile(profile, which="dev"):
    i = next(i for i in range(1, 11) if T4.PROFILES[i - 1] == profile)
    return T4.synthetic_task4(which, i)


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = T4.all_tasks4()

    def test_counts_and_ids_only(self):
        self.assertEqual({k: len(v) for k, v in self.all.items()}, {"real": 1, "dev": 10, "heldout": 20})
        for items in self.all.values():
            for t, _ in items:
                text = T.task_json(t).decode("utf-8")
                self.assertNotIn("value_text", text)
                self.assertEqual(t["version"], "v4")

    def test_every_task_is_consistent_and_deterministic(self):
        for which in ("dev", "heldout"):
            for t, rows in self.all[which]:
                self.assertEqual(T4.consistency_problems4(t, rows), [], t["task_id"])
        again = T4.all_tasks4()
        for which in ("dev", "heldout"):
            self.assertEqual([T.task_json(t) for t, _ in self.all[which]], [T.task_json(t) for t, _ in again[which]])

    def test_new_seeds_new_numbers(self):
        old = __import__("ectd_engine.summary.m23_tasks3", fromlist=["x"])
        self.assertFalse({t["task_id"] for t, _ in self.all["heldout"]} & {t["task_id"] for t, _ in old.all_tasks3()["heldout"]})

    def test_at_least_12_of_20_heldout_show_bad_data_to_the_writer(self):
        kinds = [R.bad_data_to_writer(rows, R.links_of(t)) for t, rows in self.all["heldout"]]
        self.assertGreaterEqual(sum(k is not None for k in kinds), 12)
        for kind in ("review", "significant_change", "outside_accelerated"):
            self.assertIn(kind, kinds)
        dev_kinds = {R.bad_data_to_writer(rows, R.links_of(t)) for t, rows in self.all["dev"]}
        self.assertTrue({"review", "significant_change", "outside_accelerated"} <= dev_kinds)

    def test_every_synthetic_group_has_one_spec_fact_of_the_right_family(self):
        for which in ("dev", "heldout"):
            for t, rows in self.all[which]:
                shown = {s["fact_id"] for s in t["spec"]}
                for g in t["results"]:
                    fid = g["spec_fact"]
                    self.assertIn(fid, shown)
                    self.assertEqual(rows[fid]["family"], "spec")
                    if g["attribute"] == "Assay":
                        self.assertEqual(fid, G.spec_id("assay"))
                    elif g["attribute"] == "Dissolution (15 min)":
                        self.assertEqual(fid, G.spec_id("dissolution_av"))
                    else:
                        self.assertIn(fid[len(G.PREFIX + "SPEC-LEK-"):], T4.IMPURITY_SPEC)

    def test_real_task_links_dissolution_only(self):
        t = self.all["real"][0][0]
        for g in t["results"]:
            self.assertEqual(g["spec_fact"], G.spec_id("dissolution_av") if g["attribute"] == "Dissolution (15 min)" else None)
        rows = G.collect()
        self.assertEqual(T4.consistency_problems4(t, rows), [])
        units = T4.units_of4(t, rows)
        for u in units:
            if u["kind"] == "result":
                self.assertEqual(u["expect"], ["range", "claim"] if u["attribute"] == "Dissolution (15 min)" else ["range"])
        self.assertEqual(R.review_reasons(rows, R.links_of(t)), [])

    def test_generator_has_no_assert_and_raises_when_a_profile_lies(self):
        self.assertNotIn("assert ", inspect.getsource(T4))
        t, rows = by_profile("clean")
        with self.assertRaises(T4.TaskError):
            T4._check_profile("outside_lt", rows, R.links_of(t), 12, 12)                # clean data cannot be a review task
        t, rows = by_profile("outside_lt")
        with self.assertRaises(T4.TaskError):
            T4._check_profile("clean", rows, R.links_of(t), 12, 12)

    def test_degradation_bad_and_ok_values_follow_the_linked_limit(self):
        import random
        rng = random.Random("x")
        for lim in ("0.2", "0.3", "0.5", "0.7", "1.0", "2.0"):
            for _ in range(50):
                self.assertTrue(R.Decimal(T4._ok_value(rng, "Degradation product", lim)) <= R.Decimal(lim))
            self.assertTrue(R.Decimal(T4._bad_value("Degradation product", lim)) > R.Decimal(lim))
        self.assertTrue(R.Decimal(T4._bad_value("Assay", "96.0")) < R.Decimal("96.0"))
        self.assertTrue(R.Decimal(T4._bad_value("Dissolution (15 min)", "70")) < R.Decimal("70"))


class LimitSourceTests(unittest.TestCase):
    """R7 for every attribute: the stored limit must be the linked spec fact's; a mismatch, a missing spec fact or a missing link is refused."""

    def setup_task(self, attr):
        for i in range(1, 11):
            t, rows = dev(i)
            g = next((g for g in t["results"] if g["attribute"] == attr), None)
            if g:
                return t, rows, g
        self.fail("no dev task with " + attr)

    def test_refusal_for_each_attribute(self):
        for attr in ("Assay", "Degradation product", "Dissolution (15 min)"):
            with self.subTest(attr=attr):
                t, rows, g = self.setup_task(attr)
                links = R.links_of(t)
                self.assertEqual(R.limit_problems(rows, links), [])
                # (1) the spec fact changes: the stored rows now disagree with it -> R7 refuses
                bad = copy.deepcopy(rows)
                bad[g["spec_fact"]]["value_text"] = "0.9" if attr == "Degradation product" else "50.0"
                self.assertTrue(any(p.startswith("R7") for p in R.limit_problems(bad, links)))
                self.assertTrue(any(p.startswith("R7") for p in T4.consistency_problems4(t, bad)))
                # (2) the spec fact is not in the graph
                gone = copy.deepcopy(rows)
                del gone[g["spec_fact"]]
                self.assertTrue(any("not in the graph" in p for p in R.limit_problems(gone, links)))
                # (3) the spec table does not show the fact
                t3 = copy.deepcopy(t)
                t3["spec"] = [s for s in t3["spec"] if s["fact_id"] != g["spec_fact"]]
                self.assertTrue(any("does not show" in p for p in T4.consistency_problems4(t3, rows)))
                # (4) a synthetic group with no link is refused
                t4 = copy.deepcopy(t)
                next(x for x in t4["results"] if x["condition"] == g["condition"] and x["attribute"] == attr)["spec_fact"] = None
                self.assertTrue(any("no spec fact" in p for p in T4.consistency_problems4(t4, rows)))

    def test_the_outside_count_follows_the_spec_fact(self):
        t, rows, g = self.setup_task("Dissolution (15 min)")
        links = R.links_of(t)
        key = (g["condition"], g["attribute"])
        before = R.outside_count(rows, links, *key)
        moved = copy.deepcopy(rows)
        moved[g["spec_fact"]]["value_text"] = "99"                                      # a limit of NLT 99: now results are below it
        self.assertGreater(R.outside_count(moved, links, *key), before)

    def test_unknown_limit_is_never_zero_outside(self):
        t, rows = by_profile("clean")
        links = dict(R.links_of(t))
        key = next(k for k in links if k[0] == LONG)
        unlinked = {**links, key: None}
        broken = copy.deepcopy(rows)
        for r in MG.group_rows(broken, *key):
            r["limit_text"] = ""                                                         # no link and no readable limit
        with self.assertRaises(R.LimitUnknown):
            R.outside_count(broken, unlinked, *key)
        self.assertTrue(any("limit is unknown" in b for b in R.study_blockers(broken, unlinked)))
        self.assertTrue(R.extrapolation_blockers(broken, unlinked))
        self.assertEqual(R.review_reasons(broken, unlinked), [])                         # unknown blocks claims, it does not trigger the review route
        self.assertTrue(any(p.startswith("R7") for p in R.limit_problems(broken, unlinked)))

    def test_a_group_with_no_spec_fact_gets_no_claim_sentence_but_still_blocks(self):
        t, rows = by_profile("outside_lt")
        links = dict(R.links_of(t))
        key = next(k for k in links if k[0] == LONG)
        t2 = copy.deepcopy(t)
        next(x for x in t2["results"] if (x["condition"], x["attribute"]) == key)["spec_fact"] = None
        rows2 = copy.deepcopy(rows)
        for r in MG.group_rows(rows2, *key):                                             # its own rows keep one readable limit
            r["limit_text"] = {"Assay": "NLT 95.0", "Degradation product": "NMT 0.5"}.get(key[1], r["limit_text"])
        units = [u for u in T4.units_of4(t2, rows2) if u["kind"] == "result" and (u["condition"], u["attribute"]) == key]
        self.assertEqual(units[0]["expect"], ["range"])
        self.assertEqual(units[0]["context"]["outside"], "not stated")


class ReviewRouteTests(unittest.TestCase):
    def test_review_route_blocks_the_shelf_life_even_when_shelf_is_not_beyond_the_data(self):
        for profile in ("outside_lt", "outside_int"):
            t, rows = by_profile(profile)
            links = R.links_of(t)
            shelf, long_ = (R.Decimal(rows[t["public"][k]["fact_id"]]["value_text"]) for k in ("shelf", "long"))
            self.assertLessEqual(shelf, long_)                                           # the case T-073 allowed: shelf <= long-term with a long-term failure
            self.assertTrue(R.review_reasons(rows, links))
            pub = next(u for u in T4.units_of4(t, rows) if u["kind"] == "public")
            self.assertEqual(pub["expect"], ["excursion", "study"])
            self.assertTrue({"shelf", "st_low", "st_high"}.isdisjoint(pub["slots"]))
            self.assertTrue({"shelf", "st_low", "st_high"}.isdisjoint(pub["required"]))
            self.assertEqual(pub["context"]["shelf"], "blocked")
            self.assertEqual(pub["context"]["demonstrated"], "not allowed")
            self.assertEqual(pub["review_ids"], R.review_ids(rows, links))

    def test_no_review_route_when_only_accelerated_data_are_bad(self):
        for profile in ("outside_accel", "sig_assay", "clean", "extrap"):
            t, rows = by_profile(profile)
            self.assertEqual(R.review_reasons(rows, R.links_of(t)), [], profile)
            pub = next(u for u in T4.units_of4(t, rows) if u["kind"] == "public")
            self.assertEqual(pub["expect"], ["shelf", "excursion", "study"])
            self.assertEqual(pub["context"]["shelf"], "written")

    def test_one_bad_result_at_long_term_or_intermediate_is_enough(self):
        t, rows = by_profile("clean")
        links = R.links_of(t)
        self.assertEqual(R.review_reasons(rows, links), [])
        key = next(k for k in links if k[0] != ACCEL)
        bad = copy.deepcopy(rows)
        r = next(r for r in MG.group_rows(bad, *key) if r["month"] != "0")
        r["value_text"] = T4._bad_value(key[1], bad[links[key]]["value_text"])
        reasons = R.review_reasons(bad, links)
        self.assertEqual([(c, a) for c, a, _ in reasons], [key])
        self.assertEqual(R.review_ids(bad, links), [R.outside_id(*key)])

    def test_significant_change_and_accelerated_outside_follow_q1a(self):
        t, rows = by_profile("sig_assay")
        links = R.links_of(t)
        self.assertTrue(R.significant_change(rows, links, "Assay"))
        self.assertEqual(R.bad_data_to_writer(rows, links), "significant_change")
        self.assertTrue(any("significant change" in b for b in R.extrapolation_blockers(rows, links)))
        t, rows = by_profile("outside_accel")
        self.assertEqual(R.bad_data_to_writer(rows, R.links_of(t)), "outside_accelerated")
        self.assertEqual(R.study_blockers(rows, R.links_of(t)), [])                      # accelerated-only failures do not block "demonstrated"


if __name__ == "__main__":
    unittest.main()
