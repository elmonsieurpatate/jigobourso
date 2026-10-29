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


def prepare_series(bars, splits=()):
    """One financial basis for charts, metrics and strategies, without truncation."""
    dates, closes, basis = usable_closes(bars)
    events = [(s, None) if isinstance(s, str) else (s[0], s[1]) for s in splits]
    unknown = []
    if basis == 'raw':
        for day, ratio in events:
            if ratio is None or ratio <= 0 or not math.isfinite(ratio):
                unknown.append(day)
            else:
                boundary = next((i for i in range(1, len(dates)) if dates[i - 1] < day <= dates[i]), None)
                if boundary is None:
                    continue
                observed = closes[boundary] / closes[boundary - 1]
                # Some providers already split-adjust their nominal "close". Never
                # apply the event a second time without evidence of a unit change.
                if abs(math.log(observed * ratio)) >= abs(math.log(observed)) and ratio != 1:
                    unknown.append(day)
                else:
                    closes = [c / ratio if d < day else c for d, c in zip(dates, closes)]
    breaks = find_breaks(dates, closes, basis, unknown)
    return dates, closes, basis, breaks


def analyze_series(bars, windows, splits=()):
    """Use the same adjusted or raw series for every consumer.

    Ratio = new shares / old shares. Vendor adjustments take precedence;
    otherwise known ratios adjust all earlier raw closes. Unknown ratios
    invalidate crossing windows. No arbitrary cut-off changes the price basis.
    """
    from .measures import window_metrics, technical_state
    dates, closes, basis, breaks = prepare_series(bars, splits)
    measures, missing = {}, {}
    for n in windows:
        window, why = clean_window(closes, n, breaks)
        measures[n] = window_metrics(window) if window else None
        if window is None:
            missing[n] = why
    return dates, closes, basis, breaks, measures, missing, technical_state(closes[breaks[-1]:] if breaks else closes)
