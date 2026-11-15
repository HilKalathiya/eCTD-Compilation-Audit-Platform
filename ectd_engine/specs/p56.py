"""Computes the 3.2.P.5.6 justification facts per attribute: basis, cited Q3B quote and page, and support from accepted Lek batches."""
from dataclasses import dataclass, replace
from decimal import Decimal

from ectd_engine.knowledge import cite
from ectd_engine.rules import q3b
from ectd_engine.specs import load, p51
from ectd_engine.stats import basic
from ectd_engine.writer import batch_facts


class JustificationRefused(Exception):
    """A justification fact cannot be proven (the message says which one and why)."""


@dataclass(frozen=True)
class Justification:
    attribute: str
    test: str
    limit_kind: str
    limit: Decimal
    unit: str
    basis: str
    rule_id: object
    quote: object
    page: object
    doc_version: object
    n: int
    minimum: object
    maximum: object
    outside: int


def batch_support(row, store):
    """(n, min, max, outside) over the batches the gate accepted; quarantined batches have no fact and are left out.

    'Outside' uses stats.basic.conforms, i.e. the value is rounded half-up to the limit's own decimals first."""
    values = []
    for b in sorted(store.known_batches, key=batch_facts.id_key):
        f = store.get(batch_facts.fact_id(b, row.attribute))
        if f is not None:
            values.append(f.value)
    if not values:
        raise JustificationRefused(f"{row.attribute}: no accepted batch values")
    lo, hi = (None, row.fact.value) if row.limit_kind == "NMT" else (row.fact.value, None)
    outside = sum(1 for v in values if not basic.conforms(v, lo, hi))
    return len(values), min(values), max(values), outside


def _cite_q3b(spec, row):
    """Re-check the limit and the quote against the table and the PDF; returns the Citation."""
    value, rule_id, q_row, _ = load.q3b_limit(spec.mdd.value, _table_of(row))
    if rule_id != row.rule_id or value != row.fact.value:
        raise JustificationRefused(f"{row.attribute}: stored limit {row.fact.value} ({row.rule_id}) does not match Q3B at "
                                   f"{spec.mdd.value} mg ({value}, {rule_id})")
    try:
        c = cite.verify(q_row.doc_id, q_row.page, q_row.source_quote)
    except cite.CitationRejected as e:
        raise JustificationRefused(f"{row.attribute}: Q3B quote does not verify ({e})") from e
    if c.version != q_row.doc_version:
        raise JustificationRefused(f"{row.attribute}: document version {c.version!r} != {q_row.doc_version!r}")
    return c


def _table_of(row):
    """A one-row Table holding the row's own Q3B row (enough to look the same dose up again)."""
    return q3b.Table((row.q3b_row,))


def compute(spec, store, table=None):
    """One Justification per attribute, in P.5.1 order. The table may be passed in (tests plant changes there)."""
    p51.check_complete(spec)
    out = []
    for row in spec.rows:
        n, lo, hi, outside = batch_support(row, store)
        if row.basis == "q3b_qualification":
            if table is not None:
                row = _with_table(row, table)
            c = _cite_q3b(spec, row)
            out.append(Justification(row.attribute, row.test, row.limit_kind, row.fact.value, row.unit, row.basis,
                                     row.rule_id, c.quote, c.page, c.version, n, lo, hi, outside))
        else:
            out.append(Justification(row.attribute, row.test, row.limit_kind, row.fact.value, row.unit, row.basis,
                                     None, None, None, None, n, lo, hi, outside))
    return out


def _with_table(row, table):
    """The row as the given table holds it (same rule id), so a changed quote there is what gets checked."""
    found = [r for r in table.rows if r.rule_id == row.rule_id]
    if len(found) != 1:
        raise JustificationRefused(f"{row.attribute}: rule {row.rule_id} not found in the Q3B table")
    return replace(row, q3b_row=found[0])


def render_support(items):
    lines = ["| Attribute | Limit | n | min | max | outside limit |", "|---|---|---|---|---|---|"]
    for j in items:
        lines.append(f"| {j.test} | {j.limit_kind} {j.limit} {j.unit} | {j.n} | {j.minimum} | {j.maximum} | {j.outside} |")
    return "\n".join(lines)


def main():
    spec = load.load()
    store = batch_facts.LoaderStore()
    print(p51.render(spec))
    items = compute(spec, store)
    print()
    for j in items:
        if j.rule_id:
            print(f"{j.attribute}: {j.limit_kind} {j.limit} {j.unit}; rule {j.rule_id}; Q3B page {j.page}; {j.doc_version}")
            print(f"  quote: {j.quote}")
        else:
            print(f"{j.attribute}: {j.limit_kind} {j.limit} {j.unit}; declared (no source)")
    print()
    print(render_support(items))


if __name__ == "__main__":
    main()
