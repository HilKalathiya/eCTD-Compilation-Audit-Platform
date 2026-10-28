import json, random, sys
from collections import defaultdict

import sim

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "results.json"))
recs = d["recs"]
levels = list(sim.LEVELS.keys())
by_level = defaultdict(list)
for r in recs:
    by_level[r["level"]].append(r)
# index for neighbour lookup (binding errors)
idx = {(r["level"], r["table"], r["r"], r["c"]): r for r in recs}


def ok(text, gt):
    return sim.same_value(text, gt)


def naive(level, copy_rate, bind_rate, seed=11):
    rng = random.Random(seed)
    rs = by_level[level]
    out = dict(n=0, human=0, undetected=0, false_alarm=0, accepted=0, undetected_bind=0)
    for r in rs:
        out["n"] += 1
        claimed = r
        src = r
        bind_err = rng.random() < bind_rate
        if bind_err:
            nb = idx.get((r["level"], r["table"], r["r"] + 1, r["c"])) or idx.get((r["level"], r["table"], r["r"] - 1, r["c"]))
            if nb:
                src = nb
        ocr = src["ocr"]
        if src["n_words"] == 0:
            out["human"] += 1
            continue
        vlm = ocr if rng.random() < copy_rate else src["own"]
        if vlm.strip() == ocr.strip():
            if sim.canon(ocr) is None:
                # e.g. "0:05": not a number, so even a naive system's parser would stop it
                out["human"] += 1
                out["caught_by_parser"] = out.get("caught_by_parser", 0) + 1
                continue
            out["accepted"] += 1
            if not ok(ocr, claimed["gt"]):
                out["undetected"] += 1
                if bind_err and src is not claimed:
                    out["undetected_bind"] += 1
        else:
            out["human"] += 1
            if ok(ocr, claimed["gt"]) and ok(vlm, claimed["gt"]):
                out["false_alarm"] += 1
    return out


def fixed(level):
    rs = by_level[level]
    out = dict(n=0, agree=0, zoom=0, human=0, undetected=0, human_grid=0, human_rule=0)
    for r in rs:
        out["n"] += 1
        st = r["fx_stage"]
        if st in ("agree", "zoom"):
            out[st] += 1
            if not ok(r["fx_val"], r["gt"]):
                out["undetected"] += 1
        else:
            out["human"] += 1
            if st == "human_grid":
                out["human_grid"] += 1
            if st == "human_rule":
                out["human_rule"] += 1
    return out


def readers(level):
    rs = by_level[level]
    n = len(rs)
    a_wrong = sum(not ok(r["ocr"], r["gt"]) for r in rs)
    b_wrong = sum(not ok(r["own"], r["gt"]) for r in rs)
    both_same = sum((not ok(r["ocr"], r["gt"])) and (not ok(r["own"], r["gt"])) and sim.same_value(r["ocr"], r["own"]) for r in rs)
    both_same_text = sum((not ok(r["ocr"], r["gt"])) and r["ocr"].strip() == r["own"].strip() and r["ocr"].strip() != "" for r in rs)
    exact_disagree_both_right = sum(ok(r["ocr"], r["gt"]) and ok(r["own"], r["gt"]) and r["ocr"].strip() != r["own"].strip() for r in rs)
    return dict(n=n, tess_wrong=a_wrong, pp_wrong=b_wrong, both_wrong_same=both_same, both_same_text=both_same_text,
                format_only_disagree=exact_disagree_both_right)


def same_engine(level):
    rs = [r for r in by_level[level] if "tess_cell" in r]
    if not rs:
        return None
    n = len(rs)
    tp_w = [not ok(r["ocr"], r["gt"]) for r in rs]
    tc_w = [not ok(r["tess_cell"], r["gt"]) for r in rs]
    pp_w = [not ok(r["own"], r["gt"]) for r in rs]
    same_eng = sum(a and b and sim.same_value(r["ocr"], r["tess_cell"]) for a, b, r in zip(tp_w, tc_w, rs))
    cross = sum(a and b and sim.same_value(r["ocr"], r["own"]) for a, b, r in zip(tp_w, pp_w, rs))
    return dict(n=n, tess_page_wrong=sum(tp_w), tess_cell_wrong=sum(tc_w), pp_wrong=sum(pp_w),
                same_engine_common=same_eng, cross_engine_common=cross)


summary = {}
for lv in levels:
    s = {"readers": readers(lv), "fixed": fixed(lv), "same_engine": same_engine(lv)}
    for c in (0.0, 0.5, 0.9, 1.0):
        s[f"naive_c{c}"] = naive(lv, c, 0.02)
    summary[lv] = s
tables = d["tables"]
grid = defaultdict(lambda: [0, 0, 0])
for t in tables:
    g = grid[t["level"]]
    g[0] += 1
    g[1] += t["grid_ok"]
    g[2] += t.get("header_ok", False)
summary["_grid"] = {k: {"tables": v[0], "grid_ok": v[1], "header_ok": v[2]} for k, v in grid.items()}
summary["_seconds"] = d["seconds"]
json.dump(summary, open("summary.json", "w"), indent=1)
for lv in levels:
    s = summary[lv]
    print("==", lv, s["readers"])
    print("   fixed", s["fixed"])
    print("   same-engine", s["same_engine"])
    for c in (0.0, 0.5, 0.9, 1.0):
        print(f"   naive c={c}", s[f"naive_c{c}"])
print(summary["_grid"])
