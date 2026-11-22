"""Exact checks for headings and table rows: each must equal what the content plan / the task files say for that position, nothing else."""
from decimal import Decimal, InvalidOperation

from ectd_engine.render.plan import CONTENT_PLAN, parts


def expected_headings(title, tasks):
    """The heading texts the document must have, in order: the title, then for every part its heading and the attribute
    heading of each of its tasks. tasks = [{"part", "attribute", ...}] in the order the writer used."""
    out = [title]
    for part in parts():
        out.append(f"{part} {CONTENT_PLAN[part]['title']}")
        out += [t["attribute"] for t in tasks if t["part"] == part]
    return out


def check_headings(found, expected):
    """["heading:<text>", ...] for every heading that is not exactly the expected one at its position (extra or missing too)."""
    flags = [f"heading:{f}" for f, e in zip(found, expected) if f != e]
    flags += [f"heading:{f}" for f in found[len(expected):]]
    flags += [f"heading:missing {e}" for e in expected[len(found):]]
    return flags


def _same(a, b):
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError):
        return False


def check_row(cells, placement, task):
    """["row:<batch id>"] unless the row is exactly what the task files and its own placement say: the batch is on THIS task's
    list, the unit is the task's unit, and the value equals the row's own placement (same task, batch and column).
    An excluded batch is the row "<id> / excluded (quarantined) / -" with no placement. cells = the row's three texts."""
    from ectd_engine.writer.batch_facts import fact_id
    batch = cells[0]
    if task is None or len(cells) != 3 or batch not in set(task["batches"]):
        return [f"row:{batch}"]
    if cells[1:] == ["excluded (quarantined)", "-"]:
        return [] if placement is None else [f"row:{batch}"]
    ok = (placement is not None and cells[2] == task["unit"] and placement["id"] == fact_id(batch, task["column"])
          and placement["section"] == f"{task['part']}/{task['task_id']}/table" and _same(placement["text"], cells[1])
          and cells[1] == placement["text"])
    return [] if ok else [f"row:{batch}"]
