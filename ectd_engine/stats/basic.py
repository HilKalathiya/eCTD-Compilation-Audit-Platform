"""Mean, SD, %RSD, half-up rounding and spec comparison, using Decimal only (never float)."""
from decimal import ROUND_HALF_UP, Decimal, localcontext

PREC = 50  # digits kept inside every calculation


def _check(values):
    values = list(values)
    for v in values:
        if not isinstance(v, Decimal):
            raise TypeError(f"expected Decimal, got {type(v).__name__}: {v!r}")
    return values


def mean(values):
    values = _check(values)
    if not values:
        raise ValueError("mean needs at least 1 value")
    with localcontext() as ctx:
        ctx.prec = PREC
        return sum(values, Decimal(0)) / len(values)


def sd(values):
    """Sample standard deviation (divides by n-1)."""
    values = _check(values)
    if len(values) < 2:
        raise ValueError("sd needs at least 2 values")
    with localcontext() as ctx:
        ctx.prec = PREC
        m = mean(values)
        ss = sum(((v - m) ** 2 for v in values), Decimal(0))
        return (ss / (len(values) - 1)).sqrt()


def rsd_percent(values):
    """Relative standard deviation: SD / mean * 100."""
    values = _check(values)
    with localcontext() as ctx:
        ctx.prec = PREC
        m = mean(values)
        if m == 0:
            raise ValueError("rsd is undefined when the mean is 0")
        return sd(values) / m * 100


def round_to(value, decimals):
    """Round half up to `decimals` places (0.125 -> 0.13)."""
    if not isinstance(value, Decimal):
        raise TypeError(f"expected Decimal, got {type(value).__name__}: {value!r}")
    if not isinstance(decimals, int) or isinstance(decimals, bool) or decimals < 0:
        raise ValueError("decimals must be an int >= 0")
    with localcontext() as ctx:
        ctx.prec = PREC
        return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _places(spec):
    return max(0, -spec.as_tuple().exponent)


def conforms(value, spec_min=None, spec_max=None):
    """True if the value, rounded to each limit's own decimal places, is inside the limits."""
    if not isinstance(value, Decimal):
        raise TypeError(f"expected Decimal, got {type(value).__name__}: {value!r}")
    for spec in (spec_min, spec_max):
        if spec is not None and not isinstance(spec, Decimal):
            raise TypeError(f"spec limit must be Decimal, got {type(spec).__name__}: {spec!r}")
    if spec_min is None and spec_max is None:
        raise ValueError("give at least one spec limit")
    if spec_min is not None and round_to(value, _places(spec_min)) < spec_min:
        return False
    if spec_max is not None and round_to(value, _places(spec_max)) > spec_max:
        return False
    return True
