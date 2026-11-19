"""Runs the whole test suite once and saves how many seconds each test took (slowest first) to a CSV file.

    python tools/test_times.py evidence/T-052/before.csv
"""
import csv
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TimedResult(unittest.TextTestResult):
    """A normal test result that also remembers how long each test ran."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times, self._t0 = [], 0.0

    def startTest(self, test):
        self._t0 = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.times.append((test.id(), time.perf_counter() - self._t0))
        super().stopTest(test)


def main(dest):
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    start = time.perf_counter()
    runner = unittest.TextTestRunner(resultclass=TimedResult, verbosity=0)
    result = runner.run(suite)
    wall = time.perf_counter() - start
    rows = sorted(result.times, key=lambda r: -r[1])
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test", "seconds"])
        w.writerows((name, f"{sec:.3f}") for name, sec in rows)
        w.writerow(["# tests_run", result.testsRun])
        w.writerow(["# sum_of_test_seconds", f"{sum(s for _, s in rows):.1f}"])
        w.writerow(["# wall_seconds_including_class_setup", f"{wall:.1f}"])
        w.writerow(["# skipped", len(result.skipped)])
        w.writerow(["# failures_and_errors", len(result.failures) + len(result.errors)])
    print(f"{result.testsRun} tests, wall {wall:.1f} s, skipped {len(result.skipped)} -> {dest}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "test_times.csv"))
