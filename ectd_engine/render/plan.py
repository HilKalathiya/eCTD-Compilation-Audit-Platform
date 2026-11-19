"""The content plan: which sections the P.5.4 and P.5.6 parts hold, in order, and which facts each section must have."""

# requires = fact keys that must exist; requires_if = extra keys that are needed only when a named condition is true.
CONTENT_PLAN = {
    "3.2.P.5.4": {
        "title": "Batch analyses",
        "sections": [
            {"name": "opening", "requires": ["n_batches"], "requires_if": {"excluded": ["n_excluded", "excluded_batches"]}},
            {"name": "table", "requires": ["n_batches"], "requires_if": {}},
            {"name": "discussion", "requires": ["n_batches", "min_value", "max_value", "mean_value"],
             "requires_if": {"excluded": ["n_excluded", "excluded_batches"]}},
        ],
    },
    "3.2.P.5.6": {
        "title": "Justification of specification",
        "sections": [
            {"name": "justification", "requires": ["limit_kind", "limit", "basis", "n_batches", "min_value", "max_value"],
             "requires_if": {"q3b": ["mdd", "q3b_quote"], "outside": ["n_outside"]}},
        ],
    },
}


def parts():
    """The part numbers in document order."""
    return list(CONTENT_PLAN)


def conditions(part, flags):
    """Names of the conditions that hold for this task, read from the flags (never from the facts, so a dropped fact still counts)."""
    if part == "3.2.P.5.4":
        return {"excluded"} if flags.get("n_excluded") else set()
    out = set()
    if flags.get("basis") == "q3b_qualification":
        out.add("q3b")
    if flags.get("n_outside"):
        out.add("outside")
    return out


def required_keys(part, section_name, active):
    """The fact keys one section must have, given the active conditions."""
    sec = next(s for s in CONTENT_PLAN[part]["sections"] if s["name"] == section_name)
    keys = list(sec["requires"])
    for cond, extra in sec["requires_if"].items():
        if cond in active:
            keys += extra
    return keys
