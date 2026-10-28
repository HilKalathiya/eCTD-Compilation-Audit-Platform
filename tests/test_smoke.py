"""Smoke test: checks the engine package and its four parts can be imported."""
import unittest

import ectd_engine
from ectd_engine import facts, writer, validator, ledger  # noqa: F401


class SmokeTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(ectd_engine.__version__, "0.0.1")


if __name__ == "__main__":
    unittest.main()
