"""Checks the Q1E shelf life and the Decimal t quantile against t-tables, scipy and statsmodels."""
import unittest
from decimal import Decimal as D

import numpy as np
import statsmodels.api as sm
from scipy import stats
from scipy.optimize import brentq

from ectd_engine.stats.basic import round_to
from ectd_engine.stats.q1e import default_cap, fit, line_shelf_life, shelf_life
from ectd_engine.stats.tdist import cdf, t_quantile

MONTHS = [0, 3, 6, 9, 12, 18, 24]
NOISE = ["0.05", "-0.08", "0.12", "-0.03", "-0.10", "0.07", "0.02"]
ASSAY = [(D(m), D("100") - D("0.2") * m + D(n)) for m, n in zip(MONTHS, NOISE)]  # falls 0.2 %/month
IMPURITY = [(D(m), D("0.05") + D("0.01") * m + D(n) / 10) for m, n in zip(MONTHS, NOISE)]  # rises


def sm_fit(points):
    x = np.array([float(m) for m, _ in points])
    y = np.array([float(v) for _, v in points])
    return sm.OLS(y, sm.add_constant(x)).fit()


def sm_bound(result, month, side):
    """One-sided 95% bound = edge of the two-sided 90% interval of the mean."""
    frame = result.get_prediction(np.array([[1.0, float(month)]])).summary_frame(alpha=0.10)
    return float(frame["mean_ci_lower" if side == "lower" else "mean_ci_upper"].iloc[0])


def sm_shelf_life(points, side, spec, cap):
    result = sm_fit(points)
    sign = 1 if side == "lower" else -1
    return brentq(lambda m: sign * (sm_bound(result, m, side) - spec), 0, float(cap), xtol=1e-12)


class TestTDist(unittest.TestCase):
    def test_printed_t_table(self):
        table = {(0.95, 4): "2.132", (0.95, 1): "6.314", (0.95, 2): "2.920", (0.95, 10): "1.812",
                 (0.975, 5): "2.571", (0.95, 30): "1.697", (0.975, 12): "2.179"}
        for (p, df), printed in table.items():
            with self.subTest(p=p, df=df):
                self.assertEqual(str(round_to(t_quantile(D(str(p)), df), 3)), printed)

    def test_planted_wrong_df_fails_table(self):
        self.assertNotEqual(str(round_to(t_quantile(D("0.95"), 5), 3)), "2.132")

    def test_matches_scipy_odd_and_even_df(self):
        for df in (3, 4, 5, 6, 9, 20, 51):
            for p in ("0.9", "0.95", "0.975", "0.995"):
                with self.subTest(df=df, p=p):
                    q = float(t_quantile(D(p), df))
                    self.assertAlmostEqual(q, stats.t.ppf(float(p), df), places=8)  # scipy ppf is only ~1e-10 exact
                    self.assertAlmostEqual(stats.t.cdf(q, df), float(p), places=13)  # round trip is exact

    def test_cdf_and_symmetry(self):
        self.assertEqual(cdf(D(0), 7), D("0.5"))
        self.assertAlmostEqual(float(t_quantile(D("0.05"), 6)), -float(t_quantile(D("0.95"), 6)), places=25)
        self.assertAlmostEqual(float(cdf(D("2.132"), 4)), stats.t.cdf(2.132, 4), places=12)

    def test_bad_input(self):
        for p, df in ((D("0"), 4), (D("1"), 4), (D("0.95"), 0)):
            with self.assertRaises(ValueError):
                t_quantile(p, df)
        with self.assertRaises(TypeError):
            t_quantile(0.95, 4)


class TestFitAndBound(unittest.TestCase):
    def test_fit_matches_statsmodels(self):
        for points in (ASSAY, IMPURITY):
            f, r = fit(points), sm_fit(points)
            self.assertAlmostEqual(float(f.intercept), r.params[0], places=10)
            self.assertAlmostEqual(float(f.slope), r.params[1], places=10)
            self.assertAlmostEqual(float(f.residual_sd), float(np.sqrt(r.scale)), places=10)

    def test_bound_matches_statsmodels(self):
        for points, side in ((ASSAY, "lower"), (IMPURITY, "upper")):
            f, r = fit(points), sm_fit(points)
            for month in (0, 5, 12, 24, 30, 36):
                with self.subTest(side=side, month=month):
                    self.assertAlmostEqual(float(f.bound(D(month), side)), sm_bound(r, month, side), places=10)

    def test_planted_bound_is_not_the_line(self):
        f = fit(ASSAY)
        self.assertLess(f.bound(D(24), "lower"), f.line(D(24)))
        self.assertGreater(f.bound(D(24), "upper"), f.line(D(24)))

    def test_bad_side(self):
        with self.assertRaises(ValueError):
            fit(ASSAY).bound(D(6), "middle")


class TestShelfLife(unittest.TestCase):
    def test_assay_matches_statsmodels_solve(self):
        s = shelf_life(ASSAY, spec_min=D("95"))
        self.assertFalse(s.capped)
        self.assertEqual(s.side, "lower")
        self.assertLessEqual(abs(float(s.months) - sm_shelf_life(ASSAY, "lower", 95.0, s.cap_months)), 0.01)

    def test_impurity_matches_statsmodels_solve(self):
        s = shelf_life(IMPURITY, spec_max=D("0.40"))
        self.assertFalse(s.capped)
        self.assertEqual(s.side, "upper")
        self.assertLessEqual(abs(float(s.months) - sm_shelf_life(IMPURITY, "upper", 0.40, s.cap_months)), 0.01)

    def test_planted_line_gives_longer_shelf_life_than_bound(self):
        for points, kw in ((ASSAY, {"spec_min": D("95")}), (IMPURITY, {"spec_max": D("0.40")})):
            with self.subTest(kw=kw):
                line, bound = line_shelf_life(points, **kw), shelf_life(points, **kw).months
                self.assertGreater(line, bound)
                print(f"\n  line {line} months vs bound {bound} months ({kw})")

    def test_two_limits_earlier_wins(self):
        both = shelf_life(ASSAY, spec_min=D("95"), spec_max=D("101"))
        self.assertEqual(both.months, shelf_life(ASSAY, spec_min=D("95")).months)

    def test_cap_default_and_override(self):
        self.assertEqual(default_cap(ASSAY), D("36"))  # min(48, 24 + 12)
        self.assertEqual(default_cap([(D(m), D(1)) for m in (0, 3, 6)]), D("12"))  # min(12, 18)
        s = shelf_life(ASSAY, spec_min=D("95"), cap_months=D("20"))
        self.assertTrue(s.capped)
        self.assertEqual(s.months, D("20.00"))

    def test_flat_data_never_crosses_so_capped(self):
        flat = [(D(m), D("100")) for m in MONTHS]
        s = shelf_life(flat, spec_min=D("95"))
        self.assertTrue(s.capped)
        self.assertEqual(s.months, D("36.00"))
        self.assertIn("cap", s.reason)

    def test_already_outside_at_month_0(self):
        s = shelf_life(ASSAY, spec_min=D("100.5"))
        self.assertEqual(s.months, D("0.00"))
        self.assertFalse(s.capped)

    def test_too_few_points(self):
        with self.assertRaises(ValueError):
            shelf_life(ASSAY[:2], spec_min=D("95"))

    def test_same_month_only(self):
        with self.assertRaises(ValueError):
            fit([(D(6), D(1)), (D(6), D(2)), (D(6), D(3))])

    def test_input_checks(self):
        with self.assertRaises(ValueError):
            shelf_life(ASSAY)
        with self.assertRaises(TypeError):
            shelf_life(ASSAY, spec_min=95.0)
        with self.assertRaises(TypeError):
            fit([(0, D(1)), (3, D(2)), (6, D(3))])


if __name__ == "__main__":
    unittest.main()
