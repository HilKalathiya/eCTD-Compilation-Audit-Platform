"""Checks the Q1E poolability decision and shelf life against statsmodels' ANCOVA tables."""
import unittest
from decimal import Decimal as D

import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm

from ectd_engine.stats.pool import COMMON_SLOPE, POOLED, SEPARATE, decide, poolability
from ectd_engine.stats.q1e import shelf_life
from ectd_engine.stats.tdist import f_cdf

MONTHS = [0, 3, 6, 9, 12, 18, 24]
NOISE = ["0.05", "-0.08", "0.12", "-0.03", "-0.10", "0.07", "0.02"]
SPEC_MIN = D("95")


def batch(shift, intercept, slope):
    """One batch: a straight line plus the same small noise pattern, rotated by `shift`."""
    noise = NOISE[shift:] + NOISE[:shift]
    return [(D(m), D(intercept) + D(slope) * m + D(n)) for m, n in zip(MONTHS, noise)]


CASE_A = {"A": batch(0, "100.00", "-0.2"), "B": batch(2, "100.03", "-0.2"), "C": batch(4, "99.98", "-0.2")}
CASE_B = {"A": batch(0, "101", "-0.2"), "B": batch(2, "100", "-0.2"), "C": batch(4, "99", "-0.2")}
CASE_C = {"A": batch(0, "100", "-0.2"), "B": batch(2, "100", "-0.2"), "C": batch(4, "100", "-0.4")}


def sm_p_values(batches):
    """(p for equal slopes, p for equal intercepts) from statsmodels anova_lm."""
    rows = [(b, float(m), float(v)) for b, pts in batches.items() for m, v in pts]
    frame = pd.DataFrame(rows, columns=["b", "t", "y"])
    slopes = anova_lm(smf.ols("y ~ t * C(b)", frame).fit()).loc["t:C(b)", "PR(>F)"]
    intercepts = anova_lm(smf.ols("y ~ t + C(b)", frame).fit()).loc["C(b)", "PR(>F)"]
    return slopes, intercepts


class TestPool(unittest.TestCase):
    def check_p(self, batches, result):
        sm_slope, sm_int = sm_p_values(batches)
        self.assertAlmostEqual(float(result.p_slope), sm_slope, places=10)
        self.assertAlmostEqual(float(result.p_intercept), sm_int, places=10)

    def test_a_same_slope_and_intercept_pools_fully(self):
        r = poolability(CASE_A, spec_min=SPEC_MIN)
        self.assertEqual(r.decision, POOLED)
        self.assertGreater(r.p_slope, D("0.25"))
        self.assertGreater(r.p_intercept, D("0.25"))
        self.check_p(CASE_A, r)
        merged = [p for pts in CASE_A.values() for p in pts]
        self.assertEqual(r.shelf, shelf_life(merged, spec_min=SPEC_MIN))

    def test_b_shifted_intercepts_keep_common_slope(self):
        r = poolability(CASE_B, spec_min=SPEC_MIN)
        self.assertEqual(r.decision, COMMON_SLOPE)
        self.assertGreater(r.p_slope, D("0.25"))
        self.assertLessEqual(r.p_intercept, D("0.25"))
        self.check_p(CASE_B, r)
        # lowest-starting batch (C) decides; higher intercepts last longer
        self.assertEqual(r.shelf.months, min(r.per_batch.values()))
        self.assertEqual(r.per_batch["C"], r.shelf.months)
        self.assertLess(r.per_batch["C"], r.per_batch["B"])
        self.assertLess(r.per_batch["B"], r.per_batch["A"])

    def test_c_faster_batch_means_separate_and_its_shelf_life(self):
        r = poolability(CASE_C, spec_min=SPEC_MIN)
        self.assertEqual(r.decision, SEPARATE)
        self.assertLessEqual(r.p_slope, D("0.25"))
        self.check_p(CASE_C, r)
        own = {b: shelf_life(pts, spec_min=SPEC_MIN) for b, pts in CASE_C.items()}
        self.assertEqual(r.shelf, own["C"])
        self.assertEqual(r.shelf.months, min(s.months for s in own.values()))
        self.assertEqual(r.per_batch, {b: s.months for b, s in own.items()})

    def test_planted_forcing_full_pooling_on_case_c_gives_longer_shelf_life(self):
        r = poolability(CASE_C, spec_min=SPEC_MIN)
        merged = [p for pts in CASE_C.values() for p in pts]
        forced = shelf_life(merged, spec_min=SPEC_MIN)
        self.assertGreater(forced.months, r.shelf.months)  # the over-claim Q1E poolability prevents

    def test_p_exactly_025_is_not_pooled(self):
        self.assertEqual(decide(D("0.25"), D("0.9")), SEPARATE)
        self.assertEqual(decide(D("0.26"), D("0.25")), COMMON_SLOPE)
        self.assertEqual(decide(D("0.26"), D("0.26")), POOLED)
        self.assertEqual(decide(D("0.2500000001"), D("0.2500000001")), POOLED)

    def test_slopes_are_tested_before_intercepts(self):
        self.assertEqual(decide(D("0.01"), D("0.9")), SEPARATE)  # intercepts agree, slopes do not

    def test_one_batch_is_refused(self):
        with self.assertRaises(ValueError):
            poolability({"A": CASE_A["A"]}, spec_min=SPEC_MIN)

    def test_batch_with_two_points_is_refused(self):
        bad = dict(CASE_A, C=CASE_A["C"][:2])
        with self.assertRaises(ValueError):
            poolability(bad, spec_min=SPEC_MIN)

    def test_float_is_refused(self):
        bad = dict(CASE_A, C=[(m, float(v)) for m, v in CASE_A["C"]])
        with self.assertRaises(TypeError):
            poolability(bad, spec_min=SPEC_MIN)

    def test_needs_a_spec_limit(self):
        with self.assertRaises(ValueError):
            poolability(CASE_A)


class TestFCdf(unittest.TestCase):
    def test_matches_scipy(self):
        from scipy import stats

        for d1, d2 in ((1, 1), (2, 14), (3, 17), (4, 9), (5, 30)):
            for x in ("0.1", "0.8", "1.5", "4.2", "25"):
                with self.subTest(d1=d1, d2=d2, x=x):
                    self.assertAlmostEqual(float(f_cdf(D(x), d1, d2)), stats.f.cdf(float(x), d1, d2), places=12)

    def test_edges(self):
        self.assertEqual(f_cdf(D(0), 2, 5), D(0))
        with self.assertRaises(TypeError):
            f_cdf(1.5, 2, 5)


if __name__ == "__main__":
    unittest.main()
