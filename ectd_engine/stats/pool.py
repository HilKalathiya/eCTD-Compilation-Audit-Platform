"""ICH Q1E poolability: may stability batches share one line? (ANCOVA at 0.25), then the shelf life."""
from dataclasses import dataclass
from decimal import Decimal, localcontext

from ectd_engine.stats.basic import PREC, round_to
from ectd_engine.stats.q1e import CONFIDENCE, ShelfLife, _one_side, default_cap, shelf_life
from ectd_engine.stats.tdist import f_cdf, t_quantile

ALPHA = Decimal("0.25")  # Q1E: pool only if p > 0.25 (a loose test, so a real difference is rarely missed)
SEPARATE = "separate"
COMMON_SLOPE = "common slope, separate intercepts"
POOLED = "fully pooled"


@dataclass(frozen=True)
class PoolResult:
    decision: str
    p_slope: Decimal  # equal slopes? (separate slopes vs one common slope)
    p_intercept: Decimal  # equal intercepts? (common slope, separate intercepts vs one line)
    shelf: ShelfLife  # shelf life from the chosen model
    per_batch: dict  # batch_id -> months (2 decimals) for models with separate lines, else {}


def decide(p_slope, p_intercept, alpha=ALPHA):
    """Q1E rule: slopes first, then intercepts; a p equal to alpha is NOT pooled (pool only if p > alpha)."""
    if p_slope <= alpha:
        return SEPARATE
    if p_intercept <= alpha:
        return COMMON_SLOPE
    return POOLED


def _check(batches):
    if len(batches) < 2:
        raise ValueError("poolability needs at least 2 batches")
    clean = {}
    for bid, points in batches.items():
        pts = []
        for month, value in points:
            for v in (month, value):
                if not isinstance(v, Decimal):
                    raise TypeError(f"expected Decimal, got {type(v).__name__}: {v!r}")
            pts.append((month, value))
        if len(pts) < 3:
            raise ValueError(f"batch {bid!r} has fewer than 3 points")
        if len({m for m, _ in pts}) < 2:
            raise ValueError(f"batch {bid!r} needs at least 2 different months")
        clean[bid] = pts
    return clean


def _p_value(extra_ss, extra_df, full_ss, full_df):
    """P(F > observed) for the extra sum of squares of a smaller model against a bigger one."""
    if full_ss == 0:  # perfect fit in the bigger model: any extra misfit is infinitely significant
        return Decimal(1) if extra_ss == 0 else Decimal(0)
    f = (extra_ss / extra_df) / (full_ss / full_df)
    return 1 - f_cdf(f, extra_df, full_df)


class _CommonSlope:
    """Common slope, own intercept for one batch: just enough of Fit for q1e's crossing search."""

    def __init__(self, slope, intercept, sd, df, n, xbar, sxx_within):
        self.slope, self.intercept, self.sd, self.df = slope, intercept, sd, df
        self.n, self.xbar, self.sxx = n, xbar, sxx_within

    def bound(self, month, side):
        with localcontext() as ctx:
            ctx.prec = PREC
            t = t_quantile(CONFIDENCE, self.df)
            half = t * self.sd * (1 / Decimal(self.n) + (month - self.xbar) ** 2 / self.sxx).sqrt()
            centre = self.intercept + self.slope * month
            return centre - half if side == "lower" else centre + half


def poolability(batches, spec_min=None, spec_max=None, cap_months=None, alpha=ALPHA):
    """batches = {batch_id: [(month, value), ...]} -> PoolResult (decision, both p-values, shelf life)."""
    for s in (spec_min, spec_max):
        if s is not None and not isinstance(s, Decimal):
            raise TypeError(f"spec limit must be Decimal, got {type(s).__name__}: {s!r}")
    if spec_min is None and spec_max is None:
        raise ValueError("give at least one spec limit")
    data = _check(batches)
    k = len(data)
    with localcontext() as ctx:
        ctx.prec = PREC
        allpts = [p for pts in data.values() for p in pts]
        n_all = len(allpts)
        # per-batch sums
        stats = {}
        for bid, pts in data.items():
            n = len(pts)
            xbar = sum((m for m, _ in pts), Decimal(0)) / n
            ybar = sum((v for _, v in pts), Decimal(0)) / n
            sxx = sum(((m - xbar) ** 2 for m, _ in pts), Decimal(0))
            sxy = sum(((m - xbar) * (v - ybar) for m, v in pts), Decimal(0))
            stats[bid] = (n, xbar, ybar, sxx, sxy)
        # model 1: every batch its own line
        sse_sep = Decimal(0)
        for bid, pts in data.items():
            n, xbar, ybar, sxx, sxy = stats[bid]
            b = sxy / sxx
            sse_sep += sum(((v - ybar - b * (m - xbar)) ** 2 for m, v in pts), Decimal(0))
        # model 2: one common slope, own intercepts
        sxx_w = sum((s[3] for s in stats.values()), Decimal(0))
        slope_c = sum((s[4] for s in stats.values()), Decimal(0)) / sxx_w
        sse_ci = Decimal(0)
        for bid, pts in data.items():
            n, xbar, ybar, sxx, sxy = stats[bid]
            sse_ci += sum(((v - ybar - slope_c * (m - xbar)) ** 2 for m, v in pts), Decimal(0))
        # model 3: one line for everything
        xbar_all = sum((m for m, _ in allpts), Decimal(0)) / n_all
        ybar_all = sum((v for _, v in allpts), Decimal(0)) / n_all
        sxx_all = sum(((m - xbar_all) ** 2 for m, _ in allpts), Decimal(0))
        sxy_all = sum(((m - xbar_all) * (v - ybar_all) for m, v in allpts), Decimal(0))
        sse_pool = sum(((v - ybar_all - (sxy_all / sxx_all) * (m - xbar_all)) ** 2 for m, v in allpts), Decimal(0))

        p_slope = _p_value(sse_ci - sse_sep, k - 1, sse_sep, n_all - 2 * k)
        p_int = _p_value(sse_pool - sse_ci, k - 1, sse_ci, n_all - k - 1)
        decision = decide(p_slope, p_int, alpha)

        if decision == POOLED:
            return PoolResult(decision, p_slope, p_int, shelf_life(allpts, spec_min, spec_max, cap_months), {})
        if decision == SEPARATE:
            per = {bid: shelf_life(pts, spec_min, spec_max, cap_months) for bid, pts in data.items()}
            worst = min(per.values(), key=lambda s: s.months)
            return PoolResult(decision, p_slope, p_int, worst, {b: s.months for b, s in per.items()})
        # common slope, separate intercepts: pooled error, df = N - k - 1
        sd = (sse_ci / (n_all - k - 1)).sqrt()
        cap = default_cap(allpts) if cap_months is None else cap_months
        per, results = {}, []
        for bid in data:
            n, xbar, ybar, _, _ = stats[bid]
            model = _CommonSlope(slope_c, ybar - slope_c * xbar, sd, n_all - k - 1, n, xbar, sxx_w)
            found = []
            if spec_min is not None:
                found.append(("lower",) + _one_side(model, spec_min, "lower", cap))
            if spec_max is not None:
                found.append(("upper",) + _one_side(model, spec_max, "upper", cap))
            best = min(found, key=lambda r: r[1])
            per[bid] = round_to(best[1], 2)
            results.append(best)
        side, months, capped, reason = min(results, key=lambda r: r[1])
        return PoolResult(decision, p_slope, p_int, ShelfLife(round_to(months, 2), capped, reason, cap, side), per)
