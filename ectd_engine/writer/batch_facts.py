"""Computes every value for a 3.2.P.5.4 batch-analyses section (counts, lowest/highest with batch ids, mean, table) from facts."""
from decimal import Decimal

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.loaders import lek
from ectd_engine.stats import basic
from ectd_engine.writer.facts import NUMBER_WORDS, TEST_REGISTRY, with_unit

EXCLUDED_CELL = "excluded (quarantined)"
LEK_TESTS = [test for test, _ in lek.COLUMNS.values()]
TASK_KEYS = ("task_id", "section", "product", "attribute", "column", "unit", "decimals", "batches")


class UnknownBatch(ValueError):
    """A batch id that is not in the batch registry (a typo is an error, not an exclusion)."""


def fact_id(batch, column):
    """The id the Lek loader gives a result (same pattern as ectd_engine/loaders/lek.py)."""
    return f"LEK-{batch}-{column}"


def id_key(batch):
    """Sort key: numeric ids by number (so 2 comes before 10), any other id by text after them."""
    return (0, int(batch), "") if batch.isdigit() else (1, 0, batch)


def places(value):
    return max(0, -value.as_tuple().exponent)


def ids_text(ids):
    """'Batch 5', 'Batches 5 and 7', 'Batches 5, 7 and 9'."""
    if len(ids) == 1:
        return f"Batch {ids[0]}"
    return "Batches " + ", ".join(ids[:-1]) + " and " + ids[-1]


def count_text(n):
    return f"{NUMBER_WORDS.get(n, str(n))} {'batch' if n == 1 else 'batches'}"


def check_task(task):
    """Loud errors for a malformed task (missing key, unknown column, ids not unique or not sorted)."""
    missing = [k for k in TASK_KEYS if k not in task]
    if missing:
        raise ValueError(f"task {task.get('task_id')!r} is missing: {', '.join(missing)}")
    if task["column"] not in lek.COLUMNS:
        raise ValueError(f"task {task['task_id']}: unknown column {task['column']!r}")
    if lek.COLUMNS[task["column"]][0] != task["attribute"]:
        raise ValueError(f"task {task['task_id']}: attribute {task['attribute']!r} does not match column {task['column']!r}")
    ids = task["batches"]
    if not ids or len(set(ids)) != len(ids) or ids != sorted(ids, key=id_key):
        raise ValueError(f"task {task['task_id']}: batches must be a non-empty list of unique ids, sorted (numbers by value)")
    if not isinstance(task["decimals"], int) or task["decimals"] < 0:
        raise ValueError(f"task {task['task_id']}: decimals must be an int >= 0")


def compute_batch_facts(task, get_fact, known_batches):
    """Return (facts, flags, required, table).

    get_fact(fact_id) -> Fact or None is the fact-store read (None = no accepted fact, i.e. quarantined).
    known_batches is the batch registry: a batch not in it raises UnknownBatch instead of counting as excluded.
    Only the mean is ever rounded; every other number is shown exactly as stored."""
    check_task(task)
    unit, dec = task["unit"], task["decimals"]
    included, excluded = [], []
    for b in task["batches"]:
        f = get_fact(fact_id(b, task["column"]))
        if f is None:
            if b not in known_batches:
                raise UnknownBatch(f"batch {b!r} is not in the batch registry")
            excluded.append(b)
            continue
        if not isinstance(f.value, Decimal) or f.batch != b or f.unit != unit:
            raise ValueError(f"fact {f.fact_id}: expected a Decimal for batch {b} in {unit}")
        if places(f.value) > dec:
            raise ValueError(f"fact {f.fact_id}: {f.value} has more than {dec} decimals; the task would round a source value")
        included.append((b, f.value))
    if not included:
        raise ValueError(f"task {task['task_id']}: no batch has a result")

    values = [v for _, v in included]
    lo, hi = min(values), max(values)
    lo_ids = [b for b, v in included if v == lo]
    hi_ids = [b for b, v in included if v == hi]
    lo_txt = next(str(v) for b, v in included if v == lo)
    hi_txt = next(str(v) for b, v in included if v == hi)
    mean_txt = str(basic.round_to(basic.mean(values), dec))
    n, n_ex = len(included), len(excluded)

    rng_txt = with_unit(lo_txt, unit) if lo == hi else with_unit(f"{lo_txt}{chr(8211)}{hi_txt}", unit)
    spec = {
        "n_batches": (count_text(n), "number of batches with a result", set()),
        "min_value": (f"{with_unit(lo_txt, unit)} ({ids_text(lo_ids)})", "lowest result, with its batch(es)",
                      {"min"} | ({"max"} if lo == hi else set())),
        "max_value": (f"{with_unit(hi_txt, unit)} ({ids_text(hi_ids)})", "highest result, with its batch(es)",
                      {"max"} | ({"min"} if lo == hi else set())),
        "value_range": (rng_txt, "range of the results, lowest to highest", {"range"}),
        "mean_value": (with_unit(mean_txt, unit), "mean of the results", {"mean"}),
    }
    if n_ex:
        spec["n_excluded"] = (count_text(n_ex), "number of batches excluded because their result is quarantined", set())
        spec["excluded_batches"] = (ids_text(excluded), "the excluded (quarantined) batches", set())
    facts = {k: {"value": v, "label": label, "roles": roles} for k, (v, label, roles) in spec.items()}
    required = ["n_batches", "min_value", "max_value", "mean_value"] + (["n_excluded", "excluded_batches"] if n_ex else [])
    flags = {
        "attribute": task["attribute"], "registry": sorted(set(LEK_TESTS) | set(TEST_REGISTRY)),
        "batch_ids": list(task["batches"]), "included": [b for b, _ in included], "excluded": excluded,
        "n_excluded": n_ex, "has_spec": False, "all_equal": lo == hi, "unit": unit, "required": required,
    }
    table = {"unit": unit, "decimals": dec,
             "rows": [(b, None if b in excluded else str(dict(included)[b])) for b in task["batches"]]}
    return facts, flags, required, table


def render_table(table):
    """The results table as markdown: batch id, value, unit. Written by code only; the model never sees it."""
    lines = ["| Batch | Value | Unit |", "|---|---|---|"]
    for b, text in table["rows"]:
        lines.append(f"| {b} | {EXCLUDED_CELL} | - |" if text is None else f"| {b} | {text} | {table['unit']} |")
    return "\n".join(lines)


class LoaderStore:
    """Facts exactly as the real Lek loader (gate rules included) would store them, with no database needed.

    It runs ectd_engine.loaders.lek.load against a recorder instead of Postgres, so what is accepted or
    quarantined is decided by the real code, not by a list written here."""

    def __init__(self, path=lek.CSV_PATH):
        rec = _Recorder()
        lek.load(rec, None, path)
        self.facts = {f.fact_id: f for f in rec.facts}
        self.known_batches = {row["batch"] for _, row in lek.read_rows(path)}

    def get(self, fid):
        return self.facts.get(fid)


class _Recorder:
    """Stands in for the database connection: keeps every fact the gate hands to gate_insert_fact."""

    def __init__(self):
        self.facts = []

    def execute(self, sql, params=()):
        if "gate_insert_fact" in sql:
            p = params
            self.facts.append(Fact(fact_id=p[0], value=Decimal(p[2]), unit=p[3], batch=p[4], test=p[5], condition=p[6],
                                   month=p[7], source=SourcePointer(p[8], p[9], p[10]), lineage=p[11], definition=p[12]))
        return self

    def commit(self):
        pass

    def rollback(self):
        pass

