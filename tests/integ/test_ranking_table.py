"""Tableau du classement : toutes les lignes avec scores V4, rangs, valeurs des filtres et groupes ; rien n'est inventé."""
import os

import pytest

from engine.analytics import ranking_table as R
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.integ.test_scores_admin import seed

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


def test_table_has_scores_ranks_groups_and_unknowns_stay_none():
    conn = connect()
    reset_data(conn)
    assert R.table(conn, {})['rows'] == []
    seed(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE instruments SET category='Technology' WHERE id=1")
        cur.execute("UPDATE latest_prices SET analyst_rating='1.6 - Buy' WHERE listing_id=1")      # texte de Yahoo, pas un nombre
    conn.commit()
    t = R.table(conn, {})
    rows = {r['symbol']: r for r in t['rows']}
    assert t['universe'] == 2 and set(rows) == {'UP.DE', 'ZIG.DE'}
    up = rows['UP.DE']
    assert up['analyst'] == '1.6 - Buy'
    assert up['simple'] is not None and up['rank_simple'] == 1 and up['rank_complex'] in (1, 2)
    assert up['group'] == {'country': 'country:europe', 'market': 'market:europe', 'sector': 'sector:technology', 'asset': 'asset:equity'}
    assert rows['ZIG.DE']['group']['sector'] == 'unknown'                           # secteur non renseigné : inconnu, pas « autres »
    assert up['price_eur'] == pytest.approx(250.0) and up['curve'] and set(up['perf']) == {'week', 'month', 'quarter'}
    assert up['avg_volume'] == 300000 and up['extra']['up_fraction'] is not None
    assert set(up['periods']) >= {'5', '21', '63'} and up['periods']['21']['slope'] is not None
    assert 'freshness' not in up['extra'] and 'secondary' not in up                  # fraîcheur : non fournie, jamais zéro


def test_sheet_carries_the_same_v4_scores_as_the_ranking():
    from engine.analytics import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    t = {r['symbol']: r for r in R.table(conn, {})['rows']}
    sheet = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular'})
    v4 = sheet['scores_v4']
    assert v4['simple']['score'] == pytest.approx(t['UP.DE']['simple'], abs=1e-3) and v4['complex']['score'] == pytest.approx(t['UP.DE']['complex'], abs=1e-3)
    assert v4['ranks']['simple']['rank'] == t['UP.DE']['rank_simple']


def test_personal_classement_strategies_get_their_own_score_profile_and_ranking():
    import json
    from engine.analytics import scores_admin as A
    conn = connect()
    reset_data(conn)
    seed(conn)
    doc = {'schema': 1, 'revision': 1, 'selected': 'cs-aaa', 'items': [
        {'id': 'cs-aaa', 'name': 'Blou', 'builtin': False, 'filters': [], 'config': {'periods': {
            'week': {'enabled': False, 'slope': .08, 'r2': .65}, 'month': {'enabled': True, 'slope': .08, 'r2': .65}, 'quarter': {'enabled': True, 'slope': .05, 'r2': .6},
            'half': {'enabled': False, 'slope': .05, 'r2': .6}, 'year': {'enabled': False, 'slope': .05, 'r2': .6}, 'two_year': {'enabled': False, 'slope': .05, 'r2': .6}}, 'extra': [], 'join': 'and'}}]}
    with conn.cursor() as cur:
        cur.execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('ct_strategies:7',%s,NOW())", (json.dumps(doc),))
    conn.commit()
    names = [s['name'] for s in A.state(conn)['strategies'] if s['engine'] == 'v4']
    assert 'ct:7:cs-aaa' in names and 'ct:regular' in names and 'ct:calm' in names and 'growth_v4' in names        # « Blou » est dans l'interface des scores
    blou = [s for s in A.state(conn)['strategies'] if s['name'] == 'ct:7:cs-aaa'][0]
    assert blou['label'] == 'Blou' and [p for p, v in blou['current']['periods'].items() if v['enabled']] == ['month', 'quarter']
    # son propre profil : des poids complexes différents changent SES notes, pas celles des autres stratégies
    base_fast = {r['symbol']: r['complex'] for r in R.table(conn, {'ct_id': 'fast', 'user_id': 7})['rows']}
    prof = dict(blou['current'], name='ct:7:cs-aaa')
    prof['complex_weights'] = dict(prof['complex_weights'], dynamics=10, liquidity=40)      # total inchangé (100 %)
    A.save(conn, {'profile': prof})
    t = R.table(conn, {'ct_id': 'cs-aaa', 'user_id': 7})
    assert t['strategy'] == 'ct:7:cs-aaa' and t['label'] == 'Blou' and t['universe'] == 2
    assert {r['symbol']: r['complex'] for r in R.table(conn, {'ct_id': 'fast', 'user_id': 7})['rows']} == base_fast
    assert R.table(conn, {'ct_id': 'cs-inconnu', 'user_id': 7})['strategy'] == 'growth_v4'                      # identifiant inconnu : stratégie commune
    assert R.table(conn, {'ct_id': 'cs-aaa', 'user_id': 8})['strategy'] == 'growth_v4'                          # la stratégie d'un autre utilisateur n'est pas la sienne
