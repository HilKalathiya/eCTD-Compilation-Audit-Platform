"""Reads "<LOQ" / "ND" results and applies an explicit policy; a number is never invented silently."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from ectd_engine.stats.q1e import shelf_life


@dataclass(frozen=True)
class Below:
    """A result too small to measure: 'below `loq`'."""

    loq: Decimal


class Policy(Enum):
    EXCLUDE = "exclude"  # default: drop the point from the regression and say so
    REPORT_ONLY = "report_only"  # no regression at all
    SUBSTITUTE = "substitute"  # only with an explicit value AND a reason


@dataclass(frozen=True)
class PolicyResult:
    points: tuple  # (month, Decimal) pairs ready for the regression; empty if REPORT_ONLY
    dropped: tuple  # (month, Below) pairs left out or replaced
    note: str  # plain sentence for the reviewer


def _decimal(text):
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"cannot read result {text!r}: not a number, '<LOQ', '<number' or 'ND'") from None


def parse(cell, loq):
    """Text cell -> Decimal, or Below(limit) for '<LOQ', '<0.05' and 'ND'."""
    if not isinstance(loq, Decimal):
        raise TypeError(f"loq must be Decimal, got {type(loq).__name__}: {loq!r}")
    text = str(cell).strip()
    upper = text.upper().replace(" ", "")
    if upper in ("<LOQ", "ND"):
        return Below(loq)
    if upper.startswith("<"):
        return Below(_decimal(upper[1:]))
    return _decimal(text)


def apply_policy(rows, policy=Policy.EXCLUDE, substitute_value=None, reason=None):
    """rows = (month, Decimal | Below) pairs -> PolicyResult with the points to use and a plain note."""
    if not isinstance(policy, Policy):
        raise TypeError(f"policy must be a Policy, got {policy!r}")
    if policy is Policy.SUBSTITUTE:
        if not isinstance(substitute_value, Decimal):
            raise ValueError("SUBSTITUTE needs an explicit Decimal substitute_value")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("SUBSTITUTE needs a reason string (why this value is justified)")
    kept = [(m, v) for m, v in rows if not isinstance(v, Below)]
    dropped = tuple((m, v) for m, v in rows if isinstance(v, Below))
    months = ", ".join(str(m) for m, _ in dropped)
    count = len(dropped)
    if count == 0:
        return PolicyResult(tuple(kept), (), "no <LOQ results")
    word = "point" if count == 1 else "points"
    if policy is Policy.EXCLUDE:
        note = f"{count} {word} <LOQ excluded (month {months})"
        if not kept:
            note += "; no measured points left"
        return PolicyResult(tuple(kept), dropped, note)
    if policy is Policy.REPORT_ONLY:
        note = f"{count} {word} <LOQ (month {months}): no regression done, results reported only"
        return PolicyResult((), dropped, note)
    filled = [(m, substitute_value if isinstance(v, Below) else v) for m, v in rows]
    note = f"{count} {word} <LOQ (month {months}) replaced by {substitute_value}; reason: {reason.strip()}"
    return PolicyResult(tuple(filled), dropped, note)


def shelf_life_with_policy(rows, spec_min=None, spec_max=None, policy=Policy.EXCLUDE,
                           substitute_value=None, reason=None, cap_months=None):
    """-> (ShelfLife or None, note). None means no shelf life was computed; the note says why."""
    res = apply_policy(rows, policy, substitute_value, reason)
    if policy is Policy.REPORT_ONLY and res.dropped:
        return None, res.note
    try:
        return shelf_life(res.points, spec_min, spec_max, cap_months), res.note
    except ValueError as err:
        return None, f"{res.note}; shelf life not computed: {err}"
