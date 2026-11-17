"""Mesures propres aux scores, calculées par fenêtre depuis les clôtures (en plus de strategy_metrics : pente, R², volatilité, drawdown).

  up_fraction  part des séances de la fenêtre qui ont monté
  spike_share  concentration V1 : ln(1 + plus forte hausse d'une séance) / ln(cours final / cours initial) ; 1 si la fenêtre ne monte pas
  accel        différence de pente par séance entre les deux moitiés successives de la période
  r2_prev      minimum des R² des deux moitiés, pour la fiabilité de l'accélération
  mrar         rendement ajusté du risque (Morningstar, γ = 2) annualisé, en %, sur les rendements mensuels CALENDAIRES de la fenêtre (cours de prix : ni dividendes ni frais)

Une fenêtre lacunaire reste mesurable si elle respecte la règle de couverture commune (measures.window_diagnosis : MIN_COVERAGE, MAX_GAP) : les mesures portent alors sur les clôtures réellement observées et leur rang
de séance réel, jamais sur un cours inventé. Au-delà (interruption, historique trop court) : None.
"""

import math
from ..series.measures import dated_window_metrics, observed_points, window_diagnosis


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
    for i in range(1, len(anchors)):
        year, month = int(anchors[i - 1][0][:4]), int(anchors[i - 1][0][5:7])
        if anchors[i][0] != f'{year + month // 12:04d}-{month % 12 + 1:02d}':
            return []  # un mois entier sans aucune clôture : interruption, aucun rendement mensuel fiable
    return [anchors[i][1] / anchors[i - 1][1] - 1 for i in range(1, len(anchors))]


def mrar_input(dates, closes, sessions=None):
    """MRAR annualisé en % (γ = 2) : [ (1/T) · Σ (1 + r_k)^(−γ) ]^(−12/γ) − 1. None si la fenêtre est trop courte pour être significative.
    Aucun taux sans risque : pour un taux constant il transforme tous les titres de la même façon et ne change aucun classement.
    Rendement de PRIX : les dividendes ne sont pas dans les cours stockés."""
    if not closes or (len(closes) - 1 if sessions is None else sessions) < MRAR_MIN_SESSIONS:
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
    """MRAR d'une fenêtre de séances à partir des clôtures observées (fiche titre) ; None si la fenêtre ne respecte pas la règle de couverture."""
    points = observed_points(current_dates, observations)
    if window_diagnosis(len(current_dates), points)['status'] != 'ok':
        return None
    return mrar_input([current_dates[i] for i, _ in points], [v for _, v in points], len(current_dates) - 1)


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


def _period_points(count, points):
    """Mesures de trajectoire d'une période de count-1 séances à partir des clôtures observées [(rang, clôture)] (lacunes tolérées, jamais comblées)."""
    out = {'accel': None, 'r2_prev': None, 'momentum_perf': None, 'recovery': None}
    if len(points) < 4:
        return out
    n = count - 1
    cut = n // 2
    if cut >= 3 and n - cut >= 3:
        ranks, seen = list(range(count)), dict(points)
        first, second = dated_window_metrics(ranks[: cut + 1], seen)[0], dated_window_metrics(ranks[cut:], seen)[0]
        if first and second and first['slope'] is not None and second['slope'] is not None:
            out['accel'] = second['slope'] - first['slope']
            out['r2_prev'] = min(first['r2'], second['r2'])
    measured = n - recent_exclusion(n)
    if measured >= 1:
        end = [v for i, v in points if i <= measured][-1]  # dernière clôture observée à ou avant la séance J − e(n) : jamais un cours inventé
        out['momentum_perf'] = 100 * (end / points[0][1] - 1)
    out['recovery'] = recovery_input([v for _, v in points])
    return out


def period_path_inputs(closes):
    """Mesures de trajectoire internes à une période complète de n séances."""
    if not closes or len(closes) < 4:
        return {'accel': None, 'r2_prev': None, 'momentum_perf': None, 'recovery': None}
    return _period_points(len(closes), list(enumerate(closes)))


def _path_points(points):
    """up_fraction et spike_share depuis les clôtures observées [(rang, clôture)] : chaque variation entre deux clôtures observées compte pour les séances qu'elle couvre
    (part des séances en hausse pondérée par la durée) ; la plus forte hausse est celle observée entre deux clôtures consécutives."""
    if len(points) < 3:
        return {'up_fraction': None, 'spike_share': None}
    spans = [b[0] - a[0] for a, b in zip(points, points[1:])]
    steps = [b[1] / a[1] - 1 for a, b in zip(points, points[1:])]
    total = math.log(points[-1][1] / points[0][1])
    return {
        'up_fraction': sum(k for k, s in zip(spans, steps) if s > 0) / sum(spans),
        'spike_share': (math.log1p(max(steps)) / total) if total > 0 else 1.0,
    }


def path_inputs(closes):
    """up_fraction et spike_share d'une fenêtre complète de n+1 clôtures."""
    if not closes:
        return {'up_fraction': None, 'spike_share': None}
    return _path_points(list(enumerate(closes)))


def window_inputs(current_dates, previous_dates, observations):
    """Mesures de score internes à la fenêtre courante ; previous_dates reste accepté par l'ancienne interface.
    Fenêtre complète ou lacunaire dans la tolérance commune : mesurée sur les clôtures observées. Sinon : tout à None."""
    out = {'up_fraction': None, 'spike_share': None, 'accel': None, 'r2_prev': None, 'momentum_perf': None, 'recovery': None, 'mrar': None}
    points = observed_points(current_dates, observations)
    if window_diagnosis(len(current_dates), points)['status'] != 'ok':
        return out
    out.update(_path_points(points))
    out.update(_period_points(len(current_dates), points))
    out['mrar'] = mrar_input([current_dates[i] for i, _ in points], [v for _, v in points], len(current_dates) - 1)
    return out
