"""Plan de suivi : réglage individuel des règles (route tracking/rules). Mode automatique par défaut, valeur personnalisée jamais écrasée par le moteur,
retour à l'automatique règle par règle, activation indépendante ; aucune transaction, aucun lot, aucune ancienne règle d'alerte n'est touché. PHP 8.3."""
import datetime as dt

import pytest

from engine.shared.db import connect
from tests.integ.test_api import login, server, world  # noqa: F401  (fixtures)

pytestmark = pytest.mark.integration


def seed_prices():
    """200 clôtures synthétiques (hausse bruitée) pour le titre 1 : le moteur peut calculer risque et protection automatique."""
    conn = connect()
    days, d = [], dt.date.today() - dt.timedelta(days=1)
    while len(days) < 200:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    days.sort()
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)', [(day, round(100 * (1.6 ** (i / 199)) * (1.012 if i % 2 else 0.988), 4)) for i, day in enumerate(days)])
        cur.execute('UPDATE latest_prices SET price=160 WHERE listing_id=1')
    conn.commit()
    conn.close()


def counts(conn):
    out = {}
    with conn.cursor() as cur:
        for t in ('portfolio_transactions', 'lot_settings', 'lot_origin', 'alert_rules', 'alert_events', 'position_watch'):
            cur.execute(f'SELECT COUNT(*) n FROM {t}')
            out[t] = cur.fetchone()['n']
    return out


def plan_of(a, pf):
    st, state = a.call('tracking/state', params=f'&portfolio={pf}')
    assert st == 200
    return state['positions']['1']


def rule(plan, key):
    return next(r for r in plan['rules'] if r['key'] == key)


def setup(world):
    seed_prices()
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Règles'})[1]['id']
    assert a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 10, 'unit_price': 100, 'trade_at': (dt.date.today() - dt.timedelta(days=190)).isoformat()})[0] == 200
    return a, pf


def set_rule(a, pf, rule_key, **kw):
    return a.call('tracking/rules', dict(portfolio_id=pf, listing_id=1, rule=rule_key, **kw))


def test_defaults_are_automatic_and_active(world):
    a, pf = setup(world)
    p = plan_of(a, pf)
    assert [r['key'] for r in p['rules']] == ['stop', 'recul', 'trend', 'risk', 'target']
    s = rule(p, 'stop')
    assert s['mode'] == 'auto' and s['enabled'] is True and s['auto'] is not None and s['effective'] == s['auto'] == p['prices']['suggested']
    assert rule(p, 'recul')['mode'] == 'auto' and rule(p, 'recul')['auto'] is not None and rule(p, 'target')['mode'] == 'none'
    assert p['advice']['protection'].startswith('Protection automatique')


def test_custom_stop_then_return_to_automatic_without_touching_other_rules(world):
    a, pf = setup(world)
    conn = connect(); before = counts(conn)
    auto = rule(plan_of(a, pf), 'stop')['auto']
    assert set_rule(a, pf, 'recul', mode='custom', value=12)[0] == 200
    assert set_rule(a, pf, 'stop', mode='custom', value=130)[0] == 200
    p = plan_of(a, pf)
    assert rule(p, 'stop')['mode'] == 'custom' and abs(rule(p, 'stop')['effective'] - 130) < 1e-9 and abs(rule(p, 'stop')['auto'] - auto) < 1e-6   # la suggestion continue d'être calculée
    assert rule(p, 'recul')['mode'] == 'custom' and rule(p, 'recul')['custom'] == 12
    # activation seule : aucune valeur n'est touchée
    assert set_rule(a, pf, 'trend', enabled=False)[0] == 200 and set_rule(a, pf, 'stop', enabled=False)[0] == 200
    p = plan_of(a, pf)
    assert rule(p, 'trend')['enabled'] is False and rule(p, 'stop')['enabled'] is False and rule(p, 'stop')['custom_local'] == 130 and rule(p, 'stop')['effective'] is None
    assert set_rule(a, pf, 'stop', enabled=True)[0] == 200
    assert abs(rule(plan_of(a, pf), 'stop')['effective'] - 130) < 1e-9
    # retour à l'automatique : cette règle seulement
    assert set_rule(a, pf, 'stop', mode='auto')[0] == 200
    p = plan_of(a, pf)
    assert rule(p, 'stop')['mode'] == 'auto' and abs(rule(p, 'stop')['effective'] - auto) < 1e-6
    assert rule(p, 'recul')['mode'] == 'custom' and rule(p, 'recul')['custom'] == 12 and rule(p, 'trend')['enabled'] is False
    assert counts(conn) == before                                  # transactions, lots, origines, anciennes règles et événements, stratégie : intacts


def test_personal_objective_and_stop_share_levels_without_overwriting_each_other(world):
    a, pf = setup(world)
    assert set_rule(a, pf, 'stop', mode='custom', value=130)[0] == 200 and set_rule(a, pf, 'target', mode='custom', value=250)[0] == 200
    p = plan_of(a, pf)
    assert p['personal']['stop'] == 130 and p['personal']['target'] == 250 and rule(p, 'target')['mode'] == 'custom'
    assert set_rule(a, pf, 'target', mode='auto')[0] == 200
    p = plan_of(a, pf)
    assert p['personal']['stop'] == 130 and p['personal']['target'] is None and rule(p, 'target')['mode'] == 'none'
    assert set_rule(a, pf, 'stop', mode='auto')[0] == 200
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM position_levels'); assert cur.fetchone()['n'] == 0          # plus aucun niveau : ligne supprimée
        cur.execute('SELECT COUNT(*) n FROM position_plan_rules'); assert cur.fetchone()['n'] == 0      # pas de ligne = tout automatique et actif


def test_validation_and_ownership(world):
    a, pf = setup(world)
    for kw, code in (({'rule': 'inconnue'}, 422), ({'rule': 'recul', 'mode': 'custom', 'value': 0}, 422), ({'rule': 'recul', 'mode': 'custom', 'value': 100}, 422), ({'rule': 'recul', 'mode': 'custom', 'value': 'abc'}, 422),
                     ({'rule': 'stop', 'mode': 'custom', 'value': -5}, 422), ({'rule': 'stop', 'mode': 'custom'}, 422), ({'rule': 'trend', 'mode': 'custom', 'value': 5}, 422), ({'rule': 'stop', 'mode': 'bizarre'}, 422)):
        assert a.call('tracking/rules', dict(portfolio_id=pf, listing_id=1, **kw))[0] == code, kw
    assert set_rule(a, pf, 'target', mode='custom', value=140)[0] == 200
    assert set_rule(a, pf, 'stop', mode='custom', value=150)[0] == 422                      # le filet doit rester sous l'objectif
    assert a.call('tracking/rules', {'portfolio_id': pf, 'listing_id': 2, 'rule': 'trend', 'enabled': False})[0] == 404     # titre non détenu
    bob = login(world, 'bob', 'bob-secret-12345')
    assert bob.call('tracking/rules', {'portfolio_id': pf, 'listing_id': 1, 'rule': 'trend', 'enabled': False})[0] == 404    # cloisonnement entre utilisateurs


def test_exit_state_follows_the_effective_protection(world):
    a, pf = setup(world)
    assert rule(plan_of(a, pf), 'stop')['triggered'] is False
    assert set_rule(a, pf, 'stop', mode='custom', value=170)[0] == 200                     # protection personnelle au-dessus du cours (160)
    p = plan_of(a, pf)
    assert p['advice']['state'] == 'exit' and p['advice']['rule'] == 'stop' and 'personnelle' in p['advice']['headline']
    assert set_rule(a, pf, 'stop', mode='auto')[0] == 200
    assert plan_of(a, pf)['advice']['state'] != 'exit'
