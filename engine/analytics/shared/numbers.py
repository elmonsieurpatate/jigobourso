"""Conversion numérique tolérante."""
import math


def finite(value):
    """`value` converti en float, ou None s'il n'est pas convertible ou pas fini (NaN, infini)."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def downsample(values, points):
    """Au plus `points` valeurs réparties régulièrement, première et dernière comprises (la forme de la courbe est conservée)."""
    if len(values) <= points:
        return list(values)
    last = len(values) - 1
    return [values[round(i * last / (points - 1))] for i in range(points)]
