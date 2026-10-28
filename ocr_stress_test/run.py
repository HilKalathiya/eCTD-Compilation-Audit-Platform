import difflib, json, random, re, sys, time
from multiprocessing import Pool

import numpy as np
import pandas as pd

import sim

# Value columns printed on the certificate, taken from the Lek/Sandoz Laboratory.csv
COLS = [
    {"key": "dissolution_av", "header": ["Dissolution", "mean (%)"], "width": 330},
    {"key": "dissolution_min", "header": ["Dissolution", "min (%)"], "width": 330},
    {"key": "impurity_o", "header": ["Impurity O", "(%)"], "width": 330},
    {"key": "impurity_l", "header": ["Impurity L", "(%)"], "width": 330},
    {"key": "impurities_total", "header": ["Total", "impurities (%)"], "width": 330},
    {"key": "resodual_solvent", "header": ["Residual", "solvent"], "width": 330},
]
N_ROWS = 10


DECIMALS = {"dissolution_av": 1, "dissolution_min": 0, "impurity_o": 2, "impurity_l": 2,
            "impurities_total": 2, "resodual_solvent": 2}


def load(path, decimals):
    df = pd.read_csv(path, sep=";")
    keep = ["batch"] + [c["key"] for c in COLS]
    df = df[[k for k in keep if k in df.columns]].dropna()
    df = df.drop_duplicates("batch")
    rows = []
    for _, r in df.iterrows():
        printed = [f"{float(r[c['key']]):.{decimals[c['key']]}f}" for c in COLS]
        rows.append((f"B{int(r['batch']):04d}", printed))
    return rows


def rules_for(all_rows, decimals):
    """Plausible ranges from the whole real dataset, widened by 25% of the span."""
    rng = {}
    for i, c in enumerate(COLS):
        vals = np.array([float(r[1][i]) for r in all_rows])
        lo, hi = vals.min(), vals.max()
        span = hi - lo if hi > lo else max(hi, 1e-6)
        rng[c["key"]] = (max(0.0, lo - 0.25 * span), hi + 0.25 * span)
    return {"decimals": decimals, "range": rng}


def cell_ok(key, text, rules):
    v = sim.canon(text)
    if v is None:
        return False
    if v[2] != rules["decimals"][key]:
        return False
    lo, hi = rules["range"][key]
    return lo <= float(v[1]) <= hi


def row_ok(vals):
    """Cross-cell rules inside one batch row (values as floats keyed by column)."""
    if {"dissolution_min", "dissolution_av"} <= vals.keys():
        if vals["dissolution_min"] > vals["dissolution_av"]:
            return False
    # NOTE: "each impurity <= total" looks obvious but fails on 20 of 1,005 real
    # Lek batches, so it is NOT used; rules must be checked against real data first.
    return True


def process(job):
    t_idx, level, params, batch_ids, rows, rules, seed, do_same_engine = job
    rng = np.random.default_rng(seed)
    im, gt, _ = sim.render_table(batch_ids, COLS, rows,
                                 ["CERTIFICATE OF ANALYSIS", "Film-coated tablets - release results (real batch values: Lek/Sandoz, Scientific Data 2022)"])
    a, M, ang = sim.degrade(im, params, rng)
    k = params["dpi"] / 300.0
    pad = max(2, int(5 * k))

    # ---------------- naive: page OCR words + independent cell read (VLM stand-in)
    words = sim.tess_words(a)
    recs = []
    for g in gt:
        poly = sim.poly_of(g["box"], M)
        ws = sim.words_in_poly(words, poly)
        crop = sim.crop_poly(a, poly, pad)
        rec = {"table": t_idx, "level": level, "r": g["r"], "c": g["c"], "key": g["key"], "gt": g["text"],
               "ocr": " ".join(w["text"] for w in ws), "n_words": len(ws), "own": sim.rapid_read(crop)}
        if do_same_engine:
            rec["tess_cell"] = sim.tess_cell(crop)
        recs.append(rec)

    # ---------------- fixed: deskew, grid, two independent reads, rules, zoom, human
    ad, ang2 = sim.deskew(a)
    xs, ys = sim.detect_grid(ad)
    adc = sim.remove_lines(ad)
    ncols, nrows = len(COLS) + 1, len(rows)
    grid_ok = len(xs) == ncols + 1 and len(ys) == nrows + 2
    table_info = {"table": t_idx, "level": level, "angle": ang, "deskew": ang2, "grid_ok": grid_ok,
                  "nx": len(xs), "ny": len(ys)}
    fixed = {}
    if grid_ok:
        # header binding: each column's header must read as the expected name
        hdr_ok = True
        for ci, c in enumerate(COLS):
            hx0, hx1, hy0, hy1 = xs[ci + 1], xs[ci + 2], ys[0], ys[1]
            hcrop = adc[hy0 + pad:hy1 - pad, hx0 + pad:hx1 - pad]
            want = re.sub(r"[^a-z]", "", c["header"][0].lower())
            reads = [sim.rapid_read(hcrop[: hcrop.shape[0] // 2 + pad]), sim.tess_cell(hcrop[: hcrop.shape[0] // 2 + pad])]
            names = {re.sub(r"[^a-z]", "", cc["header"][0].lower()) for cc in COLS}
            def score(nm):
                return max(difflib.SequenceMatcher(None, re.sub(r"[^a-z]", "", t.lower()), nm).ratio() for t in reads)
            mine = score(want)
            others = max([score(nm) for nm in names if nm != want] or [0])
            table_info.setdefault("hdr_reads", []).append(reads)
            # the header must look most like ITS expected name (not like another column's)
            if mine < 0.5 or mine < others - 0.02:
                hdr_ok = False
        table_info["header_ok"] = hdr_ok
        words2 = sim.tess_words(ad)
        for r in range(nrows):
            for ci, c in enumerate(COLS):
                x0, x1, y0, y1 = xs[ci + 1], xs[ci + 2], ys[r + 1], ys[r + 2]
                ws = [w for w in words2 if x0 <= w["cx"] <= x1 and y0 <= w["cy"] <= y1]
                ws.sort(key=lambda w: w["cx"])
                A = " ".join(w["text"] for w in ws)
                crop = adc[y0 + pad:y1 - pad, x0 + pad:x1 - pad]
                B = sim.rapid_read(crop)
                dec = rules["decimals"][c["key"]]
                pa, pb = sim.parse_col(A, dec), sim.parse_col(B, dec)
                stage, val, extra = "human", None, {}
                if hdr_ok and pa and pa == pb and cell_ok(c["key"], pa, rules):
                    stage, val = "agree", pa
                elif hdr_ok:
                    # second chance, only on disagreement: more reads from BOTH engine families
                    z = sim.zoom(crop)
                    C, Az, Bz = sim.tess_cell(crop, numeric=True), sim.tess_cell(z, numeric=True), sim.rapid_read(z)
                    extra = {"C": C, "Az": Az, "Bz": Bz}
                    tess_vals = {v for v in (pa, sim.parse_col(C, dec), sim.parse_col(Az, dec)) if v}
                    pp_vals = {v for v in (pb, sim.parse_col(Bz, dec)) if v}
                    both = {v for v in tess_vals & pp_vals if cell_ok(c["key"], v, rules)}
                    if len(both) == 1:
                        stage, val = "zoom", both.pop()
                fixed[(r, ci)] = {"A": A, "B": B, "stage": stage, "val": val, **extra}
        # row rules: a violated row sends its accepted cells to a person
        for r in range(nrows):
            vals = {COLS[ci]["key"]: float(sim.canon(fixed[(r, ci)]["val"])[1])
                    for ci in range(len(COLS)) if fixed[(r, ci)]["val"] is not None}
            if not row_ok(vals):
                for ci in range(len(COLS)):
                    if fixed[(r, ci)]["stage"] != "human":
                        fixed[(r, ci)]["stage"] = "human_rule"
                        fixed[(r, ci)]["val"] = None
    for rec in recs:
        f = fixed.get((rec["r"], rec["c"]))
        rec["fx_stage"] = f["stage"] if f else "human_grid"
        rec["fx_val"] = f["val"] if f else None
        rec["fx_A"] = f["A"] if f else None
        rec["fx_B"] = f["B"] if f else None
        for k2 in ("C", "Az", "Bz"):
            rec["fx_" + k2] = f.get(k2) if f else None
    return recs, table_info


def main(csv_path, n_tables, out):
    decimals = DECIMALS
    rows_all = load(csv_path, decimals)
    rules = rules_for(rows_all, decimals)
    random.seed(7)
    sample = random.sample(rows_all, n_tables * N_ROWS)
    tables = [sample[i * N_ROWS:(i + 1) * N_ROWS] for i in range(n_tables)]
    jobs = []
    for li, (lname, params) in enumerate(sim.LEVELS.items()):
        for ti, t in enumerate(tables):
            same = (li >= 2 and ti < 10)
            jobs.append((ti, lname, params, [b for b, _ in t], [v for _, v in t], rules, 1000 * li + ti, same))
    t0 = time.time()
    with Pool(2) as p:
        res = p.map(process, jobs, chunksize=1)
    recs = [r for rr, _ in res for r in rr]
    infos = [i for _, i in res]
    json.dump({"decimals": decimals, "rules": {k: list(v) for k, v in rules["range"].items()},
               "recs": recs, "tables": infos, "seconds": time.time() - t0}, open(out, "w"))
    print("done", len(recs), "cells", round(time.time() - t0), "s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
