"""Student t distribution (cdf and quantile) in Decimal only, for the confidence bounds."""
from decimal import Decimal, localcontext
from functools import lru_cache
from math import factorial

from ectd_engine.stats.basic import PREC

_PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494459")
_EPS = Decimal("1e-40")
_TINY = Decimal("1e-60")
_HALF = Decimal("0.5")


def _beta_half(a):
    """B(a, 1/2) for a = df/2, where df is a whole number (a is whole or half-whole)."""
    two_a = int(a * 2)
    if two_a % 2 == 0:  # a = m
        m = two_a // 2
        return Decimal(factorial(m - 1) * 4**m * factorial(m)) / Decimal(factorial(2 * m))
    m = (two_a - 1) // 2  # a = m + 1/2
    return _PI * Decimal(factorial(2 * m)) / Decimal(4**m * factorial(m) ** 2)


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta (modified Lentz method)."""
    qab, qap, qam = a + b, a + 1, a - 1
    c = Decimal(1)
    d = 1 - qab * x / qap
    d = 1 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, 2000):
        m2 = 2 * m
        for aa in (
            m * (b - m) * x / ((qam + m2) * (a + m2)),
            -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2)),
        ):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > _TINY else _TINY)
            c = 1 + aa / c
            if abs(c) < _TINY:
                c = _TINY
            delta = c * d
            h *= delta
        if abs(delta - 1) < _EPS:
            return h
    raise ArithmeticError("incomplete beta did not converge")


def _ibeta_half(a, x):
    """Regularized incomplete beta I_x(a, 1/2), 0 < x < 1."""
    b = _HALF
    front = x**a * (1 - x) ** b / _beta_half(a)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    # symmetry: I_x(a,b) = 1 - I_(1-x)(b,a); same front factor
    return 1 - front * _betacf(b, a, 1 - x) / b


def _check_df(df):
    if not isinstance(df, int) or isinstance(df, bool) or df < 1:
        raise ValueError("df must be a whole number >= 1")


def cdf(t, df):
    """P(T <= t) for Student t with df degrees of freedom."""
    if not isinstance(t, Decimal):
        raise TypeError(f"expected Decimal, got {type(t).__name__}: {t!r}")
    _check_df(df)
    with localcontext() as ctx:
        ctx.prec = PREC
        if t == 0:
            return _HALF
        x = Decimal(df) / (Decimal(df) + t * t)
        tail = _ibeta_half(Decimal(df) / 2, x) / 2
        return 1 - tail if t > 0 else tail


@lru_cache(maxsize=256)
def _quantile(p, df):
    with localcontext() as ctx:
        ctx.prec = PREC
        hi = Decimal(1)
        while cdf(hi, df) < p:
            hi *= 2
            if hi > Decimal(10) ** 12:
                raise ArithmeticError("t quantile out of range")
        lo = hi / 2 if hi > 1 else Decimal(0)
        while hi - lo > Decimal("1e-30"):
            mid = (lo + hi) / 2
            if cdf(mid, df) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


def t_quantile(p, df):
    """The t value with P(T <= t) = p (for example p = 0.95, df = 4 gives 2.1318...)."""
    if not isinstance(p, Decimal):
        raise TypeError(f"expected Decimal, got {type(p).__name__}: {p!r}")
    _check_df(df)
    if not Decimal(0) < p < Decimal(1):
        raise ValueError("p must be between 0 and 1 (not including them)")
    if p == _HALF:
        return Decimal(0)
    if p < _HALF:
        return -_quantile(1 - p, df)
    return _quantile(p, df)
