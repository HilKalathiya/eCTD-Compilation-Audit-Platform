"""Out-of-trend check: is a new stability result outside the prediction interval of earlier points?"""
from dataclasses import dataclass
from decimal import Decimal, localcontext

from ectd_engine.stats.basic import PREC
from ectd_engine.stats.loq import Below, Policy, apply_policy
from ectd_engine.stats.q1e import fit
from ectd_engine.stats.tdist import t_quantile

LEVEL = Decimal("0.99")  # two-sided


@dataclass(frozen=True)
class OK:
    low: Decimal
    high: Decimal
    value: Decimal


@dataclass(frozen=True)
class OOT:
    low: Decimal
    high: Decimal
    value: Decimal


@dataclass(frozen=True)
class NotEnoughData:
    message: str


def interval(history, month, level=LEVEL):
    """Two-sided PREDICTION interval (low, high) for ONE new result at `month`."""
    if not isinstance(level, Decimal) or not Decimal(0) < level < Decimal(1):
        raise ValueError("level must be a Decimal between 0 and 1")
    f = fit(history)
    with localcontext() as ctx:
        ctx.prec = PREC
        t = t_quantile((1 + level) / 2, f.n - 2)
        half = t * f.residual_sd * (1 + 1 / Decimal(f.n) + (month - f.xbar) ** 2 / f.sxx).sqrt()
        centre = f.line(month)
        return centre - half, centre + half


def check(history, new_point, level=LEVEL):
    """history = (month, Decimal) pairs; new_point = (month, Decimal) -> OK | OOT | NotEnoughData."""
    month, value = new_point
    for v in (month, value):
        if not isinstance(v, Decimal):
            raise TypeError(f"expected Decimal, got {type(v).__name__}: {v!r}")
    pts = list(history)
    if len(pts) < 3:
        return NotEnoughData(f"not enough data: {len(pts)} earlier point(s), need at least 3")
    if len({m for m, _ in pts}) < 2:
        return NotEnoughData("not enough data: earlier points are all at the same month")
    low, high = interval(pts, month, level)
    return OK(low, high, value) if low <= value <= high else OOT(low, high, value)


def check_with_policy(rows, new_point, policy=Policy.EXCLUDE, substitute_value=None, reason=None, level=LEVEL):
    """Apply the <LOQ policy to the history first -> (result, plain note of what was done)."""
    month, value = new_point
    res = apply_policy(rows, policy, substitute_value, reason)
    if isinstance(value, Below):
        return NotEnoughData("new result is <LOQ: it cannot be compared with the interval"), res.note
    if policy is Policy.REPORT_ONLY and res.dropped:
        return NotEnoughData("no trend check: policy REPORT_ONLY and the history has <LOQ results"), res.note
    return check(res.points, (month, value), level), res.note
