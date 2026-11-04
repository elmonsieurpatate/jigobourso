"""Proposition de scores, non intégrée à l'application et NON validée.

Rejouer : .venv/bin/python -m scripts.preview_growth_v4
Uniquement des séries synthétiques ; aucun accès base, réseau ou configuration.
"""
import json
import math

from engine.analytics.measures import window_metrics
from engine.analytics.explorer_metrics import path_metrics
from engine.analytics import strategy, explorer_config


PERIODS = (5, 21, 63)
SLOPE_SCALE = .15  # %/séance, proposition non validée.
THRESHOLDS = {5: (.08, .65), 21: (.08, .70), 63: (.08, .75)}


def fixtures():
    paths = {}
    for name, start, end in [('acceleration', .0015, .0045),
                              ('stable', .003, .003),
                              ('ralentissement', .0033, .0027)]:
        logs = [math.log(100)]
        for i in range(63):
            logs.append(logs[-1] + start + (end - start) * i / 62)
        paths[name] = [math.exp(x) for x in logs]
    paths['plateau'] = [100 * math.exp(.003 * min(i, 58)) for i in range(64)]
    paths['pic_unique'] = [100.] * 59 + [110.] * 5
    paths['plat'] = [100.] * 64
    return paths


def proposal(prices, periods=PERIODS):
    """Banc de décision, pas une formule applicative gelée."""
    if not periods or len(prices) <= max(periods):
        return {'status': 'indisponible', 'simple': None, 'complexe': None,
                'reason': 'historique insuffisant', 'mesures': {}}
    metrics = {}
    for n in periods:
        window = prices[-(n + 1):]
        valid = sum(p is not None and p > 0 and math.isfinite(p) for p in window)
        core = window_metrics(window) if valid == len(window) else None
        coverage = dict(observations=valid, expected_closes=n + 1, coverage=valid / (n + 1))
        path = path_metrics(window) if core else {}
        metrics[n] = dict(core or {}, **path, **coverage)
    if any(m['coverage'] < 1 for m in metrics.values()):
        return {'status': 'indisponible', 'simple': None, 'complexe': None,
                'reason': 'clôtures manquantes ou invalides, aucune interpolation', 'mesures': metrics}
    admitted = all(m['slope'] >= THRESHOLDS[n][0] and m['r2'] >= THRESHOLDS[n][1]
                   for n, m in metrics.items())
    force = sum(100 * max(0, m['slope']) / (max(0, m['slope']) + SLOPE_SCALE)
                for m in metrics.values()) / len(metrics)
    regularity = sum(100 * m['r2'] for m in metrics.values()) / len(metrics)
    ordered = sorted(periods)
    changes = []
    for short, long in zip(ordered, ordered[1:]):
        a, b = metrics[short], metrics[long]
        denominator = abs(a['slope']) + abs(b['slope'])
        difference = (a['slope'] - b['slope']) / denominator if denominator else 0
        concentration = a['gain_share'] / 100
        anti_jump = min(1, (2 / short) / concentration) if concentration else 0
        # A single positive session has q=0, irrespective of jump amplitude.
        anti_jump *= max(0, (1 - concentration) / (1 - 1 / short))
        changes.append(math.tanh(2 * difference) * math.sqrt(a['r2'] * b['r2']) * anti_jump)
    evolution = 50 + 50 * sum(changes) / len(changes) if changes else None
    simple_parts = [(force, .35), (regularity, .35)]
    if evolution is not None:
        simple_parts.append((evolution, .30))
    simple = sum(v * w for v, w in simple_parts) / sum(w for _, w in simple_parts)
    risk = sum(100 / (1 + max(m['volatility'] / 1.5, m['drawdown'] / 20) ** 2)
               for m in metrics.values()) / len(metrics)
    continuity = sum(100 * min(m['up_fraction'], max(0, min(1, (1 - m['gain_share'] / 100) / (1 - 1 / n))))
                     for n, m in metrics.items()) / len(metrics)
    complex_parts = [(force, .25), (regularity, .25), (risk, .20), (continuity, .10)]
    if evolution is not None:
        complex_parts.append((evolution, .20))
    complex_score = sum(v * w for v, w in complex_parts) / sum(w for _, w in complex_parts)
    return {'status': 'admis' if admitted else 'non_admis',
            'simple': simple if admitted else None, 'complexe': complex_score if admitted else None,
            'decomposition': {
                'simple': [dict(valeur=v, poids=w, poids_effectif=w / sum(x[1] for x in simple_parts),
                                contribution=v * w / sum(x[1] for x in simple_parts)) for v, w in simple_parts],
                'complexe': [dict(valeur=v, poids=w, poids_effectif=w / sum(x[1] for x in complex_parts),
                                  contribution=v * w / sum(x[1] for x in complex_parts)) for v, w in complex_parts]},
            'components': dict(force=force, regularite=regularity, evolution=evolution,
                               risque=risk, continuite=continuity),
            'mesures': metrics}


def compare():
    out = {}
    for name, prices in fixtures().items():
        metrics = {n: window_metrics(prices[-(n + 1):]) for n in PERIODS}
        v3 = strategy.judge(strategy.preset('fast'), metrics, {}, {})
        day = prices[-1] / prices[-2] - 1
        week = prices[-1] / prices[-6] - 1
        month = prices[-1] / prices[-22] - 1
        steps = [math.log(b / a) for a, b in zip(prices[-22:-1], prices[-21:])]
        net = math.log(prices[-1] / prices[-22])
        spike_share = max(steps) / net if net > 0 else 1
        # Comparison of audited trajectory gates only: not the V1 scanner,
        # not its universe/liquidity/news checks and not a historical ranking.
        v1 = day > 0 and week >= .03 and month >= .08 and metrics[21]['r2'] >= .6 and spike_share <= .45
        proposed = proposal(prices)
        out[name] = dict(v1_strict_prix=v1, v3_fast=v3['status'], v4_proposition=proposed)
    return out


if __name__ == '__main__':
    missing = fixtures()['stable'][:]
    missing[-3] = None
    print(json.dumps({'statut': 'PROPOSITION_NON_VALIDEE', 'version': 'growth-draft-20261104',
                      'comparaison': compare(), 'donnees_manquantes': proposal(missing),
                      'une_periode': proposal(fixtures()['stable'], periods=(21,))},
                     ensure_ascii=False, indent=2))
