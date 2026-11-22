"""Checks a P.8.3 stability paragraph sentence by sentence: only allowed sentence shapes, numbers equal to the facts, demo values labelled."""
import re
from collections import namedtuple
from decimal import Decimal

DEMO_LABEL = "illustrative demonstration data"
LABEL_PREFIX = "In " + DEMO_LABEL + ", "
Result = namedtuple("Result", "sentence status code")   # status: ok | unsupported | unrecognised | demo_unlabelled
N = r"(\d+(?:\.\d+)?)"
DEG = "°"

# public sentence shapes: (regex over the whole sentence, fact ids the numbers must equal, in order)
PUBLIC_SHAPES = [
    ("shelf_life", r"The proposed shelf life is %s months when stored at %s%sC to %s%sC\." % (N, N, DEG, N, DEG),
     ("shelf_life_months", "storage_low", "storage_high")),
    ("storage", r"Store at %s%sC to %s%sC\." % (N, DEG, N, DEG), ("storage_low", "storage_high")),
    ("excursion", r"Excursions are permitted from %s%sC to %s%sC\." % (N, DEG, N, DEG), ("excursion_low", "excursion_high")),
    ("study_length", r"Stability was demonstrated for %s months at long-term conditions and %s months at accelerated conditions\." % (N, N),
     ("long_term_months", "accel_months")),
]
NO_CHANGE = re.compile(r"^No significant change was observed(?: in [^.]+)?\.$")


def split_sentences(text):
    """Split a paragraph into sentences (a full stop followed by space)."""
    return [s for s in re.split(r"(?<=\.)\s+", text.strip()) if s]


def _same(a, b):
    return Decimal(str(a)) == Decimal(str(b))


def _demo_shapes(demo):
    """Demo sentence regexes built from the real condition/attribute names, so unknown names never match."""
    if not demo:
        return []
    cond = "|".join(re.escape(c) for c in sorted({c for c, _ in demo}, key=len, reverse=True))
    attr = "|".join(re.escape(a) for a in sorted({a for _, a in demo}, key=len, reverse=True))
    head = r"(?P<a>%s) at (?P<c>%s) " % (attr, cond)
    return [
        ("demo_range", head + r"ranged from %s to %s over %s time points\." % (N, N, N)),
        ("demo_none_outside", head + r"had none of its %s results outside the limit\." % N),
        ("demo_some_outside", head + r"had %s of its %s results outside the limit\." % (N, N)),
    ]


def check_sentence(sentence, facts):
    """Result for one sentence."""
    pub, demo = facts["public"], facts["demo"]
    for name, rx, slots in PUBLIC_SHAPES:
        m = re.match("^" + rx + "$", sentence)
        if m:
            ok = all(_same(pub[s], v) for s, v in zip(slots, m.groups()))
            return Result(sentence, "ok" if ok else "unsupported", name if ok else name + ":number_differs_from_fact")
    if NO_CHANGE.match(sentence):
        ok = bool(facts.get("no_significant_change"))
        return Result(sentence, "ok" if ok else "unsupported", "no_change" if ok else "no_change:no_fact")
    labelled = sentence.startswith(LABEL_PREFIX)
    rest = sentence[len(LABEL_PREFIX):] if labelled else sentence
    for name, rx in _demo_shapes(demo):
        m = re.match("^" + rx + "$", rest)
        if not m:
            continue
        f = demo[(m.group("c"), m.group("a"))] if (m.group("c"), m.group("a")) in demo else None
        nums = m.groups()[2:]
        if f is None:
            return Result(sentence, "unsupported", name + ":no_such_fact")
        want = {"demo_range": (f.min, f.max, f.n), "demo_none_outside": (f.n,),
                "demo_some_outside": (f.n_outside, f.n)}[name]
        if name == "demo_none_outside" and f.n_outside != 0:
            return Result(sentence, "unsupported", name + ":some_are_outside")
        if name == "demo_some_outside" and f.n_outside == 0:
            return Result(sentence, "unsupported", name + ":none_are_outside")
        if not all(_same(w, v) for w, v in zip(want, nums)):
            return Result(sentence, "unsupported", name + ":number_differs_from_fact")
        if not labelled:
            return Result(sentence, "demo_unlabelled", name + ":missing '" + DEMO_LABEL + "'")
        return Result(sentence, "ok", name)
    return Result(sentence, "unrecognised", "no_shape")


def check_paragraph(text, facts):
    """List of Result, one per sentence."""
    return [check_sentence(s, facts) for s in split_sentences(text)]


def paragraph_ok(text, facts):
    """True only if the paragraph has sentences and every one is ok."""
    results = check_paragraph(text, facts)
    return bool(results) and all(r.status == "ok" for r in results)
