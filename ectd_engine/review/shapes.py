"""The sentence forms the writer is allowed to produce, each with a fact check; a sentence that fits none of them is not trusted."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache

# ---- masking: numbers and batch ids are replaced by tokens so one regex covers every value -------------------------------
_ID = r"[A-Za-z0-9-]*\d[A-Za-z0-9-]*"                       # a batch id has at least one digit
_IDS = _ID + r"(?:(?:, | and )" + _ID + r")*"
BREF = re.compile(r"\(Batch(?:es)? (" + _IDS + r")\)")        # "(Batch 7)" / "(Batches 4, 5 and 6)"
BLIST = re.compile(r"\bBatch(?:es)? (" + _IDS + r")")        # "Batches 4, 5 and 6" (no brackets)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _count_ids(s):
    return len(re.split(r", | and ", s))


def mask(sentence):
    """(masked text, numbers in order, [ids per bracketed batch ref], [ids per bare batch list])."""
    brefs, blists = [], []

    def b1(m):
        brefs.append(_count_ids(m.group(1)))
        return "<B>"

    def b2(m):
        blists.append(_count_ids(m.group(1)))
        return "<L>"
    s = BLIST.sub(b2, BREF.sub(b1, sentence))
    nums = NUMBER.findall(s)
    return NUMBER.sub("<n>", s), nums, brefs, blists


def _norm(s):
    return " ".join(unicodedata.normalize("NFKC", s).split())


@lru_cache(maxsize=None)
def stored_quotes():
    """The Q3B retrieval quotes we store (one row per dose band). Only these exact texts may appear inside a quote."""
    from ectd_engine.writer.spec_facts import q3b_row_quote
    out = []
    for mdd in ("40", "5", "500"):
        try:
            out.append(_norm(q3b_row_quote(mdd)))
        except (ValueError, KeyError, OSError):
            pass
    return tuple(out)


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _same(facts, key, value):
    a, b = _dec(facts.get(key)), _dec(value)
    return a is not None and b is not None and a == b


# ---- the shapes ---------------------------------------------------------------------------------------------------------
class Shape:
    """name; regex over the masked sentence (or the raw one if raw=True); slots = fact ids the numbers must equal, in order;
    extra = optional further check(facts, ctx) -> bool."""

    def __init__(self, name, body, slots=(), extra=None, raw=False):
        self.name, self.slots, self.extra, self.raw = name, tuple(slots), extra, raw
        self.rx = re.compile("^" + body + "$")

    def match(self, sentence, ctx):
        """None = this is not the form; (True, groups) = the form and the facts agree; (False, groups) = the form, but a fact disagrees."""
        m = self.rx.match(sentence if self.raw else ctx["masked"])
        if not m:
            return None
        ok = True if self.raw else (len(ctx["nums"]) == len(self.slots)
                                    and all(_same(ctx["facts"], s, v) for s, v in zip(self.slots, ctx["nums"])))
        return bool(ok and (self.extra is None or self.extra(m, ctx))), m.groupdict()


A = r"(?P<a>[A-Za-z][A-Za-z0-9]*(?: [A-Za-z0-9]+){0,3})"     # an attribute name such as "Total impurities"
PROD = r"(?P<p>[A-Z][A-Za-z0-9 -]*?)"
OPT_B = r"(?: <B>)?"
PCT = r"<n>%"
FROM_TO = "from " + PCT + OPT_B + " to " + PCT + OPT_B
LOHI = ("min_value", "max_value")


def _same_min_max(m, ctx):   # "a range of X%" is one value only: the slot ties X to the lowest result, this ties it to the highest too
    return _same(ctx["facts"], "max_value", ctx["facts"].get("min_value"))


def _direction(m, ctx):
    d, kind = m.group("d"), ctx["facts"].get("limit_kind")
    return kind is None or (d == "less") == (kind == "NLT")


def _excluded_open(m, ctx):
    return bool(ctx["brefs"]) and _same(ctx["facts"], "n_excluded", ctx["brefs"][0])


def _excluded_list(m, ctx):
    return bool(ctx["blists"]) and _same(ctx["facts"], "n_excluded", ctx["blists"][0])


def _none_outside(m, ctx):
    return _same(ctx["facts"], "n_outside", 0)


def _q3b(m, ctx):
    f = ctx["facts"]
    q3b_page = f.get("q3b_page")
    return (_same(f, "limit", m.group("limit")) and _same(f, "mdd", m.group("mdd"))
            and _norm(m.group("q")) in ctx["quotes"]
            and (q3b_page is None or _same(f, "q3b_page", m.group("page")))
            and _direction(m, ctx))


SUBJECTS = (("attr_n", A + "(?: results)? for <n> batch(?:es)?", ("n_batches",)), ("results", "The results", ()))
RANGES = (
    ("ranged", "ranged " + FROM_TO, LOHI, None),
    ("showed_range", "(?:showed|exhibited|displayed|presented) a range " + FROM_TO, LOHI, None),
    ("assessed_showing", "(?:were|was) (?:assessed|determined|analyzed), (?:showing|exhibiting|yielding) a range " + FROM_TO, LOHI, None),
    ("spanned_from", "spanned " + FROM_TO, LOHI, None),
    ("spanned_dash", r"(?:spanned|covered) the range <n>[–-]<n>%", LOHI, None),
    ("within_dash", r"(?:was|were) found to be within the range <n>[–-]<n>%", LOHI, None),
    ("range_single", r"(?:showed|exhibited) a range of <n>%", ("min_value",), _same_min_max),
    ("assessed_only", "(?:were|was) (?:assessed|determined|analyzed)", (), None),
)
TAILS = (("", "", ()), ("mean", ", with a mean of <n>%", ("mean_value",)), ("mean_alt", ", (?:presenting|yielding) a mean of <n>%", ("mean_value",)))

SENTENCE_SHAPES = [
    # P.5.4 opening
    Shape("opening", "Batch analysis results for (?P<a>[A-Za-z][A-Za-z0-9 ]*?) of " + PROD + r" are presented below for <n> batch(?:es)?\.",
          ("n_batches",)),
    Shape("excluded_open", r"Results for <n> batch(?:es)? <B> are shown as excluded \(quarantined\)\.", ("n_excluded",), _excluded_open),
    # P.5.4 discussion: how many batches, range, mean, highest/lowest, excluded
    Shape("obtained", A + r"(?: results)? (?:were|was) (?:obtained|determined|assessed|analyzed) for <n> batch(?:es)?\.", ("n_batches",)),
    Shape("mean_then_range", A + r" for <n> batch(?:es)? had a mean of <n>%, with results ranging " + FROM_TO + r"\.",
          ("n_batches", "mean_value") + LOHI),
    Shape("single_range_hilo", r"The results spanned the range <n>%, exhibiting a lowest result of <n>%" + OPT_B
          + r" and a highest result of <n>%" + OPT_B + r"\.", ("min_value", "min_value", "max_value"), _same_min_max),
    Shape("mean_only", r"The mean of the results was <n>%\.", ("mean_value",)),
    Shape("high_low", r"The highest result(?: obtained| observed)? was <n>%" + OPT_B + r" and the lowest result was <n>%" + OPT_B + r"\.",
          ("max_value", "min_value")),
    Shape("low_high", r"The lowest result was <n>%" + OPT_B + r" and the highest result was <n>%" + OPT_B + r"\.", ("min_value", "max_value")),
    Shape("high_low_value", r"The highest observed value was <n>%" + OPT_B + r" and the lowest observed value was <n>%" + OPT_B + r"\.",
          ("max_value", "min_value")),
    Shape("excluded_list", r"(?:The results for |Results for )?<n> batch(?:es)?, <L>, (?:were|was) quarantined and are not included"
          r"(?: in this analysis)?\.", ("n_excluded",), _excluded_list),
    # P.5.6: criterion (declared or Q3B basis), results, outside count
    Shape("criterion_declared", "The acceptance criterion for " + A + r" is not (?P<d>less|more) than <n>%, which is declared by the author "
          r"for this demonstration, with no public source\.", ("limit",), _direction),
    Shape("criterion_q3b", "The acceptance criterion for " + A + r" is not (?P<d>less|more) than (?P<limit>\d+(?:\.\d+)?)%, set at the "
          r"ICH Q3B\(R2\) qualification threshold for an assumed maximum daily dose of (?P<mdd>\d+(?:\.\d+)?) mg: "
          "[“\"](?P<q>.+)[”\"] " r"\(ICH Q3B\(R2\), Step [^,()]*, page (?P<page>\d+)\)\.", extra=_q3b, raw=True),
    Shape("none_outside", r"No result was outside the limit\.", (), _none_outside),
    Shape("outside_count", r"<n> of <n> results (?:was|were) outside the limit\.", ("n_outside", "n_batches")),
]
for _sn, _sb, _ss in SUBJECTS:
    for _rn, _rb, _rs, _rx in RANGES:
        for _tn, _tb, _ts in TAILS:
            SENTENCE_SHAPES.append(Shape(f"{_sn}+{_rn}{'+' + _tn if _tn else ''}", _sb + " " + _rb + _tb + r"\.", _ss + _rs + _ts, _rx))


def classify(sentence, facts, quotes):
    """("ok", shape) | ("unsupported", shape) | ("unrecognised", None) for one sentence."""
    masked, nums, brefs, blists = mask(sentence)
    ctx = {"masked": masked, "nums": nums, "brefs": brefs, "blists": blists, "facts": facts, "quotes": quotes}
    failed = None
    for shape in SENTENCE_SHAPES:
        got = shape.match(sentence, ctx)
        if got is None:
            continue
        ok, groups = got
        want = _norm(facts.get("attribute") or "").lower()   # when the caller knows the attribute (its heading), the sentence must name it
        if ok and want and groups.get("a") is not None:
            ok = re.sub(r" results$", "", _norm(groups["a"]).lower()) in (want, "results")
        if ok:
            return "ok", shape, groups
        failed = failed or (shape, groups)
    if failed:
        return "unsupported", failed[0], failed[1]
    return "unrecognised", None, {}


# ---- Module 2.3 (T-071): a SEPARATE closed set for the 2.3 writer; the P.5 / P.8.3 set above is not touched ------------------
# Each form is fixed text with fields. {n} = one number, {u} = the unit written right after it, {test} {attr} {cond} {kind} = a word
# from a short list the task supplies. A rendered sentence must match one form COMPLETELY; anything else is "unrecognised".
M23_LABEL = "In illustrative demonstration data, "
M23_UNIT_TEXT = ("% label claim", "% area", "% dissolved", "%")          # longest first
M23_TEMPLATES = {
    "shelf": "The proposed shelf life is {n} months when stored at {n}°C to {n}°C.",
    "excursion": "Excursions are permitted from {n}°C to {n}°C.",
    "study": "Stability was demonstrated for {n} months at long-term conditions and {n} months at accelerated conditions.",
    "spec_intro": M23_LABEL + "the drug product specification lists these tests and acceptance criteria.",
    "spec_row": "{test}: {kind} {n}{u}",
    "result": M23_LABEL + "{attr} under {cond} conditions ranged from {n}{u} to {n}{u}.",
}
_FIELD = re.compile(r"\{(n|u|test|attr|cond|kind)\}")


@lru_cache(maxsize=None)
def _m23_regex(name, words):
    """Compiled full-match regex of one form; words = ((field, (allowed words...)), ...). An empty list for a field matches nothing."""
    allowed = dict(words)
    out, pos, count = [], 0, {}
    text = M23_TEMPLATES[name]
    for m in _FIELD.finditer(text):
        out.append(re.escape(text[pos:m.start()]))
        f = m.group(1)
        count[f] = count.get(f, 0) + 1
        g = f"{f}{count[f]}"
        if f == "n":
            out.append(r"(?P<%s>\d+(?:\.\d+)?)" % g)
        elif f == "u":
            out.append(r"(?P<%s>%s)" % (g, "|".join(re.escape(u) for u in M23_UNIT_TEXT)))
        else:
            alts = sorted(allowed.get(f, ()), key=len, reverse=True)
            out.append(r"(?P<%s>%s)" % (g, "|".join(re.escape(a) for a in alts) if alts else r"(?!)"))
        pos = m.end()
    out.append(re.escape(text[pos:]))
    return re.compile("^" + "".join(out) + "$")


def m23_classify(sentence, names, only=None):
    """(form name, groups) when the rendered sentence matches one 2.3 form completely, else None. names = {"test": [...], "attr": [...], ...}."""
    words = tuple(sorted((k, tuple(v)) for k, v in names.items()))
    for name in (only or M23_TEMPLATES):
        m = _m23_regex(name, words).match(sentence)
        if m:
            return name, m.groupdict()
    return None


def m23_vocabulary(task_words=()):
    """Every word a 2.3 sentence may hold: the words of the fixed forms plus the words the task supplies. The ONLY allowlist for claim words."""
    vocab = set(re.findall(r"[A-Za-z][A-Za-z-]*", _FIELD.sub(" ", " ".join(M23_TEMPLATES.values()))))
    for w in task_words:
        vocab.update(re.findall(r"[A-Za-z][A-Za-z-]*", w))
    vocab.update(("NLT", "NMT"))
    vocab.update(w for u in M23_UNIT_TEXT for w in re.findall(r"[A-Za-z]+", u))
    return vocab


def m23_unknown_words(text, vocab):
    """Words of text that are not in the allowed vocabulary (empty list = no claim beyond the forms)."""
    return sorted({w for w in re.findall(r"[A-Za-z][A-Za-z-]*", text) if w not in vocab})
