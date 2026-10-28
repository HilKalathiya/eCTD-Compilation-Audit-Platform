"""Planted-error test for wrong binding. No model is involved.

    python -m writer_test.mutation_test --tasks 1000 --per-type 300

1. Builds many synthetic stability tasks (the 8 real test tasks plus random ones).
2. Writes a CORRECT paragraph for each with a rule-based writer, in several
   sentence shapes, and requires the validator to accept all of them
   (measures false rejections).
3. Plants one wrong-binding error at a time into a correct paragraph and
   requires the validator to reject it (measures misses).
4. Tampers with the RENDERED text (a hand edit after rendering) and requires the
   independent re-read in rendercheck.py to reject it.

The errors were chosen by the author of the checker, who can only imagine the
errors he already guards against. So the report also lists what these checks
cannot see, and the real test is still the model's own mistakes (see README).
"""
import argparse
import json
import random
import re
from pathlib import Path

from .facts import compute_facts
from .rendercheck import verify_render
from .validator import render, validate

ROOT = Path(__file__).resolve().parent.parent
OTHER_TESTS = ["Assay", "Dissolution", "Water content", "Impurity A", "Impurity B", "Total impurities"]
GRIDS = {"long-term": ("25°C/60% RH", [0, 3, 6, 9, 12, 18, 24]),
         "intermediate": ("30°C/65% RH", [0, 3, 6, 9, 12]),
         "accelerated": ("40°C/75% RH", [0, 3, 6])}


# ---------------------------------------------------------------- random tasks
def make_task(rng, i):
    kind = rng.choice(["assay", "impurity", "impurity_a", "water", "dissolution"])
    cond_kind = rng.choice(list(GRIDS))
    condition, months = GRIDS[cond_kind]
    n = rng.randint(3, 5)
    ids = [f"B{j + 1}" for j in range(n)] if rng.random() < 0.5 else [f"L{2300 + j * 7 + i % 5}" for j in range(n)]
    direction = rng.choice(["up", "down", "flat"])
    if kind == "assay":
        attr, unit, dec, spec, base, step = "Assay", "% label claim", 1, {"type": "range", "lower": 95.0, "upper": 105.0}, 100.0, 0.05
        direction = rng.choice(["down", "flat"])
    elif kind == "impurity":
        attr, unit, dec, spec, base, step = "Total impurities", "%", 2, {"type": "nmt", "limit": 1.0, "decimals": 1}, 0.1, 0.012
        direction = rng.choice(["up", "up", "flat"])
    elif kind == "impurity_a":
        attr, unit, dec, spec, base, step = "Impurity A", "%", 2, {"type": "nmt", "limit": 0.2}, 0.04, 0.004
        direction = rng.choice(["up", "flat"])
    elif kind == "water":
        attr, unit, dec, spec, base, step = "Water content", "%", 1, {"type": "nmt", "limit": 3.0}, 2.0, 0.02
        direction = rng.choice(["flat", "up"])
    else:
        attr, unit, dec, spec, base, step = "Dissolution", "%", 0, {"type": "nlt", "limit": 80, "note": "Q"}, 92.0, 0.15
        direction = rng.choice(["flat", "down"])
    sign = {"up": 1, "down": -1, "flat": 0}[direction]
    mixed = rng.random() < 0.3 and sign != 0
    batches = {}
    for k, b in enumerate(ids):
        s = sign * (-1 if (mixed and k == 0) else 1)
        start = base + rng.uniform(-1, 1) * step * 6
        vals = [max(0.0, round(start + s * step * m + rng.uniform(-1, 1) * step * 1.5, dec)) for m in months]
        batches[b] = vals
    if rng.random() < 0.25:  # push one late result across the limit
        b = rng.choice(ids)
        if spec["type"] == "range":
            batches[b][-1] = round(spec["upper"] + 0.4, dec)
        elif spec["type"] == "nmt":
            batches[b][-1] = round(spec["limit"] + 10 ** -dec, dec)
        else:
            batches[b][-1] = round(spec["limit"] - 2, dec)
    return {"task_id": f"rnd{i}", "section": "3.2.P.8.3", "product": "Product X (synthetic)", "attribute": attr,
            "unit": unit, "spec": spec, "decimals": dec, "condition": condition, "months": months, "batches": batches}


# ------------------------------------------------------------ correct writer
def oracle(task, facts, flags, rng):
    """A correct paragraph in one of several sentence shapes. Returns (text, shape)."""
    attr, trend = task["attribute"], flags["trend"]
    verb = {"increasing": "increased", "decreasing": "decreased", "no meaningful change": "showed no meaningful change"}[trend]
    worst = flags["worst_fact"]
    other = "min_value" if worst == "max_value" else "max_value"
    word = lambda f: "highest" if f == "max_value" else "lowest"
    shapes = ["plain", "across"] + (["all"] if flags["batches_agree"] else [])
    shape = rng.choice(shapes)
    where = {"plain": "at [[condition]]", "across": "across [[n_batches]] batches at [[condition]]",
             "all": "in all [[n_batches]] batches at [[condition]]"}[shape]
    tail = ", ranging from [[initial_range]] to [[final_range]]" if (trend == "no meaningful change" and flags["ends_span_all"]) \
        else ", from [[initial_range]] to [[final_range]]"
    parts = [f"{attr} {verb} {where}{tail}."]
    parts.append(f"The {word(worst)} result was [[{worst}]].")
    if rng.random() < 0.4 and worst != other:
        parts.append(f"The {word(other)} result was [[{other}]].")
    if "oos_results" in facts:
        parts.append("The result of [[oos_results]] did not meet the acceptance criterion of [[spec]] and is out of specification.")
    else:
        parts.append(rng.choice(["All results remained within the acceptance criterion of [[spec]].",
                                 "All results were within the acceptance criterion of [[spec]]."]))
    text = " ".join(parts[:4])
    return text, shape


# --------------------------------------------------------------- mutations
def _swap(text, a, b):
    return text.replace(a, "\0").replace(b, a).replace("\0", b)


def m_role_flip(t, ctx):
    f = ctx["flags"]["worst_fact"]
    if {"max", "min"} <= ctx["facts"][f]["roles"]:
        return None
    return _swap(t, "highest", "lowest") if ("highest" in t or "lowest" in t) else None


def m_fact_swap(t, ctx):
    f = ctx["flags"]["worst_fact"]
    other = "min_value" if f == "max_value" else "max_value"
    role = "max" if f == "max_value" else "min"
    if role in ctx["facts"][other]["roles"]:
        return None
    return t.replace(f"[[{f}]]", f"[[{other}]]", 1)


def m_order_swap(t, ctx):
    if ctx["flags"]["trend"] == "no meaningful change":
        return None
    return t.replace("from [[initial_range]] to [[final_range]]", "from [[final_range]] to [[initial_range]]", 1)


def m_other_test(t, ctx):
    attr = ctx["task"]["attribute"]
    new = ctx["rng"].choice([x for x in OTHER_TESTS if x.lower() != attr.lower() and not attr.lower().startswith(x.lower())])
    return t.replace(attr, new, 1)


# --- second round: the kinds of wrong binding the hand audit of the model's own drafts found ---
def m_point_called_range(t, ctx):
    """'the initial range of [[min_value]]': one batch's result presented as the range of all batches."""
    return t.replace("[[initial_range]]", "the initial range of [[min_value]]", 1) if "[[initial_range]]" in t else None


def m_initial_results_points(t, ctx):
    """'initial results of [[max_value]]': a single result called the initial results of every batch."""
    return t.replace("[[initial_range]]", "the initial results of [[max_value]]", 1) if "[[initial_range]]" in t else None


def m_change_between_points(t, ctx):
    """'increased from [[min_value]] to [[max_value]]': two different batches presented as one change."""
    if ctx["flags"]["trend"] == "no meaningful change":
        return None
    return t.replace("from [[initial_range]] to [[final_range]]", "from [[min_value]] to [[max_value]]", 1)


def m_last_timepoint_mix(t, ctx):
    """Results from different months all placed 'at the last time point'."""
    if "[[final_range]]" not in t:
        return None
    if "final" in ctx["facts"]["min_value"]["roles"] and "final" in ctx["facts"]["max_value"]["roles"]:
        return None  # both really are at the last time point, so the sentence would be true
    return t.replace("from [[initial_range]] to [[final_range]]", "from [[min_value]] to [[max_value]] at the last time point", 1)


def m_repeat_time(t, ctx):
    """'[[final_range]] at the last time point': the range already says which month."""
    return t.replace("[[final_range]]", "[[final_range]] at the last time point", 1) if "[[final_range]]" in t else None


def m_span_claim(t, ctx):
    """'ranging from [[initial_range]] to [[final_range]]' when other results lie outside both."""
    if ctx["flags"]["ends_span_all"]:
        return None
    return t.replace(", from [[initial_range]] to [[final_range]]", ", ranging from [[initial_range]] to [[final_range]]", 1)


def m_article_point_change(t, ctx):
    """'decreased from the [[max_value]] to the [[min_value]]': the article must not hide a cross-batch change."""
    if ctx["flags"]["trend"] == "no meaningful change":
        return None
    return t.replace("from [[initial_range]] to [[final_range]]", "from the [[max_value]] to the [[min_value]]", 1)


def m_remaining_between(t, ctx):
    """'remaining between [[initial_range]] and [[final_range]]' when other results lie outside both."""
    if ctx["flags"]["ends_span_all"]:
        return None
    return t.replace(", from [[initial_range]] to [[final_range]]", ", remaining between [[initial_range]] and [[final_range]]", 1)


def m_truncated_test_name(t, ctx):
    """'Dissolution at [[condition]]': the test name loses its '30 minutes'."""
    attr = ctx["task"]["attribute"]
    if " at " not in attr:
        return None
    return t.replace(attr, attr.split(" at ")[0] + " at [[condition]]", 1)


def m_condition_oos(t, ctx):
    return t.replace(" and is out of specification.", ", resulting in the condition being out of specification.", 1) \
        if "is out of specification." in t else None


UNLISTED_TESTS = ["Related substances", "Residual solvents", "Degradation products", "Hardness", "Friability",
                  "Content uniformity", "Disintegration time", "Microbial limits", "Particle size", "Appearance"]


def m_unlisted_test(t, ctx):
    """A test name the registry has never heard of, used as the subject (the registry cannot catch it)."""
    attr = ctx["task"]["attribute"]
    return t.replace(attr, ctx["rng"].choice(UNLISTED_TESTS), 1)


def m_condition_word(t, ctx):
    own = ctx["flags"]["condition_type"]
    wrong = "long-term" if own == "accelerated" else "accelerated"
    return t.replace("at [[condition]]", f"under {wrong} conditions at [[condition]]", 1)


def m_trend_flip(t, ctx):
    for a, b in [("increased", "decreased"), ("decreased", "increased"),
                 ("showed no meaningful change", "showed an increasing trend")]:
        if a in t:
            return t.replace(a, b, 1)
    return None


def m_all_batches(t, ctx):
    if ctx["flags"]["batches_agree"] or "in all [[n_batches]]" in t:
        return None
    if "across [[n_batches]] batches" in t:
        return t.replace("across [[n_batches]] batches", "in all [[n_batches]] batches", 1)
    return t.replace("at [[condition]]", "in all [[n_batches]] batches at [[condition]]", 1)


def m_compliance_flip(t, ctx):
    if "oos_results" in ctx["facts"]:
        return re.sub(r"The result of \[\[oos_results\]\].*?out of specification\.",
                      "All results remained within the acceptance criterion of [[spec]].", t)
    return re.sub(r"All results (remained|were) within the acceptance criterion of \[\[spec\]\]\.",
                  "One result did not meet the acceptance criterion of [[spec]] and is out of specification.", t)


def m_omit_oos(t, ctx):
    if "oos_results" not in ctx["facts"]:
        return None
    return re.sub(r" The result of \[\[oos_results\]\].*?out of specification\.", "", t)


def m_batch_words(t, ctx):
    w = ctx["rng"].choice(["the second batch", "the last batch", "the other batches", "the first lot"])
    return t.replace(".", f", particularly in {w}.", 1)


def m_time_words(t, ctx):
    w = ctx["rng"].choice(["after one year", "over the first year", "after a year", "within six weeks"])
    return t.replace(".", f", {w}.", 1)


def m_inference(t, ctx):
    w = ctx["rng"].choice(["due to degradation", "supporting the proposed shelf life", "because of moisture uptake",
                           "which justifies the retest period"])
    return t.replace(".", f", {w}.", 1)


def m_typed_number(t, ctx):
    f = ctx["flags"]["worst_fact"]
    return t.replace(f"[[{f}]]", ctx["facts"][f]["value"].split(" ")[0], 1)


def m_typed_batch(t, ctx):
    b = ctx["rng"].choice(ctx["flags"]["batch_ids"])
    return t.replace("The ", f"In Batch {b}, the ", 1)


def m_unknown_fact(t, ctx):
    f = ctx["flags"]["worst_fact"]
    return t.replace(f"[[{f}]]", f"[[{f}_where]]", 1)


MUTATIONS = [
    ("Role word flipped (highest <-> lowest)", m_role_flip),
    ("Wrong fact under a role word ([[min_value]] called highest)", m_fact_swap),
    ("Start and end swapped in 'increased from A to B'", m_order_swap),
    ("Another test's name used (Assay in an impurity section)", m_other_test),
    ("Test name that is not in the registry, as the subject", m_unlisted_test),
    ("One batch's result called 'the initial range'", m_point_called_range),
    ("One batch's result called 'the initial results'", m_initial_results_points),
    ("'Increased from [[min]] to [[max]]' (two different batches as one change)", m_change_between_points),
    ("Results from different months placed 'at the last time point'", m_last_timepoint_mix),
    ("Time point repeated after a range that already carries it", m_repeat_time),
    ("'Ranging from first to last range' when other results lie outside", m_span_claim),
    ("Condition (not a result) called out of specification", m_condition_oos),
    ("'From the [[max]] to the [[min]]' (article hides two batches)", m_article_point_change),
    ("'Remaining between first and last range' when other results lie outside", m_remaining_between),
    ("Test name cut short ('Dissolution at [[condition]]')", m_truncated_test_name),
    ("Wrong storage-condition word (accelerated vs long-term)", m_condition_word),
    ("Trend word flipped (increased <-> decreased)", m_trend_flip),
    ("'In all batches' when one batch behaves differently", m_all_batches),
    ("Compliance flipped (pass <-> out of specification)", m_compliance_flip),
    ("Out-of-specification result left out", m_omit_oos),
    ("Batch named in words ('the second batch')", m_batch_words),
    ("Time period in words ('after one year')", m_time_words),
    ("Cause or shelf-life claim added", m_inference),
    ("Number typed instead of a placeholder", m_typed_number),
    ("Batch ID typed by the model", m_typed_batch),
    ("Placeholder that is not a fact", m_unknown_fact),
]


# ------------------------------------------------------- tampering on rendered text
def t_digit(r, task, rng):
    ms = list(re.finditer(r"(\d+\.?\d*)%? \(Batch \S+, Month \d+\)", r))
    if not ms:
        return None
    m = rng.choice(ms)
    v = m.group(1)
    i = rng.randrange(len(v))
    if not v[i].isdigit():
        return None
    nv = v[:i] + str((int(v[i]) + rng.randint(1, 8)) % 10) + v[i + 1:]
    return r[:m.start(1)] + nv + r[m.end(1):]


def t_batch(r, task, rng):
    ms = list(re.finditer(r"\(Batch (\S+), Month (\d+)\)", r))
    if not ms or len(task["batches"]) < 2:
        return None
    m = rng.choice(ms)
    b, mo = m.group(1), int(m.group(2))
    idx = task["months"].index(mo)
    cur = task["batches"][b][idx]
    others = [x for x in task["batches"] if x != b and task["batches"][x][idx] != cur]
    if not others:
        return None
    return r[:m.start(1)] + rng.choice(others) + r[m.end(1):]


def t_month(r, task, rng):
    ms = list(re.finditer(r"\(Batch (\S+), Month (\d+)\)", r))
    if not ms:
        return None
    m = rng.choice(ms)
    b, mo = m.group(1), int(m.group(2))
    cur = task["batches"][b][task["months"].index(mo)]
    others = [x for x in task["months"] if x != mo and task["batches"][b][task["months"].index(x)] != cur]
    if not others:
        return None
    return r[:m.start(2)] + str(rng.choice(others)) + r[m.end(2):]


def t_range_month(r, task, rng):
    ms = list(re.finditer(r"(\d+\.?\d*)(?:–(\d+\.?\d*))?%? at Month (\d+)", r))
    if not ms:
        return None
    m = rng.choice(ms)
    mo = int(m.group(3))
    col = lambda x: [v[task["months"].index(x)] for v in task["batches"].values()]
    others = [x for x in task["months"] if x != mo and (min(col(x)), max(col(x))) != (min(col(mo)), max(col(mo)))]
    if not others:
        return None
    return r[:m.start(3)] + str(rng.choice(others)) + r[m.end(3):]


TAMPERS = [("Digit changed in a value", t_digit), ("Batch label changed", t_batch),
           ("Month changed on a result", t_month), ("Month changed on a range", t_range_month)]

# Correct paragraphs a person or model might write in other words. All must pass.
LEGIT = [
    ("lt_total_impurities", "Total impurities showed an increasing trend across [[n_batches]] batches at [[condition]]. Results ranged from [[min_value]] to [[max_value]]. All results remained within the acceptance criterion of [[spec]]."),
    ("lt_total_impurities", "Total impurities increased at [[condition]], from [[initial_range]] to [[final_range]]. The highest result was [[max_value]], and all results met the acceptance criterion of [[spec]]."),
    ("lt_assay", "Assay decreased gradually at [[condition]], from [[initial_range]] to [[final_range]]. The lowest result was [[min_value]]. All results remained within the acceptance criterion of [[spec]]."),
    ("lt_assay", "Assay showed a decreasing trend across [[n_batches]] batches. The lowest result was [[min_value]] and the highest result was [[max_value]]. All results were within the acceptance criterion of [[spec]]."),
    ("lt_water", "Water content showed no meaningful change at [[condition]], with results ranging from [[min_value]] to [[max_value]]. All results remained within the acceptance criterion of [[spec]]."),
    ("lt_dissolution", "Dissolution showed no meaningful change across [[n_batches]] batches at [[condition]]. The lowest result was [[min_value]]. All results remained within the acceptance criterion of [[spec]]."),
    ("acc_impurity_b_oos", "Impurity B increased at [[condition]], from [[initial_range]] to [[final_range]]. The highest result was [[max_value]]. The result of [[oos_results]] exceeded the acceptance criterion of [[spec]] and is out of specification."),
    ("acc_impurity_b_oos", "Impurity B showed an increasing trend at [[condition]]. The result of [[oos_results]] did not meet the acceptance criterion of [[spec]]; it is the highest result, [[max_value]]."),
    ("acc_assay", "Assay decreased at [[condition]] with a mean change of [[mean_change]]. The lowest result was [[min_value]]. All results remained within the acceptance criterion of [[spec]]."),
    ("lt_impurity_a", "Impurity A increased at [[condition]]. The highest result was [[max_value]], observed in the final results, and all results remained within the acceptance criterion of [[spec]]."),
]


# Wrong paragraphs written by hand AFTER the checks existed, aiming at gaps. Each is
# (task, text, what is wrong). The report lists every one that still gets through.
HAND_WRONG = [
    ("lt_total_impurities", "Total impurities increased at [[condition]]. The peak result was [[min_value]]. All results remained within the acceptance criterion of [[spec]].", "min called peak"),
    ("lt_total_impurities", "Total impurities increased at [[condition]]. Values were highest at the start. The highest result was [[max_value]]. All results were within the acceptance criterion of [[spec]].", "highest at the start (it was at the end)"),
    ("lt_total_impurities", "Total impurities increased at [[condition]]. The result of [[max_value]] was the lowest. All results were within the acceptance criterion of [[spec]].", "role word after the placeholder"),
    ("lt_total_impurities", "Total impurities increased at [[condition]], and the highest result [[max_value]] was lower than [[initial_range]]. All results were within the acceptance criterion of [[spec]].", "false comparison between two results"),
    ("lt_total_impurities", "Total impurities increased early and then levelled off at [[condition]]. The highest result was [[max_value]]. All results were within the acceptance criterion of [[spec]].", "claim about timing in words"),
    ("lt_total_impurities", "Total impurities increased at [[condition]] while Impurity A was stable. The highest result was [[max_value]]. All results were within the acceptance criterion of [[spec]].", "claim about another test"),
    ("lt_total_impurities", "Related substances increased at [[condition]]. The highest result was [[max_value]]. All results were within the acceptance criterion of [[spec]].", "test name not in the registry"),
    ("lt_assay", "Assay decreased at [[condition]]. The result of [[min_value]] was the highest. All results were within the acceptance criterion of [[spec]].", "min called highest"),
    ("lt_assay", "Assay decreased at [[condition]], and the largest value was [[min_value]]. All results were within the acceptance criterion of [[spec]].", "min called largest"),
    ("lt_assay", "Assay decreased at [[condition]]. The lowest result was [[min_value]] percent. All results were within the acceptance criterion of [[spec]].", "unit written after the value"),
    ("lt_water", "Water content showed no meaningful change at [[condition]]. The highest result was [[max_value]], observed under accelerated conditions. All results were within the acceptance criterion of [[spec]].", "wrong condition"),
    ("acc_impurity_b_oos", "Impurity B increased at [[condition]]. The highest result was [[max_value]]. All results remained within the acceptance criterion of [[spec]], except Batch B1.", "hides the failing result"),
    ("acc_impurity_b_oos", "Impurity B increased at [[condition]]. The highest result was [[max_value]]. The result of [[oos_results]] did not meet the acceptance criterion of [[spec]], as did the other batches.", "claims more failures than exist"),
    ("lt_dissolution", "Dissolution showed no meaningful change at [[condition]]. The lowest result was [[min_value]]. All results exceeded the acceptance criterion of [[spec]].", "'exceeded' used for a pass"),
    ("lt_dissolution", "Dissolution showed no meaningful change at [[condition]]. The lowest result was [[min_value]], which is the same as the last result. All results were within [[spec]].", "claims min equals the last result"),
    # Real drafts by Gemma 4 that passed the earlier checks and were wrong or misleading (hand audit):
    ('lt_dissolution', 'Dissolution at 30 minutes showed no meaningful change across the [[n_batches]] batches stored at [[condition]] over a duration of [[duration]]. The results ranged from [[initial_range]] to [[final_range]], with the lowest result being [[min_value]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'results ranged from 92% to 92-93%' but the lowest result stated is 90"),
    ('lt_dissolution', 'Dissolution at 30 minutes showed no meaningful change over [[duration]] at [[condition]], with results ranging from [[initial_range]] to [[final_range]] across [[n_batches]] batches. The lowest result observed was [[min_value]]. All results complied with the acceptance criterion of [[spec]].', "model draft, audit: 'results ranging from 92% to 92-93%' but the lowest result stated is 9"),
    ('acc_total_impurities', 'Total impurities increased at [[condition]], showing a mean change of [[mean_change]]. Results progressed from [[min_value]] to [[max_value]] across [[n_batches]] batches over [[duration]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'progressed from 0.10% (Batch B1) to 0.54% (Batch B2)'"),
    ('acc_total_impurities', 'Total impurities increased over the storage duration of [[condition]], moving from [[min_value]] to [[max_value]]. The mean change from initial to last time point was a mean change of [[mean_change]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'moving from 0.10% (Batch B1) to 0.54% (Batch B2)'"),
    ('acc_total_impurities', 'Total impurities increased across the [[n_batches]] batches under [[condition]], showing a mean change of [[mean_change]] from the initial range of [[min_value]] to the final range of [[final_range]]. The highest result observed was [[max_value]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'initial range of 0.10% (Batch B1)'"),
    ('acc_total_impurities', 'Total impurities increased across [[n_batches]] batches under [[condition]], showing a mean change of [[mean_change]] from the initial range of [[min_value]] to the final range of [[final_range]]. The highest result observed was [[max_value]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'initial range of 0.10% (Batch B1)'"),
    ('acc_total_impurities', 'Total impurities showed an increasing trend across the [[n_batches]] batches during the [[duration]] under [[condition]]. The mean change of [[mean_change]] was observed from the initial range of [[min_value]] to the final range of [[final_range]]. The highest result was [[max_value]], and all results were within the acceptance criterion of [[spec]].', "model draft, audit: 'initial range of 0.10% (Batch B1)'"),
    ('acc_total_impurities', 'Total impurities increased at [[condition]] over a duration of [[duration]], demonstrating a mean change of [[mean_change]]. The impurities ranged from [[min_value]] to [[max_value]] at the last time point. All results were within the acceptance criterion of [[spec]].', "model draft, audit: 'ranged from 0.10% (Month 0) to 0.54% (Month 6) at the last time point"),
    ('acc_total_impurities', 'Total impurities showed an increasing trend across the [[n_batches]] batches stored under [[condition]]. The values ranged from [[min_value]] to [[max_value]] at the last time point tested of [[duration]]. All results remained within the acceptance criterion of [[spec]].', "model draft, audit: 'ranged from 0.10% (Month 0) to 0.54% (Month 6) at the last time point"),
    ('acc_assay', 'Assay decreased over the longest time point tested of [[duration]] at [[condition]], exhibiting a mean change of [[mean_change]]. Initial results ranged from [[max_value]] and [[min_value]], while the final results ranged from [[min_value]] to [[final_range]]. All results remained within the acceptance criterion of [[spec]].', 'model draft, audit: says INITIAL results ranged from 100.5% (Month 0) and 97.6% (Month 6);'),
    ('acc_impurity_b_oos', 'Impurity B exhibited an increasing trend across [[n_batches]] batches under [[condition]], showing a mean change of [[mean_change]]. The final range was [[final_range]], with the highest result being [[max_value]]. The result of [[oos_results]] did not meet the acceptance criterion of [[spec]], resulting in the condition being out of specification.', "model draft, audit: 'the condition being out of specification'"),
]


def upper95(n):
    """Exact one-sided 95% upper bound on the miss rate after 0 misses in n trials."""
    return 1 - 0.05 ** (1 / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=1000)
    ap.add_argument("--per-type", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "outputs" / "mutation_report.md"))
    args = ap.parse_args()
    rng = random.Random(args.seed)

    base = json.load(open(ROOT / "data" / "tasks.json", encoding="utf-8"))["tasks"]
    tasks = base + [make_task(rng, i) for i in range(args.tasks)]
    ctxs = []
    for task in tasks:
        facts, flags, required = compute_facts(task)
        text, shape = oracle(task, facts, flags, rng)
        ctxs.append({"task": task, "facts": facts, "flags": flags, "required": required, "text": text,
                     "shape": shape, "rng": rng})

    # 1. false rejections on correct text
    bad_oracle = [(c["task"]["task_id"], c["text"], validate(c["text"], c["facts"], c["flags"], c["required"]))
                  for c in ctxs]
    bad_oracle = [b for b in bad_oracle if b[2]]
    bad_render = [c for c in ctxs if verify_render(render(c["text"], c["facts"]), c["task"])]
    by_id = {t["task_id"]: t for t in base}
    legit_bad = []
    for tid, text in LEGIT:
        facts, flags, required = compute_facts(by_id[tid])
        p = validate(text, facts, flags, required)
        if p:
            legit_bad.append((tid, text, p))

    # 2. planted errors
    rows, misses = [], []
    for name, fn in MUTATIONS:
        tried = caught = 0
        for c in ctxs:
            if tried >= args.per_type:
                break
            mutated = fn(c["text"], c)
            if mutated is None or mutated == c["text"]:
                continue
            tried += 1
            if validate(mutated, c["facts"], c["flags"], c["required"]):
                caught += 1
            else:
                misses.append((name, c["task"]["task_id"], mutated))
        rows.append((name, tried, caught))

    # 2b. hand-written wrong paragraphs the checks were not designed around
    hand_missed = []
    for tid, text, why in HAND_WRONG:
        facts, flags, required = compute_facts(by_id[tid])
        if not validate(text, facts, flags, required):
            hand_missed.append((tid, why, text))

    # 3. tampering after rendering
    trows, tmiss = [], []
    for name, fn in TAMPERS:
        tried = caught = 0
        for c in ctxs:
            if tried >= args.per_type:
                break
            r = render(c["text"], c["facts"])
            mutated = fn(r, c["task"], rng)
            if mutated is None or mutated == r:
                continue
            tried += 1
            if verify_render(mutated, c["task"]):
                caught += 1
            else:
                tmiss.append((name, c["task"]["task_id"], mutated))
        trows.append((name, tried, caught))

    L = ["# Planted-error test: wrong binding", "",
         f"{len(tasks)} synthetic tasks ({len(base)} fixed + {args.tasks} random), seed {args.seed}. No model involved.", "",
         "## Correct text must pass (false rejections)", "",
         f"- Correct paragraphs accepted by the validator: {len(ctxs) - len(bad_oracle)} of {len(ctxs)}",
         f"- Their rendered text accepted by the independent re-read: {len(ctxs) - len(bad_render)} of {len(ctxs)}",
         f"- Hand-written correct paraphrases accepted: {len(LEGIT) - len(legit_bad)} of {len(LEGIT)}", "",
         "## Planted errors in the draft (validator)", "",
         "| Error planted | Planted | Caught | Missed | 95% upper bound on miss rate |", "| --- | --- | --- | --- | --- |"]
    for name, tried, caught in rows:
        miss = tried - caught
        bound = f"{upper95(tried) * 100:.1f}%" if miss == 0 and tried else ("n/a" if not tried else f"{miss / tried * 100:.1f}% observed")
        L.append(f"| {name} | {tried} | {caught} | {miss} | {bound} |")
    L += ["", "## Hand edits after rendering (independent re-read of the finished text)", "",
          "| Error planted | Planted | Caught | Missed | 95% upper bound on miss rate |", "| --- | --- | --- | --- | --- |"]
    for name, tried, caught in trows:
        miss = tried - caught
        bound = f"{upper95(tried) * 100:.1f}%" if miss == 0 and tried else ("n/a" if not tried else f"{miss / tried * 100:.1f}% observed")
        L.append(f"| {name} | {tried} | {caught} | {miss} | {bound} |")
    L += ["", "## Wrong paragraphs written by hand, and real model drafts found wrong by the audit", "",
          f"Caught: {len(HAND_WRONG) - len(hand_missed)} of {len(HAND_WRONG)}. The first round of these exposed three gaps "
          "(a role word with no result next to it, timing words, comparisons between results); those were fixed, "
          "so this list shows that the gaps stay closed, not that unseen errors are caught. The last 11 are real "
          "Gemma 4 drafts that passed the earlier checks and were found wrong or misleading by reading them."]
    if hand_missed:
        L += ["", "Still accepted (known gaps):", ""] + [f"- {t}: {why}: {x}" for t, why, x in hand_missed]
    total = sum(r[1] for r in rows) + sum(r[1] for r in trows)
    got = sum(r[2] for r in rows) + sum(r[2] for r in trows)
    L += ["", f"**Total: {got} of {total} planted errors caught.**", ""]
    for title, items in [("Missed in drafts", misses), ("Missed after rendering", tmiss)]:
        if items:
            L += [f"### {title} (first 8)", ""] + [f"- {n} / {t}: {x}" for n, t, x in items[:8]] + [""]
    if bad_oracle:
        L += ["### Correct paragraphs wrongly rejected (first 8)", ""] + [f"- {t}: {p} :: {x}" for t, x, p in bad_oracle[:8]] + [""]
    if legit_bad:
        L += ["### Correct paraphrases wrongly rejected", ""] + [f"- {t}: {p} :: {x}" for t, x, p in legit_bad] + [""]
    L += ["## What these checks cannot see", "",
          "- A true but unhelpful choice: mentioning the lowest result when the highest matters more. Only the required-facts rule and a reviewer cover that.",
          "- Wording that is false in a way no list anticipates. A test name outside the registry is caught only when it starts a sentence; in the middle of a sentence it gets through. Magnitude words (\"slightly\", \"gradually\") are not checked.",
          "- Errors in the data itself (a wrong value in the fact store).",
          "- These errors were planted by the author of the checks. The unbiased test is the model's own mistakes: run the model, hand-label every failure it makes, and see whether each was caught."]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
