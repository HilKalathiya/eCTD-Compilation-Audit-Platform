"""Tests for blind.py --model-run (a sheet of model-written paragraphs only) and the wrong_min plant; planted facts only reach blind_key.csv."""
import contextlib
import csv
import io
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.stability import blind, heldout, heldout67, loop, reread
from ectd_engine.stability.runner import run_p83

QUIET = lambda *_: None  # noqa: E731
COLUMNS = ["row_id", "hil_verdict", "paragraph", "csv_data", "hil_note"]


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_old(folder, paragraphs=()):
    """A stand-in for an earlier sheet folder (its texts must not be reused)."""
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "blind.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_id", "paragraph"])
        w.writeheader()
        w.writerows({"row_id": "R%02d" % i, "paragraph": p} for i, p in enumerate(paragraphs, 1))
    with open(folder / "blind_key.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_id", "original_paragraph"])
        w.writeheader()


def number_tokens(text):
    return re.findall(r"\d+(?:\.\d+)?", text)


class WrongMin(unittest.TestCase):
    def test_the_planted_lowest_value_is_really_lower_and_only_it_changes(self):
        text = "In illustrative demonstration data, Hardness at Cool 15C ranged from 87 to 99 over 5 time points."
        new, change = blind.wrong_min(text)
        old_n, new_n = number_tokens(text), number_tokens(new)
        self.assertEqual([i for i, (a, b) in enumerate(zip(old_n, new_n)) if a != b], [old_n.index("87")])
        self.assertEqual(len(old_n), len(new_n))
        self.assertLess(Decimal(new_n[old_n.index("87")]), Decimal("87"))
        self.assertIn("lowest", change)
        self.assertEqual(new.replace("84", "87"), text)

    def test_decimals_keep_their_places(self):
        new, _ = blind.wrong_min("x ranged from 1.9 to 3.2 over 4 time points.")
        self.assertIn("ranged from 1.6 to 3.2", new)

    def test_a_negative_result_is_never_made(self):
        self.assertIsNone(blind.wrong_min("x ranged from 0.2 to 0.8 over 4 time points."))
        self.assertIsNone(blind.wrong_min("x ranged from 2 to 9 over 4 time points."))

    def test_text_without_a_range_is_left_alone(self):
        self.assertIsNone(blind.wrong_min("Nothing to change here."))


class ModelRunSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        d = Path(cls.tmp)
        cls.csv = d / "held.csv"
        heldout.write_csv(cls.csv, heldout67.generate())
        run_p83(loop.StabilityMockClient(), d / "run", csv_path=cls.csv, heldout=True, log=QUIET)
        cls.run_dir = d / "run"
        write_old(d / "old")

    def build(self, out_name, old=("old",)):
        out = Path(self.tmp) / out_name
        buf = io.StringIO()
        argv = ["--fresh-csv", str(self.csv), "--model-run", str(self.run_dir), "--out-dir", str(out),
                "--heldout-run", "x", "--heldout-data", "x"]
        for o in old:
            argv += ["--old-dir", str(Path(self.tmp) / o)]
        with contextlib.redirect_stdout(buf):
            code = blind.main(argv)
        return code, out, buf.getvalue()

    def test_25_rows_all_model_written_3_planted_verdict_is_column_2(self):
        code, out, printed = self.build("a")
        self.assertEqual(code, 0)
        sheet, key = read(out / "blind.csv"), read(out / "blind_key.csv")
        self.assertEqual((len(sheet), len(key)), (25, 25))
        self.assertEqual(list(sheet[0]), COLUMNS)
        self.assertTrue(all(k["set"].startswith("model") for k in key))
        self.assertEqual(sorted(k["planted_change"].split(" ")[0] for k in key if k["truth"] == "wrong"), ["highest", "lowest", "outside"])
        self.assertTrue(all(s["hil_verdict"] == "" and s["hil_note"] == "" for s in sheet))

    def test_every_planted_row_is_caught_by_the_recount_and_changes_one_number(self):
        _, out, _ = self.build("b")
        sheet, key = read(out / "blind.csv"), {k["row_id"]: k for k in read(out / "blind_key.csv")}
        pool = {p["task_id"]: p for p in blind.load_pool(self.run_dir, self.csv, "model, T-067", True)}
        for s in sheet:
            k = key[s["row_id"]]
            if k["truth"] != "wrong":
                continue
            task = pool[k["task_id"]]
            self.assertTrue(reread.reread(s["paragraph"], task["task"], task["rows"]))
            old_n, new_n = number_tokens(k["original_paragraph"]), number_tokens(s["paragraph"])
            self.assertEqual(len(old_n), len(new_n))
            self.assertEqual(sum(a != b for a, b in zip(old_n, new_n)), 1)
            self.assertEqual(reread.reread(k["original_paragraph"], task["task"], task["rows"]), [])

    def test_planted_ids_and_changes_are_written_only_to_blind_key_csv(self):
        _, out, printed = self.build("c")
        key = read(out / "blind_key.csv")
        planted = [k for k in key if k["truth"] == "wrong"]
        self.assertEqual(len(planted), 3)
        for name in ("blind.csv",):
            text = (out / name).read_text(encoding="utf-8-sig")
            for k in planted:
                self.assertNotIn(k["planted_change"], text)
                self.assertNotIn(k["original_paragraph"], text)
            self.assertNotIn("planted", text.lower())
            self.assertNotIn("truth", text.lower())
        for k in planted:
            self.assertNotIn(k["row_id"], printed)          # the build prints counts only, never row ids
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["blind.csv", "blind_key.csv"])

    def test_a_paragraph_from_an_earlier_sheet_is_not_reused(self):
        _, out, _ = self.build("d")
        first = read(out / "blind.csv")[0]["paragraph"]
        # an earlier sheet that already showed this exact text: the pool shrinks below 25, so the build must refuse (nothing is padded)
        write_old(Path(self.tmp) / "old2", [first])
        with self.assertRaises(ValueError):
            self.build("e", old=("old2",))

    def test_a_small_pool_is_reported_not_padded(self):
        pool = blind.load_pool(self.run_dir, self.csv, "model, T-067", True)
        with self.assertRaises(ValueError):
            blind.build_fresh(pool[:10], set())

    def test_the_pool_is_model_written_only(self):
        pool = blind.load_pool(self.run_dir, self.csv, "model, T-067", True)
        self.assertEqual(len(pool), 25)
        self.assertTrue(all(p["set"] == "model, T-067" for p in pool))


if __name__ == "__main__":
    unittest.main()
