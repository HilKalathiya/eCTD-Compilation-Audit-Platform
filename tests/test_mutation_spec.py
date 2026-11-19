"""Planted-error test for the P.5.6 spec-justification validator: every planted error must be caught by the rule meant for it, no correct text may be rejected.

    python -m unittest tests.test_mutation_spec

No model involved. Tasks: the 5 real Lek attributes, the planted variants in data/tasks/p56_tasks.json, and seeded random tasks
(both bases, other assumed doses, n_outside 0 and above 0). Values are Decimal text built from integers only.
"""
import argparse
import json
import random
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.specs import load, p56
from ectd_engine.validator import spec as sv
from ectd_engine.validator.spec import render, validate, verify_render
from ectd_engine.writer.batch_facts import LoaderStore
from ectd_engine.writer.spec_facts import compute_spec_facts, digit_count, q3b_row_quote, quote_text, resolve_quote

ROOT = Path(__file__).resolve().parent.parent
FILE = json.loads((ROOT / "data" / "tasks" / "p56_tasks.json").read_text(encoding="utf-8"))
SEED = 11
_LIVE = {}


def live_data():
    """{mdd text: {column: Justification}} from the real loader, spec and Q3B PDF check (built once)."""
    if not _LIVE:
        store = LoaderStore()
        for m in ("40", "5", "500"):
            spec = load.load(mdd=Decimal(m))
            _LIVE[m] = {r.attribute: j for r, j in zip(spec.rows, p56.compute(spec, store))}
    return _LIVE


def fixed_tasks():
    live = live_data()
    return ([resolve_quote(t, live) for t in FILE["tasks"]] +
            [resolve_quote(t, live, planted=True) for t in FILE["synthetic"]])


def random_task(rng, i):
    live = live_data()
    q3b = rng.random() < 0.5
    col = rng.choice(["impurity_o", "impurity_l"] if q3b else ["dissolution_av", "impurities_total", "resodual_solvent"])
    mdd = rng.choice(["40", "5", "500"])
    n = rng.randint(2, 1100)
    lo, hi = sorted(rng.sample(range(0, 20000), 2))
    j = live[mdd][col]
    kind, limit = (j.limit_kind, str(j.limit)) if q3b else (rng.choice(["NMT", "NLT"]), rng.choice(["0.5", "1.0", "80", "2.5"]))
    task = {"task_id": f"r{i}", "section": "3.2.P.5.6", "product": "Lek tablets", "attribute": j.test, "column": col,
            "limit_kind": kind, "limit": limit, "unit": "%", "basis": "q3b_qualification" if q3b else "declared",
            "n": n, "min": f"{lo // 100}.{lo % 100:02d}", "max": f"{hi // 100}.{hi % 100:02d}",
            "n_outside": 0 if rng.random() < 0.5 else rng.randint(1, min(n, 20))}
    if q3b:
        task.update({"mdd": mdd, "q3b_quote": q3b_row_quote(mdd), "q3b_page": str(j.page), "q3b_version": j.doc_version})
    return task


def flip(task):
    """The same task under the other basis (used to run a text against the wrong facts)."""
    t = {k: v for k, v in task.items() if k not in ("mdd", "q3b_quote", "q3b_page", "q3b_version")}
    if task["basis"] == "q3b_qualification":
        t["basis"] = "declared"
    else:
        j = live_data()["40"]["impurity_o"]
        t.update({"basis": "q3b_qualification", "mdd": "40", "q3b_quote": q3b_row_quote("40"), "q3b_page": str(j.page),
                  "q3b_version": j.doc_version})
    return t


# ------------------------------------------------------------ correct writer
def oracle(flags, rng):
    """A correct paragraph in one of several shapes."""
    attr, kl = flags["attribute"], "[[limit_kind]] [[limit]]"
    q3b = flags["basis"] == "q3b_qualification"
    shape = rng.choice("ABC")
    if q3b:
        head = {"A": [f"The acceptance criterion for {attr} is {kl}, set at [[basis]] for an assumed maximum daily dose of [[mdd]]: [[q3b_quote]]."],
                "B": [f"For {attr}, the limit is {kl}.", "It rests on [[basis]], taking an assumed maximum daily dose of [[mdd]].",
                      "The quoted text is [[q3b_quote]]."],
                "C": [f"The limit for {attr} is {kl}, which is [[basis]].",
                      "Assuming a maximum daily dose of [[mdd]], the text is [[q3b_quote]]."]}[shape]
    else:
        head = {"A": [f"The acceptance criterion for {attr} is {kl}, which is [[basis]]."],
                "B": [f"For {attr}, the limit is {kl}.", "This limit is [[basis]]."],
                "C": [f"The limit for {attr} is {kl}.", "It is [[basis]]."]}[shape]
    res = ["Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]."]
    if rng.random() < 0.4:
        res.append("The highest result was [[max_value]] and the lowest result was [[min_value]].")
    if flags["n_outside"]:
        out = rng.choice(["[[n_outside]] had results outside the limit.", "Results for [[n_outside]] were outside the limit.",
                          "The limit was exceeded by results for [[n_outside]]."])
    else:
        out = rng.choice(["No result was outside the limit.", "No result exceeded the limit."])
    parts = head + res + [out]
    return " ".join(parts)


# --------------------------------------------------------------- mutations
COMPLIANCE_SENTENCES = ["All results complied with the limit.", "The results meet the acceptance criterion.",
                        "The other results were within the limit.", "The results are acceptable."]
SOURCED_SENTENCES = ["The limit is in accordance with ICH Q3B guidance.", "The limit is as required by the pharmacopoeia.",
                     "The limit is in line with ICH Q3B.", "The limit is consistent with published toxicological data.",
                     "The limit is taken from the literature and recommended per regulatory standards."]
SAFETY_SENTENCES = ["The limit is safe.", "The impurity is qualified by toxicology data.", "There is no safety concern.",
                    "The product is well tolerated by patients."]
FAILURE_SENTENCES = ["Some results were outside the limit.", "The limit was exceeded.", "A result failed the test."]
STAT_SENTENCES = ["The results showed low variability.", "The results were consistent.", "A decreasing trend was observed.",
                  "The quality of the batches is good."]
COUNT_SENTENCES = ["Several batches were tested.", "The data cover a single batch.", "Both batches were tested.", "Most batches were tested."]
CAUSES = ["The limit was set because of degradation.", "This supports the shelf life.", "The result is likely due to moisture uptake."]


def _is_q3b(c):
    return c["flags"]["basis"] == "q3b_qualification"


def _add(t, sentence):
    return t + " " + sentence


def m_declared_as_sourced(t, c):
    return None if _is_q3b(c) else _add(t, c["rng"].choice(SOURCED_SENTENCES))


def m_basis_swap(t, c):
    if _is_q3b(c):
        return t.replace("[[basis]]", "declared by the author for this demonstration, with no public source", 1)
    return t.replace("[[basis]]", "the ICH Q3B(R2) qualification threshold", 1)


def m_basis_swap_cross(t, c):
    return t  # same text, validated against the other basis' facts (see MUTATIONS)


def m_hide_assumption(t, c):
    return re.sub(r"\b(assumed|Assuming)\s+", "", t, count=1) if _is_q3b(c) else None


def m_assumption_moved_away(t, c):
    if not _is_q3b(c):
        return None
    return _add(re.sub(r"\b(assumed|Assuming)\s+", "", t, count=1), "The dose is only an assumption.")


def m_drop_mdd(t, c):
    return t.replace("[[mdd]]", "the dose", 1) if _is_q3b(c) else None


def m_typed_quote(t, c):
    if not _is_q3b(c):
        return None
    words = [w for w in sv._words(c["flags"]["quote"]) if w != "|"]
    i = c["rng"].randrange(0, len(words) - 5)
    return _add(t, "The table reads " + " ".join(words[i:i + 5]) + ".")


def m_quote_phrase(t, c):
    return _add(t, "The text says whichever is lower.")


def m_compliance_with_outside(t, c):
    return _add(t, c["rng"].choice(COMPLIANCE_SENTENCES)) if c["flags"]["n_outside"] else None


def m_deny_failure(t, c):
    return _add(t, "No result exceeded the limit.") if c["flags"]["n_outside"] else None


def m_failure_without_count(t, c):
    return _add(t, "Some results were outside the limit.") if c["flags"]["n_outside"] else None


def m_invented_failure(t, c):
    return None if c["flags"]["n_outside"] else _add(t, c["rng"].choice(FAILURE_SENTENCES))


def m_omit_outside_statement(t, c):
    """T-048: the last sentence (the outside-count sentence) is dropped, or, with batches outside, replaced by one that
    names [[n_outside]] but never says the results were outside the limit."""
    cut = t[:t.rfind(". ", 0, len(t) - 1) + 1]
    if c["flags"]["n_outside"] and c["rng"].random() < 0.5:
        return cut + " The count was [[n_outside]]."
    return cut


def m_safety(t, c):
    return _add(t, c["rng"].choice(SAFETY_SENTENCES))


def m_limit_kind_flip(t, c):
    other = {"NMT": ["not less than", "NLT", "at least"], "NLT": ["not more than", "NMT", "at most"]}[c["flags"]["limit_kind"]]
    return t.replace("[[limit_kind]]", c["rng"].choice(other), 1)


def m_kind_paired_wrong(t, c):
    return t.replace("[[limit_kind]] [[limit]]", "[[limit_kind]] [[max_value]]", 1)


def m_typed_number(t, c):
    return t.replace("[[max_value]]", c["facts"]["max_value"]["value"], 1)


def m_unknown_fact(t, c):
    return t.replace("[[max_value]]", "[[max_value_where]]", 1)


def m_wrong_attribute(t, c):
    attr = c["flags"]["attribute"]
    others = [n for n in c["flags"]["registry"] if n.lower() not in attr.lower() and attr.lower() not in n.lower()]
    return t.replace(attr, c["rng"].choice(others), 1) if attr in t else None


def m_stat_claim(t, c):
    return _add(t, c["rng"].choice(STAT_SENTENCES))


def m_count_words(t, c):
    return _add(t, c["rng"].choice(COUNT_SENTENCES))


def m_batch_in_words(t, c):
    return t.replace(".", ", particularly in " + c["rng"].choice(["the last batch", "the other batches", "the first lot"]) + ".", 1)


def m_all_batches(t, c):
    return _add(t, "The results apply to all batches.")


def m_unit_after(t, c):
    return t.replace("[[max_value]]", "[[max_value]] percent", 1)


def m_noun_repeat(t, c):
    return t.replace("[[n_batches]]", "[[n_batches]] batches", 1)


def m_cause(t, c):
    return _add(t, c["rng"].choice(CAUSES))


def m_role_flip(t, c):
    if "highest result was" not in t:
        return None
    return re.sub(r"\b(highest|lowest)\b", lambda m: "lowest" if m.group(1) == "highest" else "highest", t)


def m_min_max_swap(t, c):
    return t.replace("[[min_value]]", "\0").replace("[[max_value]]", "[[min_value]]").replace("\0", "[[max_value]]")


def m_mdd_unit(t, c):
    return t.replace("[[mdd]]", "[[mdd]] mg", 1) if _is_q3b(c) else None


# (name, rules meant to catch it, function, validate against the other basis' facts?)
MUTATIONS = [
    ("declared_as_sourced", ("sourced one",), m_declared_as_sourced, False),
    ("basis_swap (typed wording)", ("sourced one", "declared or unsourced"), m_basis_swap, False),
    ("basis_swap_cross (text vs other basis' facts)", ("unknown placeholders", "missing required"), m_basis_swap_cross, True),
    ("hide_assumption", ("assumption",), m_hide_assumption, False),
    ("assumption_moved_to_other_sentence", ("assumption",), m_assumption_moved_away, False),
    ("drop_mdd", ("missing required",), m_drop_mdd, False),
    ("typed_quote (5 words from the quote)", ("typed quote",), m_typed_quote, False),
    ("typed_quote_phrase", ("typed quote",), m_quote_phrase, False),
    ("compliance_with_outside", ("compliance wording",), m_compliance_with_outside, False),
    ("deny_failure_with_outside", ("denies a failure",), m_deny_failure, False),
    ("failure_without_n_outside", ("failure wording without",), m_failure_without_count, False),
    ("invented_failure (none outside)", ("invented failure",), m_invented_failure, False),
    ("omit_outside_statement", ("outside-count sentence",), m_omit_outside_statement, False),
    ("safety_claim", ("safety or qualification",), m_safety, False),
    ("limit_kind_flip (NMT/NLT typed)", ("limit direction",), m_limit_kind_flip, False),
    ("limit_kind_paired_with_result", ("limit direction",), m_kind_paired_wrong, False),
    ("typed_number", ("number written outside",), m_typed_number, False),
    ("unknown_fact", ("unknown placeholders",), m_unknown_fact, False),
    ("wrong_attribute", ("names another test", "does not name the attribute"), m_wrong_attribute, False),
    ("stat_claim", ("statistic",), m_stat_claim, False),
    ("batch_count_in_words", ("batch count",), m_count_words, False),
    ("batch_in_words", ("names a batch in words",), m_batch_in_words, False),
    ("all_batches_claim", ("claims all batches",), m_all_batches, False),
    ("unit_after_placeholder", ("unit repeated",), m_unit_after, False),
    ("noun_repeated_after_count", ("noun repeated",), m_noun_repeat, False),
    ("cause_added", ("cause",), m_cause, False),
    ("role_flip (highest <-> lowest)", ("is next to",), m_role_flip, False),
    ("min_max_swap", ("backwards", "is next to"), m_min_max_swap, False),
    ("mdd_unit_repeated", ("unit repeated",), m_mdd_unit, False),
]


# ------------------------------------------------------- tampering on rendered text
def _change_digit(num, rng):
    idx = [i for i, ch in enumerate(num) if ch.isdigit()]
    i = rng.choice(idx)
    return num[:i] + str((int(num[i]) + rng.randint(1, 8)) % 10) + num[i + 1:]


def _outside_quote(r, c):
    """(text with the quote replaced by a marker, function that puts it back)."""
    if c["task"]["basis"] != "q3b_qualification":
        return r, lambda s: s
    q = quote_text(c["task"])
    return r.replace(q, "\0"), lambda s: s.replace("\0", q)


def _nums(c):
    t = c["task"]
    return {t["limit"], t["min"], t["max"], str(t["n"]), str(t["n_outside"]), t.get("mdd", "-")}


def t_digit(r, c, rng):
    body, back = _outside_quote(r, c)
    ms = [m for m in re.finditer(r"\d+(?:\.\d+)?", body)]
    if not ms:
        return None
    m = rng.choice(ms)
    new = _change_digit(m.group(0), rng)
    return None if new in _nums(c) else back(body[:m.start()] + new + body[m.end():])


def t_direction(r, c, rng):
    body, back = _outside_quote(r, c)
    a, b = ("not more than", "not less than") if "not more than" in body else ("not less than", "not more than")
    return back(body.replace(a, b, 1))


def t_mdd(r, c, rng):
    if c["task"]["basis"] != "q3b_qualification":
        return None
    body, back = _outside_quote(r, c)
    v = f"{c['task']['mdd']} mg"
    new = _change_digit(v[:-3], rng)
    return None if new in _nums(c) else back(body.replace(v, new + " mg", 1))


def t_quote(r, c, rng):
    if c["task"]["basis"] != "q3b_qualification":
        return None
    q = quote_text(c["task"])
    i = rng.randrange(5, 40)
    return r.replace(q, q[:i] + "x" + q[i:], 1)


def t_count(r, c, rng):
    t = c["task"]
    v = digit_count(t["n"])
    other = rng.choice([k for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 99, 500) if k not in (t["n"], t["n_outside"])])
    return r.replace(v, digit_count(other), 1)


TAMPERS = [("digit changed in a rendered value", t_digit), ("limit direction flipped", t_direction),
           ("assumed dose changed", t_mdd), ("Q3B quote altered", t_quote), ("batch count changed", t_count)]

# Correct paragraphs in other words (index into fixed_tasks(): 0-4 real tasks, 5-9 planted variants). All must pass.
LEGIT = [
    (0, "For Dissolution, the limit is [[limit_kind]] [[limit]]. This limit is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit."),
    (0, "Dissolution has an acceptance criterion of [[limit_kind]] [[limit]], which is [[basis]]. The lowest result across [[n_batches]] was [[min_value]] and the highest result was [[max_value]]. No result was outside the limit."),
    (1, "The acceptance criterion for Impurity O is [[limit_kind]] [[limit]]. It follows [[basis]] and assumes a maximum daily dose of [[mdd]]; the text reads [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit."),
    (2, "For Impurity L the limit is [[limit_kind]] [[limit]], taken at [[basis]] using an assumed maximum daily dose of [[mdd]]. The quoted text is [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result exceeded the limit."),
    (3, "Total impurities are limited by [[limit_kind]] [[limit]], and this limit is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit."),
    (4, "The acceptance criterion for Residual solvent is [[limit_kind]] [[limit]]. It is [[basis]]. The results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit."),
    (5, "The acceptance criterion for Impurity O is [[limit_kind]] [[limit]], set at [[basis]] for an assumed maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. [[n_outside]] had results outside the limit."),
    (6, "For Dissolution, the limit is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. Results for [[n_outside]] were below the limit."),
    (7, "The limit for Impurity L is [[limit_kind]] [[limit]], which is [[basis]]. Assuming a maximum daily dose of [[mdd]], the text is [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit."),
]

# Wrong paragraphs written by hand AFTER the checks existed, aiming at gaps: (task index, text, what is wrong).
HAND_WRONG = [
    (1, "The acceptance criterion for Impurity O is [[limit_kind]] [[limit]], set at [[basis]] for a maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "dose not called an assumption"),
    (0, "For Dissolution, the limit is [[limit_kind]] [[limit]], which is [[basis]]. The limit follows pharmacopoeial practice. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "declared limit given a pharmacopoeia source"),
    (0, "For Dissolution, the limit is [[limit_kind]] [[limit]], which is [[basis]]. The limit reflects common industry practice. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "declared limit given an industry source"),
    (4, "The acceptance criterion for Residual solvent is [[limit_kind]] [[limit]], which is [[basis]]. The limit is a regulatory requirement. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "declared limit called a requirement"),
    (1, "The acceptance criterion for Impurity O is [[limit_kind]] [[limit]], set at [[basis]] for an assumed maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. The impurity was therefore qualified.", "qualified conclusion"),
    (5, "The acceptance criterion for Impurity O is [[limit_kind]] [[limit]], set at [[basis]] for an assumed maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. [[n_outside]] had results outside the limit. The remaining results were within the limit.", "compliance wording although some are outside"),
    (6, "For Dissolution, the limit is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. Overall the specification is met.", "compliance although some are outside"),
    (2, "The acceptance criterion for Impurity L is [[limit_kind]] [[limit]], set at [[basis]] for [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "assumption word missing"),
    (0, "For Dissolution, the limit is [[limit_kind]] [[min_value]]. This limit is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "direction attached to a result"),
    (3, "The limit for Total impurities is [[limit]] at most. It is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", "direction typed in words"),
    (2, "The acceptance criterion for Impurity L is [[limit_kind]] [[limit]], set at [[basis]] for an assumed maximum daily dose of [[mdd]]: [[q3b_quote]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. All results were above the limit.", "invented failure"),
    (4, "The acceptance criterion for Residual solvent is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. The product is suitable for patients.", "suitability claim"),
    (3, "The limit for Total impurities is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] ranged from [[min_value]] to [[max_value]]. All results were within the limit.", "no outside-count sentence (T-048)"),
]


def upper95(n):
    """Approximate one-sided 95% upper bound (percent) on the miss rate after 0 misses in n trials: the rule of three, 300/n."""
    return (Decimal(300) / n).quantize(Decimal("0.1"))


def build_contexts(rng, n_random):
    tasks = fixed_tasks() + [random_task(rng, i) for i in range(n_random)]
    ctxs = []
    for task in tasks:
        facts, flags, required = compute_spec_facts(task)
        ctxs.append({"task": task, "facts": facts, "flags": flags, "required": required, "text": oracle(flags, rng),
                     "rng": rng, "other": compute_spec_facts(flip(task))})
    return ctxs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=600)
    ap.add_argument("--per-kind", type=int, default=300)
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "mutation_report_spec.md"))
    args = ap.parse_args(argv)
    rng = random.Random(SEED)
    ctxs = build_contexts(rng, args.random)
    fixed = fixed_tasks()
    fixed_ctx = [compute_spec_facts(t) for t in fixed]

    bad_text = [(c["task"]["task_id"], c["text"], validate(c["text"], c["facts"], c["flags"], c["required"])) for c in ctxs]
    bad_text = [b for b in bad_text if b[2]]
    bad_render = [(c["task"]["task_id"], c["text"], verify_render(render(c["text"], c["facts"]), c["task"])) for c in ctxs]
    bad_render = [b for b in bad_render if b[2]]
    legit_bad = []
    for idx, text in LEGIT:
        facts, flags, required = fixed_ctx[idx]
        p = validate(text, facts, flags, required) or verify_render(render(text, facts), fixed[idx])
        if p:
            legit_bad.append((idx, text, p))

    rows, misses, wrong_rule = [], [], []
    for name, expect, fn, use_other in MUTATIONS:
        tried = caught = rejected = 0
        for c in ctxs:
            if tried >= args.per_kind:
                break
            mutated = fn(c["text"], c)
            if mutated is None or (mutated == c["text"] and not use_other):
                continue
            tried += 1
            facts, flags, required = c["other"] if use_other else (c["facts"], c["flags"], c["required"])
            problems = validate(mutated, facts, flags, required)
            rejected += bool(problems)
            if any(k in p for k in expect for p in problems):
                caught += 1
            else:
                (wrong_rule if problems else misses).append((name, c["task"]["task_id"], mutated, problems))
        rows.append((name, tried, caught, rejected))

    hand_missed = []
    for idx, text, why in HAND_WRONG:
        facts, flags, required = fixed_ctx[idx]
        if not validate(text, facts, flags, required):
            hand_missed.append((idx, why, text))

    trows, tmiss = [], []
    for name, fn in TAMPERS:
        tried = caught = 0
        for c in ctxs:
            if tried >= args.per_kind:
                break
            r = render(c["text"], c["facts"])
            mutated = fn(r, c, rng)
            if mutated is None or mutated == r:
                continue
            tried += 1
            if verify_render(mutated, c["task"]):
                caught += 1
            else:
                tmiss.append((name, c["task"]["task_id"], mutated))
        trows.append((name, tried, caught))

    n_q = sum(1 for c in ctxs if c["task"]["basis"] == "q3b_qualification")
    n_out = sum(1 for c in ctxs if c["task"]["n_outside"])
    L = ["# Planted-error test: P.5.6 spec justification paragraph", "",
         f"{len(ctxs)} tasks (5 real Lek attributes + {len(FILE['synthetic'])} planted variants + {args.random} seeded random), "
         f"{n_q} with a Q3B basis, {n_out} with batches outside the limit, seed {SEED}. No model involved.", "",
         "## Correct text must pass (false rejections)", "",
         f"- Correct paragraphs accepted by the validator: {len(ctxs) - len(bad_text)} of {len(ctxs)}",
         f"- Their rendered text accepted by the independent re-read: {len(ctxs) - len(bad_render)} of {len(ctxs)}",
         f"- Hand-written correct paraphrases accepted: {len(LEGIT) - len(legit_bad)} of {len(LEGIT)}", "",
         "## Planted errors in the draft (caught = rejected by the rule meant for it)", "",
         "| Error planted | Planted | Caught | Rejected by any rule | 95% upper bound on miss rate |", "| --- | --- | --- | --- | --- |"]
    for name, tried, caught, rejected in rows:
        bound = f"{upper95(tried)}%" if tried and caught == tried else ("n/a" if not tried else "MISSED")
        L.append(f"| {name} | {tried} | {caught} | {rejected} | {bound} |")
    L += ["", "## Planted errors on the finished text (independent re-read against the raw task)", "",
          "| Error planted | Planted | Caught | Missed |", "| --- | --- | --- | --- |"]
    for name, tried, caught in trows:
        L.append(f"| {name} | {tried} | {caught} | {tried - caught} |")
    L += ["", "## Wrong paragraphs written by hand", "", f"Caught: {len(HAND_WRONG) - len(hand_missed)} of {len(HAND_WRONG)}."]
    if hand_missed:
        L += ["", "Still accepted (known gaps):", ""] + [f"- task {i}: {why}: {x}" for i, why, x in hand_missed]
    total = sum(r[1] for r in rows) + sum(r[1] for r in trows)
    got = sum(r[2] for r in rows) + sum(r[2] for r in trows)
    L += ["", f"**Total: {got} of {total} planted errors caught.**", ""]
    for title, items in [("Missed in drafts", misses), ("Rejected, but not by the rule meant for it", wrong_rule),
                         ("Missed after rendering", tmiss)]:
        if items:
            L += [f"### {title} (first 8)", ""] + [f"- {i[0]} / {i[1]}: {i[2]}" + (f" :: {i[3]}" if len(i) > 3 else "") for i in items[:8]] + [""]
    if bad_text:
        L += ["### Correct paragraphs wrongly rejected (first 8)", ""] + [f"- {t}: {p} :: {x}" for t, x, p in bad_text[:8]] + [""]
    if bad_render:
        L += ["### Correct rendered text wrongly rejected by the re-read (first 8)", ""] + [f"- {t}: {p} :: {x}" for t, x, p in bad_render[:8]] + [""]
    if legit_bad:
        L += ["### Correct paraphrases wrongly rejected", ""] + [f"- {i}: {p} :: {x}" for i, x, p in legit_bad] + [""]
    L += ["## What these checks cannot see", "",
          "- Wrong wording that no word list anticipates (the lists are the checks' own).",
          "- A value swapped for another of the same task's numbers after rendering (the re-read checks the set of numbers, not their places).",
          "- A wrong value in the fact store itself, or a wrong Q3B row chosen upstream.",
          "- These errors were planted by the author of the checks; the unbiased test is a real model's own mistakes."]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return {"rows": rows, "trows": trows, "got": got, "total": total, "bad_text": bad_text, "bad_render": bad_render,
            "legit_bad": legit_bad, "hand_missed": hand_missed, "n_ctx": len(ctxs), "n_out": n_out, "n_q": n_q,
            "n_hand": len(HAND_WRONG), "n_legit": len(LEGIT), "wrong_rule": wrong_rule, "misses": misses, "tmiss": tmiss}


class MutationSpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            cls.r = main([])

    def test_correct_text_is_never_rejected(self):
        self.assertEqual(self.r["bad_text"], [])
        self.assertEqual(self.r["bad_render"], [])
        self.assertEqual(self.r["legit_bad"], [])

    def test_enough_kinds_and_every_kind_was_planted(self):
        self.assertGreaterEqual(len(self.r["rows"]) + len(self.r["trows"]), 12)
        for name, tried, *_ in self.r["rows"] + self.r["trows"]:
            self.assertGreaterEqual(tried, 20, f"{name}: only {tried} planted")

    def test_every_planted_error_is_caught_by_its_own_rule(self):
        self.assertEqual(self.r["misses"], [])
        self.assertEqual(self.r["wrong_rule"], [])
        for name, tried, caught, *_ in self.r["rows"] + self.r["trows"]:
            self.assertEqual(tried, caught, f"{name}: {tried - caught} missed")
        self.assertEqual(self.r["got"], self.r["total"])

    def test_hand_written_wrong_paragraphs_are_caught(self):
        self.assertEqual(self.r["hand_missed"], [])

    def test_both_bases_and_outside_cases_are_covered(self):
        self.assertGreaterEqual(self.r["n_q"], 100)
        self.assertGreaterEqual(self.r["n_out"], 100)

    def test_planted_gap_is_noticed(self):
        """Independence: with the declared-source rule removed the test must report misses, not pass."""
        original = sv.SOURCE_WORDS
        sv.SOURCE_WORDS = re.compile(r"\bxyzzy\b")
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                r = main(["--random", "80", "--out", str(Path(tempfile.gettempdir()) / "mutation_spec_gap.md")])
        finally:
            sv.SOURCE_WORDS = original
        self.assertTrue(r["misses"] or r["wrong_rule"])
        self.assertTrue(any(name == "declared_as_sourced" and tried != caught for name, tried, caught, _ in r["rows"]))


if __name__ == "__main__":
    unittest.main()
