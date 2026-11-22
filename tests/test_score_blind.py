"""Tests for tools/score_blind.py: a planted miss is reported, an empty verdict column is refused, and the fresh sheet has the verdict as column 2."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import score_blind as S  # noqa: E402

KEY = [{"row_id": "R%d" % i, "task_id": "t%d" % i, "truth": "wrong" if i in (2, 4) else "right",
        "planted_change": "changed %d" % i if i in (2, 4) else "", "reread_flags": "flag" if i in (2, 4) else ""} for i in range(1, 7)]


def sheet(verdicts, col="hil_verdict"):
    return [{"row_id": "R%d" % (i + 1), col: v} for i, v in enumerate(verdicts)]


class ScoreBlindTests(unittest.TestCase):
    def test_all_caught_all_agreed(self):
        s = S.score(sheet(["right", "wrong", "right", "wrong", "right", "right"]), KEY)
        self.assertEqual((s["caught"], s["planted"], s["agree"], s["rights"]), (2, 2, 4, 4))

    def test_a_planted_miss_is_reported(self):
        s = S.score(sheet(["right", "wrong", "right", "right", "right", "right"]), KEY)
        self.assertEqual((s["caught"], s["planted"]), (1, 2))
        self.assertEqual([k["row_id"] for k in s["missed"]], ["R4"])
        self.assertIn("MISSED R4", S.report(s))

    def test_a_false_alarm_lowers_agree(self):
        s = S.score(sheet(["wrong", "wrong", "right", "wrong", "right", "right"]), KEY)
        self.assertEqual((s["agree"], s["rights"]), (3, 4))

    def test_empty_verdict_column_is_refused(self):
        with self.assertRaises(S.Refused):
            S.score(sheet([""] * 6), KEY)

    def test_empty_column_is_scored_when_the_other_column_is_named(self):
        rows = [dict(r, hil_note=v) for r, v in zip(sheet([""] * 6), ["right", "wrong", "right", "wrong", "right", "right"])]
        with self.assertRaises(S.Refused):
            S.score(rows, KEY)
        s = S.score(rows, KEY, "hil_note", True)
        self.assertEqual(s["caught"], 2)

    def test_unknown_column_is_refused(self):
        with self.assertRaises(S.Refused):
            S.score(sheet(["right"] * 6), KEY, "nope", True)

    def test_blank_rows_count_as_not_answered(self):
        s = S.score(sheet(["right", "wrong", "", "wrong", "right", "right"]), KEY)
        self.assertEqual(s["unanswered"], ["R3"])
        self.assertEqual(s["agree"], 3)


class FreshSheetTests(unittest.TestCase):
    """The T-066 sheet, if it has been built: 25 rows, verdict is column 2, none of the T-065 paragraphs reused."""

    root = Path(__file__).resolve().parent.parent / "evidence"

    def test_fresh_sheet_shape(self):
        p = self.root / "T-066" / "blind.csv"
        if not p.exists():
            self.skipTest("sheet not built yet")
        rows = S.read(p)
        self.assertEqual(len(rows), 25)
        self.assertEqual(list(rows[0]), ["row_id", "hil_verdict", "paragraph", "csv_data", "hil_note"])
        old = {r["paragraph"] for r in S.read(self.root / "T-065" / "blind.csv")}
        self.assertFalse(old & {r["paragraph"] for r in rows})
        key = S.read(self.root / "T-066" / "blind_key.csv")
        self.assertEqual(sorted(k["planted_change"].split(" ")[0] for k in key if k["truth"] == "wrong"), ["highest", "lowest", "outside"])
        with self.assertRaises(S.Refused):
            S.score(rows, key)


if __name__ == "__main__":
    unittest.main()
