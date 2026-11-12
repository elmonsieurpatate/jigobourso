"""Conversion numérique tolérante."""
import math


def finite(value):
    """`value` converti en float, ou None s'il n'est pas convertible ou pas fini (NaN, infini)."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None
