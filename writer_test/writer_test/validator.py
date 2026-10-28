"""Deterministic checks on the model's paragraph. No model is involved here.

A draft passes only if every number is a placeholder bound to a known fact,
its wording agrees with the facts computed in code, and it has the right shape.
"""
import re

PLACEHOLDER = re.compile(r"\[\[([a-z_]+)\]\]")
# Regulatory identifiers that legitimately contain digits.
ALLOWED_TOKENS = re.compile(
    r"\bICH\s+Q\d+[A-Z]?(\(R\d+\))?|\bQ\d+[A-Z]?(\(R\d+\))?\b|\b\d+\.\d+\.[A-Z]\.\d+(\.\d+)*\b")
NUMBER_WORDS = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"dozen|twice|half|zero)\b", re.I)
# Placeholders that stand for a value. "a [[mean_change]]." reads as "a 0.4%." once
# rendered, so a value placeholder after "a" must be followed by a noun it modifies.
VALUE_AS_NOUN = re.compile(r"\b(a|an)\s+\[\[(spec|initial_range|final_range|max_value|min_value|mean_change)\]\]"
                           r"(?!\s+(mean|absolute|overall|net|change|increase|decrease|rise|decline|reduction|difference))",
                           re.I)
BATCHES_WITHOUT_NOUN = re.compile(r"\[\[n_batches\]\](?!\s+batch)", re.I)

# Role words claim something about one result. Each must sit next to a placeholder
# whose fact really has that role (computed from the data, see facts.py).
ROLE_WORDS = {
    "max": re.compile(r"^(highest|maximum|peak|greatest|largest)$", re.I),
    "min": re.compile(r"^(lowest|minimum|smallest)$", re.I),
    "initial": re.compile(r"^(initial|initially|first|baseline|starting)$", re.I),
    "final": re.compile(r"^(final|finally|last|latest)$", re.I),
}
ROLE_NAMES = {"max": "the highest result", "min": "the lowest result",
              "initial": "from the first time point", "final": "from the last time point"}
# Batches and time points may only enter the text through placeholders. Digits are
# already banned; this catches batches named in words ("the second batch").
BATCH_IN_WORDS = re.compile(r"\b(first|second|third|fourth|fifth|last|final|other|remaining|later|earlier|"
                            r"latter|former|same|another)\s+(batch|batches|lot|lots)\b", re.I)
CLAUSE_SPLIT = re.compile(r",|;|:|\band\b|\bwhile\b|\bwhereas\b|\bbut\b", re.I)
TOKEN = re.compile(r"\[\[[a-z_]+\]\]|[A-Za-z]+")


INCREASE = re.compile(r"\b(increas\w*|ris(e|es|ing)|rose|upward)\b", re.I)
DECREASE = re.compile(r"\b(decreas\w*|declin\w*|downward|fell|falling)\b", re.I)
FLAT = re.compile(r"\b(no (meaningful |significant |notable |relevant )?(trend|change)|unchanged|"
                  r"remained (stable|constant|steady)|stable|consistent over time)\b", re.I)
COMPLIANT = re.compile(r"\b(within (the )?(specification|acceptance criteri\w+|limit)s?|"
                       r"met (the )?(specification|acceptance criteri\w+)|compl(y|ied|ies)|conform\w*)\b", re.I)
UNIVERSAL = re.compile(r"\b(all|every|each|throughout|consistently)\b", re.I)
NONCOMPLIANT = re.compile(r"\b(out of specification|OOS|exceed\w*|outside (the )?(specification|"
                          r"acceptance criteri\w+|limit)s?|fail\w*|(did|does) not (meet|comply|conform)|"
                          r"not within (the )?(specification|acceptance criteri\w+|limit)s?)\b", re.I)
FORBIDDEN = re.compile(r"(^|\n)\s*(#|[-*•]\s)|\bas an AI\b|\bI (think|believe)\b", re.I)
# Negated phrases ("no increase", "did not exceed") state the absence of a
# trend or failure, so they are removed before checking for positive claims.
NEGATED_TREND = re.compile(r"\b(no|not|without( any)?|neither|nor)\b[^.;]{0,30}?"
                           r"\b(increas\w*|ris(e|es|ing)|rose|upward|decreas\w*|declin\w*|downward|fell|falling)\b", re.I)
NEGATED_FAILURE = re.compile(r"\b(no|none|not|without|neither|nor)\b[^.;]{0,40}?"
                             r"\b(out of specification|OOS|exceed\w*|outside|fail\w*)\b", re.I)


CONDITION_WORDS = {"accelerated": re.compile(r"\baccelerated\b", re.I),
                   "long-term": re.compile(r"\blong[- ]term\b", re.I),
                   "intermediate": re.compile(r"\bintermediate\b", re.I)}
TIME_WORDS = re.compile(r"\b(years?|annual\w*|yearly|weeks?|weekly|days?|daily|quarters?|decade)\b", re.I)
INFERENCE = re.compile(r"\b(because|due to|caused|attribut\w+|owing to|degradation|hydroly\w+|oxidat\w+|"
                       r"shelf[- ]?life|expiry|re-?test|justif\w+|support\w*|suggest\w*|likely|probabl\w+|"
                       r"indicat\w+ that|demonstrat\w+ that|conclu\w+|therefore|thus)\b", re.I)
FROM_TO = re.compile(r"\bfrom\s+(?:the\s+)?\[\[([a-z_]+)\]\](?:\s+[A-Za-z]+)?\s+to\s+(?:the\s+)?\[\[([a-z_]+)\]\]", re.I)
MOVE_VERB = re.compile(r"\b(increas\w*|decreas\w*|rose|ris(e|es|ing)|fell|falling|declin\w*|drop\w*|chang\w*|shift\w*|"
                       r"mov\w*|grew|grow\w*|reduc\w*|progress\w*)\b", re.I)
ALL_BATCHES = re.compile(r"\b(in|across|for)\s+(all|each|every)\b[^.]{0,30}\bbatch|\b(all|each|every)\s+batch", re.I)


TIMING_SHAPE = re.compile(r"\b(start|beginning|early|earlier|late|later|toward\w*|outset|onset|plateau\w*|"
                          r"level+ed|leveled|stabili[sz]\w*|rapid\w*|sharp\w*|sudden\w*|abrupt\w*|spike\w*|"
                          r"peaked|then|subsequently|afterwards?|thereafter)\b", re.I)
COMPARE = re.compile(r"\b(higher|lower|greater|smaller|larger|less|more|exceed\w*|above|below|than|"
                     r"equal\w*|same as|similar to|compared)\b", re.I)
RESULT_FACTS = {"max_value", "min_value", "initial_range", "final_range", "oos_results", "mean_change"}


# A sentence may start with a plain connecting word or with the test under discussion, nothing else.
# This closes the gap the test-name registry leaves: a test name the registry does not know.
SAFE_OPENERS = set("""the all results result values value data levels level no none one both each across at over in for
throughout overall however notably these this there a an it they mean observed individual while although but and with from
by when as compared based taken together collectively similarly also further additionally furthermore only most some several
every any increases decreases increase decrease change changes stability specification acceptance out within ich
initial final last first highest lowest maximum minimum peak storage average long accelerated""".split())


def opener_problems(text, flags):
    first_attr = re.match(r"[A-Za-z]+", flags.get("attribute") or "")
    first_attr = first_attr.group(0).lower() if first_attr else ""
    problems = []
    for sent in sentences(text):
        m = re.match(r"[A-Za-z]+", sent)
        if not m:
            continue  # starts with a placeholder or bracket
        w = m.group(0).lower()
        if w in SAFE_OPENERS or (first_attr and w[:4] == first_attr[:4]):
            continue
        problems.append(f"sentence starts with '{m.group(0)}', which is not this section's test "
                        f"({flags.get('attribute')}); name only the tested attribute")
    return problems

# --- Second round, from the hand audit of the model's own accepted paragraphs ---
POINT_FACTS = {"max_value", "min_value", "oos_results"}  # one result of one batch, not a range
# "the initial range of [[min_value]]", "initial results ranged from [[max_value]] and ...":
# a single result of one batch called a range, or the initial/final results of all batches.
POINT_AS_RANGE = re.compile(r"\b(?:initial|final)\s+(?:range|results)\b(?:,\s*which)?[^.\[]{0,25}?"
                            r"\[\[(max_value|min_value|oos_results)\]\]", re.I)
LAST_TIMEPOINT = re.compile(r"\b(?:last|final|longest|latest)\s+time[- ]?points?\b", re.I)
# A range placeholder already ends in "at Month N"; saying the time again repeats or contradicts it.
REPEAT_TIME = re.compile(r"\[\[(?:initial_range|final_range)\]\]\s*,?\s*(?:at|in)\s+(?:the\s+)?"
                         r"(?:month\b|(?:first|last|final|initial|longest|baseline|end)\b|\[\[duration\]\])", re.I)
SPAN_CLAIM = re.compile(r"\b(?:rang\w+|remain\w*|stay\w*|stayed|vari\w+|fluctuat\w+)\s+(?:from|between|within|in)\s+(?:the\s+)?"
                        r"\[\[initial_range\]\](?:\s+[A-Za-z]+)?\s+(?:to|and)\s+(?:the\s+)?\[\[final_range\]\]", re.I)
WRONG_SUBJECT_OOS = re.compile(r"\b(?:condition|conditions|product|batch(?:es)?|study)\s+(?:being|was|were|is|are|as|to be)\s+"
                               r"(?:\w+\s+)?(?:out of specification|OOS|failing|failed)\b", re.I)
MEAN_CHANGE_TWICE = re.compile(r"\bmean change\b[^.\[]{0,60}?\b(?:was|were)\s+a\s+(?:mean\s+)?change\s+of\b", re.I)


def binding_problems(text, facts, flags):
    """Checks added after reading the model's own accepted paragraphs by hand."""
    problems = []
    attr = (flags.get("attribute") or "").strip()
    lead = re.sub(r"^(the|a|an)\s+", "", text.strip(), flags=re.I).lower()
    first = attr.split()[0].lower() if attr else ""
    # "Dissolution at [[condition]]" fuses the test name and the storage condition: it reads as a
    # different test ("dissolution at 25C") once the values are filled in.
    if first and attr.lower() not in text.lower() and re.match(
            rf"{re.escape(first)}\s+(?:at|in|under|for)\s+\[\[condition\]\]", lead):
        problems.append(f"names the test only in part and runs it into the storage condition; write it in full: '{attr}'")
    if POINT_AS_RANGE.search(text):
        problems.append("calls the result of one batch a range, or the initial/final results of all batches "
                        "(use [[initial_range]] or [[final_range]] for those)")
    if REPEAT_TIME.search(text):
        problems.append("repeats a time point after [[initial_range]]/[[final_range]], which already end in "
                        "'at Month N'")
    if SPAN_CLAIM.search(text) and not flags.get("ends_span_all", True):
        problems.append("says results ranged from the initial to the final range, but some results lie outside both")
    if MEAN_CHANGE_TWICE.search(text):
        problems.append("says 'mean change' twice in one phrase")
    bare = PLACEHOLDER.sub(" ", text)
    if WRONG_SUBJECT_OOS.search(bare):
        problems.append("says the condition, product or batch is out of specification; only a result can be")
    for sent in sentences(text):
        m = LAST_TIMEPOINT.search(sent)
        if m:
            pts = [p for p in PLACEHOLDER.findall(sent[:m.start()]) if p in POINT_FACTS]
            if len(pts) >= 2 and any("final" not in facts[p]["roles"] for p in pts if p in facts):
                problems.append("puts results from different time points 'at the last time point'")
        for mm in FROM_TO.finditer(sent):
            lead = sent[:mm.start()]
            if MOVE_VERB.search(lead) and not re.search(r"\brang\w*\b", lead[-40:], re.I) and (
                    mm.group(1) in POINT_FACTS or mm.group(2) in POINT_FACTS):
                problems.append("describes a change from or to one batch's single result; "
                                "describe change between [[initial_range]] and [[final_range]]")
    return problems


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _tokens(text):
    return [(m.group(0), m.start()) for m in TOKEN.finditer(text)]


def role_problems(text, facts):
    """Each role word must be nearest to a placeholder that truly has that role.

    Among the role-bearing placeholders in the same clause, the nearest one is
    checked; if the clause has none, the nearest in the sentence. A role word with
    no role-bearing placeholder in its sentence is generic ("the last time point
    tested") and passes."""
    bearing = {k for k, f in facts.items() if f.get("roles") and f["roles"] - {"change"}}
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

    bare = ALLOWED_TOKENS.sub(" ", PLACEHOLDER.sub(" ", text))
    if flags.get("attribute"):
        # The attribute's own name may contain digits ("Dissolution at 30 minutes").
        bare = re.sub(re.escape(flags["attribute"]), " ", bare, flags=re.I)
    if re.search(r"\d", bare):
        problems.append("number written outside a placeholder")
    if NUMBER_WORDS.search(bare):
        problems.append("number written as a word")
    if re.search(r"\]\]\s*(%|percent\b|months?\b|°C)", text, re.I):
        problems.append("unit repeated after a placeholder (the value already carries it)")

    if VALUE_AS_NOUN.search(text):
        problems.append("a value placeholder is used as a noun (write 'a change of [[mean_change]]', "
                        "not 'a [[mean_change]]')")
    if BATCHES_WITHOUT_NOUN.search(text):
        problems.append("[[n_batches]] must be followed by 'batches'")
    if BATCH_IN_WORDS.search(PLACEHOLDER.sub(" ", text)):
        problems.append("names a batch in words (batches come only from placeholders)")
    problems += role_problems(text, facts)

    # Names of things must come from the section, not from the model's memory.
    bare_words = PLACEHOLDER.sub(" ", text)
    attr = (flags.get("attribute") or "").lower()
    for name in flags.get("registry", []):
        if re.search(rf"\b{re.escape(name)}\b", bare_words, re.I) and not (
                name.lower() in attr or attr.startswith(name.lower())):
            problems.append(f"names another test ({name}) in a section about {flags.get('attribute')}")
    problems += opener_problems(text, flags)
    problems += binding_problems(text, facts, flags)
    own = flags.get("condition_type")
    for kind, rx in CONDITION_WORDS.items():
        if own and kind != own and rx.search(bare_words):
            problems.append(f"says '{kind}' in a section stored under {own} conditions")
    for bid in flags.get("batch_ids", []):
        if re.search(rf"\b{re.escape(bid)}\b", bare_words):
            problems.append(f"types batch ID {bid} (batches come only from placeholders)")
    if re.search(r"\bBatch(es)?\s+[A-Z]", bare_words):
        problems.append("types a batch name (batches come only from placeholders)")
    if TIME_WORDS.search(bare_words):
        problems.append("states a time period in words (time points come only from placeholders)")
    if INFERENCE.search(bare_words):
        problems.append("adds a cause, conclusion or shelf-life claim that no fact supports")
    if TIMING_SHAPE.search(bare_words):
        problems.append("describes timing or the shape of the change in words (not computed)")
    for sent in sentences(text):
        res = [m for m in PLACEHOLDER.finditer(sent) if m.group(1) in RESULT_FACTS]
        if len(res) >= 2 and COMPARE.search(sent[res[0].end():res[-1].start()]):
            problems.append("compares two results in words (comparisons are made by code, not the model)")
    months = flags.get("fact_month", {})
    for sent in sentences(text):
        for m in FROM_TO.finditer(sent):
            lead = sent[:m.start()]
            # "ranging from A to B" describes a span of values; "increased from A to B" describes time.
            if re.search(r"\brang\w*\b", lead[-40:], re.I) or not MOVE_VERB.search(lead):
                continue
            a_, b_ = m.group(1), m.group(2)
            if a_ in months and b_ in months and months[a_] >= months[b_]:
                problems.append(f"'from [[{a_}]] to [[{b_}]]' runs backwards in time")
    if ALL_BATCHES.search(bare_words) and not flags.get("batches_agree", True):
        problems.append("claims the trend holds in all batches, but at least one batch differs")

    trend = flags["trend"]
    positive = NEGATED_TREND.sub(" ", text)
    if trend == "increasing" and (DECREASE.search(positive) or FLAT.search(text)):
        problems.append("wording contradicts the computed trend (increasing)")
    if trend == "decreasing" and (INCREASE.search(positive) or FLAT.search(text)):
        problems.append("wording contradicts the computed trend (decreasing)")
    if trend == "no meaningful change" and (INCREASE.search(positive) or DECREASE.search(positive)):
        problems.append("wording claims a trend the data do not show")

    if flags["all_within_spec"]:
        if NONCOMPLIANT.search(NEGATED_FAILURE.sub(" ", text)):
            problems.append("claims a failure, but all results are within specification")
    else:
        if not NONCOMPLIANT.search(text):
            problems.append("does not state that a result is out of specification")
        for s in sentences(text):
            if UNIVERSAL.search(s) and COMPLIANT.search(s):
                problems.append("claims all results comply, but at least one does not")
                break

    n = len(sentences(text))
    words = len(text.split())
    if not 2 <= n <= 5:
        problems.append(f"needs 2-5 sentences, got {n}")
    if words > 130:
        problems.append(f"too long: {words} words (limit 130)")
    if FORBIDDEN.search(text):
        problems.append("contains headings, bullets or chat phrases")
    return problems


def render(text, facts):
    """Replace each placeholder with its value computed in code."""
    return PLACEHOLDER.sub(lambda m: facts[m.group(1)]["value"] if m.group(1) in facts else m.group(0), text)
