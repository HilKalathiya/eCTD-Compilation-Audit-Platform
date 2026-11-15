"""Renders the 3.2.P.5.1 specification table (test, acceptance criterion, basis) by code; refuses if any spec fact is missing."""
from decimal import Decimal

from ectd_engine.loaders import lek
from ectd_engine.specs.load import SpecRefused


class SpecIncomplete(SpecRefused):
    """A specification fact is missing or blank (the message names it)."""


def criterion(row):
    return f"{row.limit_kind} {row.fact.value} {row.unit}"


def basis_label(spec, row):
    if row.basis == "q3b_qualification":
        return (f"ICH Q3B(R2) qualification threshold at {spec.mdd.value} mg/day assumed maximum daily dose "
                f"(rule {row.rule_id}, page {row.q3b_row.page})")
    return "Declared for demo (no public source)"


def check_complete(spec):
    """Every Lek attribute needs a spec row whose fact is a real Decimal; otherwise raise and name what is missing."""
    by_attr = {r.attribute: r for r in spec.rows}
    problems = []
    for attr in lek.COLUMNS:
        row = by_attr.get(attr)
        if row is None or row.fact is None:
            problems.append(f"{attr}: no spec fact")
        elif not isinstance(row.fact.value, Decimal) or not row.basis or not row.limit_kind:
            problems.append(f"{attr}: blank value, basis or limit kind")
    if spec.mdd is None:
        problems.append("ASSUMPTION-MDD: missing")
    if problems:
        raise SpecIncomplete("P.5.1 cannot be written; " + "; ".join(problems))


def render(spec):
    """The P.5.1 table as markdown."""
    check_complete(spec)
    lines = ["| Test | Acceptance criterion | Basis |", "|---|---|---|"]
    for row in spec.rows:
        lines.append(f"| {row.test} | {criterion(row)} | {basis_label(spec, row)} |")
    return "\n".join(lines)
