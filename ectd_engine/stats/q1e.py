"""ICH Q1E shelf life: least-squares line, one-sided 95% bound of the mean line, extrapolation cap."""
from dataclasses import dataclass
from decimal import Decimal, localcontext

from ectd_engine.stats.basic import PREC, round_to
from ectd_engine.stats.tdist import t_quantile

CONFIDENCE = Decimal("0.95")  # one-sided
_STEP = Decimal("1e-8")  # bisection stops when the bracket is this narrow (months)


def _clean(points):
    pts = []
    for p in points:
        month, value = p
        for v in (month, value):
            if not isinstance(v, Decimal):
                raise TypeError(f"expected Decimal, got {type(v).__name__}: {v!r}")
        pts.append((month, value))
    if len(pts) < 3:
        raise ValueError("Q1E regression needs at least 3 points")
    if len({m for m, _ in pts}) < 2:
        raise ValueError("points need at least 2 different months")
    return pts


@dataclass(frozen=True)
class Fit:
    """Result of the least-squares line y = intercept + slope * month."""

    slope: Decimal
    intercept: Decimal
    residual_sd: Decimal
    n: int
    xbar: Decimal
    sxx: Decimal

    def line(self, month):
        return self.intercept + self.slope * month

    def bound(self, month, side):
        """One-sided 95% confidence bound of the MEAN line at `month` ('lower' or 'upper')."""
        if side not in ("lower", "upper"):
            raise ValueError("side must be 'lower' or 'upper'")
        with localcontext() as ctx:
            ctx.prec = PREC
            t = t_quantile(CONFIDENCE, self.n - 2)
            half = t * self.residual_sd * (1 / Decimal(self.n) + (month - self.xbar) ** 2 / self.sxx).sqrt()
            centre = self.line(month)
            return centre - half if side == "lower" else centre + half


def fit(points):
    """Least squares on (month, value) points -> Fit (slope, intercept, residual SD with n-2)."""
    pts = _clean(points)
    n = len(pts)
    with localcontext() as ctx:
        ctx.prec = PREC
        xbar = sum((m for m, _ in pts), Decimal(0)) / n
        ybar = sum((v for _, v in pts), Decimal(0)) / n
        sxx = sum(((m - xbar) ** 2 for m, _ in pts), Decimal(0))
        sxy = sum(((m - xbar) * (v - ybar) for m, v in pts), Decimal(0))
        slope = sxy / sxx
        intercept = ybar - slope * xbar
        sse = sum(((v - intercept - slope * m) ** 2 for m, v in pts), Decimal(0))
        return Fit(slope, intercept, (sse / (n - 2)).sqrt(), n, xbar, sxx)


@dataclass(frozen=True)
class ShelfLife:
    months: Decimal  # proposed shelf life, 2 decimals
    capped: bool
    reason: str
    cap_months: Decimal
    side: str  # 'lower' (vs spec_min) or 'upper' (vs spec_max): the one that decided


def default_cap(points):
    """min(2 x longest month, longest + 12): how far Q1E lets you extrapolate."""
    longest = max(m for m, _ in _clean(points))
    return min(2 * longest, longest + 12)


def _one_side(f, spec, side, cap):
    """Return (months, capped, reason) for one limit; months is exact (not yet rounded)."""
    def margin(x):  # >= 0 means the bound is still inside the limit
        b = f.bound(x, side)
        return b - spec if side == "lower" else spec - b

    if margin(Decimal(0)) < 0:
        return Decimal(0), False, f"{side} bound is already outside the limit at month 0"
    if margin(cap) >= 0:
        return cap, True, f"{side} bound does not cross the limit within the cap of {cap} months"
    lo, hi = Decimal(0), cap  # the bound is concave/convex, so it crosses exactly once here
    while hi - lo > _STEP:
        mid = (lo + hi) / 2
        if margin(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2, False, f"{side} bound crosses the limit"


def shelf_life(points, spec_min=None, spec_max=None, cap_months=None):
    """First month where the 95% one-sided bound meets the spec, solved to 0.01 month.

    Lower bound is compared with spec_min, upper bound with spec_max; with both limits the
    earlier crossing wins. The answer never goes past the extrapolation cap.
    """
    for s in (spec_min, spec_max):
        if s is not None and not isinstance(s, Decimal):
            raise TypeError(f"spec limit must be Decimal, got {type(s).__name__}: {s!r}")
    if spec_min is None and spec_max is None:
        raise ValueError("give at least one spec limit")
    f = fit(points)
    cap = default_cap(points) if cap_months is None else cap_months
    results = []
    with localcontext() as ctx:
        ctx.prec = PREC
        if spec_min is not None:
            results.append(("lower",) + _one_side(f, spec_min, "lower", cap))
        if spec_max is not None:
            results.append(("upper",) + _one_side(f, spec_max, "upper", cap))
    side, months, capped, reason = min(results, key=lambda r: r[1])
    return ShelfLife(round_to(months, 2), capped, reason, cap, side)


def line_shelf_life(points, spec_min=None, spec_max=None):
    """WRONG way, kept only so tests can show the gap: month where the plain line meets the spec.

    Returns None if the line never reaches the limit (it moves the wrong way or is flat).
    """
    if spec_min is None and spec_max is None:
        raise ValueError("give at least one spec limit")
    f = fit(points)
    found = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for spec, falling in ((spec_min, True), (spec_max, False)):
            if spec is None or f.slope == 0 or (f.slope < 0) != falling:
                continue
            found.append((spec - f.intercept) / f.slope)
    return round_to(min(found), 2) if found else None
