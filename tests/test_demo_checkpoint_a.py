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


def run_demo(extra=(), **kw):
    """Run the demo with --mock in its own fresh temp folder (default = the CSV chain; extra=["--synthetic"] = the invented task);
    returns (exit code, console text, result json, out folder)."""
    tmp = Path(tempfile.mkdtemp(prefix="demo_a_"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = D.main(["--out", str(tmp / "run"), "--mock", *extra], **kw)
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
        self.assertIn("RUN FINGERPRINT:", text)      # T-076: renamed from "RUN ID" (the card says: not a ledger)
        self.assertNotIn("ledger", text.replace("not a ledger entry", ""))      # no ledger claim anywhere in the console text
        self.assertIn("SOURCE TRACE OK", text)
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


class CsvChain(unittest.TestCase):
    """The default mode is one chain from the CSV: every number in the saved files traces to a CSV line."""

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_every_number_traces_to_the_csv_and_count_equals_crosscheck_total(self):
        code, text, res, self.tmp = run_demo()
        self.assertEqual(code, 0, text)
        t = res["source_trace"]
        self.assertGreater(t["numbers"], 0)
        self.assertEqual(t["untraced"], 0)
        self.assertEqual(t["traced"], t["numbers"])
        self.assertEqual(t["numbers"], t["crosscheck_total"])
        self.assertFalse(res["synthetic"])
        self.assertIn("finerenone_stability.csv", res["hashes"])
        self.assertRegex(text, r"PUBLIC fact: .*expiry_period_proposed.*\n\s+source: finerenone_stability.csv, row=\d+.*FDA review page 3")
        self.assertRegex(text, r"DEMO fact: .*label the writer must show: \"In illustrative demonstration data,\"\n\s+source: .*\(b\)\(4\) redacted in FDA review page 7")

    def test_stats_print_their_inputs_from_the_csv_rows(self):
        _, text, _, self.tmp = run_demo()
        self.assertIn("inputs: Assay at 25C/60%RH, 8 rows (row=6, row=7", text)
        self.assertIn("result: Q1E shelf-life estimate", text)

    def test_synthetic_mode_is_still_there_and_clearly_labelled(self):
        code, text, res, self.tmp = run_demo(extra=["--synthetic"])
        self.assertEqual(code, 0, text)
        self.assertIn("SYNTHETIC MODE", text)
        self.assertTrue(res["synthetic"])
        self.assertIsNone(res["source_trace"])

    def test_trace_fails_when_a_fact_does_not_lead_to_the_csv(self):
        _, rows = D.build_csv_world()
        lines = D.csv_lines()
        pub = "M23-P8|20-25C CRT|expiry_period_proposed|36"
        self.tmp = Path(tempfile.mkdtemp(prefix="demo_a_"))
        self.assertTrue(D.trace_one(pub, rows, lines)[0])
        other = {k: dict(v) for k, v in rows.items()}
        other[pub]["doc_id"] = "lek_spec.csv"                               # the fact claims another source
        self.assertFalse(D.trace_one(pub, other, lines)[0])
        other = {k: dict(v) for k, v in rows.items()}
        other[pub]["value_text"] = "37"                                     # the fact says a value the CSV line does not hold
        self.assertFalse(D.trace_one(pub, other, lines)[0])
        other = {k: dict(v) for k, v in rows.items()}
        other[pub]["locator"] = "row=999"                                   # a line the CSV does not have
        self.assertFalse(D.trace_one(pub, other, lines)[0])
        self.assertFalse(D.trace_one("M23-NOPE", rows, lines)[0])
        traced, bad, total = D.trace_numbers([{"number": "7", "fact_id": "", "format": "html"}], rows, lines)
        self.assertEqual((traced, len(bad), total), (0, 1, 1))

    def test_spec_limit_comes_from_the_csv_limit_column_not_the_lek_file(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="demo_a_"))
        task, rows = D.build_csv_world()
        spec = rows[task["spec"][0]["fact_id"]]
        self.assertEqual((spec["doc_id"], spec["limit_kind"], spec["value_text"]), ("finerenone_stability.csv", "NLT", "80"))
        self.assertTrue(spec["locator"].startswith("row="))


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
