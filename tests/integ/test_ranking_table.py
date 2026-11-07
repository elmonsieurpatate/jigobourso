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
    assert up['price_eur'] == pytest.approx(250.0) and up['curve'] and set(up['perf']) == {'week', 'month', 'quarter', 'half'}
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
    assert 'ct:7:cs-aaa' in names and 'growth_regular' in names and 'calm_rise' in names and 'rebound' in names and 'growth_v4' in names        # « Blou » est dans l'interface des scores
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


def _extra_titles(conn):
    """Un jumeau exact de UP.DE (notes strictement identiques) et deux titres en baisse identiques (notes simples à 0) : de vrais ex æquo."""
    import datetime
    import exchange_calendars as xc
    from engine.analytics import compute
    calendar = xc.get_calendar('XETR', start='2026-01-05', end='2027-01-31')
    days = [d.date() for d in calendar.sessions if d.date() >= datetime.date(2026, 1, 5)][:260]
    now = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (3,'sym:XETR:TWIN.DE','equity','Jumeau AG','Germany'),(4,'sym:XETR:DOWN.DE','equity','Baisse AG','Germany'),"
                    "(5,'sym:XETR:DOWN2.DE','equity','Baisse bis AG','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (3,3,'XETR','TWIN.DE','EUR','selected',1),(4,4,'XETR','DOWN.DE','EUR','selected',1),(5,5,'XETR','DOWN2.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                        [(3, d, round(100 * 1.004 ** i, 6)) for i, d in enumerate(days)] + [(n, d, round(100 * 0.998 ** i, 6)) for n in (4, 5) for i, d in enumerate(days)])
        cur.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (%s,%s,%s,'daily','EUR',%s)", [(3, 250.0, now, 300000), (4, 60.0, now, 1000), (5, 60.0, now, 1000)])
    conn.commit()
    compute.compute_all(conn, now)


def test_classement_and_scores_admin_rank_the_same_titles_in_the_same_order_with_the_same_notes_and_ranks():
    from engine.analytics import scores_admin as A
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    for ct_id, name in A.CT_BUILTIN.items():
        t = R.table(conn, {'ct_id': ct_id, 'user_id': 1})
        assert t['strategy'] == name
        for which in ('simple', 'complex'):
            admin = A.ranking(conn, {'strategy': name, 'which': which, 'limit': 100})['listing']['rows']
            mine = sorted((r for r in t['rows'] if r[which] is not None), key=lambda r: r['pos_' + which])
            assert [r['id'] for r in mine] == [r['id'] for r in admin], (name, which)                           # mêmes titres, même ordre
            assert [r[which] for r in mine] == [r[which] for r in admin] and [r['rank_' + which] for r in mine] == [r['rank'] for r in admin], (name, which)
            assert len(mine) == t['scored'][which]
        assert t['evaluated'] == len(t['rows']) and t['universe'] == 5 and t['default_sort'] in ('simple', 'complex')


def test_identical_raw_scores_share_a_rank_and_the_order_is_deterministic():
    from engine.analytics import scores_admin as A
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    t = R.table(conn, {'strategy': 'growth_v4'})
    rows = {r['symbol']: r for r in t['rows']}
    assert rows['UP.DE']['simple'] == rows['TWIN.DE']['simple'] and rows['UP.DE']['rank_simple'] == rows['TWIN.DE']['rank_simple'] == 1
    assert rows['UP.DE']['tie_simple'] == 2 and rows['UP.DE']['pos_simple'] != rows['TWIN.DE']['pos_simple']       # même rang, ordre des lignes départagé
    assert rows['DOWN.DE']['simple'] == rows['DOWN2.DE']['simple'] == 0 and rows['DOWN.DE']['rank_simple'] == rows['DOWN2.DE']['rank_simple']
    assert rows['DOWN.DE']['simple'] is not None and rows['DOWN.DE']['complex'] is not None                         # aucun titre en baisse n'est exclu
    assert R.table(conn, {'strategy': 'growth_v4'})['rows'] == t['rows']                                           # résultat reproductible


# ───────────── statut de stratégie : moteur unique (Classement = Scores = fiche) ─────────────

def _strict(period='month', slope=0.3, r2=0.0):
    return {'periods': {period: {'enabled': True, 'slope': slope, 'r2': r2}}, 'extra': [], 'join': 'and'}


def test_three_modes_counts_cover_every_evaluable_title_and_never_change_scores_or_ranks():
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    loose = R.table(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': _strict(slope=0.0)})
    strict = R.table(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': _strict(slope=0.39)})
    assert loose['counts']['all'] == strict['counts']['all'] == len(loose['rows']) == loose['evaluated']
    assert loose['counts']['retained'] == loose['evaluated']                                      # aucun critère actif : tout est retenu
    assert strict['counts']['excluded'] > 0 and sum(strict['counts'][k] for k in ('retained', 'excluded', 'undetermined')) == strict['counts']['all']
    keep = lambda t: {r['id']: (r['simple'], r['complex'], r['rank_simple'], r['rank_complex'], r['pos_simple']) for r in t['rows']}
    assert keep(loose) == keep(strict)                                                             # les critères ne changent ni score ni rang
    assert {r['id'] for r in strict['rows'] if r['status'] == 'retained'} < {r['id'] for r in loose['rows']}


def test_live_verdicts_endpoint_equals_table_statuses_and_scores_admin_listing():
    from engine.analytics import scores_admin as A
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    spec = _strict(slope=0.39, r2=0.5)
    t = R.table(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': spec})
    v = R.verdicts(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': spec})
    assert v['status'] == {r['id']: r['status'] for r in t['rows']} and v['counts'] == t['counts']
    for mode in ('retained', 'excluded', 'all'):
        ids = []
        for which in ('simple', 'complex'):
            L = A.ranking(conn, {'strategy': 'growth_v4', 'which': which, 'limit': 100, 'verdict': mode, 'ct_specs': {'fast': spec}})['listing']
            assert L['counts'] == {**{k: sum(1 for r in t['rows'] if r['status'] == k and r[which] is not None) for k in ('retained', 'excluded', 'undetermined')},
                                   'all': sum(1 for r in t['rows'] if r[which] is not None)}
            expected = [r for r in t['rows'] if r[which] is not None and (mode == 'all' or r['status'] == mode)]
            assert sorted(r['id'] for r in L['rows']) == sorted(r['id'] for r in expected), (mode, which)
            for r in L['rows']:
                mine = next(x for x in t['rows'] if x['id'] == r['id'])
                assert r['rank'] == mine['rank_' + which] and r['status'] == mine['status']       # même rang et même statut dans les deux pages
            ids.append(L['total'])
        assert all(n >= 0 for n in ids)


def test_insufficient_data_is_undetermined_never_excluded():
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    with conn.cursor() as cur:
        cur.execute('DELETE FROM strategy_metrics WHERE listing_id=1 AND sessions=21')
    conn.commit()
    t = R.table(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': _strict(slope=0.01)})
    row = next(r for r in t['rows'] if r['id'] == 1)
    assert row['status'] == 'undetermined' and row['simple'] is not None                        # noté, classé, mais statut indéterminé
    assert t['counts']['undetermined'] >= 1


def test_missing_context_is_undetermined_and_builtin_defaults_come_from_the_central_source():
    conn = connect()
    reset_data(conn)
    seed(conn)
    t = R.table(conn, {'ct_id': 'cs-inconnu', 'user_id': 1})
    assert t['context'] == 'missing' and {r['status'] for r in t['rows']} == {'undetermined'}
    assert R.table(conn, {'ct_id': 'mom6', 'user_id': 1})['context'] == 'ok'
    assert {r['status'] for r in R.table(conn, {'ct_id': 'mom6', 'user_id': 1})['rows']} == {'retained'}   # Momentum : aucun critère de recherche


def test_sheet_status_and_scores_equal_the_ranking_in_every_context():
    from engine.analytics import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    _extra_titles(conn)
    spec = _strict(slope=0.39)
    t = {r['id']: r for r in R.table(conn, {'ct_id': 'fast', 'user_id': 1, 'spec': spec})['rows']}
    for lid, row in t.items():
        s = service.instrument_sheet(conn, {'listing_id': lid, 'config': 'regular', 'ct': {'id': 'fast', 'state': 'draft', 'spec': spec, 'label': 'Croissance rapide', 'user_id': 1}})
        assert s['v4']['status'] == row['status'] and s['v4']['state'] == 'draft'
        if row['status'] == 'excluded':
            assert any(c['result'] == 'fail' and c['unit'] == '% par séance' for c in s['v4']['checks'])
        assert s['scores_v4']['ranks']['simple']['rank'] == row['rank_simple'] and s['scores_v4']['ranks']['complex']['rank'] == row['rank_complex']
    lost = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular', 'ct': {'id': 'fast', 'state': 'draft_lost', 'spec': None, 'label': 'Croissance rapide', 'user_id': 1}})
    none = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular'})
    for s in (lost, none):
        assert s['v4']['status'] == 'undetermined' and s['v4']['context'] == 'missing'          # jamais « retenue » par défaut de transmission
    free = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular', 'ct': {'id': 'mom6', 'state': 'default', 'spec': None, 'label': 'Momentum', 'user_id': 1}})
    assert free['v4']['status'] == 'retained' and free['v4']['criteria_free'] is True


def test_sheet_measures_use_the_units_of_the_criteria():
    from engine.analytics import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    s = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular'})
    m = s['measures']['21']
    t = next(r for r in R.table(conn, {})['rows'] if r['id'] == 1)
    assert m['slope'] == pytest.approx(t['periods']['21']['slope'], abs=1e-3)                    # % par séance : même valeur que celle comparée aux seuils
    assert m['slope_period'] > m['slope'] * 15                                                   # pente composée sur 21 séances : plus grande, jamais comparée au seuil par séance
