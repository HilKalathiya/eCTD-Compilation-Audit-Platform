"""Tests for the 2.3 run script: half-up rounding with Decimal (no round()/float()), and a small scored run with a fake model."""
import re
import tempfile
import unittest
from pathlib import Path

from ectd_engine.summary import m23_run as R
from ectd_engine.summary import m23_tasks as T
from tests.test_m23_writer import Scripted, stub_messages

SUMMARY = Path(__file__).resolve().parent.parent / "ectd_engine" / "summary"


class HalfUp(unittest.TestCase):
    def test_a_half_second_rounds_up_not_to_even(self):
        # Python's round() gives 0, 2, 2 for 0.5, 1.5, 2.5 s: wrong here. Half up gives 1, 2, 3.
        self.assertEqual([R.seconds_from_ns(n) for n in (500_000_000, 1_500_000_000, 2_500_000_000)], [1, 2, 3])

    def test_below_and_above_the_half(self):
        self.assertEqual([R.seconds_from_ns(n) for n in (0, 499_999_999, 500_000_001, 61_000_000_000)], [0, 0, 1, 61])

    def test_the_old_round_behaviour_would_fail_the_half_case(self):
        self.assertEqual(round(2.5), 2)                      # what round() does ...
        self.assertNotEqual(R.seconds_from_ns(2_500_000_000), round(2.5))   # ... and what this code must not do

    def test_no_round_or_float_call_in_the_2_3_modules(self):
        for p in sorted(SUMMARY.glob("m23_*.py")) + [SUMMARY / "build.py", SUMMARY / "crosscheck.py"]:
            code = "\n".join(re.sub(r"#.*", "", ln) for ln in p.read_text(encoding="utf-8").splitlines())
            self.assertIsNone(re.search(r"(?<![\w.])(round|float)\(", code), p.name)


class SmallRun(unittest.TestCase):
    def test_run_set_scores_a_fake_model_run(self):
        tasks = [T.synthetic_task("dev", 1), T.synthetic_task("dev", 2)]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        class Both(Scripted):
            def __init__(self):
                self.parts = {t["task_id"]: Scripted(t) for t in tasks}
                self.calls = {}

            def chat(self, messages, temperature, seed, context=None, schema=None):
                return self.parts[context["task_id"]].chat(messages, temperature, seed, context)
        out = Path(tmp.name) / "r"
        summary = R.run_set(Both(), tasks, out, log=lambda *_: None, build_messages=stub_messages)
        self.assertEqual((summary["tasks"], summary["accepted"], summary["wrong_but_accepted"]), (2, 2, []))
        self.assertIsInstance(summary["seconds"], int)
        with self.assertRaises(FileExistsError):
            R.run_set(Both(), tasks, out, log=lambda *_: None, build_messages=stub_messages)


if __name__ == "__main__":
    unittest.main()
