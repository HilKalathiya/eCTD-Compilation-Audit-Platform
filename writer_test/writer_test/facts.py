"""Compute every number and every judgement the writer may use, in code.

The model never calculates anything. It receives these facts with IDs and
refers to them as [[id]] placeholders; code fills in the values afterwards.
"""
from decimal import Decimal, ROUND_HALF_UP

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


# Stand-in for the product's registered test list. In the real system this comes
# from the specification; here it lets the validator spot a different test's name.
TEST_REGISTRY = ["Assay", "Total impurities", "Impurity A", "Impurity B", "Dissolution", "Water content",
                 "Appearance", "Hardness", "Disintegration", "Content uniformity", "Microbial limits"]


def condition_type(condition):
    """accelerated / intermediate / long-term, from the storage temperature."""
    if "40°C" in condition:
        return "accelerated"
    if "30°C" in condition:
        return "intermediate"
    return "long-term"


def fmt(value, decimals):
    """Regulatory rounding: half up, to the specification's decimals."""
    q = Decimal(1).scaleb(-decimals) if decimals > 0 else Decimal(1)
    return str(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def with_unit(text, unit):
    return f"{text}%" if unit.startswith("%") else f"{text} {unit}"


def range_fact(values, decimals, unit, label):
    """A range like 0.28–0.30%, or a single value when every batch gave the same result."""
    lo, hi = fmt(min(values), decimals), fmt(max(values), decimals)
    if lo == hi:
        return with_unit(lo, unit), label.replace("range of ", "") + " (same for all batches)"
    return with_unit(lo + chr(8211) + hi, unit), label


def spec_text(spec, unit, decimals):
    decimals = spec.get("decimals", decimals)  # limits are often written with fewer decimals than results
    if spec["type"] == "range":
        return (f"{fmt(spec['lower'], decimals)}–{fmt(spec['upper'], decimals)}"
                f"{'%' if unit.startswith('%') else ' ' + unit}")
    if spec["type"] == "nmt":
        return f"NMT {with_unit(fmt(spec['limit'], decimals), unit)}"
    note = f" ({spec['note']})" if spec.get("note") else ""
    return f"NLT {with_unit(fmt(spec['limit'], decimals), unit)}{note}"


def within_spec(value, spec):
    if spec["type"] == "range":
        return spec["lower"] <= value <= spec["upper"]
    if spec["type"] == "nmt":
        return value <= spec["limit"]
    return value >= spec["limit"]


def pooled_slope(months, batches):
    """Least-squares slope over all points of all batches (per month)."""
    xs, ys = [], []
    for values in batches.values():
        xs += months
        ys += values
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0


def trend_label(task, slope):
    spec, months = task["spec"], task["months"]
    values = [v for vals in task["batches"].values() for v in vals]
    if spec["type"] == "range":
        scale = spec["upper"] - spec["lower"]
    elif spec["type"] == "nmt":
        scale = spec["limit"]
    else:
        scale = sum(values) / len(values)
    change = slope * (max(months) - min(months))
    threshold = max(0.05 * scale, 0.5 * 10 ** (-task["decimals"]))
    if abs(change) < threshold:
        return "no meaningful change"
    return "increasing" if change > 0 else "decreasing"


def compute_facts(task):
    """Return {fact_id: {"value", "label", "roles"}} plus flags and the required fact ids.

    A result is one fact that renders its value, batch and time point together.
    The model can choose which fact to mention, but cannot pair one fact's value
    with another fact's batch or month, because no separate batch or month fact exists."""
    unit, dec = task["unit"], task["decimals"]
    months, batches = task["months"], task["batches"]
    points = [(b, m, v) for b, vals in batches.items() for m, v in zip(months, vals)]
    max_b, max_m, max_v = max(points, key=lambda p: p[2])
    min_b, min_m, min_v = min(points, key=lambda p: p[2])
    first = [vals[0] for vals in batches.values()]
    last = [vals[-1] for vals in batches.values()]
    mean_change = sum(l - f for f, l in zip(first, last)) / len(first)
    slope = pooled_slope(months, batches)
    oos = [(b, m, v) for b, m, v in points if not within_spec(v, task["spec"])]
    n = len(batches)

    first_m, last_m = months[0], months[-1]

    def at_point(b, m, v):
        """One result rendered with its own batch and time point, so the three can never be split."""
        return f"{with_unit(fmt(v, dec), unit)} (Batch {b}, Month {m})"

    def point_roles(b, m, v):
        """Which role words may truthfully describe this result."""
        roles = set()
        if v == max_v:
            roles.add("max")
        if v == min_v:
            roles.add("min")
        if m == first_m:
            roles.add("initial")
        if m == last_m:
            roles.add("final")
        return roles

    init_text, init_label = range_fact(first, dec, unit, "range of initial results across batches")
    final_text, final_label = range_fact(last, dec, unit, "range of results at the last time point")
    facts = {
        "condition": (task["condition"], "storage condition", set()),
        "duration": (f"{last_m} months", "longest time point tested", set()),
        "n_batches": (NUMBER_WORDS.get(n, str(n)), "number of batches", set()),
        "spec": (spec_text(task["spec"], unit, dec), "acceptance criterion", set()),
        "initial_range": (f"{init_text} at Month {first_m}", init_label + ", with its time point", {"initial"}),
        "final_range": (f"{final_text} at Month {last_m}", final_label + ", with its time point", {"final"}),
        "max_value": (at_point(max_b, max_m, max_v), "highest result, with its batch and month",
                      point_roles(max_b, max_m, max_v)),
        "min_value": (at_point(min_b, min_m, min_v), "lowest result, with its batch and month",
                      point_roles(min_b, min_m, min_v)),
        "mean_change": (with_unit(fmt(abs(mean_change), dec), unit),
                        "mean absolute change from initial to last time point", {"change"}),
    }
    if oos:
        roles = set.intersection(*(point_roles(b, m, v) for b, m, v in oos)) | {"oos"}
        facts["oos_results"] = (" and ".join(at_point(b, m, v) for b, m, v in oos),
                                "results outside the acceptance criterion, with batch and month", roles)
    # The result a reviewer cares about is the one nearest the limit: the highest
    # for an NMT limit, the lowest for an NLT limit, whichever is closer for a range.
    spec = task["spec"]
    if spec["type"] == "nmt":
        worst = "max_value"
    elif spec["type"] == "nlt":
        worst = "min_value"
    else:
        worst = "min_value" if (min_v - spec["lower"]) <= (spec["upper"] - max_v) else "max_value"
    # Does the claimed trend hold for EVERY batch? (for "in all three batches ...")
    label = trend_label(task, slope)
    thr = max(0.05 * (task["spec"].get("upper", 0) - task["spec"].get("lower", 0) if task["spec"]["type"] == "range"
                      else task["spec"]["limit"] if task["spec"]["type"] == "nmt" else sum(
                          v for vs in batches.values() for v in vs) / len(points)), 0.5 * 10 ** (-dec))
    changes = [vals[-1] - vals[0] for vals in batches.values()]
    if label == "increasing":
        agree = all(c > 0 for c in changes)
    elif label == "decreasing":
        agree = all(c < 0 for c in changes)
    else:
        agree = all(abs(c) < thr for c in changes)
    month_of = {"initial_range": first_m, "final_range": last_m, "max_value": max_m, "min_value": min_m}
    if oos and len({m for _, m, _ in oos}) == 1:
        month_of["oos_results"] = oos[0][1]
    flags = {
        "registry": TEST_REGISTRY,
        "batches_agree": agree,
        "batch_ids": list(batches),
        "condition_type": condition_type(task["condition"]),
        "fact_month": month_of,
        "trend": label,
        "all_within_spec": not oos,
        "slope_per_month": slope,
        "worst_fact": worst,
        "attribute": task["attribute"],
        # True when "ranged from [initial] to [final]" is a true statement about ALL results.
        "ends_span_all": min(first + last) <= min_v and max(first + last) >= max_v,
    }
    facts = {k: {"value": v, "label": label, "roles": roles} for k, (v, label, roles) in facts.items()}
    required = ["spec", worst] + (["oos_results"] if oos else [])
    flags["required"] = required
    return facts, flags, required
