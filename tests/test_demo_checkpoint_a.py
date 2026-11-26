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


def saved_texts(tmp):
    """(html text, docx text) of the accepted render of a demo run in tmp."""
    import zipfile
    render = sorted((tmp / "run" / "draft").glob("render_*"))[-1]
    html = (render / "M23.html").read_text(encoding="utf-8")
    with zipfile.ZipFile(render / "M23.docx") as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return html, re.sub(r"<[^>]+>", "", xml)


class T077Fixes(unittest.TestCase):
    """T-077: the unit comes from the CSV, the study sentence carries the DEMO label, a changed CSV limit shows in the document,
    and a number that cannot be traced makes the demo exit 1."""

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(getattr(self, "csv_dir", self.tmp), ignore_errors=True)

    def test_dissolution_unit_comes_from_the_csv_and_study_sentence_is_labelled_in_both_files(self):
        code, text, _, self.tmp = run_demo()
        self.assertEqual(code, 0, text)
        html, docx = saved_texts(self.tmp)
        self.assertIn('data-src="M23-SPEC-LEK-dissolution_av">80</span>% dissolved', html)
        self.assertIn("NLT 80% dissolved", docx)
        _, rows = D.build_csv_world()
        spec = rows["M23-SPEC-LEK-dissolution_av"]
        self.assertEqual(spec["unit"], D.csv_lines()[46]["unit"])                    # the unit is the CSV's own unit cell
        pattern = r"In illustrative demonstration data, (stability was demonstrated|stability data cover|data are available|long-term)"
        self.assertRegex(html, pattern)
        self.assertRegex(docx, pattern)

    def test_changed_csv_limit_shows_in_the_document(self):
        self.csv_dir = Path(tempfile.mkdtemp(prefix="demo_csv_"))
        src = D.CSV_PATH.read_text(encoding="utf-8")
        self.assertIn("NLT 80", src)
        changed = self.csv_dir / "stab75.csv"
        with open(changed, "w", encoding="utf-8", newline="") as fh:
            fh.write(src.replace("NLT 80", "NLT 75"))
        code, text, _, self.tmp = run_demo(extra=["--csv", str(changed)])
        self.assertEqual(code, 0, text)
        self.assertIn("SOURCE TRACE OK", text)
        html, docx = saved_texts(self.tmp)
        self.assertIn('data-src="M23-SPEC-LEK-dissolution_av">75</span>% dissolved', html)
        self.assertIn("NLT 75% dissolved", docx)
        self.assertNotIn("NLT 80", docx)
        self.assertEqual(D.CSV_PATH, D.SF.DEFAULT_CSV)                               # the --csv choice did not leak

    def test_a_number_that_cannot_be_traced_makes_the_demo_exit_1(self):
        def world_with_untraceable_number(path=None):
            task, rows = D.build_csv_world(path)
            rows["M23-P8|20-25C CRT|expiry_period_proposed|36"]["doc_id"] = "somewhere_else.csv"      # a shown number whose source is not the CSV
            return task, rows
        code, text, res, self.tmp = run_demo(world=world_with_untraceable_number)
        self.assertEqual(code, 1, text)
        self.assertIn("NOT TRACED", text)
        self.assertIn("SOURCE TRACE FAILED", text)
        self.assertIn("DEMO FAILED", text)

    def test_a_label_inside_a_spec_row_is_refused_by_the_cross_check(self):
        """Why the spec rows are not labelled by the demo: the frozen cross-check accepts only 'test<TAB>kind number unit' for a row."""
        plain = D.label_demo

        def label_rows_too(built):
            for sections in built.values():
                for sec in sections:
                    if sec.name == "spec_table":
                        for par in sec.paragraphs:
                            par.text = "In illustrative demonstration data, " + par.text
                            D._shift(par, 0, len("In illustrative demonstration data, "))
            return plain(built)
        D.label_demo = label_rows_too
        try:
            code, text, _, self.tmp = run_demo()
        finally:
            D.label_demo = plain
        self.assertEqual(code, 1, text)
        self.assertIn("cross-check failed", text)


class CheckOneDocx(unittest.TestCase):
    """The one-line command for a classmate's edited Word file: `--check-docx FILE --kit KIT` prints the numbers it rejects."""

    def test_unedited_docx_passes_and_an_edited_number_is_rejected_by_name(self):
        import zipfile
        from tools import classmate_kit as K
        tmp = Path(tempfile.mkdtemp(prefix="check_docx_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with contextlib.redirect_stdout(io.StringIO()):
            kit = K.prepare(tmp / "kit")
        docx = kit / "for_classmate" / "M23.docx"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = D.main(["--check-docx", str(docx), "--kit", str(kit)])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn("rejected: 0", buf.getvalue())
        edited = tmp / "edited.docx"
        with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(edited, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    text = data.decode("utf-8")
                    self.assertIn("to 100.00% label claim", text)
                    data = text.replace("to 100.00% label claim", "to 101.00% label claim", 1).encode("utf-8")
                zout.writestr(info, data)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = D.main(["--check-docx", str(edited), "--kit", str(kit)])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertIn("REJECTED number 101.00 next to fact", buf.getvalue())                    # the new number has no fact that owns it
        self.assertIn("M23-STAT|25C/60%RH|Assay|max", buf.getvalue())                           # and the place of the fact that lost its number is named
        self.assertIn("REJECTED (", buf.getvalue())

    def test_missing_files_give_exit_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(D.main(["--check-docx", "nope.docx", "--kit", "nope"]), 2)


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
