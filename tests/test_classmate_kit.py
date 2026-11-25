"""Tests for the classmate kit: a SCRIPTED classmate makes 10 mixed edits and the real checks must find them (misses are asserted, not hidden)."""
import builtins
import contextlib
import csv
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools import classmate_kit as K


def edit_text(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) >= 1, f"{old!r} not found in {p.name}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def edit_docx(path, old, new):
    """Replace the first occurrence of text inside word/document.xml; every other part of the zip is copied unchanged."""
    p = Path(path)
    with zipfile.ZipFile(p) as z:
        parts = [(i, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in parts:
            if info.filename == "word/document.xml":
                text = data.decode("utf-8")
                assert old in text, f"{old!r} not in the docx"
                data = text.replace(old, new, 1).encode("utf-8")
            z.writestr(info, data)


def csv_line_of(path, start):
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if line.startswith(start):
            return i
    raise AssertionError(start)


def edit_csv_line(path, line_no, old, new):
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    assert old in lines[line_no - 1]
    lines[line_no - 1] = lines[line_no - 1].replace(old, new, 1)
    Path(path).write_text("".join(lines), encoding="utf-8")


def write_answers(kit, rows):
    with open(Path(kit) / "answers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(K.ANSWER_COLUMNS)
        for r in rows:
            w.writerow(r)


def quiet_prepare(out):
    with contextlib.redirect_stdout(io.StringIO()):
        return K.prepare(out)


class KitBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="kit_t_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def fresh_kit(self, name):
        return quiet_prepare(self.root / name)


class Prepare(KitBase):
    def test_prepare_makes_the_folders_and_the_blank_answer_sheet(self):
        kit = self.fresh_kit("p1")
        self.assertEqual(sorted(p.name for p in (kit / "for_classmate").iterdir()), ["INSTRUCTIONS.txt", "M23.docx", "M23.html", "finerenone_stability.csv"])
        self.assertTrue((kit / "trusted" / "task.json").exists())
        with open(kit / "answers.csv", newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], K.ANSWER_COLUMNS)
        self.assertEqual(len(rows), 11)
        self.assertIn("up to 10", (kit / "for_classmate" / "INSTRUCTIONS.txt").read_text(encoding="utf-8"))

    def test_prepare_refuses_an_existing_folder(self):
        kit = self.fresh_kit("p2")
        with self.assertRaises(FileExistsError):
            K.prepare(kit)

    def test_unedited_files_give_no_finding_at_all(self):
        """No false alarm: the files exactly as handed out pass every check."""
        kit = self.fresh_kit("p3")
        res = K.run_checks(kit / "for_classmate", kit / "trusted")
        self.assertEqual(res["findings"], [])
        self.assertEqual(res["changed"], {"csv": False, "html": False, "docx": False})


class StepOneNeverOpensTheAnswers(KitBase):
    def test_run_checks_does_not_open_answers_csv(self):
        kit = self.fresh_kit("s1")
        edit_text(kit / "for_classmate" / "M23.html", "Excursions are permitted from", "Excursions are allowed from")
        opened = []
        real_open, real_io_open = builtins.open, __import__("io").open

        def spy(real):
            def inner(file, *a, **k):
                opened.append(str(file))
                return real(file, *a, **k)
            return inner
        with mock.patch("builtins.open", spy(real_open)), mock.patch("io.open", spy(real_io_open)):
            res = K.run_checks(kit / "for_classmate", kit / "trusted")
        self.assertTrue(res["findings"])
        self.assertTrue(opened)
        self.assertFalse([p for p in opened if "answers" in Path(p).name], opened)

    def test_scoring_does_not_need_the_answers_for_step_one(self):
        kit = self.fresh_kit("s2")
        edit_text(kit / "for_classmate" / "M23.html", "Excursions are permitted from", "Excursions are allowed from")
        (kit / "answers.csv").unlink()                                       # the answer sheet is gone: step 1 must still work
        self.assertTrue(K.run_checks(kit / "for_classmate", kit / "trusted")["findings"])


class MatchNeedsEvidence(KitBase):
    def test_a_checker_that_finds_nothing_is_scored_missed(self):
        """Independence: with no findings every listed change is MISSED (the scorer cannot give credit the checks did not earn)."""
        answers = [{"n": "1", "file": "html", "csv_line": "", "near": "shelf life", "original_text": "36", "new_text": "48", "kind": "number"}]
        out = K.match_answers({"findings": [], "changed": {}}, answers, self.fresh_kit("m1") / "trusted")
        self.assertEqual(out["results"][0]["result"], "MISSED")

    def test_a_claimed_change_in_an_untouched_file_is_not_credited(self):
        kit = self.fresh_kit("m2")
        edit_text(kit / "for_classmate" / "M23.html", "Excursions are permitted from", "Excursions are allowed from")
        checks = K.run_checks(kit / "for_classmate", kit / "trusted")
        answers = [{"n": "1", "file": "csv", "csv_line": "12", "near": "Assay", "original_text": "99.52", "new_text": "99.50", "kind": "number"}]
        self.assertEqual(K.match_answers(checks, answers, kit / "trusted")["results"][0]["result"], "MISSED")


class ScriptedClassmate(KitBase):
    """Ten mixed edits made by a script. This is NOT the real classmate test (a person who is not on the team has not done it)."""

    EXPECTED = {
        1: ("CAUGHT", "crosscheck"),            # html number 36 -> 48
        2: ("CAUGHT", "crosscheck"),            # docx number 100.00 -> 101.00
        3: ("CAUGHT", "csv_rules"),             # csv: Assay 25C month 36 99.28 -> 89.28 (outside its limit)
        4: ("NOT LOCATED", None),               # csv: Assay 25C month 12 99.76 -> 99.70, inside the limits and never printed: only the fingerprint sees it
        5: ("CAUGHT", "csv_vs_document"),       # csv: proposed shelf life 36 -> 48 (the saved document no longer matches the CSV fact)
        6: ("CAUGHT", "compare4"),              # html claim flip
        7: ("CAUGHT", "wording"),               # docx claim flip
        8: ("CAUGHT", "crosscheck"),            # html unit change
        9: ("CAUGHT", "wording"),               # docx: a claim sentence emptied
        10: ("CAUGHT", "compare4"),             # html: DEMO label removed from one sentence
    }

    def test_ten_mixed_edits(self):
        kit = self.fresh_kit("c1")
        give = kit / "for_classmate"
        html, docx, data = give / "M23.html", give / "M23.docx", give / "finerenone_stability.csv"
        l36 = csv_line_of(data, "25C/60%RH,36,Assay,99.28")
        l12 = csv_line_of(data, "25C/60%RH,12,Assay,99.76")
        l5 = csv_line_of(data, "20-25C CRT,36,expiry_period_proposed,36")
        edit_text(html, 'expiry_period_proposed|36">36</span>', 'expiry_period_proposed|36">48</span>')
        edit_docx(docx, "99.28% label claim to 100.00% label claim", "99.28% label claim to 101.00% label claim")
        edit_csv_line(data, l36, "99.28", "89.28")
        edit_csv_line(data, l12, "99.76", "99.70")
        edit_csv_line(data, l5, "36,months", "48,months")
        edit_text(html, " min) under long-term conditions had no results outside the limit.", " min) under long-term conditions had results outside the limit.")      # the 15 sits in its own number tag in the HTML
        edit_docx(docx, "Dissolution (15 min) under intermediate conditions had no results outside the limit.", "Dissolution (15 min) under intermediate conditions had results outside the limit.")
        edit_text(html, ">0.122</span>% area.", ">0.122</span>% dissolved.")
        edit_docx(docx, "<w:t>In illustrative demonstration data, Dissolution (15 min) under accelerated conditions had no results outside the limit.</w:t>", "<w:t></w:t>")
        edit_text(html, "In illustrative demonstration data, Assay under intermediate conditions ranged", "Assay under intermediate conditions ranged")
        write_answers(kit, [
            [1, "html", "", "proposed shelf life", "36 months", "48 months", "number"],
            [2, "docx", "", "Assay long-term range", "100.00% label claim", "101.00% label claim", "number"],
            [3, "csv", l36, "Assay 25C/60%RH month 36", "99.28", "89.28", "number"],
            [4, "csv", l12, "Assay 25C/60%RH month 12", "99.76", "99.70", "number"],
            [5, "csv", l5, "expiry_period_proposed", "36", "48", "number"],
            [6, "html", "", "Dissolution long-term claim sentence", "had no results outside the limit", "had results outside the limit", "claim"],
            [7, "docx", "", "Dissolution intermediate claim sentence", "had no results outside the limit", "had results outside the limit", "claim"],
            [8, "html", "", "Degradation product long-term", "0.122% area", "0.122% dissolved", "unit"],
            [9, "docx", "", "Dissolution accelerated claim sentence", "had no results outside the limit", "", "deleted"],
            [10, "html", "", "Assay intermediate sentence", "In illustrative demonstration data,", "", "label"],
        ])
        matched = K.score(kit)
        got = {int(r["n"]): (r["result"], r["by"]) for r in matched["results"]}
        for n, (want, by) in self.EXPECTED.items():
            self.assertEqual(got[n][0], want, f"change {n}: {got[n]}")
            if by:
                self.assertIn(by, got[n][1], f"change {n}: {got[n]}")
        self.assertEqual(sum(1 for r in matched["results"] if r["result"] == "MISSED"), 0)
        self.assertEqual([r["n"] for r in matched["results"] if r["result"] != "CAUGHT"], ["4"])
        self.assertTrue(list(kit.glob("score_*.json")))

    def test_label_removed_in_the_csv_is_caught_by_the_data_rules(self):
        kit = self.fresh_kit("c2")
        data = kit / "for_classmate" / "finerenone_stability.csv"
        line = csv_line_of(data, "25C/60%RH,9,Assay")
        edit_csv_line(data, line, "DEMO: redacted", "redacted")
        write_answers(kit, [[1, "csv", line, "Assay month 9 source", "DEMO: redacted (b)(4) in ChemR p.7", "redacted (b)(4) in ChemR p.7", "label"]])
        m = K.score(kit)
        self.assertEqual((m["results"][0]["result"], m["results"][0]["by"]), ("CAUGHT", ["csv_rules"]))

    def test_a_public_number_flagged_as_demo_is_caught(self):
        kit = self.fresh_kit("c3")
        data = kit / "for_classmate" / "finerenone_stability.csv"
        line = csv_line_of(data, "20-25C CRT,36,expiry_period_proposed")
        edit_csv_line(data, line, "FDA ChemR 215341 p.3", "DEMO: redacted (b)(4) in ChemR p.3")
        write_answers(kit, [[1, "csv", line, "expiry_period_proposed source", "FDA ChemR 215341 p.3", "DEMO: redacted (b)(4) in ChemR p.3", "label"]])
        self.assertEqual(K.score(kit)["results"][0]["result"], "CAUGHT")


if __name__ == "__main__":
    unittest.main()
