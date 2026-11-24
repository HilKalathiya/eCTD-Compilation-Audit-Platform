"""T-074 task builder for the 2.3 writer: every limit from a spec fact (R7 for all attributes), bad data for the writer, new seeds; task files hold ids and slot names ONLY.

    python -m ectd_engine.summary.m23_tasks4 --out evidence/T-074/tasks     # real + dev + held-out task files, synthetic graph files, SHA256SUMS (new folder only)

Built beside m23_tasks3 (frozen history; its tests pin its bytes). What is new:
  R7 for ALL attributes: each result group of a task names ONE spec fact ("spec_fact" = a fact id) that its limit comes from: Dissolution -> dissolution_av,
     Assay -> the assay spec row (synthetic tasks add it to their 2.3.P.5 table), Degradation product -> the impurity (impurity_o, impurity_l or the total)
     its group uses. The real Kerendia task has a link for Dissolution only: Assay and Degradation product have no public spec fact, so they stay unlinked
     and the writer may give only the range sentence for them (no within/outside claim).
  Profiles (cycled by index) put bad data in front of the writer: a long-term/intermediate result outside its limit (human review route), a significant
     change at accelerated, an accelerated result outside its limit. At least 14 of 20 held-out tasks do (checked by a test, and each profile is checked
     against the rules when the task is made: the generator RAISES if the data do not show what the profile says; no assert).
"""
import argparse
import json
import random
import sys
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_rules4 as R
from ectd_engine.summary import m23_tasks2 as T
from ectd_engine.summary import m23_tasks3 as T3
from ectd_engine.summary import plan as P

PUBLIC_LABELS = T3.PUBLIC_LABELS
ATTRS = list(P.ATTR_SHOWN)
SPEC_ORDER = ["assay"] + list(P.SPEC_ATTRIBUTES)
LINK_ATTR = {"Assay": "assay", "Dissolution (15 min)": "dissolution_av"}      # Degradation product: one of IMPURITY_SPEC, chosen per group
IMPURITY_SPEC = ["impurity_o", "impurity_l", "impurities_total"]
SPEC_VALUES = {"assay": ["95.0", "96.0"], "dissolution_av": ["70", "75", "80", "85"], "impurity_o": ["0.2", "0.3", "0.5", "0.7"],
               "impurity_l": ["0.2", "0.3", "0.5", "0.7"], "impurities_total": ["0.5", "1.0", "1.5", "2.0"], "resodual_solvent": ["0.1", "0.3", "0.5"]}
# cycle of 10; with 10 dev and 20 held-out tasks 7 of 10 show bad data to the writer (review route 3, significant change 2, outside at accelerated 2)
PROFILES = ["clean", "extrap", "outside_lt", "sig_assay", "outside_accel", "outside_int", "outside_lt", "extrap", "sig_assay", "outside_accel"]
WANTS_EXTRAPOLATION = {p for p in PROFILES if p != "clean"}
DEV_COUNT, HELD_COUNT = 10, 20


class TaskError(Exception):
    """The generator made data that do not show what the profile says (replaces an assert)."""


def consistency_problems4(task, rows):
    """[reason, ...]: R0-R6 of m23_tasks2, R7 for every group, R8 (a shelf life beyond the long-term data needs no blocker); [] = consistent."""
    out = T.consistency_problems(task, rows)
    if any(p.startswith("R0") for p in out):
        return out
    links = R.links_of(task)
    out += R.limit_problems(rows, links)
    shown = {s["fact_id"] for s in task["spec"]}
    for (cond, attr), fid in sorted(links.items()):
        if fid and fid not in shown:
            out.append(f"R7: {cond} | {attr} takes its limit from {fid}, which the specification table does not show")
        if task["synthetic"] and not fid:
            out.append(f"R7: {cond} | {attr} has no spec fact (every synthetic group must have one)")
    shelf, long_ = (Decimal(rows[task["public"][s]["fact_id"]]["value_text"]) for s in ("shelf", "long"))
    if shelf > long_:
        out += [f"R8: the shelf life ({shelf}) is longer than the long-term data ({long_}) but {b}" for b in R.extrapolation_blockers(rows, links)]
    return out


def _task4(task_id, which, synthetic, note, spec_attrs, refs, groups, links, graph_file=None, extrapolation=None, refused=None, profile=None):
    t = T._task(task_id, which, synthetic, note, spec_attrs, refs, groups, graph_file=graph_file, extrapolation=extrapolation)
    t.update(version="v4", extrapolation_refused=refused, profile=profile)
    for s in ("long", "accel"):
        t["public"][s]["label"] = PUBLIC_LABELS[s]
    for g in t["results"]:
        g["spec_fact"] = links[(g["condition"], g["attribute"])]
    return t


def real_task4():
    """The real Kerendia task, ids only. Dissolution is linked to the dissolution spec fact; Assay and Degradation product have no public spec fact (no link)."""
    links = {(c, a): (G.spec_id("dissolution_av") if a == "Dissolution (15 min)" else None) for c, a in P.STAT_GROUPS}
    return _task4("m23d_real", "real", False, "Real Kerendia facts (public) and the demonstration specification.", P.SPEC_ATTRIBUTES, P.PUBLIC_REFS,
                  P.STAT_GROUPS, links)


def _bad_value(attr, limit_value):
    """A stored result that breaks its limit (Assay 94.50 under NLT 95.0/96.0; a degradation product 0.02 over its NMT; dissolution 2.50 under its NLT)."""
    if attr == "Assay":
        return "94.50"
    if attr == "Degradation product":
        return str((Decimal(limit_value) + Decimal("0.020")).quantize(Decimal("0.001")))
    return str(Decimal(limit_value) - Decimal("2.50"))


def _ok_value(rng, attr, limit_value):
    """A stored result inside its limit (a degradation product stays under 80% of its NMT, whatever the impurity)."""
    if attr == "Assay":
        return T._int_text(rng.randint(9800, 10150), 2)
    if attr == "Degradation product":
        return T._int_text(rng.randint(40, max(41, int(Decimal(limit_value) * 800))), 3)
    return T._int_text(rng.randint(9000, 9800), 2)


def _check_profile(profile, rows, links, shelf, long_):
    """Raise TaskError when the data of a synthetic task do not show the bad data (or the cleanliness) its profile promises."""
    bad = R.bad_data_to_writer(rows, links)
    want = {"clean": None, "extrap": None, "outside_lt": "review", "outside_int": "review", "sig_assay": "significant_change", "outside_accel": "outside_accelerated"}
    if bad != want[profile]:
        raise TaskError(f"profile {profile} promises {want[profile]!r} bad data but the rules find {bad!r}")
    if profile == "clean" and (R.study_blockers(rows, links) or shelf > long_):
        raise TaskError("a clean task must allow 'demonstrated' and keep the shelf life inside the long-term data")
    if profile in ("outside_lt", "outside_int") and not R.review_reasons(rows, links):
        raise TaskError("a review profile must have a long-term or intermediate result outside its limit")


def synthetic_task4(which, index):
    """(task, rows) for one synthetic task. The seed is the text 'm23d-<which>-<index>', so the result never changes."""
    rng = random.Random(f"m23d-{which}-{index}")
    profile = PROFILES[(index - 1) % len(PROFILES)]
    rows, note = {}, "SYNTHETIC test case (invented numbers, not Kerendia)."

    def put(r):
        rows[r["fact_id"]] = r
        return r["fact_id"]
    long_, accel = rng.choice([12, 18, 24, 36, 48]), rng.choice([3, 6])
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
    if profile in ("extrap", "outside_int"):
        groups.add((P.INTER, rng.choice(sorted(attrs))))
    if profile == "outside_lt":
        bad_group = (P.LONG, rng.choice(sorted(attrs)))
    elif profile == "outside_accel":
        bad_group = (P.ACCEL, bad_attr)
    elif profile == "outside_int":
        bad_group = next(iter(sorted(g for g in groups if g[0] == P.INTER)))
    groups = [g for g in P.STAT_GROUPS if g in groups]
    links = {g: G.spec_id(LINK_ATTR.get(g[1]) or rng.choice(IMPURITY_SPEC)) for g in groups}        # R7: ONE spec fact per group
    spec_attrs = set(rng.sample(P.SPEC_ATTRIBUTES, rng.randint(2, len(P.SPEC_ATTRIBUTES))))
    spec_attrs |= {fid[len(G.PREFIX + "SPEC-LEK-"):] for fid in links.values()}                    # the source of every limit must be in the table
    spec_attrs = [a for a in SPEC_ORDER if a in spec_attrs]
    real_spec, spec_value = G.collect_spec(), {}
    for a in spec_attrs:
        spec_value[a] = rng.choice(SPEC_VALUES[a])
        if a == "assay":
            put(T._row(G.spec_id(a), "spec", "demo", a, "Assay", "specification limit", "%", spec_value[a], limit_kind="NLT", note=note))
        else:
            put(T._row(G.spec_id(a), "spec", "demo", a, real_spec[G.spec_id(a)]["test"], "specification limit", "%", spec_value[a],
                       limit_kind=real_spec[G.spec_id(a)]["limit_kind"], note=note))
    for cond, attr in groups:
        allowed = [m for m in T.MONTHS[cond] if m <= (accel if cond == P.ACCEL else long_)]
        months = allowed[:rng.randint(3, len(allowed))]
        bad_at = rng.choice(months[1:]) if (cond, attr) == bad_group else None
        spec_row = rows[links[(cond, attr)]]
        limit_value, limit = spec_row["value_text"], f"{spec_row['limit_kind']} {spec_row['value_text']}"
        for m in months:
            if profile == "sig_assay" and cond == P.ACCEL and attr == "Assay":
                value = "104.00" if m == 0 else T._int_text(rng.randint(9650, 9800), 2)      # a drift of more than 5% that stays inside NLT 95.0 / 96.0
            else:
                value = _bad_value(attr, limit_value) if m == bad_at else _ok_value(rng, attr, limit_value)
            put(T._row(G.stab_id(cond, attr, m), "stability", "demo", attr, attr, cond, T.ATTR_UNIT[attr], value, m, limit_text=limit, note=note))
    ok = [m for m in (12, 18, 24, 30, 36, 48, 60) if m <= long_]
    shelf, extrap, refused = long_ if index % 4 == 0 else rng.choice(ok), None, None
    if profile in WANTS_EXTRAPOLATION:
        beyond = [m for m in (18, 24, 30, 36, 48, 60) if long_ < m <= T.q1e_max_shelf(long_)]
        wanted = beyond[-1] if index % 2 else beyond[0]
        blockers = R.extrapolation_blockers(rows, links)
        if blockers:
            refused = {"wanted_months": wanted, "reasons": blockers}
        else:
            shelf = wanted
    if (profile == "extrap") != (shelf > long_):
        raise TaskError(f"profile {profile}: shelf {shelf} against long-term {long_} (refused: {refused})")
    _check_profile(profile, rows, links, shelf, long_)
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
    tid = f"m23d_{'dev' if which == 'dev' else 'held'}_{index:02d}"
    task = _task4(tid, which, True, note, spec_attrs, refs, groups, links, graph_file=tid + ".graph.json", extrapolation=extrap, refused=refused, profile=profile)
    problems = consistency_problems4(task, rows)
    if problems:
        raise TaskError(f"{tid} is not self-consistent: {problems}")
    return task, rows


def all_tasks4():
    """{"real": [(task, None)], "dev": [(task, rows) x 10], "heldout": [(task, rows) x 20]}; no two synthetic tasks carry the same numbers."""
    out = {"real": [(real_task4(), None)], "dev": [synthetic_task4("dev", i) for i in range(1, DEV_COUNT + 1)],
           "heldout": [synthetic_task4("heldout", i) for i in range(1, HELD_COUNT + 1)]}
    seen = {}
    for t, rows in out["dev"] + out["heldout"]:
        sig = json.dumps(sorted((k, r["value_text"]) for k, r in rows.items()))
        if sig in seen:
            raise TaskError(f"{t['task_id']} repeats the numbers of {seen[sig]}")
        seen[sig] = t["task_id"]
    return out


# ---- what each unit of writing needs --------------------------------------------------------------------------------------------------

def units_of4(task, rows):
    """The T-072 units with: result units' outside count from their ONE spec fact (a group with no spec fact has NO claim sentence), the public unit's
    DEMONSTRATED line, and the review route (long-term/intermediate result outside its limit: no shelf, storage or shelf-life sentence at all)."""
    links = R.links_of(task)
    units = T.units_of(task, rows)
    reasons = R.review_reasons(rows, links)
    for u in units:
        if u["kind"] == "result":
            key = (u["condition"], u["attribute"])
            u["linked"] = bool(links.get(key))
            if u["linked"]:
                u["outside"] = R.outside_count(rows, links, *key)
                u["context"]["outside"] = "none" if u["outside"] == 0 else "some"
                u["claim_ids"] = [R.outside_id(*key)]
            else:
                u["outside"], u["expect"], u["claim_ids"] = None, ["range"], []
                u["context"]["outside"] = "not stated"
        elif u["kind"] == "public":
            blockers = R.study_blockers(rows, links)
            u["study_blockers"], u["review"] = blockers, reasons
            u["context"] = {"demonstrated": "not allowed" if blockers else "allowed", "shelf": "blocked" if reasons else "written"}
            if reasons:
                for k in ("shelf", "st_low", "st_high"):
                    u["slots"].pop(k)
                u["required"] = [k for k in u["required"] if k in u["slots"]]
                u["expect"] = ["excursion", "study"]
            shelf, long_ = (Decimal(rows[task["public"][k]["fact_id"]]["value_text"]) for k in ("shelf", "long"))
            u["extrapolates"] = (not reasons) and shelf > long_
            u["study_ids"], u["shelf_ids"] = T3.R.study_claim_ids(rows), T3.R.extrapolation_claim_ids(rows)
            u["review_ids"] = R.review_ids(rows, links)
        if any(ch.isdigit() for ch in json.dumps(u["context"])):
            raise TaskError("a prompt hint holds a digit")
    return units


def view_of4(unit):
    """What the prompt may show for a unit: slot names and digit-free labels, the hints, and which sentence kinds are expected. No values."""
    return dict(T.view_of(unit), expect=list(unit["expect"]))


def write_reference4(task, rows, folder):
    """The saved 3.2 stand-in files (made from the graph rows). Its study sentence says 'demonstrated' only when the rules allow it."""
    p5, p8 = T.write_reference(task, rows, folder)
    if R.study_blockers(rows, R.links_of(task)):
        f = p8 / "p83_public.md"
        f.write_text(f.read_text(encoding="utf-8").replace("Stability was demonstrated for", "Data are available for"), encoding="utf-8")
    return p5, p8


def write_all4(out_dir):
    """Write every task as <out>/<set>/<id>.json (+ <id>.graph.json for synthetic ones) and SHA256SUMS. The folder must be new."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder")
    sums = []
    for which, items in all_tasks4().items():
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
    for line in write_all4(ap.parse_args(argv).out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
