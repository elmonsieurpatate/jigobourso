"""Liquidité d'un titre : valeur échangée moyenne par séance, en euros.

Deux sources, jamais mélangées ni confondues :
  daily      volumes quotidiens réels (daily_prices.volume) × cours de la séance, moyenne des séances renseignées sur les 20 dernières
  estimated  volume moyen 3 mois (cotation Yahoo) × dernier cours : ESTIMATION, signalée partout tant que les volumes réels manquent
Un volume absent n'est jamais compté comme zéro : une séance sans volume est ignorée, et sous le minimum de séances renseignées on retombe sur l'estimation.
"""
import math

WINDOW = 20            # séances de la moyenne
MIN_DAYS = 15          # séances renseignées minimales pour parler de volumes réels
MAX_PLAUSIBLE_VOLUME = 1e13


def valid_volume(v):
    """Volume exploitable : entier ou flottant fini, positif ou nul, d'un ordre de grandeur plausible. Sinon None (inconnu, pas zéro)."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v) if 0 <= v <= MAX_PLAUSIBLE_VOLUME else None


def daily_turnover(bars, factor):
    """bars : [(close, volume)] des dernières séances, de la plus ancienne à la plus récente. factor : conversion en euros.
    Renvoie (valeur_eur, séances_utilisées) ou (None, n) si moins de MIN_DAYS séances ont un volume réel."""
    values = []
    for close, volume in bars[-WINDOW:]:
        v = valid_volume(volume)
        if v is not None and close is not None and close > 0 and factor:
            values.append(close * v * factor)
    if len(values) < MIN_DAYS:
        return None, len(values)
    return sum(values) / len(values), len(values)


def estimated_turnover(price, avg_volume_3m, factor):
    v = valid_volume(avg_volume_3m)
    if v is None or not price or price <= 0 or not factor:
        return None
    return price * v * factor


def liquidity(bars, price, avg_volume_3m, factor):
    """Renvoie {'turnover_eur', 'days', 'source'} ; source None si rien n'est connu."""
    real, days = daily_turnover(bars, factor)
    if real is not None:
        return {'turnover_eur': real, 'days': days, 'source': 'daily'}
    est = estimated_turnover(price, avg_volume_3m, factor)
    return {'turnover_eur': est, 'days': days, 'source': 'estimated' if est is not None else None}


US_MICS = frozenset({'XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS'})      # seuil de liquidité V1 plus élevé sur les places américaines (5 M contre 2 M)
