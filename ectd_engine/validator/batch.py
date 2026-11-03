"""Checks a model's batch-analyses paragraph (3.2.P.5.4) and re-reads the finished text against the raw table; no model involved."""
import re
from decimal import ROUND_HALF_UP, Decimal

from ectd_engine.validator.validator import (ALL_BATCHES, ALLOWED_TOKENS, BATCH_IN_WORDS, CLAUSE_SPLIT, COMPARE, FORBIDDEN,
                                            FROM_TO, INFERENCE, NUMBER_WORDS, PLACEHOLDER, TIME_WORDS, TOKEN,
                                            opener_problems, render, sentences)

RESULT_FACTS = {"min_value", "max_value", "value_range", "mean_value"}
COUNT_FACTS = ("n_batches", "n_excluded", "excluded_batches")

# --- wording rules of this section type (not shared with the stability validator) ---
# Lek has no specification limits, so any pass/fail/limit wording invents one.
COMPLIANCE = re.compile(
    r"\b(compl(?:y|ies|ied|iance|iant)|conform\w*|meets?|met|meeting|accept\w*|pass(?:es|ed|ing)?|fail\w*|specif\w*|"
    r"limits?|limited|criteri(?:on|a)|exceed\w*|outside|oos|nmt|nlt|tolerance|requirement\w*|satisf\w*|suitable|"
    r"adequate|appropriate|normal|expected)\b", re.I)
# A batch count written in words; the count must come from [[n_batches]].
COUNT_IN_WORDS = re.compile(r"\b(single|sole|both|several|few|couple|numerous|many|multiple|majority|minority|handful|pair|"
                            r"most|some|half|only)\b[^.\[]{0,15}\bbatch(?:es)?\b", re.I)
# Exclusion wording: allowed only when batches were really excluded.
EXCLUSION = re.compile(r"\b(exclu\w+|quarantin\w+|withh[eo]ld\w*|omit\w*|remov\w*|discard\w*|disregard\w*|left out|"
                       r"not included|not reported|unavailable|missing|rejected)\b", re.I)
# Statistics or patterns that were not computed (batches are not a time series either).
UNSUPPORTED = re.compile(r"\b(median|mode|deviation|sd|rsd|variab\w+|varied|vary|varying|consisten\w+|uniform\w*|homogen\w+|"
                         r"outliers?|trend\w*|increas\w*|decreas\w*|rising|rose|fell|declin\w*|stable|stability|similar\w*|"
                         r"comparable|typical\w*|narrow\w*|wide\w*|tight\w*|spread|dispersion|scatter\w*|precision|"
                         r"reproducib\w+|distribution|significan\w*|differ\w*|good|poor|excellent|robust|reliable|quality|"
                         r"favou?rable|concern\w*|satisf\w*)\b", re.I)
ROLE_WORDS = {"max": re.compile(r"^(highest|maximum|peak|greatest|largest)$", re.I),
              "min": re.compile(r"^(lowest|minimum|smallest)$", re.I),
              "mean": re.compile(r"^(mean|average|averaged|averaging)$", re.I)}
ROLE_NAMES = {"max": "the highest result", "min": "the lowest result", "mean": "the mean"}
MEAN_WORD = re.compile(r"\b(mean|average|averaged|averaging)\b", re.I)
BETWEEN = re.compile(r"\bbetween\s+(?:the\s+)?\[\[([a-z_]+)\]\]\s+and\s+(?:the\s+)?\[\[([a-z_]+)\]\]", re.I)
# "a range of [[mean_value]]", "the range [[max_value]]": one number called a range.
POINT_AS_RANGE = re.compile(r"\brang\w*\s+(?:(?:of|at|around|about|was|is|were)\s+)?(?:the\s+)?"
                            r"\[\[(min_value|max_value|mean_value)\]\]", re.I)
VALUE_AS_NOUN = re.compile(r"\b(?:a|an)\s+\[\[(?:min_value|max_value|mean_value|value_range)\]\]", re.I)
NOUN_AFTER = re.compile(r"\[\[(?:n_batches|n_excluded|excluded_batches)\]\]\s+(?:batch|batches|lot|lots)\b", re.I)
NOUN_BEFORE = re.compile(r"\b(?:batch|batches|lot|lots)\s+\[\[(?:n_batches|n_excluded|excluded_batches)\]\]", re.I)


def _tokens(text):
    return [(m.group(0), m.start()) for m in TOKEN.finditer(text)]


def role_problems(text, facts):
    """highest / lowest / mean must sit next to a placeholder whose fact truly has that role."""
    bearing = {k for k in RESULT_FACTS if k in facts}
    problems = []
    for sent in sentences(text):
        bounds, pos = [], 0
        for m in CLAUSE_SPLIT.finditer(sent):
            bounds.append((pos, m.start()))
            pos = m.end()
        bounds.append((pos, len(sent)))
        toks = _tokens(sent)
        for i, (tok, start) in enumerate(toks):
            role = next((r for r, rx in ROLE_WORDS.items() if rx.match(tok)), None)
            if not role:
                continue
            lo, hi = next((c for c in bounds if c[0] <= start < c[1]), (0, len(sent)))
            holders = [(abs(j - i), t[2:-2], st) for j, (t, st) in enumerate(toks)
                       if t.startswith("[[") and t[2:-2] in bearing]
            pool = [h for h in holders if lo <= h[2] < hi] or holders
            if not pool:
                if role in ("max", "min"):
                    problems.append(f"'{tok}' has no result placeholder in its sentence to refer to")
                continue
            best = min(d for d, _, _ in pool)
            nearest = [f for d, f, _ in pool if d == best]
            if not any(role in facts[f]["roles"] for f in nearest):
                problems.append(f"'{tok}' is next to [[{nearest[0]}]], which is not {ROLE_NAMES[role]}")
    return problems


def mean_range_problems(text):
    """The mean is one number; it is never a range, nor the end of one. Ranges run from lowest to highest."""
    problems = []
    for sent in sentences(text):
        if "[[mean_value]]" in sent and not MEAN_WORD.search(PLACEHOLDER.sub(" ", sent)):
            problems.append("[[mean_value]] is not called the mean")
        ends = [(m.group(1), m.group(2)) for m in FROM_TO.finditer(sent)] + \
               [(m.group(1), m.group(2)) for m in BETWEEN.finditer(sent)]
        for a, b in ends:
            if "mean_value" in (a, b):
                problems.append("uses the mean as the end of a range")
            elif (a, b) == ("max_value", "min_value"):
                problems.append("range runs backwards (highest to lowest)")
            elif (a, b) != ("min_value", "max_value") and (a in RESULT_FACTS or b in RESULT_FACTS):
                problems.append("a range must run from [[min_value]] to [[max_value]]")
        if POINT_AS_RANGE.search(sent):
            problems.append("calls one result or the mean a range (a range is [[value_range]], or [[min_value]] to [[max_value]])")
    return problems


def exclusion_problems(text, facts, flags):
    """Exclusion must be mentioned if and only if batches were excluded, and only with the excluded facts."""
    problems = []
    bare = PLACEHOLDER.sub(" ", text)
    n_ex = flags["n_excluded"]
    if n_ex == 0:
        if EXCLUSION.search(bare):
            problems.append("invented exclusion: says batches were excluded, but none were")
        return problems
    if not EXCLUSION.search(bare):
        problems.append(f"omits exclusion: must say that {n_ex} batch(es) were quarantined and excluded")
    for sent in sentences(text):
        sent_bare = PLACEHOLDER.sub(" ", sent)
        has_ex = "[[n_excluded]]" in sent or "[[excluded_batches]]" in sent
        if "[[n_batches]]" in sent and EXCLUSION.search(sent_bare):
            problems.append("exclusion wording applied to [[n_batches]] (the included count)")
        elif has_ex and not EXCLUSION.search(sent_bare):
            problems.append("exclusion count or ids used without saying the batches were excluded")
    if ALL_BATCHES.search(bare):
        problems.append(f"claims all batches, but {n_ex} batch(es) were excluded")
    return problems


def validate(text, facts, flags, required):
    """Return a list of violations; an empty list means the draft passes."""
    problems = []
    used = PLACEHOLDER.findall(text)
    unknown = sorted(set(u for u in used if u not in facts))
    if unknown:
        problems.append(f"unknown placeholders: {unknown}")
    missing = [r for r in required if r not in used]
    if missing:
        problems.append(f"missing required facts: {missing}")

    bare_words = PLACEHOLDER.sub(" ", text)
    bare = ALLOWED_TOKENS.sub(" ", bare_words)
    bare = re.sub(re.escape(flags.get("attribute") or "\0"), " ", bare, flags=re.I)
    if re.search(r"\d", bare):
        problems.append("number written outside a placeholder")
    if NUMBER_WORDS.search(bare):
        problems.append("number written as a word")
    if re.search(r"\]\]\s*(%|percent\b)", text, re.I):
        problems.append("unit repeated after a placeholder (the value already carries it)")
    if NOUN_AFTER.search(text) or NOUN_BEFORE.search(text):
        problems.append("noun repeated: the placeholder already carries 'batch'/'batches'")
    if VALUE_AS_NOUN.search(text):
        problems.append("a value placeholder is used as a noun (write 'a mean of [[mean_value]]', not 'a [[mean_value]]')")

    # batches and their count come only from placeholders
    if BATCH_IN_WORDS.search(bare_words):
        problems.append("names a batch in words (batches come only from placeholders)")
    if COUNT_IN_WORDS.search(bare_words):
        problems.append("states a batch count in words (use [[n_batches]])")
    for bid in flags.get("batch_ids", []):
        if re.search(rf"\b{re.escape(bid)}\b", bare_words):
            problems.append(f"types batch ID {bid} (batches come only from placeholders)")
    if re.search(r"\bBatch(es)?\s+[A-Z0-9]", bare_words):
        problems.append("types a batch name (batches come only from placeholders)")

    problems += exclusion_problems(text, facts, flags)
    if not flags.get("has_spec") and "spec" not in facts:
        m = COMPLIANCE.search(bare_words)
        if m:
            problems.append(f"compliance or specification wording ('{m.group(0)}'), but there is no specification fact")
    problems += role_problems(text, facts)
    problems += mean_range_problems(text)

    attr = (flags.get("attribute") or "").lower()
    for name in flags.get("registry", []):
        if re.search(rf"\b{re.escape(name)}\b", bare_words, re.I) and not (name.lower() in attr or attr.startswith(name.lower())):
            problems.append(f"names another test ({name}) in a section about {flags.get('attribute')}")
    problems += opener_problems(text, flags)
    if UNSUPPORTED.search(bare_words):
        problems.append(f"states a statistic or pattern that was not computed ('{UNSUPPORTED.search(bare_words).group(0)}')")
    if INFERENCE.search(bare_words):
        problems.append("adds a cause or conclusion that no fact supports")
    if TIME_WORDS.search(bare_words):
        problems.append("states a time period in words (this section has none)")
    for sent in sentences(text):
        res = [m for m in PLACEHOLDER.finditer(sent) if m.group(1) in RESULT_FACTS]
        if len(res) >= 2 and COMPARE.search(sent[res[0].end():res[-1].start()]):
            problems.append("compares two results in words (comparisons are made by code, not the model)")

    n = len(sentences(text))
    if not 2 <= n <= 5:
        problems.append(f"needs 2-5 sentences, got {n}")
    if len(text.split()) > 130:
        problems.append(f"too long: {len(text.split())} words (limit 130)")
    if FORBIDDEN.search(text):
        problems.append("contains headings, bullets or chat phrases")
    return problems


# ---------------------------------------------------------------- re-read of the finished text
NUM = r"(\d+(?:\.\d+)?)"
WORD_TO_N = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def verify_render(rendered, table):
    """Independent second route: recompute from the raw table rows and compare with the finished text.

    Uses nothing from batch_facts: lowest, highest, ties, mean (half up) are worked out again here."""
    rows = table["rows"]
    got = [(b, Decimal(t)) for b, t in rows if t is not None]
    excluded = {b for b, t in rows if t is None}
    vals = [v for _, v in got]
    lo, hi = min(vals), max(vals)
    quant = Decimal(1).scaleb(-table["decimals"])
    mean_txt = str((sum(vals, Decimal(0)) / len(vals)).quantize(quant, rounding=ROUND_HALF_UP))
    ids = sorted((b for b, _ in rows), key=len, reverse=True)
    one = "(?:" + "|".join(re.escape(i) for i in ids) + ")"
    lst = rf"{one}(?:(?:,\s*|\s+and\s+){one})*"
    problems = []

    def split_ids(s):
        return re.split(r",\s*|\s+and\s+", s)

    pair = re.compile(rf"{NUM}%\s*\((Batch(?:es)?)\s+({lst})\)")
    for m in pair.finditer(rendered):
        v, listed = Decimal(m.group(1)), split_ids(m.group(3))
        if v not in (lo, hi):
            problems.append(f"{m.group(1)}% is neither the lowest nor the highest value in the table")
            continue
        if set(listed) != {b for b, x in got if x == v} or len(set(listed)) != len(listed):
            problems.append(f"batches listed for {m.group(1)}% do not match the table")
        if (m.group(2) == "Batches") != (len(listed) > 1):
            problems.append("'Batch'/'Batches' does not match the number of ids")
    rest = pair.sub(" ", rendered)

    rng = re.compile(rf"{NUM}–{NUM}%")
    for m in rng.finditer(rest):
        if (Decimal(m.group(1)), Decimal(m.group(2))) != (lo, hi):
            problems.append(f"range {m.group(0)} is not the table's lowest to highest")
    rest = rng.sub(" ", rest)

    own = re.compile(rf"\b(Batch(?:es)?)\s+({lst})")
    ex_refs = [i for m in own.finditer(rest) for i in split_ids(m.group(2))]
    if set(ex_refs) != excluded:
        problems.append(f"excluded batches in the text {sorted(set(ex_refs))} differ from the table {sorted(excluded)}")
    rest = own.sub(" ", rest)

    allowed = {mean_txt} | ({str(next(t for _, t in rows if t is not None and Decimal(t) == lo))} if lo == hi else set())
    for m in re.finditer(rf"{NUM}%", rest):
        if m.group(1) not in allowed:
            problems.append(f"{m.group(1)}% is not the mean ({mean_txt}) or a table value with its batch")
    rest = re.sub(rf"{NUM}%", " ", rest)

    counts = {len(got), len(excluded)} - {0}
    for m in re.finditer(r"\b(\w+)\s+batch(?:es)?\b", rest, re.I):
        w = m.group(1).lower()
        n = WORD_TO_N.get(w, int(w) if w.isdigit() else None)
        if n is not None and n not in counts:
            problems.append(f"'{m.group(0)}' is not the number of batches with a result or excluded")
    rest = re.sub(r"\b(\w+)\s+batch(?:es)?\b", " ", rest, flags=re.I)
    if re.search(r"\d", rest):
        problems.append("a number in the finished text is not explained by the table")
    return problems


__all__ = ["validate", "verify_render", "render"]
