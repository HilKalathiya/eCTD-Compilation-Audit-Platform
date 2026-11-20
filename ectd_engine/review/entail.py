"""Flags sentences that make a claim (complies, within, no new signals...) which no fact supports; flags go to the reviewer, nothing is rejected."""
import re
from decimal import Decimal, InvalidOperation

# Words/phrases that make a claim. A sentence with one of these must match a rule below, and the rule's fact check must pass.
CLAIM_PHRASES = (
    r"no new signals?", r"no (?:new )?trends?", r"no trend", r"complies", r"comply", r"complied", r"compliant", r"compliance",
    r"within", r"outside", r"consistent", r"stable", r"stability", r"comparable", r"equivalent", r"similar", r"conforms?",
    r"conformed", r"meets?", r"met", r"acceptable", r"satisfactory", r"satisfies", r"unchanged", r"no change", r"no differences?",
    r"trend", r"signals?", r"all results", r"all batches", r"no result", r"no batch", r"no significant", r"no adverse",
)
CLAIM_RE = re.compile(r"\b(" + "|".join(CLAIM_PHRASES) + r")\b", re.IGNORECASE)
QUOTE_RE = re.compile(r"[“\"][^”\"]*[”\"]")   # a quoted source text is not our claim
SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def sentences(text):
    """Split a paragraph into sentences (a full stop inside a number like 0.7 does not split)."""
    return [s.strip() for s in SPLIT_RE.split(text) if s.strip()]


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _zero(facts, key):
    d = _dec(facts.get(key))
    return d is not None and d == 0


def _count_matches(facts, m):
    """'N of M results were outside the limit' must equal n_outside and n_batches."""
    n, total = _dec(m.group(1)), _dec(m.group(2))
    return (n is not None and _dec(facts.get("n_outside")) == n
            and (facts.get("n_batches") is None or _dec(facts.get("n_batches")) == total))


# (pattern, check(facts, match) -> True when a fact supports the sentence)
RULES = (
    (re.compile(r"\bno results? (?:was|were) outside\b", re.I), lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\ball (?:results|batches) (?:complied|comply|were within|met|meet)\b", re.I), lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\ball results (?:were )?within\b", re.I), lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\b(\d+) of (\d+) results (?:was|were) outside the limit\b", re.I), _count_matches),
)


def entail(text, facts):
    """Return the reviewer flags for one paragraph: ["unsupported:<phrase>", ...]. facts = {fact id: value} for this paragraph.
    A claim word with no matching rule is flagged (never passed); a matching rule whose fact says otherwise is flagged too."""
    flags = []
    for sent in sentences(QUOTE_RE.sub(" ", text)):
        claim = CLAIM_RE.search(sent)
        if not claim:
            continue
        # every claim word in the sentence must sit inside a rule match that is supported by facts
        spans = []
        for pat, check in RULES:
            for m in pat.finditer(sent):
                if check(facts, m):
                    spans.append(m.span())
        for c in CLAIM_RE.finditer(sent):
            if not any(a <= c.start() and c.end() <= b for a, b in spans):
                flags.append("unsupported:" + c.group(1).lower())
                break
    return flags
