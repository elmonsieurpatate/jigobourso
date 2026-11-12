"""Adaptations de scores par utilisateur : isolation, statuts, restaurations indépendantes, retour automatique à Officielle (vraie base)."""
import os

import pytest

from engine.analytics.admin import scores_admin as A
from engine.analytics.explorer import strategy_docs
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

SEVEN = ['growth_v4', 'growth_regular', 'calm_rise', 'rebound', 'momentum_6m', 'momentum_12m', 'momentum_risk']


def fresh():
    conn = connect()
    reset_data(conn)
    A.set_user(None)
    return conn


def tweaked(conn, name):
    prof = A.official_clean(conn, name)
    cw = dict(prof['complex_weights'])
    give = 'dynamics' if cw['dynamics'] >= 5 else 'r2'
    cw[give] -= 5
    cw['up_days'] += 5
    prof = {**prof, 'complex_weights': cw}
    return prof


def by_id(status):
    return {s['name']: s for s in status['strategies'] if s['kind'] == 'builtin'}


def test_seven_official_strategies_one_entry_each_and_all_official():
    conn = fresh()
    A.set_user(1)
    st = A.strategies_status(conn, {'ct_items': []})['strategies']
    assert [s['name'] for s in st] == SEVEN
    assert {s['status'] for s in st} == {'official'}
    assert len({s['id'] for s in st}) == 7


def test_adaptation_is_private_and_independent_between_users():
    conn = fresh()
    A.set_user(1)
    A.user_save(conn, {'name': 'growth_v4', 'profile': tweaked(conn, 'growth_v4')})
    assert by_id(A.strategies_status(conn, {}))['growth_v4']['status'] == 'adapted'
    assert by_id(A.strategies_status(conn, {}))['growth_v4']['scores']['modified'] >= 1
    assert by_id(A.strategies_status(conn, {}))['growth_v4']['criteria']['state'] == 'official'
    A.set_user(2)
    assert by_id(A.strategies_status(conn, {}))['growth_v4']['status'] == 'official'        # l'autre utilisateur ne voit rien
    A.set_user(1)
    A.user_save(conn, {'reset': 'profile', 'name': 'growth_v4'})
    assert by_id(A.strategies_status(conn, {}))['growth_v4']['status'] == 'official'


def test_saving_profile_identical_to_official_returns_to_official():
    conn = fresh()
    A.set_user(3)
    A.user_save(conn, {'name': 'calm_rise', 'profile': tweaked(conn, 'calm_rise')})
    assert by_id(A.strategies_status(conn, {}))['calm_rise']['status'] == 'adapted'
    A.user_save(conn, {'name': 'calm_rise', 'profile': A.official_clean(conn, 'calm_rise')})
    assert by_id(A.strategies_status(conn, {}))['calm_rise']['status'] == 'official'


def test_criteria_and_scores_are_judged_separately():
    conn = fresh()
    A.set_user(4)
    item = {'id': 'growth_v4', 'builtin': True, 'config': {'periods': {'week': {'slope': 0.5}}}}
    st = by_id(A.strategies_status(conn, {'ct_items': [item]}))['growth_v4']
    assert st['criteria']['state'] in ('official', 'adapted') and st['scores']['state'] == 'official'


def test_facts_come_from_executed_code_for_all_seven():
    conn = fresh()
    f = strategy_docs.facts(conn)
    assert [s['name'] for s in f['strategies']] == SEVEN
    assert f['common']['slope_levels']['very_strong'] == pytest.approx(0.27543703768897265)
    assert all(abs(sum(p['weight'] for p in s['periods']) - 100) < 1e-6 for s in f['strategies'])
