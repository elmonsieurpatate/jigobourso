"""Préparation d'une série de clôtures : choix cours bruts / ajustés et détection des ruptures de cours."""
import datetime
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


# ── Erreurs de données identifiables (sans inventer de prix ni effacer un vrai mouvement) ──
UNIT_FACTOR = 100.0        # livres / pence (Londres), rands / cents, shekels / agorot : Yahoo bascule parfois d'une unité à l'autre
UNIT_TOLERANCE = 0.06      # un vrai mouvement n'est jamais de ×100 en une séance : un saut de ×100 ou ÷100 (± 6 %) est un changement d'unité
SPIKE_FACTOR = 4.0         # un cours isolé à plus de ×4 (ou ÷4) de ses DEUX voisines, qui se ressemblent, est une erreur de donnée ponctuelle


def _near_day(day, others, tolerance=5):
    d = datetime.date.fromisoformat(day)
    return any(abs((d - datetime.date.fromisoformat(o)).days) <= tolerance for o in others)


def normalize_units(dates, closes, protected=()):
    """Ramène tous les cours à l'unité de la DERNIÈRE séance. Un saut de ×100 ou ÷100 est un changement d'unité, pas un rendement : l'historique antérieur est
    mis à l'échelle de ×100 (ou ÷100) et le vrai mouvement restant (par ex. +0,14 %) est conservé. Les dates proches d'un split déclaré sont laissées de côté.
    Renvoie (cours corrigés, notes)."""
    n = len(closes)
    out, notes, scale = list(closes), [], 1.0
    for i in range(n - 1, 0, -1):
        r = closes[i] / closes[i - 1]
        if (abs(r / UNIT_FACTOR - 1) <= UNIT_TOLERANCE or abs(r * UNIT_FACTOR - 1) <= UNIT_TOLERANCE) and not _near_day(dates[i], protected):
            factor = UNIT_FACTOR if r > 1 else 1 / UNIT_FACTOR
            scale *= factor
            notes.append({'kind': 'unit', 'date': dates[i], 'factor': factor})
        out[i - 1] = closes[i - 1] * scale
    return out, sorted(notes, key=lambda x: x['date'])


def drop_isolated_spikes(dates, closes):
    """Retire (sans rien remplacer) un cours isolé à plus de ×4 / ÷4 de ses deux voisins quand ceux-ci se ressemblent (à ×1,6 près) : erreur de donnée ponctuelle.
    Une vraie rupture ou un vrai mouvement persistant n'est jamais concerné (le cours suivant ne revient pas au niveau d'avant). Renvoie (dates, cours, notes)."""
    keep, notes = [], []
    for i in range(len(closes)):
        if 0 < i < len(closes) - 1:
            a, b, c = closes[i - 1], closes[i], closes[i + 1]
            if a > 0 and c > 0 and b > 0 and 1 / BREAK_RATIO < a / c < BREAK_RATIO and ((b / a <= 1 / SPIKE_FACTOR and b / c <= 1 / SPIKE_FACTOR) or (b / a >= SPIKE_FACTOR and b / c >= SPIKE_FACTOR)):
                notes.append({'kind': 'spike', 'date': dates[i], 'close': b, 'neighbours': [a, c]})
                continue
        keep.append(i)
    return [dates[i] for i in keep], [closes[i] for i in keep], notes


def _clean(bars, splits=()):
    """Séries utilisables + corrections de données appliquées (changements d'unité, cours aberrants isolés)."""
    dates, closes, basis = usable_closes(bars)
    protected = [s if isinstance(s, str) else s[0] for s in splits]
    closes, unit_notes = normalize_units(dates, closes, protected)
    dates, closes, spike_notes = drop_isolated_spikes(dates, closes)
    return dates, closes, basis, unit_notes + spike_notes


def data_corrections(bars, splits=()):
    """Corrections de données appliquées à cette série (pour l'afficher : rien n'est corrigé en silence)."""
    return _clean(bars, splits)[3]


def prepare_series(bars, splits=()):
    """One financial basis for charts, metrics and strategies, without truncation."""
    dates, closes, basis, _ = _clean(bars, splits)
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


def analyze_series(bars, windows, splits=(), session_windows=None, technical_sessions=None):
    """Use the same adjusted or raw series for every consumer.

    Ratio = new shares / old shares. Vendor adjustments take precedence;
    otherwise known ratios adjust all earlier raw closes. Unknown ratios
    invalidate crossing windows. No arbitrary cut-off changes the price basis.
    """
    from .measures import window_metrics, technical_state, dated_window_metrics, dated_technical_state
    dates, closes, basis, breaks = prepare_series(bars, splits)
    observations = dict(zip(dates, closes))
    measures, missing = {}, {}
    for n in windows:
        expected = (session_windows or {}).get(n)
        if session_windows is not None:
            if not expected:
                measures[n] = None
                missing[n] = 'calendar'
                continue
            measured, info = dated_window_metrics(expected, observations)
            if measured is not None:
                measured.update(info)
            start, end = expected[0], expected[-1]
            crossed_break = any(start < dates[i] <= end for i in breaks)
            if crossed_break:
                measured = None
                missing[n] = 'break'
            elif measured is None or (measured.get('slope') is None and n > 1):
                missing[n] = 'coverage'
            measures[n] = measured
        else:
            window, why = clean_window(closes, n, breaks)
            measures[n] = window_metrics(window) if window else None
            if window is None:
                missing[n] = why
    if technical_sessions is not None:
        tech = dated_technical_state(technical_sessions, observations)
    else:
        tech = technical_state(closes[breaks[-1]:] if breaks else closes)
    return dates, closes, basis, breaks, measures, missing, tech
