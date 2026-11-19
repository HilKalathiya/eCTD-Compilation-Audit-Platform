"""Checks a model's P.5.6 justification paragraph against what each limit's basis allows, and re-reads the finished text; no model involved."""
import re

from ectd_engine.validator.batch import COUNT_IN_WORDS, WORD_TO_N, mean_range_problems, role_problems
from ectd_engine.validator.validator import ALL_BATCHES, ALLOWED_TOKENS, BATCH_IN_WORDS, FORBIDDEN, NUMBER_WORDS, sentences

# The shared placeholder pattern has no digits, so it cannot see [[q3b_quote]]; this one can.
PH = re.compile(r"\[\[([a-z0-9_]+)\]\]")
Q3B, DECLARED = "q3b_qualification", "declared"

# --- wording rules of this section type (own lists; the batch and stability lists reject correct text here) ---
# A declared limit must not look sourced: any word that points at a standard, a guideline, a requirement or a study.
SOURCE_WORDS = re.compile(
    r"\b(ich|q3\w*|guidelines?|guidance|pharmacop\w*|usp|ph\.?\s*eur\w*|fda|ema|monographs?|compendi\w+|"
    r"in accordance|in line with|consistent with|aligned? with|per|as required|required|requirements?|qualif\w*|"
    r"toxicolog\w*|standards?|regulat\w+|recommend\w*|establish\w*|literature|published|sourced|derived|based on|"
    r"adopted|taken from|supported by|precedent|state of the art|industry|practice|conventions?|customary|commonly|usually)\b", re.I)
# Never allowed, whatever the basis: safety or qualification conclusions. ("qualification threshold" stays allowed for q3b.)
SAFETY = re.compile(
    r"\b(qualified|qualify|qualifies|qualifying|safe\w*|safety|toxic\w*|harm\w*|tolerat\w*|no concerns?|concerns?|"
    r"clinical\w*|patients?)\b", re.I)
# A q3b limit is sourced; it must not be described as declared or unsourced.
DECLARED_WORDS = re.compile(r"\b(declared|demonstration|demo|unsourced|no public source|by the author)\b", re.I)
ASSUME = re.compile(r"\b(assum\w*|presum\w*)\b", re.I)
# The direction of the limit comes from [[limit_kind]] only.
KIND_WORDS = re.compile(r"\b(nmt|nlt|not more than|not less than|no more than|no less than|not exceeding|at most|at least|"
                        r"up to|a maximum of|a minimum of|maximum of|minimum of|upper limit|lower limit|ceiling|floor)\b", re.I)
KIND_PAIR = re.compile(r"\[\[limit_kind\]\](?!\s*\[\[limit\]\])")
# Compliance wording is allowed only when no batch is outside the limit.
POSITIVE = re.compile(r"\b(compl(?:y|ies|ied|iance|iant)|conform\w*|meets?|met|meeting|within|acceptable|accepted|pass(?:es|ed|ing)?|"
                      r"satisf\w*|adequate|suitable)\b", re.I)
NEGATIVE = re.compile(r"\b(outside|exceed\w*|fail\w*|oos|out of specification|non-?conform\w*|breach\w*|violat\w*|"
                      r"(?:above|below) the limit)\b", re.I)
NEGATED = re.compile(r"\b(no|none|not|without|neither|nor)\b[^.;]{0,40}?\b(outside|exceed\w*|fail\w*|oos|out of specification|"
                     r"non-?conform\w*|breach\w*|violat\w*|(?:above|below) the limit)\b", re.I)
STATS = re.compile(r"\b(variab\w+|varied|trends?|consisten\w+|uniform\w*|outliers?|median|deviation|rsd|spread|increas\w*|"
                   r"decreas\w*|stable|stability|typical\w*|robust|reliable|quality|good|poor|excellent|similar\w*)\b", re.I)
INFERENCE = re.compile(r"\b(because|due to|caused|attribut\w+|owing to|degradation|shelf[- ]?life|retest|expiry|likely|"
                       r"probabl\w+|therefore|thus|conclu\w+|suggest\w*|indicat\w+|demonstrat\w+|proves?|proven)\b", re.I)
# Typed pieces of the Q3B quote: four words in a row from it, or its most telling phrases.
QUOTE_PHRASES = re.compile(r"whichever is lower|\btdi\b|total daily intake|qualification thresholds|[µμ]g\b|\bug\b", re.I)
VALUE_AS_NOUN = re.compile(r"\b(?:a|an)\s+\[\[(?:limit|min_value|max_value|mdd)\]\]", re.I)
NOUN_AFTER = re.compile(r"\[\[(?:n_batches|n_outside)\]\]\s+(?:batch|batches|lot|lots)\b", re.I)
NOUN_BEFORE = re.compile(r"\b(?:batch|batches|lot|lots)\s+\[\[(?:n_batches|n_outside)\]\]", re.I)
UNIT_AFTER = re.compile(r"\]\]\s*(%|percent\b|mg\b)", re.I)
MAX_WORDS = 130


def render(text, facts):
    """Replace each placeholder with its value computed in code."""
    return PH.sub(lambda m: facts[m.group(1)]["value"] if m.group(1) in facts else m.group(0), text)


def _words(text):
    """Lower-case word stream; a placeholder becomes '|' so word runs never join across one."""
    return re.findall(r"[a-z]+|\|", PH.sub(" | ", text).lower())


def quote_fragment(text, quote, n=4):
    """The first run of n words that the text shares with the quote, or None."""
    qw = [w for w in _words(quote) if w != "|"]
    grams = {tuple(qw[i:i + n]) for i in range(len(qw) - n + 1)}
    tw = _words(text)
    for i in range(len(tw) - n + 1):
        if tuple(tw[i:i + n]) in grams:
            return " ".join(tw[i:i + n])
    return None


def basis_problems(text, bare, facts, flags):
    problems = []
    if flags["basis"] == DECLARED:
        m = SOURCE_WORDS.search(bare)
        if m:
            problems.append(f"declared limit written like a sourced one ('{m.group(0)}'): no source or standard wording")
        return problems
    m = DECLARED_WORDS.search(bare)
    if m:
        problems.append(f"q3b limit described as declared or unsourced ('{m.group(0)}')")
    for sent in sentences(text):
        if "[[mdd]]" in sent and not ASSUME.search(PH.sub(" ", sent)):
            problems.append("the maximum daily dose is given without saying, in the same sentence, that it is an assumption")
    frag = quote_fragment(text, flags["quote"]) if flags.get("quote") else None
    if frag:
        problems.append(f"typed quote fragment ('{frag}'): the Q3B text comes only from [[q3b_quote]]")
    return problems


def outside_problems(text, flags):
    """Compliance wording only when nothing is outside the limit; failure wording only with [[n_outside]]."""
    problems, n_out = [], flags["n_outside"]
    bare = PH.sub(" ", text)
    if n_out:
        m = POSITIVE.search(bare)
        if m:
            problems.append(f"compliance wording ('{m.group(0)}') but {n_out} batch(es) are outside the limit")
        if NEGATED.search(bare):
            problems.append(f"denies a failure ('{NEGATED.search(bare).group(0)}') but {n_out} batch(es) are outside the limit")
        for sent in sentences(text):
            if NEGATIVE.search(PH.sub(" ", sent)) and "[[n_outside]]" not in sent:
                problems.append("failure wording without [[n_outside]] in the same sentence")
    else:
        m = NEGATIVE.search(NEGATED.sub(" ", bare))
        if m:
            problems.append(f"invented failure ('{m.group(0)}'): no batch is outside the limit")
    return problems


def outside_statement_problems(text, flags):
    """The paragraph must say how many results were outside the limit (T-048): the count sentence, or 'no result was outside'."""
    if flags["n_outside"]:
        ok = any("[[n_outside]]" in s and NEGATIVE.search(PH.sub(" ", s)) for s in sentences(text))
        return [] if ok else ["missing outside-count sentence: say in one sentence with [[n_outside]] that results were outside the limit"]
    ok = NEGATED.search(PH.sub(" ", text))
    return [] if ok else ["missing outside-count sentence: say that no result was outside the limit"]


def validate(text, facts, flags, required):
    """Return a list of violations; an empty list means the draft passes."""
    problems = []
    used = PH.findall(text)
    unknown = sorted(set(u for u in used if u not in facts))
    if unknown:
        problems.append(f"unknown placeholders: {unknown}")
    missing = [r for r in required if r not in used]
    if missing:
        problems.append(f"missing required facts: {missing}")

    bare_words = PH.sub(" ", text)  # words only; nothing else removed, so ICH or Q3B typed in text is still seen
    bare = ALLOWED_TOKENS.sub(" ", bare_words)  # used for the digit check only
    attr = flags.get("attribute") or ""
    bare = re.sub(re.escape(attr or "\0"), " ", bare, flags=re.I)
    if re.search(r"\d", bare):
        problems.append("number written outside a placeholder")
    if NUMBER_WORDS.search(bare):
        problems.append("number written as a word")
    if UNIT_AFTER.search(text):
        problems.append("unit repeated after a placeholder (the value already carries it)")
    if NOUN_AFTER.search(text) or NOUN_BEFORE.search(text):
        problems.append("noun repeated: the placeholder already carries 'batch'/'batches'")
    if VALUE_AS_NOUN.search(text):
        problems.append("a value placeholder is used as a noun")
    if attr and attr.lower() not in text.lower():
        problems.append(f"does not name the attribute ({attr})")
    for name in flags.get("registry", []):
        if re.search(rf"\b{re.escape(name)}\b", bare_words, re.I) and not (name.lower() in attr.lower() or attr.lower().startswith(name.lower())):
            problems.append(f"names another test ({name}) in a section about {attr}")

    m = SAFETY.search(bare_words)
    if m:
        problems.append(f"safety or qualification claim ('{m.group(0)}'): the writer may not conclude anything about safety")
    problems += basis_problems(text, bare_words, facts, flags)
    stripped = re.sub(r"maximum daily dose", " ", bare_words, flags=re.I)
    if KIND_WORDS.search(stripped):
        problems.append(f"types the limit direction in words ('{KIND_WORDS.search(stripped).group(0)}'); limit direction comes from [[limit_kind]]")
    if "[[limit_kind]]" in text and KIND_PAIR.search(text):
        problems.append("limit direction: [[limit_kind]] must be followed directly by [[limit]]")
    if QUOTE_PHRASES.search(bare_words):
        problems.append(f"typed quote fragment ('{QUOTE_PHRASES.search(bare_words).group(0)}')")
    problems += outside_problems(text, flags)
    problems += outside_statement_problems(text, flags)
    no_dose = re.sub(r"maximum daily dose", "daily dose", text, flags=re.I)  # "maximum" here is not a result word
    problems += role_problems(no_dose, facts) + mean_range_problems(no_dose)

    if BATCH_IN_WORDS.search(bare_words):
        problems.append("names a batch in words (batches come only from placeholders)")
    if COUNT_IN_WORDS.search(bare_words):
        problems.append("states a batch count in words (use [[n_batches]])")
    if ALL_BATCHES.search(bare_words):
        problems.append("claims all batches (quarantined batches are not counted)")
    if STATS.search(bare_words):
        problems.append(f"states a statistic or pattern that was not computed ('{STATS.search(bare_words).group(0)}')")
    if INFERENCE.search(bare_words):
        problems.append("adds a cause or conclusion that no fact supports")
    n = len(sentences(text))
    if not 3 <= n <= 6:
        problems.append(f"needs 3-6 sentences, got {n}")
    if len(text.split()) > MAX_WORDS:
        problems.append(f"too long: {len(text.split())} words (limit {MAX_WORDS})")
    if FORBIDDEN.search(text):
        problems.append("contains headings, bullets or chat phrases")
    return problems


# ---------------------------------------------------------------- re-read of the finished text
def verify_render(rendered, task):
    """Independent second route: check the finished text against the raw task only (nothing from spec_facts).

    The quote must be there exactly once, the direction and limit must agree, and every other number must be one of
    the task's own numbers."""
    problems, text = [], rendered
    unit = "%" if task["unit"].startswith("%") else " " + task["unit"]
    if task["basis"] == Q3B:
        quote = f"“{task['q3b_quote']}” (ICH Q3B(R2), {task['q3b_version']}, page {task['q3b_page']})"
        if text.count(quote) != 1:
            problems.append("the Q3B quote is missing, repeated or not exact")
        text = text.replace(quote, " ")
    # The shared token filter below ignores every "Q<digit>" name, so check the guideline name and the basis wording here.
    phrase = ("ICH Q3B(R2) qualification threshold" if task["basis"] == Q3B
              else "declared by the author for this demonstration, with no public source")
    if phrase not in text:
        problems.append(f"the basis wording '{phrase}' is missing or changed")
    for m in re.finditer(r"\bQ\d+[A-Z]?(?:\(R\d+\))?", text):
        if task["basis"] != Q3B or m.group(0) != "Q3B(R2)":
            problems.append(f"guideline name '{m.group(0)}' is not the one this limit rests on")
    words = {"NMT": ("not more than", "not less than"), "NLT": ("not less than", "not more than")}[task["limit_kind"]]
    if f"{words[0]} {task['limit']}{unit}" not in text:
        problems.append(f"the limit is not written as '{words[0]} {task['limit']}{unit}'")
    if words[1] in text:
        problems.append(f"'{words[1]}' appears, but the limit is {task['limit_kind']}")
    allowed = {task["limit"], task["min"], task["max"], str(task["n"]), str(task["n_outside"])}
    if task["basis"] == Q3B:
        allowed.add(task["mdd"])
    rest = ALLOWED_TOKENS.sub(" ", text)
    for m in re.finditer(r"\d+(?:\.\d+)?", rest):
        if m.group(0) not in allowed:
            problems.append(f"{m.group(0)} is not one of this attribute's numbers")
    counts = {task["n"], task["n_outside"]}
    for m in re.finditer(r"\b(\w+)\s+batch(?:es)?\b", rest, re.I):
        w = m.group(1).lower()
        k = WORD_TO_N.get(w, int(w) if w.isdigit() else None)
        if k is not None and k not in counts:
            problems.append(f"'{m.group(0)}' is not the number of batches with a result or outside the limit")
    return problems


__all__ = ["validate", "verify_render", "render"]
