"""Scores a filled-in blind sheet against its key: how many planted wrong paragraphs were caught, how many right ones were agreed with.

    python tools/score_blind.py --sheet evidence/T-065/blind.csv --key evidence/T-065/blind_key.csv --verdict-col hil_note --out evidence/T-065/score.md

It reads the verdict column (default hil_verdict). If that column is empty it refuses, unless --verdict-col names the column to use.
"""
import argparse
import csv
import sys
from pathlib import Path

DEFAULT_COL = "hil_verdict"
VALID = ("right", "wrong")


class Refused(Exception):
    """The sheet cannot be scored honestly (empty or missing verdict column)."""


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def score(sheet, key, col=DEFAULT_COL, col_given=False):
    """Dict with planted caught/total, right agreed/total, and the row ids behind each number. Raises Refused if col is empty."""
    if sheet and col not in sheet[0]:
        raise Refused("the sheet has no column called %r" % col)
    verdicts = {r["row_id"]: (r[col] or "").strip().lower() for r in sheet}
    if not any(verdicts.values()):
        hint = "" if col_given else " (if the answers are in another column, pass --verdict-col <name>)"
        raise Refused("the verdict column %r is empty%s" % (col, hint))
    planted = [k for k in key if k["truth"] == "wrong"]
    rights = [k for k in key if k["truth"] == "right"]
    missed = [k for k in planted if verdicts.get(k["row_id"]) != "wrong"]
    disagreed = [k for k in rights if verdicts.get(k["row_id"]) != "right"]
    unanswered = sorted(r for r, v in verdicts.items() if v not in VALID)
    return {"col": col, "caught": len(planted) - len(missed), "planted": len(planted),
            "agree": len(rights) - len(disagreed), "rights": len(rights),
            "missed": missed, "disagreed": disagreed, "unanswered": unanswered, "verdicts": verdicts}


def report(s):
    """The score as a short markdown note."""
    lines = ["# Blind sheet score", "",
             "Verdict column read: `%s`" % s["col"], "",
             "- Planted wrong paragraphs caught: **%d/%d**" % (s["caught"], s["planted"]),
             "- Right paragraphs agreed with: **%d/%d**" % (s["agree"], s["rights"])]
    if s["unanswered"]:
        lines.append("- Rows with no usable right/wrong answer (counted as not caught / not agreed): %s" % ", ".join(s["unanswered"]))
    for k in s["missed"]:
        lines.append("- MISSED %s (%s): %s; the re-read flagged it: %s" % (k["row_id"], k["task_id"], k["planted_change"], k["reread_flags"]))
    for k in s["disagreed"]:
        lines.append("- DISAGREED %s (%s): a right paragraph was not marked right" % (k["row_id"], k["task_id"]))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--verdict-col")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        s = score(read(args.sheet), read(args.key), args.verdict_col or DEFAULT_COL, bool(args.verdict_col))
    except Refused as e:
        print("REFUSED: %s" % e)
        return 2
    text = report(s)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
