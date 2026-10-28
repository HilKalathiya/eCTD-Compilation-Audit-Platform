"""Value-only number tracing ('every digit traces to a fact') vs typed binding,
on the real Lek/Sandoz batch facts."""
import json, random, sys
import pandas as pd

COLS = {"dissolution_av": 1, "dissolution_min": 0, "impurity_o": 2, "impurity_l": 2,
        "impurities_total": 2, "resodual_solvent": 2}
CSV = sys.argv[1] if len(sys.argv) > 1 else "Laboratory.csv"   # Lek/Sandoz data (figshare, CC BY 4.0)
df = pd.read_csv(CSV, sep=";")
facts = []
for _, r in df.iterrows():
    for c, d in COLS.items():
        facts.append({"batch": int(r["batch"]), "test": c, "text": f"{float(r[c]):.{d}f}"})

def corrupt(f, kind, section, rng):
    v = f["text"]
    d = COLS[f["test"]]
    x = float(v)
    if kind == "wrong batch":          # writer binds the same test of another batch
        o = rng.choice([g for g in section if g["test"] == f["test"] and g["batch"] != f["batch"]])
        return o["text"]
    if kind == "wrong test":           # writer binds another test of the same batch
        o = rng.choice([g for g in section if g["batch"] == f["batch"] and g["test"] != f["test"]])
        return o["text"]
    if kind == "last-digit slip":      # 0.05 -> 0.06
        step = 10 ** -d
        return f"{x + rng.choice([-step, step]):.{d}f}"
    if kind == "decimal shift":        # the decimal point moves one place, digits kept: 0.14 -> 1.4 or 0.014
        return f"{x * 10:.{max(d - 1, 0)}f}" if rng.random() < 0.5 else f"{x / 10:.{d + 1}f}"
    if kind == "digit swap":           # 0.15 -> 0.51
        s = list(v)
        idx = [i for i, ch in enumerate(s) if ch.isdigit()]
        if len(idx) < 2:
            return v
        i = rng.randrange(len(idx) - 1)
        a, b = idx[i], idx[i + 1]
        s[a], s[b] = s[b], s[a]
        return "".join(s)
    raise ValueError(kind)

rng = random.Random(42)
batches = sorted({f["batch"] for f in facts})
KINDS = ["wrong batch", "wrong test", "last-digit slip", "decimal shift", "digit swap"]
res = {k: {"changed": 0, "pass_section": 0, "pass_product": 0} for k in KINDS}
num = lambda t: round(float(t), 6)          # value-only: "1.4" and "1.40" count as the same number
product_values = {num(f["text"]) for f in facts}
TRIALS = 400  # sections of 10 batches
picked = set()
for t in range(TRIALS):
    sec_batches = set(rng.sample(batches, 10))
    section = [f for f in facts if f["batch"] in sec_batches]
    sec_values = {num(f["text"]) for f in section}
    for f in rng.sample(section, 10):
        picked.add((f["batch"], f["test"]))
        for k in KINDS:
            w = corrupt(f, k, section, rng)
            if w == f["text"]:
                continue                     # harmless: same printed number
            res[k]["changed"] += 1
            res[k]["pass_section"] += num(w) in sec_values
            res[k]["pass_product"] += num(w) in product_values
out = {k: {**v, "pct_section": round(100 * v["pass_section"] / v["changed"], 1),
           "pct_product": round(100 * v["pass_product"] / v["changed"], 1)} for k, v in res.items()}
out["_picks"] = {"facts_picked": TRIALS * 10, "distinct_facts": len(picked)}
print(json.dumps(out, indent=1))
json.dump(out, open("tracing_results.json", "w"), indent=1)
