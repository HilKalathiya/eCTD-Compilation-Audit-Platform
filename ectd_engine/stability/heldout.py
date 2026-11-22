"""Makes the T-065 held-out stability data (20 made-up condition x attribute groups, 8 with results outside the limit) from a written rule.

THE RULE (seed 65, so the same file every time; every value is made-up and labelled DEMO):
1. Five NEW conditions x four NEW attributes = 20 groups. None of these names appears in the tuning data (data/stability).
   Conditions (with their time points in months): Refrigerated 5C [0,3,6,9,12]; Intermediate 30C/65%RH [0,1,2,3,6];
   Stress 50C/ambient RH [0,1,2,3]; Humid 25C/75%RH [0,3,6,9,12,18]; Cyclic -10C to 40C [0,1,2,3,4,5,6].
   Attributes (limit, decimals): Water content (NMT 3.0, 1); Hardness (NLT 80, 0); Related substance B (NMT 0.30, 2);
   Content uniformity (90.0-110.0, 1).
2. 8 of the 20 groups (picked by the seeded generator) get 1 to 3 results outside the limit; the other 12 have none.
   Outside values sit clearly beyond the limit; inside values sit clearly within it.
3. No name is a substring of another name, and no name holds '. ' (the checks split sentences on a full stop and a space).
4. Every demo row has the source 'DEMO: synthetic held-out set T-065'. The 6 public rows are copied unchanged from the real CSV
   (the writer needs them to build its facts); the run drops the public task, so exactly 20 tasks are written.
Values are made from whole steps and turned into text with Decimal (ROUND_HALF_UP); no float is used.

    python -m ectd_engine.stability.heldout --out evidence/T-065/heldout.csv
"""
import argparse
import csv
import random
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from ectd_engine.stability import facts as F

SEED = 65
SOURCE = "DEMO: synthetic held-out set T-065"
CONDITIONS = [
    ("Refrigerated 5C", [0, 3, 6, 9, 12]),
    ("Intermediate 30C/65%RH", [0, 1, 2, 3, 6]),
    ("Stress 50C/ambient RH", [0, 1, 2, 3]),
    ("Humid 25C/75%RH", [0, 3, 6, 9, 12, 18]),
    ("Cyclic -10C to 40C", [0, 1, 2, 3, 4, 5, 6]),
]
# attribute: (limit text, decimals, unit, range of steps that sit inside the limit, ranges of steps that sit outside it); a step is 10^-decimals
ATTRIBUTES = {
    "Water content": ("NMT 3.0", 1, "%", (6, 27), [(32, 45)]),
    "Hardness": ("NLT 80", 0, "N", (82, 100), [(60, 78)]),
    "Related substance B": ("NMT 0.30", 2, "%", (5, 27), [(32, 45)]),
    "Content uniformity": ("90.0-110.0", 1, "%", (920, 1080), [(850, 890), (1110, 1150)]),
}
N_GROUPS, N_OUTSIDE_GROUPS = 20, 8


def _text(steps, decimals):
    """Whole steps -> value text with the right decimals (Decimal, no float)."""
    return str((Decimal(steps) / (Decimal(10) ** decimals)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def generate(seed=SEED, public_rows=None):
    """The held-out rows: 6 public rows (copied) + the made-up demo rows. Each row is a dict with the CSV columns."""
    rng = random.Random(seed)
    groups = [(c, m, a) for c, m in CONDITIONS for a in ATTRIBUTES]
    outside_groups = set(rng.sample(range(len(groups)), N_OUTSIDE_GROUPS))
    rows = []
    if public_rows is None:
        public_rows = [r for r in F.load_rows() if F.source_kind(r["source"]) == "public"]
    for r in public_rows:
        rows.append({k: r[k] for k in F.COLUMNS})
    for gi, (cond, months, attr) in enumerate(groups):
        limit, dec, unit, inside, outs = ATTRIBUTES[attr]
        bad_at = set(rng.sample(range(len(months)), rng.randint(1, min(3, len(months))))) if gi in outside_groups else set()
        for i, month in enumerate(months):
            if i in bad_at:
                lo, hi = rng.choice(outs)
            else:
                lo, hi = inside
            rows.append({"condition": cond, "month": str(month), "attribute": attr, "value": _text(rng.randint(lo, hi), dec),
                         "unit": unit, "limit": limit, "source": SOURCE})
    return rows


def rule_check(rows):
    """Problems with a held-out row list against the written rule (empty list = the data obeys the rule)."""
    problems = []
    demo = [r for r in rows if r["source"] == SOURCE]
    keys = {(r["condition"], r["attribute"]) for r in demo}
    if len(keys) != N_GROUPS:
        problems.append("expected %d groups, found %d" % (N_GROUPS, len(keys)))
    for r in rows:
        if F.source_kind(r["source"]) is None and r["source"] != SOURCE:
            problems.append("row with an unknown source: " + r["source"])
    out_groups = 0
    for key in sorted(keys):
        grp = [r for r in demo if (r["condition"], r["attribute"]) == key]
        if any(F.is_outside(Decimal(r["value"]), F.parse_limit(r["limit"])) for r in grp):
            out_groups += 1
    if out_groups != N_OUTSIDE_GROUPS:
        problems.append("expected %d groups with results outside the limit, found %d" % (N_OUTSIDE_GROUPS, out_groups))
    names = sorted({r["condition"] for r in demo} | {r["attribute"] for r in demo})
    for a in names:
        if ". " in a:
            problems.append("name holds a full stop and a space: " + a)
        for b in names:
            if a != b and a in b:
                problems.append("name %r is inside name %r" % (a, b))
    tuning = {(r["condition"], r["attribute"]) for r in F.load_rows() if F.source_kind(r["source"]) == "demo"}
    if keys & tuning:
        problems.append("a group also exists in the tuning data")
    return problems


def write_csv(path, rows):
    """Write the rows with the CSV columns (utf-8)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=F.COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    rows = generate(args.seed)
    bad = rule_check(rows)
    if bad:
        print("The data breaks its own rule: " + "; ".join(bad))
        return 1
    write_csv(args.out, rows)
    print("%d rows written to %s (20 demo groups, 8 with results outside the limit)" % (len(rows), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
