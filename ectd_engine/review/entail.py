"""Gate for claims: a sentence is trusted only if it fits a known writer shape AND its numbers equal the placed facts; everything else is flagged for the reviewer."""
import re
from decimal import Decimal, InvalidOperation

from ectd_engine.review.shapes import _norm, classify, stored_quotes  # noqa: F401  (stored_quotes is re-exported)

# Claim words are only an extra label on a flag ("claim:<word>"); they are NOT what decides.
CLAIM_PHRASES = (
    r"no new signals?", r"no (?:new )?trends?", r"complies", r"comply", r"complied", r"compliant", r"compliance",
    r"pass(?:es|ed)?", r"(?:below|above|under)(?: the)? limits?", r"exceed(?:s|ed)?(?: the)? limits?", r"exceed(?:s|ed)?",
    r"oos", r"out of specification", r"no issues?", r"no concerns?", r"suitable", r"robust",
    r"within", r"outside", r"consistent", r"stable", r"stability", r"comparable", r"equivalent", r"similar", r"conforms?",
    r"conformed", r"meets?", r"met", r"acceptable", r"satisfactory", r"satisfies", r"unchanged", r"no change", r"no differences?",
    r"trend", r"signals?", r"all results", r"all batches", r"no results?", r"no batch", r"no significant", r"no adverse",
)
CLAIM_RE = re.compile(r"\b(" + "|".join(CLAIM_PHRASES) + r")\b", re.IGNORECASE)
SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
HEADING_RE = re.compile(r"^(?:3\.2\.P(?:\.\d+)+ )?[A-Z][A-Za-z0-9 ]{0,60}$")
ROW_RE = re.compile(r"^([A-Za-z0-9-]+)\t(\d+(?:\.\d+)?)\t([^\t\d]{1,12})$")
ROW_HEAD = "Batch\tValue\tUnit"
ROW_EXCLUDED_RE = re.compile(r"^[A-Za-z0-9-]*\d[A-Za-z0-9-]*\texcluded \(quarantined\)\t-$")   # the row of an excluded batch


def sentences(text):
    """Split a paragraph into sentences (a full stop inside a number like 0.7 does not split)."""
    return [s.strip() for s in SPLIT_RE.split(text) if s.strip()]


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _claim_label(text):
    m = CLAIM_RE.search(text)
    return ["claim:" + m.group(1).lower()] if m else []


def _unrecognised(text):
    return ["unrecognised:" + text[:40]] + _claim_label(text)


def entail(text, facts, quotes=None, kind="p"):
    """Return the reviewer flags for one text unit. facts = {fact id: value text} placed in this unit.
    kind "p" = paragraph, "h" = heading, "row" = table row.
    Flags: "unrecognised:<first 40 chars>" (fits no shape; plus "claim:<word>" if it has a claim word) and
    "unsupported:<shape>" (fits a shape but a number or count disagrees with the facts)."""
    if kind == "h":
        return [] if HEADING_RE.match(text) and not CLAIM_RE.search(text) else _unrecognised(text)
    if kind == "row":
        m = ROW_RE.match(text)
        known = {_dec(v) for v in facts.values()} - {None}
        return [] if text == ROW_HEAD or ROW_EXCLUDED_RE.match(text) or (m and _dec(m.group(2)) in known) else _unrecognised(text.replace("\t", " "))
    allowed = set(stored_quotes() if quotes is None else map(_norm, quotes))
    if facts.get("q3b_quote"):
        allowed.add(_norm(facts["q3b_quote"]))
    flags = []
    for sent in sentences(text):
        status, shape, groups = classify(sent, facts, allowed)
        if status == "ok" and any(CLAIM_RE.search(groups.get(k) or "") for k in ("a", "p")):
            status = "unsupported"   # a claim word hidden in the attribute/product slot
        if status == "unrecognised":
            flags += _unrecognised(sent)
        elif status == "unsupported":
            flags.append("unsupported:" + shape.name)
    return flags
