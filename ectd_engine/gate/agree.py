"""Decides if a value is confirmed by 2+ independent original sources, and flags sources that changed."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Verified:
    value: Decimal
    routes: tuple  # distinct original doc_ids that agree


@dataclass(frozen=True)
class SingleSource:
    value: Decimal
    routes: tuple  # fewer than 2 independent routes


@dataclass(frozen=True)
class ReviewItem:
    kind: str
    detail: str
    values: tuple  # (value, ...) involved
    sources: tuple  # SourcePointer(s) involved


Conflict = ReviewItem  # a Conflict is a ReviewItem of kind "conflict"


def _key(f):
    return (f.batch, f.test, f.condition, f.month)


def agree(facts):
    """Judge one (batch, test, condition, month): Verified | SingleSource | Conflict(ReviewItem)."""
    facts = list(facts)
    if not facts:
        raise ValueError("agree() needs at least one fact")
    if len({_key(f) for f in facts}) != 1:
        raise ValueError("agree() facts must share one batch, test, condition and month")
    originals = [f for f in facts if f.lineage == "original"]  # copy and unknown never count
    name = "/".join(map(str, _key(facts[0])))
    if len({f.value for f in originals}) > 1:
        values = tuple(f.value for f in originals)
        sources = tuple(f.source for f in originals)
        if len({f.source.doc_id for f in originals}) == 1 and len({f.source.doc_version for f in originals}) > 1:
            cited = "; ".join(f"v{f.source.doc_version} = {f.value}" for f in originals)
            return ReviewItem("version change", f"same document {originals[0].source.doc_id} changed between versions for {name}: {cited}", values, sources)
        return ReviewItem("conflict", "independent originals give different values for " + name, values, sources)
    routes = tuple(sorted({f.source.doc_id for f in originals}))
    value = originals[0].value if originals else facts[0].value
    odd = [f for f in facts if f.lineage != "original" and originals and f.value != value]
    if odd:
        return ReviewItem(
            "copy disagrees",
            f"a copy/unknown source differs from the original ({value}) for {name}",
            (value,) + tuple(f.value for f in odd),
            tuple(f.source for f in originals[:1] + odd),
        )
    if len(routes) >= 2:
        return Verified(value, routes)
    return SingleSource(value, routes)


def drift(stored_fact, reread_value):
    """Compare a stored fact with a fresh re-read of its source: None if same, else a review item."""
    if stored_fact.value == reread_value:
        return None
    return ReviewItem(
        "source changed",
        f"{stored_fact.fact_id}: stored {stored_fact.value}, re-read {reread_value}",
        (stored_fact.value, reread_value),
        (stored_fact.source,),
    )
