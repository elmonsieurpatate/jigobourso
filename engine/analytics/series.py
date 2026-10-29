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
    """Sauts de cours non expliqués. Sur cours bruts, un split non ajusté invalide la fenêtre ; sur cours ajustés
    il aurait déjà été absorbé, donc tout saut restant est suspect. Renvoie la liste des index i (saut entre i-1 et i)."""
    # A declared split without trustworthy adjusted prices is NOT an economic return.
    # It invalidates a crossing window, even if its ratio is below the jump heuristic.
    unexplained_splits = set(split_dates) if basis == 'raw' else set()
    return [i for i in range(1, len(closes))
            if closes[i] / closes[i - 1] > BREAK_RATIO or closes[i] / closes[i - 1] < 1 / BREAK_RATIO
            or (basis == 'raw' and any(dates[i - 1] < d <= dates[i] for d in unexplained_splits))]


def clean_window(closes, sessions, break_indexes):
    """Fenêtre de `sessions` séances (sessions+1 clôtures), ou (None, raison)."""
    need = sessions + 1
    if len(closes) < need:
        return None, 'history'
    start = len(closes) - need
    if any(i > start for i in break_indexes):
        return None, 'break'
    return closes[start:], None


def analyze_series(bars, windows, splits=()):
    """Shared financial preparation: adjusted closes, or split-adjusted raw closes.

    Split ratio = new shares / old shares. Before a 2:1 split, 100 becomes 50.
    Unknown ratios invalidate crossing windows, never simulate a gain/loss.
    No mixture of vendor-adjusted and unadjusted prices. Analysis uses 300 bars.
    """
    from .measures import window_metrics, technical_state
    rows = list(bars)[-300:]
    dates, closes, basis = usable_closes(rows)
    events = [(s, None) if isinstance(s, str) else (s[0], s[1]) for s in splits]
    unknown = []
    if basis == 'raw':
        for day, ratio in events:
            if ratio is None or ratio <= 0 or not math.isfinite(ratio):
                unknown.append(day)
            else:
                closes = [c / ratio if d < day else c for d, c in zip(dates, closes)]
    breaks = find_breaks(dates, closes, basis, unknown)
    measures, missing = {}, {}
    for n in windows:
        window, why = clean_window(closes, n, breaks)
        measures[n] = window_metrics(window) if window else None
        if window is None:
            missing[n] = why
    return dates, closes, basis, breaks, measures, missing, technical_state(closes)
