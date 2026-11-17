"""Mesures propres aux scores, calculées par fenêtre depuis les clôtures (en plus de strategy_metrics : pente, R², volatilité, drawdown).

  up_fraction  part des séances de la fenêtre qui ont monté
  spike_share  concentration V1 : ln(1 + plus forte hausse d'une séance) / ln(cours final / cours initial) ; 1 si la fenêtre ne monte pas
  accel        différence de pente par séance entre les deux moitiés successives de la période
  r2_prev      minimum des R² des deux moitiés, pour la fiabilité de l'accélération
  mrar         rendement ajusté du risque (Morningstar, γ = 2) annualisé, en %, sur les rendements mensuels CALENDAIRES de la fenêtre (cours de prix : ni dividendes ni frais)

Une clôture absente rend ces mesures indisponibles (None) : on ne comble jamais un trou.
"""

import math
from ..series.measures import window_metrics


RISK_GAMMA = 2.0  # aversion au risque du MRAR : constante de conception (Morningstar), jamais un réglage
MRAR_MIN_SESSIONS = 252  # en dessous d'un an, douze rendements mensuels n'existent pas : aucune valeur
MRAR_MIN_MONTHS = 10  # rendements mensuels complets minimaux (une fenêtre de 252 séances en contient 11 ou 12)
MRAR_CAP = 1e6  # %, borne de stockage d'une valeur extrême (colonne DECIMAL)


def monthly_returns(dates, closes):
    """Rendements des mois calendaires COMPLETS d'une fenêtre de séances (dates ISO croissantes, clôtures strictement positives, fenêtre sans trou).
    Ancre d'un mois = clôture de sa dernière séance. Le dernier mois de la fenêtre n'est pas terminé (son ancre serait la clôture du jour) : il est écarté.
    Le premier mois, commencé avant la fenêtre, ne sert que par son ancre. Une fenêtre de 756 séances (environ 36 mois) donne ainsi 34 à 36 rendements."""
    anchors = []
    for d, c in zip(dates, closes):
        month = str(d)[:7]
        if anchors and anchors[-1][0] == month:
            anchors[-1] = (month, c)
        else:
            anchors.append((month, c))
    anchors = anchors[:-1]
    return [anchors[i][1] / anchors[i - 1][1] - 1 for i in range(1, len(anchors))]


def mrar_input(dates, closes):
    """MRAR annualisé en % (γ = 2) : [ (1/T) · Σ (1 + r_k)^(−γ) ]^(−12/γ) − 1. None si la fenêtre est trop courte pour être significative.
    Aucun taux sans risque : pour un taux constant il transforme tous les titres de la même façon et ne change aucun classement.
    Rendement de PRIX : les dividendes ne sont pas dans les cours stockés."""
    if not closes or len(closes) - 1 < MRAR_MIN_SESSIONS:
        return None
    returns = monthly_returns(dates, closes)
    if len(returns) < MRAR_MIN_MONTHS:
        return None
    mean = sum((1 + r) ** -RISK_GAMMA for r in returns) / len(returns)
    try:
        value = 100 * (mean ** (-12 / RISK_GAMMA) - 1)
    except (OverflowError, ZeroDivisionError):
        return None
    return min(value, MRAR_CAP) if math.isfinite(value) else None


def window_mrar(current_dates, observations):
    """MRAR d'une fenêtre de séances à partir des clôtures observées (fiche titre) ; None si la fenêtre n'est pas complète."""
    return mrar_input(current_dates, _values(current_dates, observations))


def recent_exclusion(sessions):
    """Séances écartées du momentum ; les demis sont arrondis vers le haut."""
    return max(1, min(21, (sessions + 6) // 12))


def recovery_input(closes):
    """Plus grand recul sommet-creux, premier couple en cas d'égalité, puis reprise à la clôture."""
    if not closes or len(closes) < 4:
        return None
    peak = closes[0]
    best_depth = 0.0
    best_peak = best_trough = None
    for trough in closes[1:-1]:
        depth = 1 - trough / peak
        if depth > best_depth:
            best_depth, best_peak, best_trough = depth, peak, trough
        if trough > peak:
            peak = trough
    if best_peak is None:
        return 0.0
    recovered = max(0.0, min(1.0, (closes[-1] - best_trough) / (best_peak - best_trough)))
    return 100 * recovered * min(1.0, best_depth / 0.10)


def period_path_inputs(closes):
    """Mesures de trajectoire internes à une période complète de n séances."""
    out = {'accel': None, 'r2_prev': None, 'momentum_perf': None, 'recovery': None}
    if not closes or len(closes) < 4:
        return out
    n = len(closes) - 1
    cut = n // 2
    if cut >= 3 and n - cut >= 3:
        first, second = window_metrics(closes[: cut + 1]), window_metrics(closes[cut:])
        if first and second:
            out['accel'] = second['slope'] - first['slope']
            out['r2_prev'] = min(first['r2'], second['r2'])
    measured = n - recent_exclusion(n)
    if measured >= 1:
        out['momentum_perf'] = 100 * (closes[measured] / closes[0] - 1)
    out['recovery'] = recovery_input(closes)
    return out


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
    return {'up_fraction': sum(1 for s in steps if s > 0) / len(steps), 'spike_share': (math.log1p(max(steps)) / total) if total > 0 else 1.0}


def window_inputs(current_dates, previous_dates, observations):
    """Mesures de score internes à la fenêtre courante ; previous_dates reste accepté par l'ancienne interface."""
    cur = _values(current_dates, observations)
    out = {'up_fraction': None, 'spike_share': None, 'accel': None, 'r2_prev': None, 'momentum_perf': None, 'recovery': None, 'mrar': None}
    if cur is None:
        return out
    out.update(path_inputs(cur))
    out.update(period_path_inputs(cur))
    out['mrar'] = mrar_input(current_dates, cur)
    return out
