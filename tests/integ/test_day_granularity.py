"""Var. 1J et granularité Jour sur une vraie base : colonne, tri, critère de recherche, poids de score, stratégies personnelles, colonnes enregistrées (vrai PHP + MariaDB)."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from engine.analytics.scoring import ranking_table as R
from engine.analytics.admin import scores_admin as A
from engine.analytics.admin import scores_ranking
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.integ.test_scores_admin import seed

pytestmark = pytest.mark.integration
if os.environ.get('JIGO_TEST_DATABASE') != '1':
    pytest.skip('base jetable requise', allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / 'app/config/table_columns.json').read_text(encoding='utf-8'))['pages']


def clean(conn):
    reset_data(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM settings WHERE name IN ('scores_profiles','scores_v4','table_layouts') OR name LIKE 'ct\\_strategies:%'")
        cur.execute('DELETE FROM result_cache')
    conn.commit()


def last_two(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date DESC LIMIT 2', (lid,))
        a, b = [float(r['close_px']) for r in cur.fetchall()]
    return 100 * (a / b - 1)


def scores(conn, name='growth_v4', **extra):
    rows = scores_ranking.ranking(conn, {'strategy': name, 'which': 'simple', 'limit': 100, **extra})['listing']['rows']
    return {r['symbol']: (r['simple'], r['complex'], r['rank']) for r in rows}


def test_var_1j_is_the_move_between_the_last_two_closed_sessions_in_every_table():
    conn = connect()
    clean(conn)
    seed(conn)
    want = {'UP.DE': last_two(conn, 1), 'ZIG.DE': last_two(conn, 2)}
    rows = {r['symbol']: r for r in R.table(conn, {})['rows']}
    adm = {r['symbol']: r for r in scores_ranking.ranking(conn, {'strategy': 'growth_v4', 'which': 'simple', 'limit': 100})['listing']['rows']}
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, perf FROM strategy_metrics WHERE sessions=1')
        one = {r['listing_id']: float(r['perf']) for r in cur.fetchall()}
    for sym, lid in (('UP.DE', 1), ('ZIG.DE', 2)):
        assert rows[sym]['change'] == pytest.approx(want[sym], abs=1e-3) and adm[sym]['change'] == pytest.approx(want[sym], abs=1e-3)
        assert one[lid] == pytest.approx(want[sym], abs=1e-3)                                  # la mesure « Jour » est la même variation, jamais une autre
    assert rows['UP.DE']['change'] != rows['UP.DE']['perf']['week']                            # ≠ performance de la période
    assert 1 not in {int(k) for k in rows['UP.DE']['periods']}                                 # pas de pente ni de R² « sur une séance »


def test_scores_listing_sorts_on_var_1j_without_changing_global_ranks():
    conn = connect()
    clean(conn)
    seed(conn)
    base = scores_ranking.ranking(conn, {'strategy': 'growth_v4', 'which': 'simple', 'limit': 100})['listing']['rows']
    ranks = {r['symbol']: r['rank'] for r in base}
    for direction in ('desc', 'asc'):
        rows = scores_ranking.ranking(conn, {'strategy': 'growth_v4', 'which': 'simple', 'limit': 100, 'sort': [{'key': 'change', 'dir': direction}]})['listing']['rows']
        values = [r['change'] for r in rows]
        assert values == sorted(values, reverse=direction == 'desc')
        assert {r['symbol']: r['rank'] for r in rows} == ranks


def test_day_search_criterion_filters_only_and_never_touches_scores_or_ranks():
    conn = connect()
    clean(conn)
    seed(conn)
    spec = lambda v: {'periods': {'day': {'enabled': True, 'return': v}}, 'extra': [], 'join': 'and'}
    free = R.table(conn, {'ct_id': 'fast', 'spec': {'periods': {}, 'extra': [], 'join': 'and'}})
    up, down = R.table(conn, {'ct_id': 'fast', 'spec': spec(100.0)}), R.table(conn, {'ct_id': 'fast', 'spec': spec(-100.0)})
    assert {r['status'] for r in up['rows']} == {'excluded'} and {r['status'] for r in down['rows']} == {'retained'}
    key = lambda t: {r['symbol']: (r['simple'], r['complex'], r['rank_simple'], r['rank_complex']) for r in t['rows']}
    assert key(up) == key(down) == key(free)
    v = R.verdicts(conn, {'ct_id': 'fast', 'spec': spec(100.0)})
    assert v['counts']['excluded'] == 2 and v['active'] == 1
    # activée sans seuil : aucun critère (jamais un seuil inventé)
    assert R.verdicts(conn, {'ct_id': 'fast', 'spec': {'periods': {'day': {'enabled': True, 'return': None}}, 'extra': [], 'join': 'and'}})['active'] == 0


def test_day_weight_changes_scores_only_when_it_has_a_weight():
    conn = connect()
    clean(conn)
    seed(conn)
    before = scores(conn)
    st = next(s for s in A.state(conn)['strategies'] if s['name'] == 'growth_v4')
    p = dict(st['current'], name='growth_v4')
    p['periods'] = {k: dict(v) for k, v in p['periods'].items()}
    p['periods']['day'].update(enabled=True, min_return=0.0)
    A.save(conn, {'profile': p})                                                      # Jour activé (critère de recherche), mode automatique : poids 0
    assert scores(conn) == before
    p['weights_mode'] = 'custom'
    p['weights'] = {'day': 0.0, 'week': 41.6, 'month': 58.4}
    A.save(conn, {'profile': p})                                                      # poids explicite 0 %
    after_zero = scores(conn)
    assert {k: v[2] for k, v in after_zero.items()} == {k: v[2] for k, v in before.items()}
    assert all(after_zero[k][0] == pytest.approx(before[k][0], abs=0.01) for k in before)      # poids 41,6 / 58,4 arrondis : écart inférieur au centième
    p['weights'] = {'day': 30.0, 'week': 29.0, 'month': 41.0}
    A.save(conn, {'profile': p})
    weighted = scores(conn)
    assert weighted != before                                                         # Jour pondéré : les notes tiennent compte de la variation 1J
    p['periods']['day']['enabled'] = False
    p['weights_mode'] = 'auto'
    p['weights'] = {}
    A.save(conn, {'profile': p})
    assert scores(conn) == before                                                     # désactivé : retour exact aux notes initiales
    sim = scores_ranking.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE'})
    assert [x['id'] for x in sim['periods']] == ['week', 'month']
    clean(conn)


def test_personal_strategy_with_day_enabled_keeps_its_scores():
    conn = connect()
    clean(conn)
    seed(conn)

    def doc(day_on):
        per = {k: {'enabled': k in ('month', 'quarter'), 'slope': .08, 'r2': .65} for k in ('week', 'month', 'quarter', 'half', 'year', 'two_year')}
        per['day'] = {'enabled': day_on, 'return': 0.0}
        return {'schema': 1, 'revision': 1, 'selected': 'cs-aaa', 'items': [{'id': 'cs-aaa', 'name': 'Blou', 'builtin': False, 'filters': [], 'config': {'periods': per, 'extra': [], 'join': 'and'}}]}

    def write(d):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM settings WHERE name='ct_strategies:7'")
            cur.execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('ct_strategies:7',%s,NOW())", (json.dumps(d),))
        conn.commit()

    write(doc(False))
    off = {r['symbol']: (r['simple'], r['complex'], r['rank_simple']) for r in R.table(conn, {'ct_id': 'cs-aaa', 'user_id': 7})['rows']}
    write(doc(True))
    on = R.table(conn, {'ct_id': 'cs-aaa', 'user_id': 7})
    assert on['strategy'] == 'ct:7:cs-aaa' and {r['symbol']: (r['simple'], r['complex'], r['rank_simple']) for r in on['rows']} == off
    blou = next(s for s in A.state(conn)['strategies'] if s['name'] == 'ct:7:cs-aaa')
    assert blou['current']['periods']['day']['enabled'] and blou['auto_weights'].get('day', 0) == 0                         # Jour actif comme critère, jamais de poids automatique
    clean(conn)


def php(code):
    body = 'require ' + json.dumps(str(ROOT / 'app/services/ct_strategies.php')) + ';require ' + json.dumps(str(ROOT / 'app/services/table_layouts.php')) + ';' + code
    r = subprocess.run(['php', '-r', body], cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def ct_config(cfg):
    return php('try { echo json_encode(["ok" => ct_config(json_decode(' + json.dumps(json.dumps(cfg)) + ', true))]); } catch (ApiError $e) { echo json_encode(["error" => $e->getMessage(), "code" => $e->status]); }')


def base_periods():
    return {k: {'enabled': k == 'month', 'slope': .08, 'r2': .65} for k in ('week', 'month', 'quarter', 'half', 'year', 'two_year')}


def test_strategy_config_accepts_day_and_stays_compatible_with_strategies_saved_before():
    legacy = ct_config({'periods': base_periods(), 'extra': [], 'join': 'and'})['ok']
    assert legacy['periods']['day'] == {'enabled': False, 'return': None}                                   # enregistrée avant l'ajout de Jour : désactivé
    assert legacy['periods']['month'] == {'enabled': True, 'slope': 0.08, 'r2': 0.65}                       # le reste est identique
    per = base_periods()
    per['day'] = {'enabled': True, 'return': 0.5, 'slope': 9, 'r2': 9}
    ok = ct_config({'periods': per, 'extra': [], 'join': 'and'})['ok']
    assert ok['periods']['day'] == {'enabled': True, 'return': 0.5}                                         # jamais de pente ni de R² pour Jour
    tree = {'kind': 'group', 'join': 'and', 'children': [{'kind': 'rule', 'metric': 'return', 'period': 'day', 'op': '>=', 'value': 1.0}]}
    assert ct_config({'periods': per, 'extra': [], 'join': 'and', 'tree': tree})['ok']['tree']['children'][0]['period'] == 'day'
    per['day'] = {'enabled': 'oui'}
    assert ct_config({'periods': per, 'extra': [], 'join': 'and'})['code'] == 422
    per['day'] = {'enabled': True, 'return': 20000}
    assert ct_config({'periods': per, 'extra': [], 'join': 'and'})['code'] == 422


def test_saved_columns_survive_the_rename_and_new_columns_arrive_hidden():
    conn = connect()
    clean(conn)
    old = {'schema': 1, 'revision': 3, 'layouts': {
        'explorer.desktop': {'columns': [{'id': 'name', 'visible': True, 'width': None}, {'id': 'change', 'visible': True, 'width': 130}, {'id': 'rank', 'visible': False, 'width': None}],
                             'sort': [{'key': 'change', 'dir': 'asc'}, {'key': 'name', 'dir': 'desc'}], 'filters': {'verdict': 'excluded', 'page_size': 100}},
        'scores.mobile': {'columns': [{'id': 'simple', 'visible': True, 'width': None}, {'id': 'name', 'visible': True, 'width': None}], 'sort': [], 'filters': {'verdict': 'all'}}}}
    with conn.cursor() as cur:
        cur.execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('table_layouts', %s, NOW())", (json.dumps(old),))
    conn.commit()
    d = php('echo json_encode(tl_read());')
    ex = d['layouts']['explorer.desktop']
    ids = [c['id'] for c in ex['columns']]
    assert ids[:3] == ['name', 'change', 'rank'] and ex['columns'][1]['visible'] and ex['columns'][1]['width'] == 130 and not ex['columns'][2]['visible']
    assert ex['sort'] == [{'key': 'change', 'dir': 'asc'}, {'key': 'name', 'dir': 'desc'}] and ex['filters']['verdict'] == 'excluded' and ex['filters']['page_size'] == 100
    assert 'last_close' in ids and not next(c for c in ex['columns'] if c['id'] == 'last_close')['visible']      # nouvelle colonne : en fin de liste, masquée
    sc = d['layouts']['scores.mobile']
    assert 'change' in [c['id'] for c in sc['columns']] and not next(c for c in sc['columns'] if c['id'] == 'change')['visible']
    assert next(c for c in d['catalog']['explorer']['columns'] if c['id'] == 'change')['label'] == 'Var. 1J (%)'
    assert next(c for c in d['catalog']['explorer']['columns'] if c['id'] == 'change')['hint'] == 'Variation du cours entre les deux dernières séances clôturées.'
    clean(conn)
