"""Mesures de tendance sur une fenêtre de clôtures. Fonctions pures, bibliothèque standard seulement.

Une fenêtre de n séances utilise n+1 clôtures consécutives. Toutes les mesures portent sur le logarithme
du cours : une hausse de 10 % puis une baisse de 10 % ne s'annulent pas, et un titre à 5 € se compare à
un titre à 500 €.

Définitions (unités affichables) :
  slope       pente de la régression de ln(cours) sur le temps, en % par séance : 100·(e^b − 1)
  r2          part de la variance de ln(cours) expliquée par cette droite, 0 à 1 (régularité de la hausse)
  perf        variation entre première et dernière clôture, en %
  volatility  écart-type des variations quotidiennes de ln(cours), en % par séance
  drawdown    plus forte baisse depuis un sommet de la fenêtre, en % (valeur positive)
  er          rendement net / distance parcourue en ln(cours) : +1 = montée sans aucun repli, 0 = aller-retour,
              négatif = baisse. Mesure l'efficacité de la progression.
Fenêtres courtes : 1 séance = performance seule ; 2 séances = pas de régression (R² et ER non définis) ;
volatilité à partir de 3 séances.
"""

import math

MIN_SESSIONS, MAX_SESSIONS = 1, 1260


def window_metrics(closes):
    """Mesures d'une fenêtre ; `closes` = n+1 clôtures strictement positives. None si fenêtre invalide."""
    if len(closes) < 2 or any(not (c > 0) or not math.isfinite(c) for c in closes):
        return None
    n = len(closes) - 1
    logs = [math.log(c) for c in closes]
    steps = [logs[i + 1] - logs[i] for i in range(n)]
    out = {'sessions': n, 'perf': 100 * math.expm1(logs[-1] - logs[0]), 'slope': None, 'slope_log': None, 'r2': None, 'volatility': None, 'drawdown': None, 'er': None}
    peak, worst = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        worst = max(worst, 1 - c / peak)
    out['drawdown'] = 100 * worst
    if n == 1:
        out['slope_log'] = steps[0]
        out['slope'] = 100 * math.expm1(steps[0])
        return out
    # Régression par moindres carrés sur t = 0..n
    mean_t, mean_y = n / 2, sum(logs) / (n + 1)
    sxx = sum((t - mean_t) ** 2 for t in range(n + 1))
    sxy = sum((t - mean_t) * (y - mean_y) for t, y in enumerate(logs))
    syy = sum((y - mean_y) ** 2 for y in logs)
    b = sxy / sxx
    out['slope_log'] = b
    out['slope'] = 100 * math.expm1(b)
    out['r2'] = 1.0 if syy == 0 else min(1.0, (sxy * sxy) / (sxx * syy))
    if n >= 3:
        m = sum(steps) / n
        out['volatility'] = 100 * math.sqrt(sum((s - m) ** 2 for s in steps) / (n - 1))
    path = sum(abs(s) for s in steps)
    out['er'] = 0.0 if path == 0 else (logs[-1] - logs[0]) / path
    return out


# Tolérance aux données imparfaites (Yahoo omet des séances, jours fériés inconnus du calendrier, suspensions) : une règle unique pour toutes les mesures d'une fenêtre.
MIN_COVERAGE = 0.80  # part minimale des n+1 clôtures attendues réellement observées
MAX_GAP = 10  # séances consécutives manquantes tolérées (au milieu, au début ou à la fin de la fenêtre) ; au-delà : interruption, la fenêtre n'est pas mesurée


def observed_points(session_dates, observations):
    """[(rang de la séance attendue, clôture)] des clôtures réellement observées aux séances attendues (cours strictement positifs). Rien n'est comblé ni inventé."""
    points = []
    for i, day in enumerate(session_dates or ()):
        value = observations.get(day)
        if value is None:
            continue
        value = float(value)
        if value > 0 and math.isfinite(value):
            points.append((i, value))
    return points


def window_diagnosis(count, points):
    """Qualifie une fenêtre de `count` clôtures attendues dont `points` sont observées.
    status : 'ok' (complète, ou lacunes tolérées : couverture ≥ MIN_COVERAGE et aucune interruption de plus de MAX_GAP séances),
             'history' (le titre ne cote que depuis plus de MAX_GAP séances après le début de la fenêtre : historique trop court),
             'gap' (interruption de plus de MAX_GAP séances en cours de fenêtre ou à sa fin), 'coverage' (trop de clôtures absentes)."""
    info = {'observations': len(points), 'expected_closes': count, 'coverage': (len(points) / count) if count else 0.0, 'missing_sessions': count - len(points), 'max_gap': count}
    if len(points) < 2:
        info['status'] = 'history' if not points else 'coverage'
        return info
    lead, trail = points[0][0], count - 1 - points[-1][0]
    inner = max((b[0] - a[0] - 1 for a, b in zip(points, points[1:])), default=0)
    info['max_gap'] = max(lead, trail, inner)
    if len(points) == count:
        info['status'] = 'ok'
    elif lead > MAX_GAP and inner <= MAX_GAP and trail <= MAX_GAP:
        info['status'] = 'history'
    elif inner > MAX_GAP or trail > MAX_GAP or lead > MAX_GAP:
        info['status'] = 'gap'
    elif info['coverage'] < MIN_COVERAGE:
        info['status'] = 'coverage'
    else:
        info['status'] = 'ok'
    return info


def gap_metrics(points, n):
    """Mêmes mesures que window_metrics sur des clôtures observées à des rangs de séance quelconques (lacunes tolérées).
    Rien n'est comblé : pente et R² par régression sur le rang réel des séances ; volatilité par séance = variance des variations observées divisée par la durée
    qu'elles couvrent (un intervalle de k séances compte k séances, jamais une) ; drawdown et efficacité sur les clôtures observées.
    Sur une fenêtre complète le résultat est identique à window_metrics (testé)."""
    idx = [i for i, _ in points]
    vals = [v for _, v in points]
    logs = [math.log(v) for v in vals]
    gaps = [idx[j + 1] - idx[j] for j in range(len(idx) - 1)]
    steps = [logs[j + 1] - logs[j] for j in range(len(idx) - 1)]
    out = {'sessions': n, 'perf': 100 * math.expm1(logs[-1] - logs[0]), 'slope': None, 'slope_log': None, 'r2': None, 'volatility': None, 'drawdown': None, 'er': None}
    peak, worst = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        worst = max(worst, 1 - v / peak)
    out['drawdown'] = 100 * worst
    mean_x, mean_y = sum(idx) / len(idx), sum(logs) / len(logs)
    sxx = sum((x - mean_x) ** 2 for x in idx)
    if sxx <= 0:
        return out
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(idx, logs))
    syy = sum((y - mean_y) ** 2 for y in logs)
    b = sxy / sxx
    out['slope_log'] = b
    out['slope'] = 100 * math.expm1(b)
    out['r2'] = 1.0 if syy == 0 else min(1.0, (sxy * sxy) / (sxx * syy))
    if len(steps) >= 3:
        drift = sum(steps) / (idx[-1] - idx[0])
        out['volatility'] = 100 * math.sqrt(sum((s - g * drift) ** 2 / g for s, g in zip(steps, gaps)) / (len(steps) - 1))
    path = sum(abs(s) for s in steps)
    out['er'] = 0.0 if path == 0 else (logs[-1] - logs[0]) / path
    return out


def dated_window_metrics(session_dates, observations):
    """Mesures d'une fenêtre indexée par ses vraies séances, sans jamais combler les trous.

    `session_dates` contient n+1 dates de clôture attendues ; observations est {date_iso: close}. Fenêtre complète : calcul historique, résultats inchangés.
    Fenêtre lacunaire : toutes les mesures (pente, R², volatilité, drawdown, efficacité, performance) sont calculées sur les clôtures réellement observées et leur rang réel
    (gap_metrics), tant que la fenêtre respecte la règle de couverture (voir window_diagnosis : MIN_COVERAGE et MAX_GAP). Sinon, mesures à None et `status` explique pourquoi."""
    expected = list(session_dates or ())
    if len(expected) < 2:
        return None, {'observations': 0, 'expected_closes': len(expected), 'coverage': 0.0, 'status': 'coverage'}
    points = observed_points(expected, observations)
    info = window_diagnosis(len(expected), points)
    n_expected = len(expected) - 1
    if info['status'] != 'ok':
        return {'sessions': n_expected, 'perf': None, 'slope': None, 'slope_log': None, 'r2': None, 'volatility': None, 'drawdown': None, 'er': None}, info
    if len(points) == len(expected):
        return dict(window_metrics([v for _, v in points]), **{'coverage': 1.0, 'observations': len(points), 'expected_closes': len(expected), 'missing_sessions': 0}), info
    if n_expected == 1 or len(points) < 3:
        return {'sessions': n_expected, 'perf': None, 'slope': None, 'slope_log': None, 'r2': None, 'volatility': None, 'drawdown': None, 'er': None}, info
    return gap_metrics(points, n_expected), info


def moving_average(closes, length):
    """Moyenne simple des `length` dernières clôtures ; None si historique trop court."""
    return sum(closes[-length:]) / length if len(closes) >= length else None


def technical_state(closes):
    """Indicateurs de contexte : dernière clôture, MA20, MA50, MA50 d'il y a 5 séances, variation du jour, écart à la MA20."""
    if not closes:
        return {'close': None, 'ma20': None, 'ma50': None, 'ma50_prev': None, 'daily_change': None, 'gap_to_ma20': None}
    ma20 = moving_average(closes, 20)
    return {
        'close': closes[-1],
        'ma20': ma20,
        'ma50': moving_average(closes, 50),
        'ma50_prev': moving_average(closes[:-5], 50) if len(closes) > 5 else None,
        'ma200': moving_average(closes, 200),
        'ma200_prev': moving_average(closes[:-5], 200) if len(closes) > 205 else None,
        'daily_change': 100 * (closes[-1] / closes[-2] - 1) if len(closes) >= 2 else None,
        'gap_to_ma20': 100 * (closes[-1] / ma20 - 1) if ma20 else None,
    }


def dated_technical_state(expected_dates, observations):
    """Indicateurs de contexte calculés sur des séances calendaires sans sauter les trous."""
    dates = list(expected_dates or ())

    def values(days):
        if len(days) != len(set(days)) or not days or any(d not in observations for d in days):
            return None
        return [float(observations[d]) for d in days]

    close = observations.get(dates[-1]) if dates else None
    last20, last50 = values(dates[-20:]), values(dates[-50:])
    prev50 = values(dates[-55:-5]) if len(dates) >= 55 else None
    last200 = values(dates[-200:])
    prev200 = values(dates[-205:-5]) if len(dates) >= 205 else None
    last2 = values(dates[-2:])
    ma20 = sum(last20) / 20 if last20 else None
    ma50 = sum(last50) / 50 if last50 else None
    ma50_prev = sum(prev50) / 50 if prev50 else None
    ma200 = sum(last200) / 200 if last200 else None
    ma200_prev = sum(prev200) / 200 if prev200 else None
    daily = 100 * (last2[-1] / last2[0] - 1) if last2 else None
    return {
        'close': float(close) if close is not None else None,
        'ma20': ma20,
        'ma50': ma50,
        'ma50_prev': ma50_prev,
        'ma200': ma200,
        'ma200_prev': ma200_prev,
        'daily_change': daily,
        'gap_to_ma20': 100 * (float(close) / ma20 - 1) if close is not None and ma20 else None,
    }
