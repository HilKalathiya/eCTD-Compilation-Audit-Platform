"""Builds the 2.3 writing tasks by code from facts: the real Kerendia task plus synthetic variants (dev and held-out), each saved as one JSON file.

    python -m ectd_engine.summary.m23_tasks --out evidence/T-071/tasks      # writes real/dev/heldout JSON files + SHA256SUMS (a new folder only)

A task = one whole Module 2.3 (P.5 and P.8) for one set of facts. Gemma never sees a value: units_of() hands the prompt only slot names and digit-free labels.
Synthetic tasks are marked in the JSON ("synthetic": true), in the document title and in every fact definition; they never touch Neo4j.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import plan as P

SYNTH_TITLE = P.TITLE + " (synthetic test case)"
PUBLIC_SLOTS = ["shelf", "st_low", "st_high", "ex_low", "ex_high", "long", "accel"]
PUBLIC_LABELS = {"shelf": "proposed shelf life in months", "st_low": "lowest storage temperature", "st_high": "highest storage temperature",
                 "ex_low": "lowest permitted excursion temperature", "ex_high": "highest permitted excursion temperature",
                 "long": "months of stability demonstrated at long-term conditions",
                 "accel": "months of stability demonstrated at accelerated conditions"}
PUBLIC_ATTR = {"shelf": "expiry_period_proposed", "st_low": "storage_low", "st_high": "storage_high", "ex_low": "excursion_permitted_low",
               "ex_high": "excursion_permitted_high", "long": "study_duration_demonstrated", "accel": "study_duration_demonstrated"}
ATTR_UNIT = {"Assay": "% label claim", "Degradation product": "% area", "Dissolution (15 min)": "% dissolved"}
SPEC_VALUES = {"dissolution_av": ["70", "75", "80", "85"], "impurity_o": ["0.1", "0.2", "0.3", "0.5", "0.7"],
               "impurity_l": ["0.1", "0.2", "0.3", "0.5", "0.7"], "impurities_total": ["0.5", "1.0", "1.5", "2.0"],
               "resodual_solvent": ["0.1", "0.3", "0.5"]}
STORAGE = [(2, 8), (15, 25), (20, 25), (15, 30), (2, 25), (5, 25)]
EXCURSION = [(0, 40), (5, 40), (15, 30), (2, 30), (10, 35)]
DEV_COUNT, HELD_COUNT = 10, 20


def _row(fact_id, family, kind, attribute, test, condition, unit, value, month="", limit_kind="", note=""):
    """One graph-shaped fact row (all the fields the cross-check and the builder read)."""
    return {"attribute": attribute, "basis": "", "batch": G.PREFIX + ("SPEC" if family == "spec" else "P8"), "condition": condition,
            "definition": note, "demo_label": G.LABEL if kind == "demo" else "", "derived": "no", "doc_id": "synthetic" if note else "",
            "doc_version": "", "fact_id": fact_id, "family": family, "kind": kind, "limit_kind": limit_kind, "limit_text": "",
            "lineage": "unknown", "locator": "", "month": str(month), "page": "", "test": test, "unit": unit, "value_text": str(value)}


def _slot(row, label=""):
    return {"label": label, "fact_id": row["fact_id"], "value": row["value_text"], "unit": row["unit"]}


def _stats(rows, cond, attr):
    """(lowest row, highest row, how many) of the demo rows of one condition x attribute; the same rule the builder uses."""
    from decimal import Decimal
    grp = [r for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo" and r["condition"] == cond and r["attribute"] == attr]
    lo = min(grp, key=lambda r: Decimal(r["value_text"]))
    hi = max(grp, key=lambda r: Decimal(r["value_text"]))
    return lo, hi, len(grp)


def _task(task_id, which, synthetic, note, rows, spec_attrs, refs, groups):
    """Assemble the task dict from graph rows + which facts go where. refs = {public slot: fact_id}; groups = [(cond, attr)]."""
    spec = []
    for a in spec_attrs:
        r = rows[G.spec_id(a)]
        spec.append({"attribute": a, "test": r["test"], "limit_kind": r["limit_kind"], "slot": "spec_" + a, "fact_id": r["fact_id"],
                     "value": r["value_text"], "unit": r["unit"]})
    public = {s: _slot(rows[refs[s]], PUBLIC_LABELS[s]) for s in PUBLIC_SLOTS}
    results = []
    for cond, attr in groups:
        lo, hi, n = _stats(rows, cond, attr)
        results.append({"condition": cond, "attribute": attr, "cond_word": P.COND_WORD[cond], "attr_shown": P.ATTR_SHOWN[attr], "n_points": n,
                        "low": _slot(dict(lo, fact_id=P.stat_id(cond, attr, "min")), "lowest stored result"),
                        "high": _slot(dict(hi, fact_id=P.stat_id(cond, attr, "max")), "highest stored result")})
    return {"task_id": task_id, "set": which, "synthetic": synthetic, "note": note,
            "title": SYNTH_TITLE if synthetic else P.TITLE, "graph_rows": rows, "spec": spec, "public": public, "results": results}


def real_task():
    """The real Kerendia task, from the facts the 2.3 builder uses (read from the stability and specification CSV files, not from Neo4j)."""
    rows = G.collect()
    return _task("m23_real", "real", False, "Real Kerendia facts (public) and the demonstration specification.", rows, P.SPEC_ATTRIBUTES,
                 P.PUBLIC_REFS, P.STAT_GROUPS)


def _int_text(n, places):
    """n / 10**places as plain text without float: 5012 with 2 places -> '50.12'."""
    s = str(n).rjust(places + 1, "0")
    return s[:-places] + "." + s[-places:]


def _values(rng, attr, count):
    if attr == "Assay":
        return [_int_text(rng.randint(9800, 10150), 2) for _ in range(count)]
    if attr == "Degradation product":
        return [_int_text(rng.randint(50, 250), 3) for _ in range(count)]
    return [_int_text(rng.randint(9000, 9800), 2) for _ in range(count)]


def synthetic_task(which, index):
    """One synthetic task. which = 'dev' | 'heldout'; the seed is the text 'm23-<which>-<index>', so the result never changes."""
    rng = random.Random(f"m23-{which}-{index}")
    sl, sh = rng.choice(STORAGE)
    xl, xh = rng.choice(EXCURSION)
    shelf, accel = rng.choice([18, 24, 30, 36, 48]), rng.choice([3, 6])
    long_ = rng.choice([12, 18, 24, 36, 48])
    if index % 4 == 0:
        long_ = shelf          # same number in two different places: a swap of the two would be invisible to a value check
    if index % 5 == 0:
        xl = sl                # storage low = excursion low
    note = "SYNTHETIC test case (invented numbers, not Kerendia)."
    rows = {}

    def put(r):
        rows[r["fact_id"]] = r
        return r["fact_id"]
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
    real_spec = G.collect_spec()
    keep = sorted(rng.sample(range(len(P.SPEC_ATTRIBUTES)), rng.randint(3, len(P.SPEC_ATTRIBUTES))))
    spec_attrs = [P.SPEC_ATTRIBUTES[i] for i in keep]
    for a in spec_attrs:
        base = real_spec[G.spec_id(a)]
        put(_row(G.spec_id(a), "spec", "demo", a, base["test"], "specification limit", "%", rng.choice(SPEC_VALUES[a]),
                 limit_kind=base["limit_kind"], note=note))
    all_groups = list(P.STAT_GROUPS)
    groups = [all_groups[i] for i in sorted(rng.sample(range(len(all_groups)), rng.randint(2, 4)))]
    for cond, attr in groups:
        months = [0, 3, 6, 9, 12][:rng.randint(3, 5)]
        for m, v in zip(months, _values(rng, attr, len(months))):
            put(_row(G.stab_id(cond, attr, m), "stability", "demo", attr, attr, cond, ATTR_UNIT[attr], v, m, note=note))
    task_id = f"m23_{'dev' if which == 'dev' else 'held'}_{index:02d}"
    return _task(task_id, which, True, note, rows, spec_attrs, refs, groups)


def all_tasks():
    """{"real": [task], "dev": [10 tasks], "heldout": [20 tasks]}; no two synthetic tasks carry the same numbers."""
    out = {"real": [real_task()], "dev": [synthetic_task("dev", i) for i in range(1, DEV_COUNT + 1)],
           "heldout": [synthetic_task("heldout", i) for i in range(1, HELD_COUNT + 1)]}
    seen = {}
    for t in out["dev"] + out["heldout"]:
        sig = json.dumps([t["spec"], t["public"], t["results"]], sort_keys=True)
        for k in ("fact_id", "label"):
            sig = re.sub(r'"%s": "[^"]*",? ?' % k, "", sig)
        assert sig not in seen, f"{t['task_id']} repeats the numbers of {seen[sig]}"
        seen[sig] = t["task_id"]
    return out


def task_json(task):
    """The exact bytes saved and hashed for a task (sorted keys, LF line ends)."""
    return (json.dumps(task, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(task):
    return hashlib.sha256(task_json(task)).hexdigest()


# ---- what each unit of writing needs (used by the prompt, the gate and the renderer) ----------------------------------------------

def _text(slot):
    """The text a slot renders to: the value, then its unit the way the plan writes it."""
    return slot["value"] + P.UNIT_TEXT[slot["unit"]]


def units_of(task):
    """The writing units of a task, in document order. Each unit:
    unit_id, part, kind (spec | public | result), slots {name: {label, fact_id, text, ...}}, required [names],
    expect [(form name, [slot names in that sentence])], names {field: [allowed words]}, words [extra vocabulary], context {digit-free hints}."""
    units = []
    tests = [s["test"] for s in task["spec"]]
    spec_slots = {s["slot"]: {"label": f"acceptance limit for {s['test']} ({s['limit_kind']})", "fact_id": s["fact_id"], "text": _text(s),
                              "value": s["value"], "unit": s["unit"]} for s in task["spec"]}
    units.append({"unit_id": "spec", "part": "2.3.P.5", "kind": "spec", "slots": spec_slots, "required": list(spec_slots),
                  "expect": [("spec_intro", [])] + [("spec_row", [s["slot"]]) for s in task["spec"]],
                  "names": {"test": tests, "kind": ["NLT", "NMT"]}, "words": tests,
                  "rows": [(s["test"], s["limit_kind"]) for s in task["spec"]], "context": {"tests": tests}})
    pub = {k: {"label": v["label"], "fact_id": v["fact_id"], "text": _text(v), "value": v["value"], "unit": v["unit"]} for k, v in task["public"].items()}
    units.append({"unit_id": "public", "part": "2.3.P.8", "kind": "public", "slots": pub, "required": list(PUBLIC_SLOTS),
                  "expect": [("shelf", ["shelf", "st_low", "st_high"]), ("excursion", ["ex_low", "ex_high"]), ("study", ["long", "accel"])],
                  "names": {}, "words": [], "context": {}})
    for g in task["results"]:
        slots = {"low": {"label": g["low"]["label"], "fact_id": g["low"]["fact_id"], "text": _text(g["low"]), "value": g["low"]["value"], "unit": g["low"]["unit"]},
                 "high": {"label": g["high"]["label"], "fact_id": g["high"]["fact_id"], "text": _text(g["high"]), "value": g["high"]["value"], "unit": g["high"]["unit"]}}
        units.append({"unit_id": f"result:{g['condition']}|{g['attribute']}", "part": "2.3.P.8", "kind": "result", "slots": slots,
                      "required": ["low", "high"], "expect": [("result", ["low", "high"])],
                      "names": {"attr": [g["attr_shown"]], "cond": [g["cond_word"]]}, "words": [g["attr_shown"], g["cond_word"]],
                      "condition": g["condition"], "attribute": g["attribute"],
                      "context": {"attribute": g["attr_shown"], "condition": g["cond_word"]}})
    for u in units:
        for name, s in u["slots"].items():
            assert not re.search(r"\d", name + s["label"]), f"slot name or label holds a digit: {name} / {s['label']}"
        assert not re.search(r"\d", json.dumps(u["context"])), "a prompt hint holds a digit"
    return units


def view_of(unit):
    """What the prompt may show for a unit: slot names and digit-free labels, the required names and the hints. No values."""
    return {"unit_id": unit["unit_id"], "kind": unit["kind"], "slots": {k: s["label"] for k, s in unit["slots"].items()},
            "required": list(unit["required"]), "context": unit["context"]}


# ---- the saved 3.2 files the cross-check compares against (written from the task, never from the 2.3 text) -------------------------

def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def write_reference(task, folder):
    """Write p8/p83_public.md, p8/demo_<cond>_<attr>.md and p5_placements.jsonl in the format the cross-check reads. Returns (p5 path, p8 dir)."""
    root = Path(folder)
    p8 = root / "p8"
    p8.mkdir(parents=True, exist_ok=False)
    v = {k: s["value"] for k, s in task["public"].items()}
    (p8 / "p83_public.md").write_text(
        f"The proposed shelf life is {v['shelf']} months when stored at {v['st_low']}°C to {v['st_high']}°C. "
        f"Excursions are permitted from {v['ex_low']}°C to {v['ex_high']}°C. "
        f"Stability was demonstrated for {v['long']} months at long-term conditions and {v['accel']} months at accelerated conditions.\n", encoding="utf-8")
    for g in task["results"]:
        (p8 / f"demo_{_slug(g['condition'])}_{_slug(g['attribute'])}.md").write_text(
            f"ranged from {g['low']['value']} to {g['high']['value']} over {g['n_points']} time points.\n", encoding="utf-8")
    with open(root / "p5_placements.jsonl", "w", encoding="utf-8") as fh:
        for i, s in enumerate(task["spec"]):
            fh.write(json.dumps({"section": f"3.2.P.5.6/w{i:03d}_{s['attribute']}/justification", "id": "limit", "text": s["value"]}) + "\n")
    return root / "p5_placements.jsonl", p8


def write_all(out_dir):
    """Write every task as <out>/<set>/<task id>.json plus SHA256SUMS (one line per file). The folder must be new."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder")
    sums = []
    for which, tasks in all_tasks().items():
        (out / which).mkdir(parents=True)
        for t in tasks:
            (out / which / (t["task_id"] + ".json")).write_bytes(task_json(t))
            sums.append(f"{sha256(t)}  {which}/{t['task_id']}.json")
    (out / "SHA256SUMS").write_bytes(("\n".join(sums) + "\n").encode("utf-8"))
    return sums


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="a NEW folder for the task files")
    args = ap.parse_args(argv)
    for line in write_all(args.out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
