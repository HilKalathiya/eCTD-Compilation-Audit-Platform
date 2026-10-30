"""Tests for the out-of-trend check and the <LOQ policy, with planted errors."""
import unittest
from decimal import Decimal as D

from ectd_engine.stats import loq, oot
from ectd_engine.stats.loq import Below, Policy

HISTORY = [(D(m), D(v)) for m, v in [(0, "100.1"), (3, "99.8"), (6, "99.6"), (9, "99.1"), (12, "98.9")]]


class OotTests(unittest.TestCase):
    def test_point_inside_interval_is_ok(self):
        r = oot.check(HISTORY, (D(18), D("98.2")))
        self.assertIsInstance(r, oot.OK)
        self.assertLess(r.low, D("98.2"))
        self.assertGreater(r.high, D("98.2"))

    def test_planted_far_point_is_oot(self):
        r = oot.check(HISTORY, (D(18), D("90")))
        self.assertIsInstance(r, oot.OOT)

    def test_inside_spec_but_outside_interval_is_still_oot(self):
        spec_min = D("95")
        value = D("96.0")
        self.assertGreaterEqual(value, spec_min)  # passes the specification
        r = oot.check(HISTORY, (D(18), value))
        self.assertIsInstance(r, oot.OOT)  # but it breaks the trend
        self.assertGreater(r.low, value)

    def test_too_little_data(self):
        r = oot.check(HISTORY[:2], (D(18), D("98")))
        self.assertIsInstance(r, oot.NotEnoughData)
        self.assertIn("at least 3", r.message)

    def test_all_same_month(self):
        same = [(D(6), D(v)) for v in ("99.1", "99.3", "99.2")]
        r = oot.check(same, (D(12), D("98")))
        self.assertIsInstance(r, oot.NotEnoughData)
        self.assertIn("same month", r.message)

    def test_missing_months_and_ties_work(self):
        gaps = [(D(0), D("100.1")), (D(6), D("99.6")), (D(6), D("99.5")), (D(18), D("98.2"))]
        self.assertIsInstance(oot.check(gaps, (D(12), D("99.0"))), oot.OK)

    def test_float_refused(self):
        with self.assertRaises(TypeError):
            oot.check(HISTORY, (D(18), 98.2))

    def test_bad_level(self):
        with self.assertRaises(ValueError):
            oot.interval(HISTORY, D(18), D("1.5"))

    def test_matches_statsmodels_prediction_interval(self):
        import numpy as np
        import statsmodels.api as sm

        x = np.array([float(m) for m, _ in HISTORY])
        y = np.array([float(v) for _, v in HISTORY])
        res = sm.OLS(y, sm.add_constant(x)).fit()
        for month, level, alpha in ((18, "0.99", 0.01), (7, "0.95", 0.05)):
            frame = res.get_prediction(np.array([[1.0, float(month)]])).summary_frame(alpha=alpha)
            low, high = oot.interval(HISTORY, D(month), D(level))
            self.assertAlmostEqual(float(low), float(frame["obs_ci_lower"].iloc[0]), places=10)
            self.assertAlmostEqual(float(high), float(frame["obs_ci_upper"].iloc[0]), places=10)

    def test_interval_wider_than_confidence_bound(self):
        from ectd_engine.stats.q1e import fit

        low, high = oot.interval(HISTORY, D(18), D("0.90"))
        f = fit(HISTORY)
        self.assertLess(low, f.bound(D(18), "lower"))
        self.assertGreater(high, f.bound(D(18), "upper"))


class LoqParseTests(unittest.TestCase):
    def test_parse_forms(self):
        self.assertEqual(loq.parse("<LOQ", D("0.05")), Below(D("0.05")))
        self.assertEqual(loq.parse(" < loq ", D("0.05")), Below(D("0.05")))
        self.assertEqual(loq.parse("ND", D("0.05")), Below(D("0.05")))
        self.assertEqual(loq.parse("<0.1", D("0.05")), Below(D("0.1")))
        self.assertEqual(loq.parse("0.140", D("0.05")), D("0.140"))

    def test_garbage_refused(self):
        with self.assertRaises(ValueError):
            loq.parse("abc", D("0.05"))
        with self.assertRaises(ValueError):
            loq.parse("<abc", D("0.05"))


class LoqPolicyTests(unittest.TestCase):
    ROWS = [(D(0), D("0.10")), (D(3), D("0.12")), (D(6), Below(D("0.05"))), (D(9), D("0.16")),
            (D(12), Below(D("0.05"))), (D(18), D("0.20"))]

    def test_default_excludes_and_lists_dropped(self):
        res = loq.apply_policy(self.ROWS)
        self.assertEqual(len(res.points), 4)
        self.assertEqual([m for m, _ in res.dropped], [D(6), D(12)])
        self.assertIn("2 points <LOQ excluded", res.note)
        self.assertTrue(all(isinstance(v, D) for _, v in res.points))

    def test_loq_never_becomes_a_number_without_substitute(self):
        for pol in (Policy.EXCLUDE, Policy.REPORT_ONLY):
            res = loq.apply_policy(self.ROWS, pol)
            self.assertFalse(any(isinstance(v, Below) for _, v in res.points))
            self.assertNotIn(D("0.05"), [v for _, v in res.points])
            self.assertNotIn(D("0.025"), [v for _, v in res.points])

    def test_report_only_no_regression(self):
        res = loq.apply_policy(self.ROWS, Policy.REPORT_ONLY)
        self.assertEqual(res.points, ())
        self.assertIn("no regression", res.note)
        sl, note = loq.shelf_life_with_policy(self.ROWS, spec_max=D("0.5"), policy=Policy.REPORT_ONLY)
        self.assertIsNone(sl)
        self.assertIn("no regression", note)

    def test_substitute_needs_value_and_reason(self):
        with self.assertRaises(ValueError):
            loq.apply_policy(self.ROWS, Policy.SUBSTITUTE)
        with self.assertRaises(ValueError):
            loq.apply_policy(self.ROWS, Policy.SUBSTITUTE, D("0.025"))
        with self.assertRaises(ValueError):
            loq.apply_policy(self.ROWS, Policy.SUBSTITUTE, D("0.025"), "   ")
        with self.assertRaises(ValueError):
            loq.apply_policy(self.ROWS, Policy.SUBSTITUTE, None, "LOQ/2 per SOP")

    def test_substitute_is_recorded(self):
        res = loq.apply_policy(self.ROWS, Policy.SUBSTITUTE, D("0.025"), "LOQ/2 per SOP-12")
        self.assertIn(D("0.025"), [v for _, v in res.points])
        self.assertIn("0.025", res.note)
        self.assertIn("SOP-12", res.note)

    def test_all_loq_gives_clear_message(self):
        rows = [(D(0), Below(D("0.05"))), (D(3), Below(D("0.05"))), (D(6), Below(D("0.05")))]
        res = loq.apply_policy(rows)
        self.assertEqual(res.points, ())
        self.assertIn("no measured points left", res.note)
        sl, note = loq.shelf_life_with_policy(rows, spec_max=D("0.5"))
        self.assertIsNone(sl)
        self.assertIn("shelf life not computed", note)
        self.assertIn("at least 3", note)

    def test_shelf_life_caller_gets_note(self):
        sl, note = loq.shelf_life_with_policy(self.ROWS, spec_max=D("0.5"))
        self.assertIsNotNone(sl)
        self.assertIn("2 points <LOQ excluded", note)

    def test_oot_caller_gets_note(self):
        r, note = oot.check_with_policy(self.ROWS, (D(24), D("0.22")))
        self.assertIsInstance(r, oot.OK)
        self.assertIn("2 points <LOQ excluded", note)
        r, _ = oot.check_with_policy(self.ROWS, (D(24), D("5.0")))
        self.assertIsInstance(r, oot.OOT)

    def test_oot_new_point_below_loq_is_not_tested(self):
        r, _ = oot.check_with_policy(self.ROWS, (D(24), Below(D("0.05"))))
        self.assertIsInstance(r, oot.NotEnoughData)

    def test_oot_all_loq_history(self):
        rows = [(D(0), Below(D("0.05"))), (D(3), Below(D("0.05")))]
        r, note = oot.check_with_policy(rows, (D(6), D("0.1")))
        self.assertIsInstance(r, oot.NotEnoughData)
        self.assertIn("no measured points left", note)


if __name__ == "__main__":
    unittest.main()
