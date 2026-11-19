"""Computes every value for a 3.2.P.5.6 justification paragraph (limit, direction, basis, assumed dose, batch support, Q3B quote) from facts."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ectd_engine.knowledge import cite
from ectd_engine.loaders import lek
from ectd_engine.rules import q3b
from ectd_engine.validator.spec import render
from ectd_engine.writer.batch_facts import LEK_TESTS, NUMBER_WORDS, count_text
from ectd_engine.writer.facts import TEST_REGISTRY, with_unit

Q3B, DECLARED = "q3b_qualification", "declared"
KIND_TEXT = {"NMT": "not more than", "NLT": "not less than"}
BASIS_TEXT = {Q3B: "the ICH Q3B(R2) qualification threshold",
              DECLARED: "declared by the author for this demonstration, with no public source"}
DOC_NAME = "ICH Q3B(R2)"
TASK_KEYS = ("task_id", "section", "product", "attribute", "column", "limit_kind", "limit", "unit", "basis",
             "n", "min", "max", "n_outside")
QUOTE_KEYS = ("q3b_quote", "q3b_page", "q3b_version")


def q3b_row_quote(mdd, full_quote=None):
    """Only the printed qualification row whose dose band holds this dose (text as the PDF prints it, micro sign kept).

    If full_quote (the longer cited text, heading and earlier rows included) is given, the row must be inside it."""
    dose = Decimal(mdd)
    for r in q3b.read_entry(q3b.ENTRY_A):
        if r["kind"] != "qualification":
            continue
        low, low_incl, high, high_incl = q3b.parse_dose(r["max_daily_dose"])
        if (low is None or dose > low or (low_incl and dose == low)) and (high is None or dose < high or (high_incl and dose == high)):
            row = q3b.printed_row(r)
            if full_quote is None:
                return row
            # Compare in Unicode-normal form (micro sign and Greek mu are the same letter) but hand back the cited text itself.
            nf, nr = unicodedata.normalize("NFKC", full_quote), unicodedata.normalize("NFKC", row)
            at = nf.find(nr)
            if at < 0 or len(nf) != len(full_quote):
                raise ValueError(f"the Q3B row for {mdd} mg ({row!r}) is not inside the cited text")
            return full_quote[at:at + len(nr)]
    raise ValueError(f"no qualification row holds {mdd} mg")


def row_of(task):
    """The one row to show for this task: the row of its dose band, cut out of the task's cited text.

    A quote that shows a table row of ANOTHER dose band (and not this dose's row) is refused. Text with no table row
    in it at all is left as it is; the live path (resolve_quote -> narrow_quote) is stricter and demands the row."""
    quote = task["q3b_quote"]
    try:
        return q3b_row_quote(task["mdd"], quote)
    except ValueError:
        norm = unicodedata.normalize("NFKC", quote)
        others = [q3b.printed_row(r) for r in q3b.read_entry(q3b.ENTRY_A) if r["kind"] == "qualification"]
        if any(unicodedata.normalize("NFKC", o) in norm for o in others):
            raise
        return quote


def narrowed(task):
    """The task with only the dose row as its quote (no PDF access; use narrow_quote to also re-verify on the PDF)."""
    return dict(task, q3b_quote=row_of(task)) if task.get("basis") == Q3B else task


@lru_cache(maxsize=None)
def _verified_row(page, row):
    """Prove the one row is word for word on that page of the PDF (cached; the PDF is opened once per row)."""
    return cite.verify(q3b.DOC_ID, int(page), row)


def narrow_quote(task):
    """The task with its Q3B quote cut down to the one row for its dose, re-verified on the PDF page (page and version kept)."""
    if task.get("basis") != Q3B:
        return task
    row = q3b_row_quote(task["mdd"], task["q3b_quote"])  # strict: the dose row must really be in the cited text
    c = _verified_row(str(task["q3b_page"]), row)
    if c.version != task["q3b_version"]:
        raise ValueError(f"task {task['task_id']}: document version {c.version!r} != {task['q3b_version']!r}")
    return dict(task, q3b_quote=row)


def bare_text(n):
    """A count with no noun ("two", "17"), for sentences like "17 of 25 results"."""
    return NUMBER_WORDS.get(n, str(n))


def render_paragraph(text, facts, basis=None):
    """The validator's render, plus two wording repairs made by code: in "X of Y results" the counts lose "batches",
    and a declared basis never follows "resting on" or "set" (it reads ", which is ...")."""
    text = text.replace("[[n_outside]] of [[n_batches]] results", "[[n_outside_bare]] of [[n_batches_bare]] results")
    facts = {k: dict(v) for k, v in facts.items()}
    if "n_outside" in facts and "bare" in facts["n_outside"] and re.search(r"(?:^|[.!?]\s)\[\[n_outside_bare\]\]", text):
        facts["n_outside"]["bare"] = facts["n_outside"]["bare"].capitalize()  # a count that opens a sentence
    if basis == DECLARED:
        text = re.sub(r"(?:,\s*)?\b(?:resting on|rests on|set at|set|based on)\s+\[\[basis\]\]", ", which is [[basis]]", text)
    extra = {f"{k}_bare": {"value": v["bare"]} for k, v in facts.items() if "bare" in v}
    return render(text, {**facts, **extra})


def quote_text(task):
    """The Q3B quote exactly as the PDF check returned it, with its page and document version. Written by code only."""
    return f"“{row_of(task)}” ({DOC_NAME}, {task['q3b_version']}, page {task['q3b_page']})"


def check_task(task):
    """Loud errors for a malformed task (missing key, unknown column, wrong basis, quote missing or present by mistake)."""
    missing = [k for k in TASK_KEYS if k not in task]
    if missing:
        raise ValueError(f"task {task.get('task_id')!r} is missing: {', '.join(missing)}")
    tid = task["task_id"]
    if task["column"] not in lek.COLUMNS or lek.COLUMNS[task["column"]][0] != task["attribute"]:
        raise ValueError(f"task {tid}: attribute {task['attribute']!r} does not match column {task['column']!r}")
    if task["limit_kind"] not in KIND_TEXT:
        raise ValueError(f"task {tid}: limit_kind must be NMT or NLT")
    if task["basis"] not in BASIS_TEXT:
        raise ValueError(f"task {tid}: basis must be one of {tuple(BASIS_TEXT)}")
    try:
        lim, lo, hi = Decimal(task["limit"]), Decimal(task["min"]), Decimal(task["max"])
    except (InvalidOperation, TypeError):
        raise ValueError(f"task {tid}: limit, min and max must be decimal numbers written as text") from None
    if not (lim.is_finite() and lo.is_finite() and hi.is_finite()) or lo > hi:
        raise ValueError(f"task {tid}: min must not be above max")
    if not isinstance(task["n"], int) or isinstance(task["n"], bool) or task["n"] < 1:
        raise ValueError(f"task {tid}: n must be an int >= 1")
    if not isinstance(task["n_outside"], int) or not 0 <= task["n_outside"] <= task["n"]:
        raise ValueError(f"task {tid}: n_outside must be an int between 0 and n")
    has_q = [k for k in ("mdd", *QUOTE_KEYS) if task.get(k) not in (None, "")]
    if task["basis"] == Q3B:
        if len(has_q) != 4:
            raise ValueError(f"task {tid}: a q3b task needs mdd and the quote, page and version (resolve it first)")
        try:
            if Decimal(task["mdd"]) <= 0:
                raise ValueError(f"task {tid}: mdd must be above 0")
        except InvalidOperation:
            raise ValueError(f"task {tid}: mdd must be a decimal number written as text") from None
        try:
            row_of(task)
        except ValueError as e:
            raise ValueError(f"task {tid}: the Q3B quote must hold the one row whose dose band holds {task['mdd']} mg ({e})") from None
    elif has_q:
        raise ValueError(f"task {tid}: a declared task must not carry mdd or a Q3B quote ({', '.join(has_q)})")


def compute_spec_facts(task):
    """Return (facts, flags, required). Every value is text built here; nothing is rounded (values are shown as stored)."""
    check_task(task)
    unit, q3b = task["unit"], task["basis"] == Q3B
    spec = {
        "limit_kind": (KIND_TEXT[task["limit_kind"]], "direction of the limit", set()),
        "limit": (with_unit(task["limit"], unit), "the acceptance limit", set()),
        "basis": (BASIS_TEXT[task["basis"]], "what the limit rests on", set()),
        "n_batches": (count_text(task["n"]), "number of batches with a result", set()),
        "min_value": (with_unit(task["min"], unit), "lowest result", {"min"}),
        "max_value": (with_unit(task["max"], unit), "highest result", {"max"}),
    }
    if q3b:
        spec["mdd"] = (f"{task['mdd']} mg", "maximum daily dose; an ASSUMPTION, not a source value", set())
        spec["q3b_quote"] = (quote_text(task), "the Q3B text and page the limit comes from", set())
    if task["n_outside"]:
        spec["n_outside"] = (count_text(task["n_outside"]), "number of batches with a result outside the limit", set())
    facts = {k: {"value": v, "label": label, "roles": roles} for k, (v, label, roles) in spec.items()}
    facts["n_batches"]["bare"] = bare_text(task["n"])
    if task["n_outside"]:
        facts["n_outside"]["bare"] = bare_text(task["n_outside"])
    required = ["limit_kind", "limit", "basis", "n_batches", "min_value", "max_value"]
    required += ["mdd", "q3b_quote"] if q3b else []
    required += ["n_outside"] if task["n_outside"] else []
    flags = {
        "attribute": task["attribute"], "registry": sorted(set(LEK_TESTS) | set(TEST_REGISTRY)),
        "basis": task["basis"], "limit_kind": task["limit_kind"], "n_outside": task["n_outside"],
        "quote": row_of(task) if q3b else "", "required": required,
    }
    return facts, flags, required


def task_from_justification(j, column, mdd=None, task_id=None, product="Lek tablets"):
    """A task dict from a p56 Justification (the quote fields are added by resolve_quote)."""
    task = {"task_id": task_id or f"p56_{column}", "section": "3.2.P.5.6", "product": product,
            "attribute": j.test, "column": column, "limit_kind": j.limit_kind, "limit": str(j.limit), "unit": j.unit,
            "basis": j.basis, "n": j.n, "min": str(j.minimum), "max": str(j.maximum), "n_outside": j.outside}
    if j.basis == Q3B:
        task["mdd"] = str(mdd)
    return task


def resolve_quote(task, live, planted=False):
    """Fill the Q3B quote, page and version from the live p56 result for this dose; refuse a stale or wrong task.

    live: {mdd text: {column: Justification}}. The task's frozen numbers must equal the live ones, so an old
    task file cannot quietly describe other data. planted=True lets n_outside differ (a planted test case)."""
    out = dict(task)
    j = live.get(task.get("mdd") or "40", {}).get(task["column"])
    if j is None:
        raise ValueError(f"task {task['task_id']}: no live result for column {task['column']!r} at mdd {task.get('mdd')!r}")
    want = task_from_justification(j, task["column"], task.get("mdd"), task["task_id"], task["product"])
    for key in ("attribute", "limit_kind", "limit", "unit", "basis", "n", "min", "max") + (() if planted else ("n_outside",)):
        if task[key] != want[key]:
            raise ValueError(f"task {task['task_id']}: {key} is {task[key]!r} but the live data says {want[key]!r}")
    if task["basis"] == Q3B:
        out["q3b_quote"], out["q3b_page"], out["q3b_version"] = j.quote, str(j.page), j.doc_version
        out = narrow_quote(out)
    return out


def render_support(task):
    """The batch-support row as markdown, written by code."""
    return "\n".join(["| Attribute | Limit | Basis | n | min | max | outside limit |", "|---|---|---|---|---|---|---|",
                      f"| {task['attribute']} | {task['limit_kind']} {with_unit(task['limit'], task['unit'])} | "
                      f"{'Q3B qualification threshold, assumed dose ' + task['mdd'] + ' mg' if task['basis'] == Q3B else 'declared (no public source)'}"
                      f" | {task['n']} | {with_unit(task['min'], task['unit'])} | {with_unit(task['max'], task['unit'])} | {task['n_outside']} |"])
