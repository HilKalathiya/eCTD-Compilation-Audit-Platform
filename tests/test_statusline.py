"""Tests that the status line script shows four gauges and never crashes on odd input."""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "statusline.py")


def run(stdin_text):
    p = subprocess.run([sys.executable, SCRIPT], input=stdin_text, capture_output=True, text=True, timeout=5)
    return p.returncode, p.stdout.strip()


class StatusLineTests(unittest.TestCase):
    def test_full_input(self):
        code, out = run(json.dumps({
            "context_window": {"used_percentage": 42.4},
            "cost": {"total_cost_usd": 1.234},
            "rate_limits": {"five_hour": {"used_percentage": 17}},
        }))
        self.assertEqual(code, 0)
        self.assertIn("ctx 42%", out)
        self.assertIn("cost $1.23", out)
        self.assertIn("5h 17%", out)

    def test_no_rate_limits(self):
        code, out = run(json.dumps({"context_window": {"used_percentage": 5}, "cost": {"total_cost_usd": 0}}))
        self.assertEqual(code, 0)
        self.assertIn("5h -", out)
        self.assertIn("ctx 5%", out)
        self.assertIn("cost $0.00", out)

    def test_empty_stdin(self):
        code, out = run("")
        self.assertEqual(code, 0)
        self.assertIn("ctx - | cost - | 5h -", out)

    def test_garbage_stdin(self):
        for bad in ("not json", "[1,2]", '{"cost": "x", "context_window": null}'):
            code, out = run(bad)
            self.assertEqual(code, 0)
            self.assertIn("ctx - | cost - | 5h -", out)


if __name__ == "__main__":
    unittest.main()
