"""Planted-error test for the P.5.4 batch validator: every planted error must be caught by the rule meant to catch it, no correct text may be rejected.

    python -m unittest tests.test_mutation_batch

No model involved. Tasks: seeded 3-12 batch windows drawn from the real Lek facts (the loader decides what is quarantined),
plus synthetic stores with ties, several exclusions and all-equal results. Values are Decimal built from integers only.
"""
import argparse
import json
import random
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.loaders import lek
from ectd_engine.validator.batch import render, validate, verify_render
from ectd_engine.writer.batch_facts import LoaderStore, compute_batch_facts, fact_id, id_key, places
from ectd_engine.writer.facts import NUMBER_WORDS
from tests.test_batch_writer import make_store, make_task

OTHER_TESTS = [t for t, _ in lek.COLUMNS.values()] + ["Assay", "Water content", "Hardness"]
SEED = 7


# ---------------------------------------------------------------- tasks
def real_windows(store, rng, count):
    """Seeded windows of Lek batches; for the impurity columns many windows hold quarantined batches."""
    bad = sorted((b for b in store.known_batches if store.get(fact_id(b, "impurities_total")) is None), key=id_key)
    out = []
    for i in range(count):
        col = rng.choice(list(lek.COLUMNS))
        pool = sorted((b for b in store.known_batches if (store.get(fact_id(b, col)) is None)
                       or places(store.get(fact_id(b, col)).value) <= 2), key=id_key)
        good = [b for b in pool if b not in bad]
        n = rng.randint(3, 12)
        k = rng.randint(1, min(3, n - 1)) if (col in lek.PARTS and rng.random() < 0.6) else 0
        ids = rng.sample(bad, k) + rng.sample(good, n - k)
        task = {"task_id": f"win{i}", "section": "3.2.P.5.4", "product": "Lek tablets", "attribute": lek.COLUMNS[col][0],
                "column": col, "unit": "%", "decimals": 2, "batches": sorted(ids, key=id_key)}
        out.append((task, store.get, store.known_batches))
    return out


def synthetic(rng, count):
    """Fake-store tasks: ties, 0-3 exclusions, and now and then every result equal."""
    out = []
    for i in range(count):
        n = rng.randint(2, 12)
        ids = sorted((str(x) for x in rng.sample(range(1, 200), n)), key=id_key)
        top = rng.choice([4, 40, 400])  # a small top makes ties likely
        vals = {b: f"{rng.randint(1, top) // 100}.{rng.randint(1, top) % 100:02d}" for b in ids}
        if rng.random() < 0.06:
            vals = {b: "0.05" for b in ids}
        for b in rng.sample(ids, rng.choice([0, 0, 1, 2, 3]) if n > 3 else 0):
            vals[b] = None
        get, known = make_store(vals)
        task = make_task(ids)
        task["task_id"] = f"syn{i}"
        out.append((task, get, known))
    return out


# ------------------------------------------------------------ correct writer
def oracle(flags, rng):
    """A correct paragraph in one of several shapes; the exclusion sentence goes in different places."""
    attr = flags["attribute"]
    shape = rng.choice("ABC")
    if shape == "A":
        parts = [f"{attr} results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]."]
        if rng.random() < 0.5:
            parts.append("The highest result was [[max_value]] and the lowest result was [[min_value]].")
        else:
            parts.append("The lowest result was [[min_value]].")
    elif shape == "B":
        parts = ["The mean result for [[n_batches]] was [[mean_value]].",
                 "The lowest result was [[min_value]] and the highest result was [[max_value]]."]
    else:
        parts = [f"{attr} was determined for [[n_batches]].",
                 "The results covered the range [[value_range]], with a mean of [[mean_value]].",
                 "The highest result was [[max_value]] and the lowest result was [[min_value]]."]
    if flags["n_excluded"]:
        ex = rng.choice(["Results for [[n_excluded]], [[excluded_batches]], were quarantined and are not included.",
                         "The results for [[n_excluded]], [[excluded_batches]], were excluded as they are quarantined."])
        parts.insert(rng.randint(1, len(parts)), ex)
    if "[[max_value]]" not in " ".join(parts):  # keep the required facts in
        parts[-1] += " The highest result was [[max_value]]."
    return " ".join(parts)


# --------------------------------------------------------------- mutations
def _swap(t, a, b):
    return t.replace(a, "\0").replace(b, a).replace("\0", b)


def _first_dot(t, add):
    return t.replace(".", add, 1)


COMPLIANCE_SENTENCES = ["All results complied with the specification.", "All batches met the acceptance criteria.",
                        "The results are acceptable.", "All batches passed.", "No result was out of specification.",
                        "The results did not meet the limit.", "All results conform to the requirements.",
                        "No result exceeded the limit.", "The results are within the specification."]
STAT_SENTENCES = ["The results showed low variability.", "The median was similar for all results.",
                  "The results were consistent.", "A decreasing trend was observed.", "The quality of the batches is good.",
                  "There was a narrow spread."]
COUNT_SENTENCES = ["Several batches were tested.", "The data cover a single batch.", "Both batches were tested.",
                   "Most batches were tested."]
INVENTED_EXCLUSIONS = ["A batch was excluded as it was quarantined.", "One batch was quarantined and is not included.",
                       "Some results were omitted.", "The results of a batch were removed."]
CAUSES = [", due to degradation.", ", which supports the proposed shelf life.", ", likely because of moisture uptake.",
          ", which justifies the retest period."]


def m_compliance_claim(t, c):
    return t + " " + c["rng"].choice(COMPLIANCE_SENTENCES)


def m_count_flip(t, c):
    return _swap(t, "[[n_batches]]", "[[n_excluded]]") if c["flags"]["n_excluded"] else None


def m_min_max_swap(t, c):
    return None if c["flags"]["all_equal"] else _swap(t, "[[min_value]]", "[[max_value]]")


def m_role_flip(t, c):
    if c["flags"]["all_equal"]:
        return None
    return re.sub(r"\b(highest|lowest)\b", lambda m: "lowest" if m.group(1) == "highest" else "highest", t)


def m_mean_as_range(t, c):
    options = []
    if "with a mean of" in t:
        options.append(t.replace("with a mean of", "with a mean range of", 1))
    if "ranged from [[min_value]] to [[max_value]]" in t:
        options.append(t.replace("ranged from [[min_value]] to [[max_value]]", "ranged from [[min_value]] to [[mean_value]]", 1))
    if "the range [[value_range]]" in t:
        options.append(t.replace("the range [[value_range]]", "the range [[mean_value]]", 1))
    return c["rng"].choice(options) if options else None


def m_omit_exclusion(t, c):
    if not c["flags"]["n_excluded"]:
        return None
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", t) if "[[n_excluded]]" not in s)


def m_invented_exclusion(t, c):
    return None if c["flags"]["n_excluded"] else t + " " + c["rng"].choice(INVENTED_EXCLUSIONS)


def m_typed_number(t, c):
    return t.replace("[[mean_value]]", c["facts"]["mean_value"]["value"], 1)


def m_batch_in_words(t, c):
    return _first_dot(t, ", particularly in " + c["rng"].choice(["the second batch", "the last batch", "the other batches", "the first lot"]) + ".")


def m_unknown_fact(t, c):
    return t.replace("[[mean_value]]", "[[mean_value_where]]", 1)


def m_wrong_attribute(t, c):
    attr = c["flags"]["attribute"]
    if attr not in t:
        return None
    return t.replace(attr, c["rng"].choice([x for x in OTHER_TESTS if x.lower() != attr.lower()]), 1)


def m_mean_word_swap(t, c):
    return t.replace("[[mean_value]]", "[[max_value]]", 1) if not c["flags"]["all_equal"] else None


def m_count_words(t, c):
    return t + " " + c["rng"].choice(COUNT_SENTENCES)


def m_all_batches(t, c):
    return t + " The results apply to all batches." if c["flags"]["n_excluded"] else None


def m_stat_claim(t, c):
    return t + " " + c["rng"].choice(STAT_SENTENCES)


def m_unit_after(t, c):
    return t.replace("[[mean_value]]", "[[mean_value]] percent", 1)


def m_noun_repeat(t, c):
    return t.replace("[[n_batches]]", "[[n_batches]] batches", 1)


def m_typed_batch_id(t, c):
    return _first_dot(t, ", as seen in Batch " + c["rng"].choice(c["flags"]["batch_ids"]) + ".")


def m_cause(t, c):
    return _first_dot(t, c["rng"].choice(CAUSES))


def m_article_noun(t, c):
    return t.replace("with a mean of [[mean_value]]", "with a [[mean_value]]", 1) if "with a mean of [[mean_value]]" in t else None


def m_time_words(t, c):
    return _first_dot(t, c["rng"].choice([", across the year.", ", measured daily.", ", over many weeks."]))


MUTATIONS = [
    ("compliance_claim", ("compliance",), m_compliance_claim),
    ("count_flip", ("exclusion",), m_count_flip),
    ("min_max_swap", ("backwards", "is next to"), m_min_max_swap),
    ("role_flip (highest <-> lowest)", ("is next to",), m_role_flip),
    ("mean_as_range", ("range", "not called the mean"), m_mean_as_range),
    ("omit_exclusion", ("omits exclusion",), m_omit_exclusion),
    ("invented_exclusion", ("invented exclusion",), m_invented_exclusion),
    ("typed_number", ("number written outside",), m_typed_number),
    ("batch_in_words", ("names a batch in words",), m_batch_in_words),
    ("unknown_fact", ("unknown placeholders",), m_unknown_fact),
    ("wrong_attribute", ("another test", "sentence starts with"), m_wrong_attribute),
    ("mean_word_swap (mean next to [[max_value]])", ("is next to",), m_mean_word_swap),
    ("batch_count_in_words", ("batch count",), m_count_words),
    ("all_batches_claim_with_exclusion", ("claims all batches",), m_all_batches),
    ("stat_claim (variability, trend, quality)", ("statistic",), m_stat_claim),
    ("unit_after_placeholder", ("unit repeated",), m_unit_after),
    ("noun_repeated_after_count", ("noun repeated",), m_noun_repeat),
    ("typed_batch_id", ("types batch ID",), m_typed_batch_id),
    ("cause_or_shelf_life_added", ("cause",), m_cause),
    ("mean_with_article_as_noun", ("noun",), m_article_noun),
    ("time_period_in_words", ("time period",), m_time_words),
]


# ------------------------------------------------------- tampering on rendered text
def _change_digit(num, rng):
    idx = [i for i, ch in enumerate(num) if ch.isdigit()]
    i = rng.choice(idx)
    return num[:i] + str((int(num[i]) + rng.randint(1, 8)) % 10) + num[i + 1:]


def t_digit(r, c, rng):
    ms = list(re.finditer(r"\d+(?:\.\d+)?(?=%)", r))
    if not ms:
        return None
    m = rng.choice(ms)
    return r[:m.start()] + _change_digit(m.group(0), rng) + r[m.end():]


def t_batch(r, c, rng):
    ms = [m for m in re.finditer(r"%\s*\(Batch (\S+)\)", r)]
    if not ms:
        return None
    m = rng.choice(ms)
    others = [b for b in c["flags"]["batch_ids"] if b != m.group(1)]
    return r[:m.start(1)] + rng.choice(others) + r[m.end(1):]


def t_mean(r, c, rng):
    v = c["facts"]["mean_value"]["value"]
    m = re.search(r"(?<![\d.])" + re.escape(v), r)
    return None if not m else r[:m.start()] + _change_digit(v, rng) + r[m.end():]


def t_count(r, c, rng):
    v = c["facts"]["n_batches"]["value"]
    n = len(c["flags"]["included"])
    other = rng.choice([k for k in NUMBER_WORDS if k not in (n, c["flags"]["n_excluded"])])
    return r.replace(v, NUMBER_WORDS[other] + (" batch" if other == 1 else " batches"), 1)


def t_excluded_id(r, c, rng):
    if not c["flags"]["n_excluded"]:
        return None
    v = c["facts"]["excluded_batches"]["value"]
    return r.replace(v, "Batch " + rng.choice(c["flags"]["included"]), 1)


def t_range(r, c, rng):
    m = re.search(r"\d+\.\d+–(\d+\.\d+)%", r)
    return None if not m else r[:m.start(1)] + _change_digit(m.group(1), rng) + r[m.end(1):]


TAMPERS = [("digit changed in a rendered value", t_digit), ("batch id changed on a result", t_batch),
           ("mean changed", t_mean), ("batch count changed", t_count), ("excluded batch id changed", t_excluded_id),
           ("range end changed", t_range)]

# Correct paragraphs in other words (task index in data/tasks/p54_tasks.json, text). All must pass.
LEGIT = [
    (0, "Dissolution results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. The lowest result was [[min_value]]."),
    (0, "The mean result for [[n_batches]] was [[mean_value]]. The highest result was [[max_value]] and the lowest result was [[min_value]]."),
    (1, "Impurity O was determined for [[n_batches]]. The average result was [[mean_value]], and the results covered the range [[value_range]]. The highest result was [[max_value]] and the lowest result was [[min_value]]."),
    (2, "Impurity L results ranged from [[min_value]] to [[max_value]] for [[n_batches]], with a mean of [[mean_value]]. The lowest result was [[min_value]]."),
    (3, "Total impurities results for [[n_batches]] had a mean of [[mean_value]]. The highest result was [[max_value]] and the lowest result was [[min_value]]."),
    (4, "Residual solvent results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. The highest result was [[max_value]]."),
    (5, "Total impurities results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. Results for [[n_excluded]], [[excluded_batches]], were quarantined and are not included."),
    (5, "The results for [[n_excluded]], [[excluded_batches]], were quarantined and are excluded. Total impurities were determined for [[n_batches]], with a mean of [[mean_value]]. The highest result was [[max_value]] and the lowest result was [[min_value]]."),
]

# Wrong paragraphs written by hand AFTER the checks existed, aiming at gaps: (task index, text, what is wrong).
HAND_WRONG = [
    (0, "Dissolution results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. The batches were of good quality.", "quality claim"),
    (1, "Impurity O results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. The highest values occurred in the later batches.", "batch order claim"),
    (1, "Impurity O had a mean of [[mean_value]] and the highest result was [[min_value]]. The lowest result was [[min_value]].", "min called highest"),
    (2, "Impurity L results are between [[mean_value]] and [[max_value]] for [[n_batches]]. The lowest result was [[min_value]].", "mean as end of a range"),
    (4, "Residual solvent results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]], all above [[min_value]].", "comparison in words"),
    (5, "Total impurities results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. Results for [[excluded_batches]] were not available.", "exclusion without its count"),
    (5, "Total impurities results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. Results for [[n_excluded]], [[excluded_batches]], were quarantined, so the mean is likely higher.", "guess about the effect"),
    (5, "Total impurities results for all [[n_batches]] batches ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. Results for [[n_excluded]], [[excluded_batches]], were quarantined and are not included.", "all batches although one is excluded"),
    (3, "Total impurities results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]. The total is acceptable.", "acceptable without a spec"),
]


def upper95(n):
    """Approximate one-sided 95% upper bound (percent) on the miss rate after 0 misses in n trials: the rule of three, 300/n."""
    return (Decimal(300) / n).quantize(Decimal("0.1"))


def build_contexts(store, rng, n_real, n_syn):
    ctxs = []
    for task, get, known in real_windows(store, rng, n_real) + synthetic(rng, n_syn):
        facts, flags, required, table = compute_batch_facts(task, get, known)
        ctxs.append({"task": task, "facts": facts, "flags": flags, "required": required, "table": table,
                     "text": oracle(flags, rng), "rng": rng})
    return ctxs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=int, default=400)
    ap.add_argument("--synthetic", type=int, default=300)
    ap.add_argument("--per-kind", type=int, default=300)
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "mutation_report_batch.md"))
    args = ap.parse_args(argv)
    rng = random.Random(SEED)
    store = LoaderStore()
    ctxs = build_contexts(store, rng, args.real, args.synthetic)

    bad_text = [(c["task"]["task_id"], c["text"], validate(c["text"], c["facts"], c["flags"], c["required"])) for c in ctxs]
    bad_text = [b for b in bad_text if b[2]]
    bad_render = [(c["task"]["task_id"], c["text"], verify_render(render(c["text"], c["facts"]), c["table"])) for c in ctxs]
    bad_render = [b for b in bad_render if b[2]]
    fixed = [(t, store.get, store.known_batches) for t in json.loads(
        (Path(__file__).resolve().parent.parent / "data" / "tasks" / "p54_tasks.json").read_text(encoding="utf-8"))["tasks"]]
    fixed_ctx = []
    for task, get, known in fixed:
        facts, flags, required, table = compute_batch_facts(task, get, known)
        fixed_ctx.append((facts, flags, required, table))
    legit_bad = []
    for idx, text in LEGIT:
        facts, flags, required, table = fixed_ctx[idx]
        p = validate(text, facts, flags, required) or verify_render(render(text, facts), table)
        if p:
            legit_bad.append((idx, text, p))

    rows, misses, wrong_rule = [], [], []
    for name, expect, fn in MUTATIONS:
        tried = caught = rejected = 0
        for c in ctxs:
            if tried >= args.per_kind:
                break
            mutated = fn(c["text"], c)
            if mutated is None or mutated == c["text"]:
                continue
            tried += 1
            problems = validate(mutated, c["facts"], c["flags"], c["required"])
            rejected += bool(problems)
            if any(k in p for k in expect for p in problems):
                caught += 1
            else:
                (wrong_rule if problems else misses).append((name, c["task"]["task_id"], mutated, problems))
        rows.append((name, tried, caught, rejected))

    hand_missed = []
    for idx, text, why in HAND_WRONG:
        facts, flags, required, table = fixed_ctx[idx]
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
            if verify_render(mutated, c["table"]):
                caught += 1
            else:
                tmiss.append((name, c["task"]["task_id"], mutated))
        trows.append((name, tried, caught))

    n_ex = sum(1 for c in ctxs if c["flags"]["n_excluded"])
    L = ["# Planted-error test: P.5.4 batch paragraph", "",
         f"{len(ctxs)} tasks ({args.real} windows of real Lek facts + {args.synthetic} synthetic), {n_ex} with excluded batches, seed {SEED}. No model involved.", "",
         "## Correct text must pass (false rejections)", "",
         f"- Correct paragraphs accepted by the validator: {len(ctxs) - len(bad_text)} of {len(ctxs)}",
         f"- Their rendered text accepted by the independent re-read: {len(ctxs) - len(bad_render)} of {len(ctxs)}",
         f"- Hand-written correct paraphrases accepted: {len(LEGIT) - len(legit_bad)} of {len(LEGIT)}", "",
         "## Planted errors in the draft (caught = rejected by the rule meant for it)", "",
         "| Error planted | Planted | Caught | Rejected by any rule | 95% upper bound on miss rate |", "| --- | --- | --- | --- | --- |"]
    for name, tried, caught, rejected in rows:
        bound = f"{upper95(tried)}%" if tried and caught == tried else ("n/a" if not tried else "MISSED")
        L.append(f"| {name} | {tried} | {caught} | {rejected} | {bound} |")
    L += ["", "## Planted errors on the finished text (independent re-read against the raw table)", "",
          "| Error planted | Planted | Caught | Missed |", "| --- | --- | --- | --- |"]
    for name, tried, caught in trows:
        L.append(f"| {name} | {tried} | {caught} | {tried - caught} |")
    must = HAND_WRONG
    L += ["", "## Wrong paragraphs written by hand", "", f"Caught: {len(must) - len(hand_missed)} of {len(must)}."]
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
          "- A wrong value in the fact store itself, or a wrong quarantine decision upstream.",
          "- These errors were planted by the author of the checks; the unbiased test is a real model's own mistakes."]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return {"rows": rows, "trows": trows, "got": got, "total": total, "bad_text": bad_text, "bad_render": bad_render,
            "legit_bad": legit_bad, "hand_missed": hand_missed, "n_ctx": len(ctxs), "n_ex": n_ex, "n_hand": len(must),
            "n_legit": len(LEGIT), "wrong_rule": wrong_rule, "misses": misses, "tmiss": tmiss}


class MutationBatchTest(unittest.TestCase):
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
        self.assertGreaterEqual(len(self.r["rows"]) + len(self.r["trows"]), 10)
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

    def test_windows_include_quarantined_batches(self):
        self.assertGreaterEqual(self.r["n_ex"], 50)

    def test_planted_gap_is_noticed(self):
        """Independence: with the compliance rule removed the test must report misses, not pass."""
        from ectd_engine.validator import batch as bv
        original = bv.COMPLIANCE
        bv.COMPLIANCE = re.compile(r"\bxyzzy\b")
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                r = main(["--real", "40", "--synthetic", "20", "--out", str(Path(tempfile.gettempdir()) / "mutation_gap.md")])
        finally:
            bv.COMPLIANCE = original
        self.assertTrue(r["misses"] or r["wrong_rule"])
        self.assertTrue(any(name == "compliance_claim" and tried != caught for name, tried, caught, _ in r["rows"]))


if __name__ == "__main__":
    unittest.main()
