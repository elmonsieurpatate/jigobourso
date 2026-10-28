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

MIN_SESSIONS, MAX_SESSIONS = 1, 252


def window_metrics(closes):
    """Mesures d'une fenêtre ; `closes` = n+1 clôtures strictement positives. None si fenêtre invalide."""
    if len(closes) < 2 or any(not (c > 0) or not math.isfinite(c) for c in closes):
        return None
    n = len(closes) - 1
    logs = [math.log(c) for c in closes]
    steps = [logs[i + 1] - logs[i] for i in range(n)]
    out = {'sessions': n, 'perf': 100 * math.expm1(logs[-1] - logs[0]),
           'slope': None, 'slope_log': None, 'r2': None, 'volatility': None, 'drawdown': None, 'er': None}
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


def moving_average(closes, length):
    """Moyenne simple des `length` dernières clôtures ; None si historique trop court."""
    return sum(closes[-length:]) / length if len(closes) >= length else None


def technical_state(closes):
    """Indicateurs de contexte : dernière clôture, MA20, MA50, MA50 d'il y a 5 séances, variation du jour, écart à la MA20."""
    if not closes:
        return {'close': None, 'ma20': None, 'ma50': None, 'ma50_prev': None, 'daily_change': None, 'gap_to_ma20': None}
    ma20 = moving_average(closes, 20)
    return {'close': closes[-1], 'ma20': ma20, 'ma50': moving_average(closes, 50),
            'ma50_prev': moving_average(closes[:-5], 50) if len(closes) > 5 else None,
            'daily_change': 100 * (closes[-1] / closes[-2] - 1) if len(closes) >= 2 else None,
            'gap_to_ma20': 100 * (closes[-1] / ma20 - 1) if ma20 else None}
