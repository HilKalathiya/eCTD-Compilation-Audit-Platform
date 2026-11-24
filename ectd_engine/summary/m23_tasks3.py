"""T-073 task builder for the 2.3 writer: realistic test cases (one limit source R7, claim rules R8) from new seeds; task files hold slot names and fact ids ONLY.

    python -m ectd_engine.summary.m23_tasks3 --out evidence/T-073/tasks     # real + dev + held-out task files, synthetic graph files, SHA256SUMS (new folder only)

Built beside the T-072 builder (m23_tasks2, frozen history; its tests pin its bytes). Rules every task must pass (consistency_problems3 = R0-R6 of m23_tasks2 plus):
  R7 a stability attribute shown with a spec fact takes its limit from that spec fact; the spec fact must be in the task's specification table;
  R8 a shelf life beyond the long-term data needs an extrapolation fact AND no blocker (m23_rules.extrapolation_blockers: results outside the limit at
     long-term / intermediate, significant change at accelerated, no accelerated data). The generator refuses such a task and records the refusal in the task.
Each synthetic task is built to a PROFILE (clean, extrap, outside_lt, ...); the profile list is cycled by index so the quotas are met by construction.
"""
import argparse
import json
import random
import re
import sys
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_rules as R
from ectd_engine.summary import m23_tasks2 as T
from ectd_engine.summary import plan as P

# Neutral labels: the T-072 label said "months of stability demonstrated", which is itself the claim the data may not support.
PUBLIC_LABELS = dict(T.PUBLIC_LABELS, long="months of long-term data", accel="months of accelerated data")
ROW_LIMIT = {"Assay": "95.0-105.0", "Degradation product": "NMT 0.50"}        # Dissolution takes its limit from the spec fact (R7)
ATTRS = list(P.ATTR_SHOWN)
# index 1..10 repeats; with 10 dev and 20 held-out tasks: 6 outside, 3+ extrapolations, 6+ refusals per 10 tasks
PROFILES = ["clean", "extrap", "outside_lt", "extrap", "sig_assay", "outside_accel", "outside_int", "extrap", "no_accel", "outside_lt"]
WANTS_EXTRAPOLATION = {p for p in PROFILES if p != "clean"}
DEV_COUNT, HELD_COUNT = 10, 20


def consistency_problems3(task, rows):
    """[reason, ...] for every rule the task and its graph rows break (R0-R6 of m23_tasks2, R7, R8); [] = consistent."""
    out = T.consistency_problems(task, rows)
    if any(p.startswith("R0") for p in out):
        return out
    out += R.limit_problems(rows)
    shown = {s["fact_id"] for s in task["spec"]}
    for attr in sorted({a for _, a in R.groups_in(rows)}):
        if attr in R.SPEC_LINK and G.spec_id(R.SPEC_LINK[attr]) not in shown:
            out.append(f"R7: {attr} takes its limit from {G.spec_id(R.SPEC_LINK[attr])}, which the specification table does not show")
    shelf, long_ = (Decimal(rows[task["public"][s]["fact_id"]]["value_text"]) for s in ("shelf", "long"))
    if shelf > long_:
        out += [f"R8: the shelf life ({shelf}) is longer than the long-term data ({long_}) but {b}" for b in R.extrapolation_blockers(rows)]
    return out


def _task3(task_id, which, synthetic, note, spec_attrs, refs, groups, graph_file=None, extrapolation=None, refused=None, profile=None):
    t = T._task(task_id, which, synthetic, note, spec_attrs, refs, groups, graph_file=graph_file, extrapolation=extrapolation)
    t.update(version="v3", extrapolation_refused=refused, profile=profile)
    for s in ("long", "accel"):
        t["public"][s]["label"] = PUBLIC_LABELS[s]
    return t


def real_task3():
    """The real Kerendia task, ids only, with the neutral labels. Its numbers are read from Neo4j when it is rendered."""
    return _task3("m23c_real", "real", False, "Real Kerendia facts (public) and the demonstration specification.", P.SPEC_ATTRIBUTES, P.PUBLIC_REFS, P.STAT_GROUPS)


def _bad_value(attr, spec_value):
    """A stored result that breaks its limit (Assay below 95.0, degradation product above 0.50, dissolution 2.5 below the specification value)."""
    if attr == "Assay":
        return "94.50"
    if attr == "Degradation product":
        return "0.520"
    return str(Decimal(spec_value) - Decimal("2.50"))


def _ok_value(rng, attr):
    return {"Assay": lambda: T._int_text(rng.randint(9800, 10150), 2), "Degradation product": lambda: T._int_text(rng.randint(50, 250), 3)}.get(
        attr, lambda: T._int_text(rng.randint(9000, 9800), 2))()


def synthetic_task3(which, index):
    """(task, rows) for one synthetic task. The seed is the text 'm23c-<which>-<index>', so the result never changes."""
    rng = random.Random(f"m23c-{which}-{index}")
    profile = PROFILES[(index - 1) % len(PROFILES)]
    rows, note = {}, "SYNTHETIC test case (invented numbers, not Kerendia)."

    def put(r):
        rows[r["fact_id"]] = r
        return r["fact_id"]
    long_ = rng.choice([12, 18, 24, 36, 48])
    accel = rng.choice([3, 6])
    attrs = set(rng.sample(ATTRS, rng.randint(1, 3)))
    bad_group, bad_attr = None, None
    if profile == "sig_assay":
        attrs.add("Assay")
    if profile == "outside_accel":
        bad_attr = rng.choice(["Degradation product", "Dissolution (15 min)"])
        attrs.add(bad_attr)
    groups = {(P.LONG, a) for a in attrs}
    if profile in ("extrap", "sig_assay", "outside_lt", "outside_accel", "outside_int"):
        groups |= {(P.ACCEL, a) for a in attrs}
    if profile == "clean":
        groups |= {(rng.choice([P.ACCEL, P.INTER]), rng.choice(sorted(attrs)))}
    if profile in ("extrap", "outside_int", "no_accel"):
        groups.add((P.INTER, rng.choice(sorted(attrs))))
    if profile == "outside_lt":
        bad_group = (P.LONG, rng.choice(sorted(attrs)))
    elif profile == "outside_accel":
        bad_group = (P.ACCEL, bad_attr)
    elif profile == "outside_int":
        bad_group = next(iter(sorted(g for g in groups if g[0] == P.INTER)))
    groups = [g for g in P.STAT_GROUPS if g in groups]
    spec_attrs = set(rng.sample(P.SPEC_ATTRIBUTES, rng.randint(3, len(P.SPEC_ATTRIBUTES))))
    if "Dissolution (15 min)" in attrs:
        spec_attrs.add(R.SPEC_LINK["Dissolution (15 min)"])                     # R7: the limit's source must be in the specification table
    spec_attrs = [a for a in P.SPEC_ATTRIBUTES if a in spec_attrs]
    real_spec, spec_value = G.collect_spec(), {}
    for a in spec_attrs:
        spec_value[a] = rng.choice(T.SPEC_VALUES[a])
        put(T._row(G.spec_id(a), "spec", "demo", a, real_spec[G.spec_id(a)]["test"], "specification limit", "%", spec_value[a],
                   limit_kind=real_spec[G.spec_id(a)]["limit_kind"], note=note))
    for cond, attr in groups:
        allowed = [m for m in T.MONTHS[cond] if m <= (accel if cond == P.ACCEL else long_)]
        months = allowed[:rng.randint(3, len(allowed))]
        bad_at = rng.choice(months[1:]) if (cond, attr) == bad_group else None
        limit = ROW_LIMIT.get(attr) or f"NLT {spec_value[R.SPEC_LINK[attr]]}"
        for m in months:
            if profile == "sig_assay" and cond == P.ACCEL and attr == "Assay":
                value = "104.00" if m == 0 else T._int_text(rng.randint(9650, 9800), 2)      # a drift of more than 5% that stays inside 95.0-105.0
            else:
                value = _bad_value(attr, spec_value.get(R.SPEC_LINK.get(attr))) if m == bad_at else _ok_value(rng, attr)
            put(T._row(G.stab_id(cond, attr, m), "stability", "demo", attr, attr, cond, T.ATTR_UNIT[attr], value, m, limit_text=limit, note=note))
    wanted = None
    ok = [m for m in (12, 18, 24, 30, 36, 48, 60) if m <= long_]
    shelf, extrap, refused = long_ if index % 4 == 0 else rng.choice(ok), None, None
    if profile in WANTS_EXTRAPOLATION:
        beyond = [m for m in (18, 24, 30, 36, 48, 60) if long_ < m <= T.q1e_max_shelf(long_)]
        wanted = beyond[-1] if index % 2 else beyond[0]
        blockers = R.extrapolation_blockers(rows)
        if blockers:
            refused = {"wanted_months": wanted, "reasons": blockers}
        else:
            shelf = wanted
    assert (profile == "extrap") == (shelf > long_), (profile, shelf, long_, refused)
    crt_lo, crt_hi = rng.choice(T.STORAGE)
    xl, xh = rng.choice([e for e in T.EXCURSION if e[0] <= crt_lo and crt_hi <= e[1]])
    if index % 5 == 0:
        xl = crt_lo
    crt, exc = f"{crt_lo}-{crt_hi}C CRT", f"{xl}-{xh}C excursion"
    pub = lambda fid, attribute, cond_, unit, value, month: put(T._row(fid, "stability", "public", attribute, attribute, cond_, unit, value, month, note=note))  # noqa: E731
    refs = {"shelf": pub(G.stab_id(crt, "expiry_period_proposed", shelf), "expiry_period_proposed", crt, "months", shelf, shelf),
            "st_low": pub(G.stab_id(crt, "storage_low", shelf), "storage_low", crt, "C", crt_lo, shelf),
            "st_high": pub(G.stab_id(crt, "storage_high", shelf), "storage_high", crt, "C", crt_hi, shelf),
            "ex_low": pub(G.stab_id(exc, "excursion_permitted_low", 0), "excursion_permitted_low", exc, "C", xl, 0),
            "ex_high": pub(G.stab_id(exc, "excursion_permitted_high", 0), "excursion_permitted_high", exc, "C", xh, 0),
            "long": pub(G.stab_id(P.LONG, "study_duration_demonstrated", long_), "study_duration_demonstrated", P.LONG, "months", long_, long_),
            "accel": pub(G.stab_id(P.ACCEL, "study_duration_demonstrated", accel), "study_duration_demonstrated", P.ACCEL, "months", accel, accel)}
    if shelf > long_:
        extrap = pub(G.stab_id("extrapolation", "extrapolation_to_months", shelf), "extrapolation_to_months", "extrapolation", "months", shelf, shelf)
    tid = f"m23c_{'dev' if which == 'dev' else 'held'}_{index:02d}"
    task = _task3(tid, which, True, note, spec_attrs, refs, groups, graph_file=tid + ".graph.json", extrapolation=extrap, refused=refused, profile=profile)
    problems = consistency_problems3(task, rows)
    assert not problems, (tid, problems)
    return task, rows


def all_tasks3():
    """{"real": [(task, None)], "dev": [(task, rows) x 10], "heldout": [(task, rows) x 20]}; no two synthetic tasks carry the same numbers."""
    out = {"real": [(real_task3(), None)], "dev": [synthetic_task3("dev", i) for i in range(1, DEV_COUNT + 1)],
           "heldout": [synthetic_task3("heldout", i) for i in range(1, HELD_COUNT + 1)]}
    seen = {}
    for t, rows in out["dev"] + out["heldout"]:
        sig = json.dumps(sorted((k, r["value_text"]) for k, r in rows.items()))
        assert sig not in seen, f"{t['task_id']} repeats the numbers of {seen[sig]}"
        seen[sig] = t["task_id"]
    return out


# ---- what each unit of writing needs (T-072 units + the claim facts) ---------------------------------------------------------------------

def units_of3(task, rows):
    """The T-072 units with: result units' outside count from the ONE limit source (m23_rules), their claim fact ids, and for the public unit whether
    "demonstrated" is allowed, whether the shelf life goes beyond the data, and the claim fact ids of the study and shelf sentences."""
    units = T.units_of(task, rows)
    for u in units:
        if u["kind"] == "result":
            u["outside"] = R.outside_count(rows, u["condition"], u["attribute"])
            u["context"]["outside"] = "none" if u["outside"] == 0 else "some"
            u["claim_ids"] = [R.outside_id(u["condition"], u["attribute"])]
        elif u["kind"] == "public":
            blockers = R.study_blockers(rows)
            u["study_blockers"] = blockers
            u["context"] = {"demonstrated": "not allowed" if blockers else "allowed"}
            u["extrapolates"] = Decimal(u["slots"]["shelf"]["value"]) > Decimal(u["slots"]["long"]["value"])
            u["study_ids"], u["shelf_ids"] = R.study_claim_ids(rows), R.extrapolation_claim_ids(rows)
        assert not re.search(r"\d", json.dumps(u["context"])), "a prompt hint holds a digit"
    return units


view_of = T.view_of


def write_reference3(task, rows, folder):
    """Like m23_tasks2.write_reference (the saved 3.2 stand-in files, made from the graph rows), but its study sentence says 'demonstrated' only when the
    rules allow it; otherwise 'Data are available for ...' (the cross-check reads both)."""
    p5, p8 = T.write_reference(task, rows, folder)
    if R.study_blockers(rows):
        f = p8 / "p83_public.md"
        f.write_text(f.read_text(encoding="utf-8").replace("Stability was demonstrated for", "Data are available for"), encoding="utf-8")
    return p5, p8


def write_all3(out_dir):
    """Write every task as <out>/<set>/<id>.json (+ <id>.graph.json for synthetic ones) and SHA256SUMS. The folder must be new."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder")
    sums = []
    for which, items in all_tasks3().items():
        (out / which).mkdir(parents=True)
        for t, rows in items:
            files = [(t["task_id"] + ".json", T.task_json(t))] + ([(t["graph_file"], T.graph_json(rows))] if rows is not None else [])
            for name, data in files:
                (out / which / name).write_bytes(data)
                sums.append(f"{T.sha256(data)}  {which}/{name}")
    (out / "SHA256SUMS").write_bytes(("\n".join(sums) + "\n").encode("utf-8"))
    return sums


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="a NEW folder for the task files")
    for line in write_all3(ap.parse_args(argv).out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
