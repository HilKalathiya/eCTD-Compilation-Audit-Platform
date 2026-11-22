"""Makes the T-067 held-out stability data (25 made-up condition x attribute groups, 10 with results outside the limit) from a written rule.

THE RULE (seed 67, so the same file every time; every value is made-up and labelled DEMO):
1. Five conditions x five attributes = 25 groups. None of these names appears in the tuning data or in the T-065 held-out data.
   Conditions (time points in months): Frozen -20C [0,3,6,12]; Warm 35C/60%RH [0,1,3,6]; Cool 15C [0,3,6,9]; Tropical 30C/80%RH [0,3,6,9,12];
   Hot 45C/75%RH [0,1,2,3].
   Attributes (limit, decimals): Total impurities (NMT 1.0, 1); Loss on drying (NMT 2.0, 1); Disintegration time (NMT 15, 0);
   Friability (NMT 1.0, 1); Residual solvents (NMT 500, 0).
2. 10 of the 25 groups (picked by the seeded generator) get 1 to 3 results outside the limit; the other 15 have none.
3. No name is a substring of another name (new or old), and no name holds '. '.
4. Every demo row has the source 'DEMO: synthetic held-out set T-067'. The 6 public rows are copied unchanged from the real CSV.
Values are made from whole steps and turned into text with Decimal (ROUND_HALF_UP); no float is used.

    python -m ectd_engine.stability.heldout67 --out evidence/T-067/heldout.csv
"""
import argparse
import random
import sys
from decimal import Decimal

from ectd_engine.stability import facts as F, heldout as H

SEED = 67
SOURCE = "DEMO: synthetic held-out set T-067"
CONDITIONS = [
    ("Frozen -20C", [0, 3, 6, 12]),
    ("Warm 35C/60%RH", [0, 1, 3, 6]),
    ("Cool 15C", [0, 3, 6, 9]),
    ("Tropical 30C/80%RH", [0, 3, 6, 9, 12]),
    ("Hot 45C/75%RH", [0, 1, 2, 3]),
]
# attribute: (limit text, decimals, unit, steps inside the limit, ranges of steps outside it); a step is 10^-decimals
ATTRIBUTES = {
    "Total impurities": ("NMT 1.0", 1, "%", (2, 8), [(12, 20)]),
    "Loss on drying": ("NMT 2.0", 1, "%", (5, 16), [(24, 35)]),
    "Disintegration time": ("NMT 15", 0, "min", (4, 12), [(18, 26)]),
    "Friability": ("NMT 1.0", 1, "%", (1, 8), [(12, 20)]),
    "Residual solvents": ("NMT 500", 0, "ppm", (50, 420), [(560, 720)]),
}
N_GROUPS, N_OUTSIDE_GROUPS = 25, 10


def generate(seed=SEED, public_rows=None):
    """The held-out rows: 6 public rows (copied) + the made-up demo rows."""
    rng = random.Random(seed)
    groups = [(c, m, a) for c, m in CONDITIONS for a in ATTRIBUTES]
    outside_groups = set(rng.sample(range(len(groups)), N_OUTSIDE_GROUPS))
    if public_rows is None:
        public_rows = [r for r in F.load_rows() if F.source_kind(r["source"]) == "public"]
    rows = [{k: r[k] for k in F.COLUMNS} for r in public_rows]
    for gi, (cond, months, attr) in enumerate(groups):
        limit, dec, unit, inside, outs = ATTRIBUTES[attr]
        bad_at = set(rng.sample(range(len(months)), rng.randint(1, min(3, len(months))))) if gi in outside_groups else set()
        for i, month in enumerate(months):
            lo, hi = rng.choice(outs) if i in bad_at else inside
            rows.append({"condition": cond, "month": str(month), "attribute": attr, "value": H._text(rng.randint(lo, hi), dec),
                         "unit": unit, "limit": limit, "source": SOURCE})
    return rows


def rule_check(rows):
    """Problems with a row list against the written rule (empty list = the data obeys the rule)."""
    problems = []
    demo = [r for r in rows if r["source"] == SOURCE]
    keys = {(r["condition"], r["attribute"]) for r in demo}
    if len(keys) != N_GROUPS:
        problems.append("expected %d groups, found %d" % (N_GROUPS, len(keys)))
    for r in rows:
        if F.source_kind(r["source"]) is None and r["source"] != SOURCE:
            problems.append("row with an unknown source: " + r["source"])
    out_groups = sum(1 for key in keys if any(
        F.is_outside(Decimal(r["value"]), F.parse_limit(r["limit"])) for r in demo if (r["condition"], r["attribute"]) == key))
    if out_groups != N_OUTSIDE_GROUPS:
        problems.append("expected %d groups with results outside the limit, found %d" % (N_OUTSIDE_GROUPS, out_groups))
    new = {r["condition"] for r in demo} | {r["attribute"] for r in demo}
    old = {c for c, _ in H.CONDITIONS} | set(H.ATTRIBUTES)
    tuning = {r["condition"] for r in F.load_rows()} | {r["attribute"] for r in F.load_rows()}
    if new & (old | tuning):
        problems.append("names used before: " + ", ".join(sorted(new & (old | tuning))))
    for a in sorted(new):
        if ". " in a:
            problems.append("name holds a full stop and a space: " + a)
        for b in sorted(new | old | tuning):
            if a != b and (a in b or b in a):
                problems.append("name %r is inside name %r (or the other way round)" % (a, b))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    rows = generate()
    bad = rule_check(rows)
    if bad:
        print("The data breaks its own rule: " + "; ".join(bad))
        return 1
    H.write_csv(args.out, rows)
    print("%d rows written to %s (%d demo groups, %d with results outside the limit)" % (len(rows), args.out, N_GROUPS, N_OUTSIDE_GROUPS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
