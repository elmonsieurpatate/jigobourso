"""Mesures propres aux scores, calculées par fenêtre depuis les clôtures (en plus de strategy_metrics : pente, R², volatilité, drawdown).

  up_fraction  part des séances de la fenêtre qui ont monté
  spike_share  concentration V1 : ln(1 + plus forte hausse d'une séance) / ln(cours final / cours initial) ; 1 si la fenêtre ne monte pas
  accel        pente de la fenêtre moins pente de la fenêtre précédente de même durée (deux fenêtres consécutives sans chevauchement de rendements)
  r2_prev      R² de la fenêtre précédente (une accélération entre deux fenêtres irrégulières n'est pas fiable)

Une clôture absente rend ces mesures indisponibles (None) : on ne comble jamais un trou.
"""
import math
from .measures import window_metrics


def _values(dates, observations):
    if not dates:
        return None
    vals = [observations.get(d) for d in dates]
    return None if any(v is None or not v > 0 or not math.isfinite(v) for v in vals) else [float(v) for v in vals]


def path_inputs(closes):
    """up_fraction et spike_share d'une fenêtre complète de n+1 clôtures."""
    if not closes or len(closes) < 3:
        return {'up_fraction': None, 'spike_share': None}
    steps = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    total = math.log(closes[-1] / closes[0])
    return {'up_fraction': sum(1 for s in steps if s > 0) / len(steps),
            'spike_share': (math.log1p(max(steps)) / total) if total > 0 else 1.0}


def window_inputs(current_dates, previous_dates, observations):
    """Mesures de score d'une fenêtre. current_dates / previous_dates : séances attendues (n+1 chacune) ; observations : {date: clôture}."""
    cur = _values(current_dates, observations)
    out = {'up_fraction': None, 'spike_share': None, 'accel': None, 'r2_prev': None}
    if cur is None:
        return out
    out.update(path_inputs(cur))
    prev = _values(previous_dates, observations)
    if prev is not None:
        a, b = window_metrics(cur), window_metrics(prev)
        if a and b and a['slope'] is not None and b['slope'] is not None:
            out['accel'], out['r2_prev'] = a['slope'] - b['slope'], b['r2']
    return out
