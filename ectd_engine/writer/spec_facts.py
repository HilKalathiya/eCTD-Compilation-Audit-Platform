"""Computes every value for a 3.2.P.5.6 justification paragraph (limit, direction, basis, assumed dose, batch support, Q3B quote) from facts."""
from decimal import Decimal, InvalidOperation

from ectd_engine.loaders import lek
from ectd_engine.writer.batch_facts import LEK_TESTS, count_text
from ectd_engine.writer.facts import TEST_REGISTRY, with_unit

Q3B, DECLARED = "q3b_qualification", "declared"
KIND_TEXT = {"NMT": "not more than", "NLT": "not less than"}
BASIS_TEXT = {Q3B: "the ICH Q3B(R2) qualification threshold",
              DECLARED: "declared by the author for this demonstration, with no public source"}
DOC_NAME = "ICH Q3B(R2)"
TASK_KEYS = ("task_id", "section", "product", "attribute", "column", "limit_kind", "limit", "unit", "basis",
             "n", "min", "max", "n_outside")
QUOTE_KEYS = ("q3b_quote", "q3b_page", "q3b_version")


def quote_text(task):
    """The Q3B quote exactly as the PDF check returned it, with its page and document version. Written by code only."""
    return f"“{task['q3b_quote']}” ({DOC_NAME}, {task['q3b_version']}, page {task['q3b_page']})"


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
    required = ["limit_kind", "limit", "basis", "n_batches", "min_value", "max_value"]
    required += ["mdd", "q3b_quote"] if q3b else []
    required += ["n_outside"] if task["n_outside"] else []
    flags = {
        "attribute": task["attribute"], "registry": sorted(set(LEK_TESTS) | set(TEST_REGISTRY)),
        "basis": task["basis"], "limit_kind": task["limit_kind"], "n_outside": task["n_outside"],
        "quote": task["q3b_quote"] if q3b else "", "required": required,
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
    return out


def render_support(task):
    """The batch-support row as markdown, written by code."""
    return "\n".join(["| Attribute | Limit | Basis | n | min | max | outside limit |", "|---|---|---|---|---|---|---|",
                      f"| {task['attribute']} | {task['limit_kind']} {with_unit(task['limit'], task['unit'])} | "
                      f"{'Q3B qualification threshold, assumed dose ' + task['mdd'] + ' mg' if task['basis'] == Q3B else 'declared (no public source)'}"
                      f" | {task['n']} | {with_unit(task['min'], task['unit'])} | {with_unit(task['max'], task['unit'])} | {task['n_outside']} |"])
