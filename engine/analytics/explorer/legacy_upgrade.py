"""Conversion des anciennes stratégies (V3) vers la configuration V4 et exposition de leurs formules comme composants génériques.
Couche au-dessus de strategy (validation V3) et d'explorer_config (V4) : explorer_config ne dépend donc pas de strategy."""

import copy

from . import explorer_config as C
from . import strategy


def upgrade(config):
    c = copy.deepcopy(config)
    if c.get('version') == 4:
        return C.validate(c)
    if c.get('version') != 3:
        raise ValueError('Version de stratégie inconnue : conversion explicite nécessaire')
    c = strategy.validate(c)
    c.pop('_upgrade', None)
    c['version'] = 4
    c['slope_unit'] = 'percent_per_session'
    for p in c['periods']:
        # V3 required coverage on every selected period, even without thresholds.
        p['require_history'] = bool(p['enabled'])
        for field in C.BOUNDS:
            p.setdefault(field, None)
    c['ranking']['weights'] = {p['id']: c['ranking'].get('weights', {}).get(p['id'], 1 if p['enabled'] else 0) for p in c['periods']}
    c['selection'] = {'combine': 'all', 'missing': 'unknown', 'require_fresh': True}
    c['liquidity'] = {'min_quoted_volume': None}
    c['asset_rules'] = {}
    c['presentation'] = {'configuration': 'period'}
    return C.validate(c)


def editable(raw):
    """Expose legacy formulas as generic components without changing their math."""
    c = upgrade(raw)
    c.pop('_editable', None)
    r = c['ranking']
    mode = r['mode']
    if mode in ('weighted', C.SCORES_MODE):
        return c
    if mode == 'momentum_risk':
        specs = [('momentum6', 'half', 0.35, 'higher', True), ('momentum12', 'year', 0.45, 'higher', True), ('volatility', 'year', 0.10, 'lower', False), ('drawdown', 'year', 0.10, 'lower', False)]
    elif mode in ('momentum', 'momentum12'):
        specs = [('momentum12' if mode == 'momentum12' else 'momentum6', 'year' if mode == 'momentum12' else 'half', 1, 'higher', True)]
    else:
        metric = {'trend': 'slope', 'performance': 'perf', 'regularity': 'r2', 'stability': 'volatility'}[mode]
        specs = [
            (metric, p['id'], r['weights'].get(p['id'], 0), 'lower' if mode == 'stability' else 'higher', False) for p in c['periods'] if p['sessions'] >= 3 or metric not in ('r2', 'volatility', 'er')
        ]
    c['ranking'] = {
        'mode': 'weighted',
        'missing': 'renormalize',
        'aggregation': 'mean',
        'grouping': 'asset_kind',
        'components': [
            dict(
                id='legacy-' + period + '-' + metric,
                metric=metric,
                period=period,
                weight=weight,
                direction=direction,
                required=required,
                kind='all',
                enabled=True,
                normalization='percentile',
                transform='identity',
                min=0,
                max=100,
                exponent=1,
            )
            for metric, period, weight, direction, required in specs
        ],
    }
    return C.validate(c)
