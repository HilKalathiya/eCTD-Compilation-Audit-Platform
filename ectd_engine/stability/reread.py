"""Independent audit of an accepted P.8.3 text: recounts the numbers straight from the CSV rows (not through facts.py or the validator)."""
import csv
import re
from decimal import Decimal

LABEL = "In illustrative demonstration data, "
NUM = re.compile(r"\d+(?:\.\d+)?")


def read_rows(path):
    """The CSV as a list of dicts (plain csv module)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _outside(value, limit):
    """True if value breaks a limit text like '95.0-105.0', 'NMT 0.5' or 'NLT 90'."""
    limit = (limit or "").strip()
    if not limit:
        return False
    m = re.match(r"^NMT (\S+)$", limit)
    if m:
        return value > Decimal(m.group(1))
    m = re.match(r"^NLT (\S+)$", limit)
    if m:
        return value < Decimal(m.group(1))
    lo, hi = limit.split("-")
    return value < Decimal(lo) or value > Decimal(hi)


def _one(rows, cond, attr):
    got = [r for r in rows if r["condition"] == cond and r["attribute"] == attr]
    return Decimal(got[-1]["value"]) if got else None


def expected_public(rows):
    """The 7 numbers the public paragraph holds, recounted from the rows."""
    crt = next(r["condition"] for r in rows if r["attribute"] == "expiry_period_proposed")
    lo, hi = re.match(r"^(\d+)-(\d+)C", crt).groups()
    return sorted([_one(rows, crt, "expiry_period_proposed"), Decimal(lo), Decimal(hi),
                   _one(rows, "15-30C excursion", "excursion_permitted_low"), _one(rows, "15-30C excursion", "excursion_permitted_high"),
                   _one(rows, "25C/60%RH", "study_duration_demonstrated"), _one(rows, "40C/75%RH", "study_duration_demonstrated")])


def expected_demo(rows, cond, attr):
    """The numbers one demo paragraph holds: min, max, n, n (and the outside count + n again when some are outside)."""
    got = [r for r in rows if r["condition"] == cond and r["attribute"] == attr and r["source"].startswith("DEMO")]
    vals = [Decimal(r["value"]) for r in got]
    out = sum(1 for r, v in zip(got, vals) if _outside(v, r["limit"]))
    nums = [min(vals), max(vals), Decimal(len(vals)), Decimal(len(vals))]
    return sorted(nums + ([Decimal(out)] if out else [])), out


def reread(text, task, rows):
    """List of problems found in a finished text (empty list = the text is right). task is a task from loop.make_tasks."""
    problems = []
    if task["kind"] == "public":
        want, body = expected_public(rows), text
        if "illustrative" in text:
            problems.append("public paragraph holds a demo label")
    else:
        cond, attr = task["key"]
        want, out = expected_demo(rows, cond, attr)
        if text.count(LABEL) != 2:
            problems.append("demo paragraph must hold the demo label in both sentences")
        if text.count(attr + " at " + cond) != 2:
            problems.append("demo paragraph must name the attribute and condition twice")
        if ("results outside the limit" in text) != True:
            problems.append("no outside-the-limit sentence")
        if (out == 0) != ("none of its" in text):
            problems.append("outside-the-limit sentence does not match the recount")
        body = text.replace(attr, "").replace(cond, "")
    got = sorted(Decimal(x) for x in NUM.findall(body))
    if got != want:
        problems.append("numbers in the text %s differ from the recount %s" % ([str(x) for x in got], [str(x) for x in want]))
    return problems
