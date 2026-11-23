"""T-072 task builder for the 2.3 writer: task files hold slot names and fact ids ONLY; every value comes from the graph when the document is rendered.

    python -m ectd_engine.summary.m23_tasks2 --out evidence/T-072/tasks     # real + dev + held-out task files, synthetic graph files, SHA256SUMS (new folder only)

A synthetic task has a second file, <id>.graph.json, that is its own labelled graph (namespace SYNTHETIC); the real task has none, because its
values are read from Neo4j. consistency_problems() is the rule list every task must pass; the generator refuses to emit a task that breaks one.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import plan as P

# Q1E (ICH, Step 4, 6 Feb 2003), page 8, stored chunk Q1E:p8-c2 (data/public/SOURCES.md: ich/Q1E.pdf sha256 5926a3a4...960d):
# "The proposed retest period or shelf life can be up to twice, but should not be more than 12 months beyond, the period covered by long-term data."
Q1E_FACTOR, Q1E_EXTRA_MONTHS = 2, 12
Q1E_SOURCE = "ICH Q1E page 8, chunk Q1E:p8-c2 (extrapolation with little or no change over time)"

SYNTH_TITLE = P.TITLE + " (synthetic test case)"
PUBLIC_SLOTS = ["shelf", "st_low", "st_high", "ex_low", "ex_high", "long", "accel"]
PUBLIC_LABELS = {"shelf": "proposed shelf life in months", "st_low": "lowest storage temperature", "st_high": "highest storage temperature",
                 "ex_low": "lowest permitted excursion temperature", "ex_high": "highest permitted excursion temperature",
                 "long": "months of stability demonstrated at long-term conditions",
                 "accel": "months of stability demonstrated at accelerated conditions"}
ATTR_UNIT = {"Assay": "% label claim", "Degradation product": "% area", "Dissolution (15 min)": "% dissolved"}
ATTR_LIMIT = {"Assay": "95.0-105.0", "Degradation product": "NMT 0.50", "Dissolution (15 min)": "NLT 80"}
SPEC_VALUES = {"dissolution_av": ["70", "75", "80", "85"], "impurity_o": ["0.1", "0.2", "0.3", "0.5", "0.7"],
               "impurity_l": ["0.1", "0.2", "0.3", "0.5", "0.7"], "impurities_total": ["0.5", "1.0", "1.5", "2.0"],
               "resodual_solvent": ["0.1", "0.3", "0.5"]}
STORAGE = [(15, 25), (20, 25), (15, 30), (2, 25), (5, 25), (10, 30)]          # every range holds the long-term temperature (25)
EXCURSION = [(0, 40), (5, 40), (10, 35), (2, 30), (15, 30), (0, 30)]
MONTHS = {P.LONG: [0, 3, 6, 9, 12, 18, 24, 36, 48], P.INTER: [0, 3, 6, 9, 12, 18, 24, 36, 48], P.ACCEL: [0, 1, 3, 6]}
DEV_COUNT, HELD_COUNT = 10, 20


def q1e_max_shelf(long_months):
    """The longest shelf life Q1E lets a task claim beyond its long-term data: twice the data, but not more than 12 months beyond it."""
    return min(Q1E_FACTOR * long_months, long_months + Q1E_EXTRA_MONTHS)


def attr_base(attribute):
    """The attribute as written without its time point: 'Dissolution (15 min)' -> 'Dissolution' (P.ATTR_SHOWN)."""
    return P.ATTR_SHOWN[attribute]


# ---- the rules every task must pass ------------------------------------------------------------------------------------------------------

def consistency_problems(task, rows):
    """[reason, ...] for every rule the task and its graph rows break; [] = consistent.

    R1 accelerated rows only up to the stated accelerated duration; R2 long-term and intermediate rows only up to the long-term duration;
    R3 shelf life <= long-term duration, unless the task carries an extrapolation fact, and then <= the Q1E limit; R4 the long-term test
    temperature lies inside the storage range; R5 the excursion range holds the storage range; R6 each group has >= 3 distinct stored months."""
    out = []
    try:
        val = {s: Decimal(rows[task["public"][s]["fact_id"]]["value_text"]) for s in PUBLIC_SLOTS}
    except KeyError as e:
        return [f"R0: a public fact is missing from the graph: {e}"]
    for g in task["results"]:
        grp = MG.group_rows(rows, g["condition"], g["attribute"])
        months = [int(r["month"]) for r in grp]
        limit = val["accel"] if g["condition"] == P.ACCEL else val["long"]
        rule = "R1" if g["condition"] == P.ACCEL else "R2"
        if months and max(months) > limit:
            out.append(f"{rule}: {g['condition']} | {g['attribute']} has a row at month {max(months)}, beyond its stated duration of {limit} months")
        if len(set(months)) != len(months) or len(months) < 3:
            out.append(f"R6: {g['condition']} | {g['attribute']} needs at least 3 distinct months (has {sorted(months)})")
    if val["shelf"] > val["long"]:
        ex = task.get("extrapolation")
        if not ex or ex not in rows or Decimal(rows[ex]["value_text"]) != val["shelf"]:
            out.append(f"R3: the shelf life ({val['shelf']}) is longer than the long-term duration ({val['long']}) and no extrapolation fact states it")
        elif val["shelf"] > q1e_max_shelf(val["long"]):
            out.append(f"R3: the shelf life ({val['shelf']}) is beyond the Q1E limit of {q1e_max_shelf(val['long'])} months ({Q1E_SOURCE})")
    temp = Decimal(re.match(r"(\d+)C", P.LONG).group(1))
    if not (val["st_low"] <= temp <= val["st_high"]):
        out.append(f"R4: the long-term temperature {temp} is outside the storage range {val['st_low']} to {val['st_high']}")
    if not (val["ex_low"] <= val["st_low"] and val["st_high"] <= val["ex_high"]):
        out.append(f"R5: the excursion range {val['ex_low']} to {val['ex_high']} does not hold the storage range {val['st_low']} to {val['st_high']}")
    return out


# ---- task + graph rows ---------------------------------------------------------------------------------------------------------------

def _task(task_id, which, synthetic, note, spec_attrs, refs, groups, graph_file=None, extrapolation=None):
    results = []
    for cond, attr in groups:
        results.append({"condition": cond, "attribute": attr, "cond_word": P.COND_WORD[cond], "attr_base": attr_base(attr),
                        "stat": {w: P.stat_id(cond, attr, w) for w in ("min", "max")} | ({"timepoint": P.stat_id(cond, attr, "timepoint")}
                                                                                         if re.search(r"\(\d+ min\)", attr) else {})})
    return {"version": "v2", "task_id": task_id, "set": which, "synthetic": synthetic, "note": note,
            "title": SYNTH_TITLE if synthetic else P.TITLE, "graph_file": graph_file, "extrapolation": extrapolation,
            "spec": [{"attribute": a, "slot": "spec_" + a, "fact_id": G.spec_id(a)} for a in spec_attrs],
            "public": {s: {"label": PUBLIC_LABELS[s], "fact_id": refs[s]} for s in PUBLIC_SLOTS}, "results": results}


def real_task():
    """The real Kerendia task: slot names and fact ids from the plan. No value is in it; the values are read from Neo4j when it is rendered."""
    return _task("m23b_real", "real", False, "Real Kerendia facts (public) and the demonstration specification.", P.SPEC_ATTRIBUTES, P.PUBLIC_REFS, P.STAT_GROUPS)


def _row(fact_id, family, kind, attribute, test, condition, unit, value, month="", limit_kind="", limit_text="", note=""):
    return {"attribute": attribute, "basis": "", "batch": G.PREFIX + ("SPEC" if family == "spec" else "P8"), "condition": condition,
            "definition": note, "demo_label": G.LABEL if kind == "demo" else "", "derived": "no", "doc_id": "synthetic", "doc_version": "",
            "fact_id": fact_id, "family": family, "kind": kind, "limit_kind": limit_kind, "limit_text": limit_text, "lineage": "unknown",
            "locator": "", "month": str(month), "namespace": "SYNTHETIC", "page": "", "test": test, "unit": unit, "value_text": str(value)}


def _int_text(n, places):
    s = str(n).rjust(places + 1, "0")
    return s[:-places] + "." + s[-places:]


def _value(rng, attr, bad):
    """One stored result as text. bad=True gives a result that breaks the attribute's limit."""
    if attr == "Assay":
        return _int_text(9450 if bad else rng.randint(9800, 10150), 2)
    if attr == "Degradation product":
        return _int_text(520 if bad else rng.randint(50, 250), 3)
    return _int_text(7850 if bad else rng.randint(9000, 9800), 2)


def synthetic_task(which, index):
    """(task, rows) for one synthetic task. The seed is the text 'm23b-<which>-<index>', so the result never changes."""
    rng = random.Random(f"m23b-{which}-{index}")
    rows, note = {}, "SYNTHETIC test case (invented numbers, not Kerendia)."

    def put(r):
        rows[r["fact_id"]] = r
        return r["fact_id"]
    long_ = rng.choice([12, 18, 24, 36, 48])
    ok = [m for m in (12, 18, 24, 30, 36, 48, 60) if m <= long_]
    shelf, extrap = rng.choice(ok), None
    if index % 3 == 0:                                   # some tasks extrapolate, up to the Q1E limit
        beyond = [m for m in (18, 24, 30, 36, 48, 60) if long_ < m <= q1e_max_shelf(long_)]
        if beyond:
            shelf = beyond[-1] if index % 2 else beyond[0]
    if index % 4 == 0:
        shelf = long_                                    # the same number in two places: a swap of the two would be invisible to a value check
    accel = rng.choice([3, 6])
    sl, sh = rng.choice(STORAGE)
    xl, xh = rng.choice([e for e in EXCURSION if e[0] <= sl and sh <= e[1]])
    if index % 5 == 0:
        xl = sl                                          # storage low = excursion low
    crt, exc = f"{sl}-{sh}C CRT", f"{xl}-{xh}C excursion"
    refs = {
        "shelf": put(_row(G.stab_id(crt, "expiry_period_proposed", shelf), "stability", "public", "expiry_period_proposed",
                          "expiry_period_proposed", crt, "months", shelf, shelf, note=note)),
        "st_low": put(_row(G.stab_id(crt, "storage_low", shelf), "stability", "public", "storage_low", "storage_low", crt, "C", sl, shelf, note=note)),
        "st_high": put(_row(G.stab_id(crt, "storage_high", shelf), "stability", "public", "storage_high", "storage_high", crt, "C", sh, shelf, note=note)),
        "ex_low": put(_row(G.stab_id(exc, "excursion_permitted_low", 0), "stability", "public", "excursion_permitted_low",
                           "excursion_permitted_low", exc, "C", xl, 0, note=note)),
        "ex_high": put(_row(G.stab_id(exc, "excursion_permitted_high", 0), "stability", "public", "excursion_permitted_high",
                            "excursion_permitted_high", exc, "C", xh, 0, note=note)),
        "long": put(_row(G.stab_id(P.LONG, "study_duration_demonstrated", long_), "stability", "public", "study_duration_demonstrated",
                         "study_duration_demonstrated", P.LONG, "months", long_, long_, note=note)),
        "accel": put(_row(G.stab_id(P.ACCEL, "study_duration_demonstrated", accel), "stability", "public", "study_duration_demonstrated",
                          "study_duration_demonstrated", P.ACCEL, "months", accel, accel, note=note)),
    }
    if shelf > long_:
        extrap = put(_row(G.stab_id("extrapolation", "extrapolation_to_months", shelf), "stability", "public", "extrapolation_to_months",
                          "extrapolation_to_months", "extrapolation", "months", shelf, shelf, note=note))
    real_spec = G.collect_spec()
    keep = sorted(rng.sample(range(len(P.SPEC_ATTRIBUTES)), rng.randint(3, len(P.SPEC_ATTRIBUTES))))
    spec_attrs = [P.SPEC_ATTRIBUTES[i] for i in keep]
    for a in spec_attrs:
        base = real_spec[G.spec_id(a)]
        put(_row(G.spec_id(a), "spec", "demo", a, base["test"], "specification limit", "%", rng.choice(SPEC_VALUES[a]), limit_kind=base["limit_kind"], note=note))
    groups = [P.STAT_GROUPS[i] for i in sorted(rng.sample(range(len(P.STAT_GROUPS)), rng.randint(2, 4)))]
    for cond, attr in groups:
        allowed = [m for m in MONTHS[cond] if m <= (accel if cond == P.ACCEL else long_)]
        months = allowed[:rng.randint(3, len(allowed))]
        bad_at = rng.choice(months[1:]) if rng.randrange(4) == 0 else None      # about one group in four has a result outside its limit
        for m in months:
            put(_row(G.stab_id(cond, attr, m), "stability", "demo", attr, attr, cond, ATTR_UNIT[attr], _value(rng, attr, m == bad_at), m,
                     limit_text=ATTR_LIMIT[attr], note=note))
    tid = f"m23b_{'dev' if which == 'dev' else 'held'}_{index:02d}"
    task = _task(tid, which, True, note, spec_attrs, refs, groups, graph_file=tid + ".graph.json", extrapolation=extrap)
    problems = consistency_problems(task, rows)
    assert not problems, (tid, problems)
    return task, rows


def all_tasks():
    """{"real": [(task, None)], "dev": [(task, rows) x 10], "heldout": [(task, rows) x 20]}; no two synthetic tasks carry the same numbers."""
    out = {"real": [(real_task(), None)], "dev": [synthetic_task("dev", i) for i in range(1, DEV_COUNT + 1)],
           "heldout": [synthetic_task("heldout", i) for i in range(1, HELD_COUNT + 1)]}
    seen = {}
    for t, rows in out["dev"] + out["heldout"]:
        sig = json.dumps(sorted((k, r["value_text"]) for k, r in rows.items()))
        assert sig not in seen, f"{t['task_id']} repeats the numbers of {seen[sig]}"
        seen[sig] = t["task_id"]
    return out


def task_json(task):
    """The exact bytes saved and hashed for a task (sorted keys, LF line ends)."""
    return (json.dumps(task, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def graph_json(rows):
    """The exact bytes of a synthetic graph file."""
    return (json.dumps({"namespace": "SYNTHETIC", "note": "SYNTHETIC test graph: invented numbers; never written to Neo4j", "rows": rows},
                       indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---- what each unit of writing needs ---------------------------------------------------------------------------------------------------

def _text(row):
    """The text a slot renders to: the stored value, then its unit the way the plan writes it."""
    return row["value_text"] + P.UNIT_TEXT[row["unit"]]


def _slot(label, row):
    return {"label": label, "fact_id": row["fact_id"], "text": _text(row), "value": row["value_text"], "unit": row["unit"]}


def units_of(task, rows):
    """The writing units, in document order, with every value read from rows (the graph). Each unit:
    unit_id, part, kind (spec | public | result), slots {name: {label, fact_id, text, value, unit}}, required [names], expect [kinds, in order],
    names {field: [allowed words]}, words [extra vocabulary], context {digit-free hints}, and for result units outside (count) and has_tp."""
    units, tests = [], []
    for s in task["spec"]:
        tests.append(rows[s["fact_id"]]["test"])
    spec_slots = {s["slot"]: _slot(f"acceptance limit for {rows[s['fact_id']]['test']} ({rows[s['fact_id']]['limit_kind']})", rows[s["fact_id"]])
                  for s in task["spec"]}
    units.append({"unit_id": "spec", "part": "2.3.P.5", "kind": "spec", "slots": spec_slots, "required": list(spec_slots),
                  "expect": ["spec_intro"] + ["spec_row"] * len(task["spec"]), "names": {"test": tests, "kind": ["NLT", "NMT"]}, "words": tests,
                  "rows": [(rows[s["fact_id"]]["test"], rows[s["fact_id"]]["limit_kind"], s["slot"]) for s in task["spec"]],
                  "context": {"tests": tests}})
    pub = {k: _slot(v["label"], rows[v["fact_id"]]) for k, v in task["public"].items()}
    units.append({"unit_id": "public", "part": "2.3.P.8", "kind": "public", "slots": pub, "required": list(PUBLIC_SLOTS),
                  "expect": ["shelf", "excursion", "study"], "names": {}, "words": [], "context": {}})
    for g in task["results"]:
        st = MG.stats(rows, g["condition"], g["attribute"])
        slots = {"low": _slot("lowest stored result", st["low"]), "high": _slot("highest stored result", st["high"])}
        has_tp = st["timepoint"] is not None
        if has_tp:
            slots["tp"] = _slot("dissolution time point", st["timepoint"])
        shown = g["attr_base"] + (" (" + st["timepoint"]["value_text"] + " min)" if has_tp else "")
        units.append({"unit_id": f"result:{g['condition']}|{g['attribute']}", "part": "2.3.P.8", "kind": "result", "slots": slots,
                      "required": list(slots), "expect": ["range", "claim"], "names": {"attr": [shown], "cond": [g["cond_word"]]},
                      "words": [shown, g["cond_word"]], "condition": g["condition"], "attribute": g["attribute"], "outside": st["outside"],
                      "has_tp": has_tp, "attr_template": g["attr_base"] + (" ([[tp]])" if has_tp else ""),
                      "context": {"attribute": g["attr_base"] + (" ([[tp]])" if has_tp else ""), "condition": g["cond_word"],
                                  "outside": "none" if st["outside"] == 0 else "some"}})
    for u in units:
        for name, s in u["slots"].items():
            assert not re.search(r"\d", name + s["label"]), f"slot name or label holds a digit: {name} / {s['label']}"
        assert not re.search(r"\d", json.dumps(u["context"])), "a prompt hint holds a digit"
    return units


def view_of(unit):
    """What the prompt may show for a unit: slot names and digit-free labels, the required names and the hints. No values."""
    return {"unit_id": unit["unit_id"], "kind": unit["kind"], "slots": {k: s["label"] for k, s in unit["slots"].items()},
            "required": list(unit["required"]), "context": unit["context"]}


# ---- the saved 3.2 files the cross-check compares against (written from the graph rows, never from the 2.3 text) ----------------------

def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def write_reference(task, rows, folder):
    """Write p8/p83_public.md, p8/demo_<cond>_<attr>.md and p5_placements.jsonl in the format the cross-check reads. Returns (p5 path, p8 dir)."""
    root = Path(folder)
    p8 = root / "p8"
    p8.mkdir(parents=True, exist_ok=False)
    v = {k: rows[s["fact_id"]]["value_text"] for k, s in task["public"].items()}
    (p8 / "p83_public.md").write_text(
        f"The proposed shelf life is {v['shelf']} months when stored at {v['st_low']}°C to {v['st_high']}°C. "
        f"Excursions are permitted from {v['ex_low']}°C to {v['ex_high']}°C. "
        f"Stability was demonstrated for {v['long']} months at long-term conditions and {v['accel']} months at accelerated conditions.\n", encoding="utf-8")
    for g in task["results"]:
        st = MG.stats(rows, g["condition"], g["attribute"])
        (p8 / f"demo_{_slug(g['condition'])}_{_slug(g['attribute'])}.md").write_text(
            f"### 3.2.P.8.3 Stability: {g['attribute']} at {g['condition']} (illustrative demonstration data)\n\n"
            f"In illustrative demonstration data, {g['attribute']} at {g['condition']} ranged from {st['low']['value_text']} to "
            f"{st['high']['value_text']} over {st['n']} time points.\n", encoding="utf-8")
    with open(root / "p5_placements.jsonl", "w", encoding="utf-8") as fh:
        for i, s in enumerate(task["spec"]):
            fh.write(json.dumps({"section": f"3.2.P.5.6/w{i:03d}_{rows[s['fact_id']]['attribute']}/justification", "id": "limit",
                                 "text": rows[s["fact_id"]]["value_text"]}) + "\n")
    return root / "p5_placements.jsonl", p8


def write_all(out_dir):
    """Write every task as <out>/<set>/<id>.json (+ <id>.graph.json for synthetic ones) and SHA256SUMS. The folder must be new."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder")
    sums = []
    for which, items in all_tasks().items():
        (out / which).mkdir(parents=True)
        for t, rows in items:
            files = [(t["task_id"] + ".json", task_json(t))] + ([(t["graph_file"], graph_json(rows))] if rows is not None else [])
            for name, data in files:
                (out / which / name).write_bytes(data)
                sums.append(f"{sha256(data)}  {which}/{name}")
    (out / "SHA256SUMS").write_bytes(("\n".join(sums) + "\n").encode("utf-8"))
    return sums


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="a NEW folder for the task files")
    for line in write_all(ap.parse_args(argv).out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
