"""Préparation d'une série de clôtures : choix cours bruts / ajustés et détection des ruptures de cours."""
import math

BREAK_RATIO = 1.6   # variation d'une séance à l'autre au-delà de laquelle un saut est suspect (×1,6 ou ÷1,6)


def usable_closes(bars):
    """bars = [(date, close, adj_close|None)] triées. Renvoie (dates, closes, basis).

    Cours ajustés si TOUTES les clôtures en ont (jamais de mélange brut/ajusté dans une même série), sinon bruts.
    Les valeurs non positives ou non finies sont ignorées."""
    rows = [(d, c, a) for d, c, a in bars if c is not None and c > 0 and math.isfinite(c)]
    if rows and all(a is not None and a > 0 and math.isfinite(a) for _, _, a in rows):
        return [d for d, _, _ in rows], [a for _, _, a in rows], 'adjusted'
    return [d for d, _, _ in rows], [c for _, c, _ in rows], 'raw'


def find_breaks(dates, closes, basis, split_dates=()):
    """Sauts de cours non expliqués. Sur cours bruts, un split connu (±1 jour) explique le saut ; sur cours ajustés
    il aurait déjà été absorbé, donc tout saut restant est suspect. Renvoie la liste des index i (saut entre i-1 et i)."""
    explained = set(split_dates) if basis == 'raw' else set()
    found = []
    for i in range(1, len(closes)):
        r = closes[i] / closes[i - 1]
        if r > BREAK_RATIO or r < 1 / BREAK_RATIO:
            near = {dates[i], dates[i - 1]}
            if not near & explained:
                found.append(i)
    return found


def clean_window(closes, sessions, break_indexes):
    """Fenêtre de `sessions` séances (sessions+1 clôtures), ou (None, raison)."""
    need = sessions + 1
    if len(closes) < need:
        return None, 'history'
    start = len(closes) - need
    if any(i > start for i in break_indexes):
        return None, 'break'
    return closes[start:], None
