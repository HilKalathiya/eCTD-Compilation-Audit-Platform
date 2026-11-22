"""Builds the blind sheet for Hil: 22 accepted P.8.3 paragraphs and 3 planted wrong ones, shuffled, plus a separate key file.

The 3 wrong ones are made by code from 3 accepted held-out paragraphs (their right version is NOT shown) and each must be flagged by the
independent re-read, or the build stops. The 22 right ones are the remaining held-out paragraphs, topped up from the T-064 tuning run
(marked "tuning" in the key) if the held-out run has fewer than 22. A pool that is too small is reported, never padded.

    python -m ectd_engine.stability.blind --heldout-run evidence/T-065/direct/run1 --heldout-data evidence/T-065/heldout.csv --out-dir evidence/T-065
"""
import argparse
import csv
import json
import random
import re
import sys
from decimal import Decimal
from pathlib import Path

from ectd_engine.stability import facts as F, loop, reread

SEED = 65
N_RIGHT, N_WRONG = 22, 3
_RANGE = re.compile(r"ranged from (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?) over ")
_OUT = re.compile(r"had (\d+) of its (\d+) results outside")
_NONE = re.compile(r"had none of its (\d+) results outside")


def load_pool(run_dir, csv_path, set_name, heldout):
    """Accepted, clean paragraphs of one run folder: a list of {task_id, set, text, task, rows}."""
    rows = reread.read_rows(csv_path)
    facts = F.p83_facts(F.load_rows(csv_path), heldout)
    tasks = {t["task_id"]: t for t in loop.make_tasks(facts)}
    pool = []
    with open(Path(run_dir) / "results.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["accepted"] and not r["reread_problems"]:
                pool.append({"task_id": r["task_id"], "set": set_name, "text": r["rendered"], "task": tasks[r["task_id"]], "rows": rows})
    return sorted(pool, key=lambda p: p["task_id"])


def _places(text):
    return len(text.split(".")[1]) if "." in text else 0


def _step(text):
    """The smallest step of a number text (1 for '85', 0.1 for '1.5')."""
    return Decimal(1).scaleb(-_places(text))


def wrong_max(text):
    """Make the highest result bigger than it is (a number that is not in the data)."""
    m = _RANGE.search(text)
    if not m:
        return None
    new = str(Decimal(m.group(2)) + _step(m.group(2)) * 3)
    return text[:m.start(2)] + new + text[m.end(2):], "highest result %s written as %s" % (m.group(2), new)


def wrong_outside(text):
    """Say one more result is outside the limit than the data shows."""
    m = _OUT.search(text)
    if not m:
        return None
    new = str(Decimal(m.group(1)) + 1)
    return text[:m.start(1)] + new + text[m.end(1):], "outside count %s written as %s" % (m.group(1), new)


def none_outside(text):
    """Say 'none' were outside when the data has some, or say 1 where there were none (whichever applies)."""
    m = _OUT.search(text)
    if m:
        return text[:m.start()] + "had none of its " + m.group(2) + " results outside" + text[m.end():], "outside count %s written as none" % m.group(1)
    m = _NONE.search(text)
    if m:
        return text[:m.start()] + "had 1 of its " + m.group(1) + " results outside" + text[m.end():], "none outside written as 1 outside"
    return None


def data_line(entry):
    """What Hil needs to judge a paragraph: the CSV values it is built from, read straight from the rows."""
    rows, task = entry["rows"], entry["task"]
    if task["kind"] == "public":
        parts = ["%s (%s) = %s" % (r["attribute"], r["condition"], r["value"]) for r in rows if F.source_kind(r["source"]) == "public"]
        return "public rows: " + "; ".join(parts)
    cond, attr = task["key"]
    got = [r for r in rows if r["condition"] == cond and r["attribute"] == attr and r["source"].startswith("DEMO")]
    return "limit %s; results (month:value): %s" % (got[0]["limit"], ", ".join("%s:%s" % (r["month"], r["value"]) for r in got))


def build(pool_heldout, pool_tuning, seed=SEED, n_right=N_RIGHT, n_wrong=N_WRONG):
    """(sheet rows, key rows). Raises ValueError if the pools are too small or a planted error is not caught (nothing is padded)."""
    ordered = list(pool_heldout) + list(pool_tuning)
    if len(ordered) < n_right + n_wrong:
        raise ValueError("pool has %d accepted paragraphs, need %d" % (len(ordered), n_right + n_wrong))
    rest_demo = [p for p in ordered if p["task"]["kind"] == "demo"]  # held-out first, so planted ones come from the held-out set
    makers = [wrong_outside, none_outside, wrong_max][:n_wrong]
    wrong, used = [], set()   # used holds id(entry): a paragraph made wrong is not also shown as right
    for fn in makers:
        for p in rest_demo:
            if id(p) in used:
                continue
            made = fn(p["text"])
            if made is None:
                continue
            text, change = made
            flags = reread.reread(text, p["task"], p["rows"])
            if not flags:
                raise ValueError("planted error in %s is not caught by the re-read: %s" % (p["task_id"], change))
            wrong.append(dict(p, text=text, truth="wrong", change=change, flags="; ".join(flags), original=p["text"]))
            used.add(id(p))
            break
        else:
            raise ValueError("no paragraph left for planted error %s" % fn.__name__)
    right = [p for p in ordered if id(p) not in used][:n_right]
    items = [dict(p, truth="right", change="", flags="", original="") for p in right] + wrong
    random.Random(seed).shuffle(items)
    sheet, key = [], []
    for i, it in enumerate(items, 1):
        rid = "R%02d" % i
        sheet.append({"row_id": rid, "paragraph": it["text"], "csv_data": data_line(it), "hil_verdict": "", "hil_note": ""})
        key.append({"row_id": rid, "task_id": it["task_id"], "set": it["set"], "truth": it["truth"], "planted_change": it["change"],
                    "reread_flags": it["flags"], "original_paragraph": it["original"]})
    return sheet, key


def write(path, rows):
    """CSV with a byte-order mark so Excel shows the degree signs."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heldout-run", required=True)
    ap.add_argument("--heldout-data", required=True)
    ap.add_argument("--tuning-run", default="evidence/T-064/direct")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    held = load_pool(args.heldout_run, args.heldout_data, "held-out", True)
    tune = load_pool(args.tuning_run, F.DEFAULT_CSV, "tuning (T-064)", False)
    sheet, key = build(held, tune)
    out = Path(args.out_dir)
    write(out / "blind.csv", sheet)
    write(out / "blind_key.csv", key)
    print("blind.csv: %d rows (%d right, %d planted wrong); held-out pool %d, tuning pool %d" % (
        len(sheet), sum(k["truth"] == "right" for k in key), sum(k["truth"] == "wrong" for k in key), len(held), len(tune)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
