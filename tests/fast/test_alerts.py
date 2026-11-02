"""Alertes de vente achat par achat : réglages par stratégie, réglages personnels, mesures depuis l'achat, règles de sortie."""
import datetime
import os
import re

from engine.analytics import alerts as al
from engine.analytics import strategy

TODAY = datetime.date(2026, 11, 2)
LOT = {'trade_date': '2026-03-02'}


def test_defaults_follow_the_exit_rule_study():
    assert al.defaults('momentum')['exit'] == 'momentum_negative' and al.defaults('momentum12')['exit'] == 'momentum_negative'
    assert al.defaults('recovery')['exit'] == 'below_ma50' and al.defaults('regular')['exit'] is None
    assert al.defaults('fast')['drop_action'] == 'alléger' and al.defaults('regular')['drop_action'] == 'surveiller'
    assert al.defaults('regular')['days'] == 182 and al.defaults('regular')['drop'] == 20
    p = al.defaults('prudent')
    assert p['drop'] is None and p['days'] == 365 and p['days_action'] == 'rééquilibrer' and not p['rank_exit']


def test_strategies_match_the_php_whitelist():
    php = open(os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'routes', 'portfolios.php'), encoding='utf-8').read()
    listed = re.search(r"const LOT_STRATEGIES = \[([^\]]*)\]", php).group(1)
    assert tuple(re.findall(r"'([a-z_0-9]+)'", listed)) == al.STRATEGIES == tuple(strategy.PRESETS) + ('prudent',)


def test_personal_settings_override_defaults():
    r = al.rules_for('regular', {'alert_days': 30, 'alert_drop_pct': 8})
    assert r['days'] == 30 and r['drop'] == 8 and r['personal'] and not r['off']
    assert al.rules_for('prudent', {'alert_drop_pct': 10})['drop_action'] == 'surveiller'
    assert al.rules_for('regular', {'alerts_off': True})['off'] and al.evaluate(LOT, al.rules_for('regular', {'alerts_off': True}), {'drop_pct': 90}, None, None, TODAY) == []


def test_measures_since_the_purchase_only():
    dates = ['2026-02-27', '2026-03-02', '2026-03-03', '2026-03-04']
    m = al.lot_measures('2026-03-02', dates, [200.0, 100.0, 120.0, 90.0])
    assert m['high'] == 120 and m['last'] == 90 and round(m['drop_pct'], 6) == 25 and m['sessions'] == 3
    assert al.lot_measures('2026-04-01', dates, [1, 2, 3, 4]) is None


def test_alerts_fire_on_duration_drop_momentum_ma50_and_rank():
    kinds = lambda xs: sorted(x['kind'] for x in xs)
    r = al.rules_for('momentum', None)
    out = al.evaluate(LOT, r, {'drop_pct': 21.0}, {'momentum_6m': -0.05, 'close': 10, 'ma50': 12}, 80, TODAY)
    assert kinds(out) == ['drop', 'duration', 'momentum', 'rank']
    assert {x['kind']: x['level'] for x in out} == {'drop': 'watch', 'duration': 'watch', 'momentum': 'act', 'rank': 'info'}
    assert kinds(al.evaluate({'trade_date': '2026-10-01'}, r, {'drop_pct': 5.0}, {'momentum_6m': 0.2}, 3, TODAY)) == []
    rec = al.evaluate({'trade_date': '2026-10-01'}, al.rules_for('recovery', None), {'drop_pct': 1.0}, {'close': 10, 'ma50': 12}, None, TODAY)
    assert kinds(rec) == ['ma50', 'rank'] and 'plus retenu' in rec[1]['message']
    fast = al.evaluate({'trade_date': '2026-10-01'}, al.rules_for('fast', None), {'drop_pct': 25.0}, None, False, TODAY)
    assert [(x['kind'], x['action'], x['level']) for x in fast] == [('drop', 'alléger', 'act')]           # rang inconnu (False) : pas d'alerte de classement
