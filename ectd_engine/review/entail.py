"""Flags sentences that make a claim (complies, passed, within the range...) which no fact supports; flags go to the reviewer, nothing is rejected."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache

# Words/phrases that make a claim. A sentence with one of these must match a rule below, and the rule's fact check must pass.
CLAIM_PHRASES = (
    r"no new signals?", r"no (?:new )?trends?", r"complies", r"comply", r"complied", r"compliant", r"compliance",
    r"pass(?:es|ed)?", r"(?:below|above|under)(?: the)? limits?", r"exceed(?:s|ed)?(?: the)? limits?", r"exceed(?:s|ed)?",
    r"oos", r"out of specification", r"no issues?", r"no concerns?", r"suitable", r"robust",
    r"within", r"outside", r"consistent", r"stable", r"stability", r"comparable", r"equivalent", r"similar", r"conforms?",
    r"conformed", r"meets?", r"met", r"acceptable", r"satisfactory", r"satisfies", r"unchanged", r"no change", r"no differences?",
    r"trend", r"signals?", r"all results", r"all batches", r"no results?", r"no batch", r"no significant", r"no adverse",
    r"rang(?:e|es|ed)",
)
CLAIM_RE = re.compile(r"\b(" + "|".join(CLAIM_PHRASES) + r")\b", re.IGNORECASE)
QUOTE_RE = re.compile(r"[“\"]([^”\"]*)[”\"]")
SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
NUM = r"-?\d+(?:\.\d+)?"
DASH = r"(?:to|–|—|-)"


def _norm(s):
    return " ".join(unicodedata.normalize("NFKC", s).split())


@lru_cache(maxsize=None)
def stored_quotes():
    """The Q3B retrieval quotes we store (one row per dose band). Only these exact texts may be left unchecked."""
    from ectd_engine.writer.spec_facts import q3b_row_quote
    out = []
    for mdd in ("40", "5", "500"):
        try:
            out.append(_norm(q3b_row_quote(mdd)))
        except (ValueError, KeyError, OSError):
            pass
    return tuple(out)


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


def _range_matches(facts, m):
    """'range from X to Y' needs X == min_value and Y == max_value; 'range of X' needs X to be both (a single value)."""
    x, y = _dec(m.group("x")), _dec(m.group("y")) if m.group("y") else None
    lo, hi = _dec(facts.get("min_value")), _dec(facts.get("max_value"))
    if x is None or lo is None or hi is None:
        return False
    return x == lo and (hi == y if y is not None else hi == lo)


# (pattern, check(facts, match) -> True when a fact supports the sentence)
RULES = (
    (re.compile(r"\bno results? (?:was|were) outside\b", re.I), lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\ball (?:results|batches) (?:complied|comply|were within|met|meet)\b", re.I),
     lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\ball results (?:were )?within\b", re.I), lambda f, m: _zero(f, "n_outside")),
    (re.compile(r"\b(\d+) of (\d+) results (?:was|were) outside the limit\b", re.I), _count_matches),
    (re.compile(r"(?:\bwithin the )?\brang(?:e|ed|es)\b(?: from| of)?\s+(?P<x>" + NUM + r")\s*%?(?:\s*\([^)]*\))?"
                r"(?:\s*" + DASH + r"\s*(?P<y>" + NUM + r")\s*%?)?", re.I), _range_matches),
)


def _unquote(text, quotes):
    """Quote marks are dropped. Quoted text is removed from the check ONLY if it exactly equals a stored quote."""
    def swap(m):
        return " " if _norm(m.group(1)) in quotes else " " + m.group(1) + " "
    return QUOTE_RE.sub(swap, text)


def entail(text, facts, quotes=None):
    """Return the reviewer flags for one paragraph: ["unsupported:<phrase>", ...]. facts = {fact id: value} for this paragraph.
    A claim word with no matching rule is flagged (never passed); a matching rule whose fact says otherwise is flagged too.
    quotes = stored retrieval quotes allowed to be skipped (default: the stored Q3B rows, plus facts["q3b_quote"])."""
    allowed = set(stored_quotes() if quotes is None else map(_norm, quotes))
    if facts.get("q3b_quote"):
        allowed.add(_norm(facts["q3b_quote"]))
    flags = []
    for sent in sentences(_unquote(text, allowed)):
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
