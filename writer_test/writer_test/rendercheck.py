"""Independent re-read of the FINISHED text against the raw data table.

validator.py checks the model's draft (placeholders). This module checks the
rendered paragraph that a reviewer would sign, and it does not use the fact
store: it parses the text and looks every value, batch and month up in the
original table. It therefore also catches a bug in the fact code, or a hand
edit made after rendering. It reads the same compound strings the renderer
writes, so it is a second route to the same truth, not a second opinion.
"""
import re

from .facts import fmt

NUM = r"(\d+(?:\.\d+)?)"
RESULT = re.compile(NUM + r"%?(?: [^\s(,;.]+)? \(Batch ([^,\s)]+), Month (\d+)\)")
RANGE = re.compile(NUM + r"(?:–" + NUM + r")?%?(?: [^\s(,;.]+)? at Month (\d+)")
ANY_BATCH = re.compile(r"\bBatch ([A-Za-z0-9_-]+)")
ANY_MONTH = re.compile(r"\bMonth (\d+)")


def verify_render(text, task):
    """Return a list of problems; empty means every quoted value, batch and month matches the table."""
    months, batches, dec = task["months"], task["batches"], task["decimals"]
    problems = []
    for m in ANY_BATCH.finditer(text):
        if m.group(1).rstrip(",.;)") not in batches:
            problems.append(f"unknown batch {m.group(1)}")
    for m in ANY_MONTH.finditer(text):
        if int(m.group(1)) not in months:
            problems.append(f"unknown time point Month {m.group(1)}")
    for m in RESULT.finditer(text):
        value, batch, month = m.group(1), m.group(2), int(m.group(3))
        if batch not in batches or month not in months:
            continue  # already reported above
        truth = fmt(batches[batch][months.index(month)], dec)
        if value != truth:
            problems.append(f"Batch {batch} at Month {month} is {truth} in the data, text says {value}")
    for m in RANGE.finditer(text):
        lo, hi, month = m.group(1), m.group(2) or m.group(1), int(m.group(3))
        if month not in months:
            continue
        col = [vals[months.index(month)] for vals in batches.values()]
        if (fmt(min(col), dec), fmt(max(col), dec)) != (lo, hi):
            problems.append(f"at Month {month} the data range is {fmt(min(col), dec)}–{fmt(max(col), dec)}, "
                            f"text says {lo}–{hi}")
    return problems
