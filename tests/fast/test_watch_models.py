"""Modèles d'alerte par stratégie : règles issues des critères réellement actifs, seuils lus dans la configuration, évaluation sur données réelles."""
import copy
import datetime

from engine.analytics.explorer import strategy
from engine.analytics.portfolio import watch


def tpl(name, cfg=None):
    return watch.template(name, cfg)


def kinds(rules, enabled=None):
    return [(r['kind'], r['granularity'], r['threshold']) for r in rules if enabled is None or r.get('enabled', True) == enabled]


def test_every_threshold_comes_from_the_strategy_configuration():
    for name in strategy.PRESETS:
        cfg = strategy.preset(name)
        periods = {p['id']: p for p in cfg['periods'] if p.get('enabled')}
        for r in tpl(name):
            if r['kind'] in ('slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min', 'er_min'):
                p = periods[r['granularity']]
                field = {'slope_min': 'min_slope', 'r2_min': 'min_r2', 'vol_max': 'max_volatility', 'drawdown_max': 'max_drawdown', 'momentum_min': 'min_return', 'er_min': 'min_er'}[r['kind']]
                assert r['threshold'] == p[field], (name, r)
            assert r['why'] and r['source'] == 'strategy'


def test_fast_regular_calm_use_their_own_active_criteria_only():
    fast = tpl('fast')
    assert {k for k, _, _ in kinds(fast)} <= {'slope_min', 'momentum_min', 'r2_min', 'er_min'}
    assert ('r2_min', 'week', 0) not in kinds(fast) and not any(k == 'r2_min' for k, _, _ in kinds(fast))   # R² seulement s'il est actif
    reg = tpl('regular')
    assert {g for _, g, _ in kinds(reg)} == {'month', 'quarter'} and {k for k, _, _ in kinds(reg)} == {'slope_min', 'r2_min'}
    calm = tpl('low_volatility')
    assert {'vol_max', 'drawdown_max'} <= {k for k, _, _ in kinds(calm)}


def test_rebound_entry_condition_is_never_monitored():
    cfg = strategy.preset('recovery')
    assert any(p.get('max_return') is not None for p in cfg['periods'] if p.get('enabled'))
    assert not any(r['kind'] == 'momentum_min' for r in tpl('recovery'))
    # une pente minimale de -100 est « aucune exigence » : pas de règle
    c = copy.deepcopy(cfg)
    for p in c['periods']:
        if p.get('enabled'):
            p['min_slope'] = -100
    assert not any(r['kind'] == 'slope_min' for r in tpl('recovery', c))


def test_disabled_criterion_makes_no_rule_and_missing_threshold_is_not_invented():
    c = copy.deepcopy(strategy.preset('regular'))
    for p in c['periods']:
        p['min_r2'] = None
    assert not any(r['kind'] == 'r2_min' for r in tpl('regular', c))
    for p in c['periods']:
        p['enabled'] = False
    assert [r for r in tpl('regular', c) if not r.get('confirm')] == []


def test_momentum_without_threshold_gives_only_a_disabled_complement():
    for name, kind in (('momentum', 'momentum6_min'), ('momentum12', 'momentum12_min')):
        rules = tpl(name)
        assert len(rules) == 1 and rules[0]['kind'] == kind and rules[0]['enabled'] is False and rules[0]['confirm'] is True
    mr = tpl('momentum_risk')
    assert ('ma_below', None, 200) in kinds(mr) and ('ma_falling', None, 200) in kinds(mr)
    assert [r for r in mr if r['kind'] == 'momentum6_min'][0]['enabled'] is False


def test_active_personal_criteria_generate_rules_and_inactive_ones_do_not():
    c = copy.deepcopy(strategy.preset('regular'))
    c['technical'] = dict(c.get('technical') or {}, above_ma50=True, max_gap_ma20=8.0, max_daily_change=None)
    k = kinds(tpl('regular', c))
    assert ('ma_below', None, 50) in k and ('gap_ma20_max', None, 8.0) in k
    assert not any(x[0] == 'daily_move' for x in k) and not any(x[0] == 'ma_falling' for x in k)


def rule(kind, g=None, thr=0.0):
    return {'id': 1, 'kind': kind, 'granularity': g, 'threshold': thr}


def series(n, f):
    d0 = datetime.date(2024, 1, 1)
    dates = [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(n)]
    return dates, [f(i) for i in range(n)]


def test_momentum_uses_the_six_minus_one_formula_not_the_raw_change():
    # forte hausse sur les 21 dernières séances : le variation brute est positive, le momentum 6−1 est négatif
    dates, closes = series(160, lambda i: 100 - 0.2 * i if i < 139 else 72 + (i - 138) * 4)
    r = watch._one(rule('momentum6_min', 'half', 0.0), 1, dates, closes, {}, None, [], [])
    raw = 100 * (closes[-1] / closes[-127] - 1)
    assert raw > 0 and r['state'] == 'triggered' and r['value'] < 0
    assert abs(r['value'] - 100 * (closes[-22] / closes[-127] - 1)) < 1e-9


def test_momentum_12_needs_253_closes():
    dates, closes = series(200, lambda i: 100 + i)
    r = watch._one(rule('momentum12_min', 'year', 0.0), 1, dates, closes, {}, None, [], [])
    assert r['state'] == 'insufficient' and '253' in r['reason']
    dates, closes = series(300, lambda i: 100 + i)
    r = watch._one(rule('momentum12_min', 'year', 0.0), 1, dates, closes, {}, None, [], [])
    assert r['state'] == 'normal' and r['value'] > 0


def test_ma_rules_and_gap():
    dates, closes = series(260, lambda i: 100 + i)
    assert watch._one(rule('ma_below', None, 200), 1, dates, closes, {}, None, [], [])['state'] == 'normal'
    assert watch._one(rule('ma_falling', None, 200), 1, dates, closes, {}, None, [], [])['state'] == 'normal'
    dates, closes = series(260, lambda i: 300 - i)
    assert watch._one(rule('ma_falling', None, 200), 1, dates, closes, {}, None, [], [])['state'] == 'triggered'
    assert watch._one(rule('ma_below', None, 200), 1, dates, closes, {}, None, [], [])['state'] == 'triggered'
    assert watch._one(rule('gap_ma20_max', None, 1.0), 1, dates, closes, {}, None, [], [])['state'] == 'triggered'
    short = series(30, lambda i: 100)
    assert watch._one(rule('ma_below', None, 200), 1, short[0], short[1], {}, None, [], [])['state'] == 'insufficient'


def test_insufficient_history_is_never_normal():
    dates, closes = series(10, lambda i: 100 + i)
    for k, g in (('slope_min', 'month'), ('r2_min', 'quarter'), ('momentum6_min', 'half'), ('er_min', 'month')):
        assert watch._one(rule(k, g, 0.1), 1, dates, closes, {}, None, [], [])['state'] == 'insufficient'
