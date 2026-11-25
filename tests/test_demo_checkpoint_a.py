"""Tests for the Checkpoint A demo: runs end to end with the scripted model, and proves the demo FAILS when a planted error is not rejected (sabotage test)."""
import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import demo_checkpoint_a as D


def run_demo(**kw):
    """Run the demo with --mock in its own fresh temp folder; returns (exit code, console text, result json, out folder)."""
    tmp = Path(tempfile.mkdtemp(prefix="demo_a_"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = D.main(["--out", str(tmp / "run"), "--mock"], **kw)
    result = tmp / "run" / "demo_result.json"
    return code, buf.getvalue(), json.loads(result.read_text(encoding="utf-8")) if result.exists() else None, tmp


class DemoMock(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_end_to_end_both_plants_rejected(self):
        code, text, res, self.tmp = run_demo()
        self.assertEqual(code, 0, text)
        self.assertTrue(res["plant_number_rejected"])
        self.assertTrue(res["plant_digit_rejected"])
        for n in range(1, 8):
            self.assertIn("[%d/7]" % n, text)
        self.assertIn("RUN ID:", text)
        self.assertRegex(text, r"PLANT 1 REJECTED")
        self.assertRegex(text, r"PLANT 2 REJECTED")

    def test_plant_names_the_number_and_its_fact(self):
        _, text, _, self.tmp = run_demo()
        m = re.search(r"changed (\d+) -> (\d+) next to fact (.+?) \(copy", text)
        self.assertTrue(m)
        self.assertIn("fact %s owns the number %s; the file now shows %s there" % (m.group(3), m.group(1), m.group(2)), text)
        self.assertIn("cross-check says FAIL: number %s," % m.group(2), text)
        self.assertIn("fact %s," % m.group(3), text)

    def test_raw_draft_has_no_digit(self):
        _, text, _, self.tmp = run_demo()
        block = [ln[6:] for ln in text.splitlines() if ln.startswith("    | ")]
        self.assertTrue(block)
        self.assertFalse(re.search(r"\d", "\n".join(block)))


class SabotageTest(unittest.TestCase):
    """If a plant is NOT rejected, the demo must exit non-zero. These plants are deliberately harmless."""

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_number_plant_that_changes_nothing_fails_the_demo(self):
        def harmless(render, work):
            shutil.copytree(render, work)
            return Path(work), "12", "12", "M23-P8|2-25C CRT|expiry_period_proposed|12"
        code, text, res, self.tmp = run_demo(plant_number=harmless)
        self.assertNotEqual(code, 0)
        self.assertFalse(res["plant_number_rejected"])
        self.assertIn("NOT REJECTED", text)

    def test_draft_plant_without_a_digit_fails_the_demo(self):
        code, text, res, self.tmp = run_demo(plant_draft=lambda good: good)
        self.assertNotEqual(code, 0)
        self.assertFalse(res["plant_digit_rejected"])

    def test_existing_output_folder_is_refused(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="demo_a_"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(D.main(["--out", str(self.tmp), "--mock"]), 2)


if __name__ == "__main__":
    unittest.main()
