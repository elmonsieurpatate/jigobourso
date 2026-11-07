"""Administration des colonnes : quatre configurations indépendantes, ordre, largeurs, tri, filtres, révision, réinitialisation, compatibilité (vrai PHP + MariaDB)."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if os.environ.get('JIGO_TEST_DATABASE') != '1':
    pytest.skip('base jetable requise', allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / 'app/config/table_columns.json').read_text(encoding='utf-8'))['pages']


def php(code):
    body = 'require ' + json.dumps(str(ROOT / 'app/services/table_layouts.php')) + ';' + code
    r = subprocess.run(['php', '-r', body], cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def call(fn, arg):
    return php('try { echo json_encode(["ok" => ' + fn + '(json_decode(' + json.dumps(json.dumps(arg)) + ', true))]); } catch (ApiError $e) { echo json_encode(["error" => $e->getMessage(), "code" => $e->status]); }')


def read():
    return php('echo json_encode(tl_read());')


def fresh():
    conn = connect()
    try:
        reset_data(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM settings WHERE name='table_layouts'")
        conn.commit()
    finally:
        conn.close()


def cfg(page, dev, visible=None, order=None, **extra):
    d = read()['layouts'][page + '.' + dev]
    cols = {c['id']: c for c in d['columns']}
    ids = order or [c['id'] for c in d['columns']]
    out = [dict(cols[i], visible=(i in visible) if visible is not None else cols[i]['visible']) for i in ids]
    return {**d, 'columns': out, **extra}


def test_four_independent_configurations_with_defaults_and_catalog():
    fresh()
    d = read()
    assert set(d['layouts']) == {'explorer.desktop', 'explorer.mobile', 'scores.desktop', 'scores.mobile'} and d['revision'] == 0
    for page, p in CATALOG.items():
        for dev in ('desktop', 'mobile'):
            c = d['layouts'][page + '.' + dev]
            assert [x['id'] for x in c['columns']] == [x['id'] for x in p['columns']]                 # ordre du catalogue
            assert [x['id'] for x in c['columns'] if x['visible']] == [i for i in [x['id'] for x in p['columns']] if i in p['defaults'][dev]['visible']]
            assert c['filters']['verdict'] == p['defaults'][dev]['filters']['verdict'] and c['sort'] == []
    assert d['layouts']['explorer.desktop']['filters']['verdict'] == 'retained' and d['layouts']['scores.desktop']['filters']['verdict'] == 'all'
    assert not any(d['saved'].values())


def test_save_order_visibility_width_sort_filters_and_leave_the_other_three_untouched():
    fresh()
    before = read()['layouts']
    order = ['name', 'simple', 'status', 'rank', 'perfMonth', 'slope', 'r2', 'turnover'] + [c['id'] for c in CATALOG['explorer']['columns'] if c['id'] not in ('name', 'simple', 'status', 'rank', 'perfMonth', 'slope', 'r2', 'turnover')]
    new = cfg('explorer', 'mobile', visible={'name', 'simple', 'status', 'rank'}, order=order)
    new['columns'][0]['width'] = 200
    new['sort'] = [{'key': 'complex', 'dir': 'desc'}, {'key': 'perfMonth', 'dir': 'desc'}, {'key': 'name', 'dir': 'asc'}]
    new['filters'] = {'verdict': 'all', 'page_size': 100}
    r = call('tl_write', {'page': 'explorer', 'device': 'mobile', 'config': new, 'revision': 0})
    assert 'ok' in r, r
    after = read()
    assert after['revision'] == 1 and after['saved']['explorer.mobile'] and not after['saved']['explorer.desktop']
    got = after['layouts']['explorer.mobile']
    assert [c['id'] for c in got['columns']][:8] == order[:8] and got['columns'][0]['width'] == 200                   # ordre exact conservé, masquées comprises
    assert [c['id'] for c in got['columns'] if c['visible']] == ['name', 'simple', 'status', 'rank']
    assert got['sort'] == new['sort'] and got['filters'] == {'verdict': 'all', 'page_size': 100}
    for k in ('explorer.desktop', 'scores.desktop', 'scores.mobile'):
        assert after['layouts'][k] == before[k], k                                                                   # indépendance des quatre configurations


def test_hidden_column_keeps_its_position_when_shown_again():
    fresh()
    base = read()['layouts']['scores.desktop']
    ids = [c['id'] for c in base['columns']]
    hide = cfg('scores', 'desktop', visible=set(ids) - {'status'})
    assert 'ok' in call('tl_write', {'page': 'scores', 'device': 'desktop', 'config': hide, 'revision': 0})
    assert [c['id'] for c in read()['layouts']['scores.desktop']['columns']] == ids                                 # position conservée
    show = cfg('scores', 'desktop', visible=set(ids))
    assert 'ok' in call('tl_write', {'page': 'scores', 'device': 'desktop', 'config': show, 'revision': 1})
    assert [c['id'] for c in read()['layouts']['scores.desktop']['columns']] == ids


def test_invalid_configurations_are_refused_never_saved_silently():
    fresh()
    good = cfg('explorer', 'desktop')
    def bad(mut, expect):
        c = json.loads(json.dumps(good)); mut(c)
        r = call('tl_write', {'page': 'explorer', 'device': 'desktop', 'config': c, 'revision': 0})
        assert r.get('code') == 422 and expect in r['error'], r
    bad(lambda c: [x.update(visible=False) for x in c['columns'] if x['id'] == 'name'], 'Titre')
    bad(lambda c: c['columns'].append({'id': 'inconnue', 'visible': True, 'width': None}), 'inconnue')
    bad(lambda c: c['columns'].append(dict(c['columns'][0])), 'double')
    bad(lambda c: c['columns'].__delitem__(3), 'manquante')
    bad(lambda c: c['columns'][1].update(width=10), 'Largeur')
    bad(lambda c: c.update(sort=[{'key': 'trend', 'dir': 'asc'}]), 'Tri invalide')                                 # colonne non triable
    bad(lambda c: c.update(sort=[{'key': 'simple', 'dir': 'asc'}, {'key': 'simple', 'dir': 'desc'}]), 'Tri invalide')
    bad(lambda c: c.update(sort=[{'key': k, 'dir': 'asc'} for k in ('simple', 'complex', 'name', 'price')]), 'Tri invalide')
    bad(lambda c: c.update(filters={'verdict': 'peut-etre', 'page_size': 50}), 'Statut')
    bad(lambda c: c.update(filters={'verdict': 'all', 'page_size': 7}), 'page')
    assert read()['revision'] == 0                                                                                     # rien n'a été enregistré


def test_concurrent_revision_is_refused_and_reset_restores_defaults_only_for_one_configuration():
    fresh()
    a = cfg('explorer', 'desktop', visible={'name', 'simple'})
    assert 'ok' in call('tl_write', {'page': 'explorer', 'device': 'desktop', 'config': a, 'revision': 0})
    stale = call('tl_write', {'page': 'explorer', 'device': 'mobile', 'config': cfg('explorer', 'mobile'), 'revision': 0})
    assert stale.get('code') == 409
    b = cfg('scores', 'mobile', visible={'name', 'simple'})
    assert 'ok' in call('tl_write', {'page': 'scores', 'device': 'mobile', 'config': b, 'revision': 1})
    assert 'ok' in call('tl_write', {'action': 'reset', 'page': 'explorer', 'device': 'desktop', 'revision': 2})
    d = read()
    assert not d['saved']['explorer.desktop'] and d['layouts']['explorer.desktop'] == d['defaults']['explorer.desktop']
    assert d['saved']['scores.mobile'] and [c['id'] for c in d['layouts']['scores.mobile']['columns'] if c['visible']] == ['name', 'simple']


def test_old_documents_stay_readable_when_the_catalogue_evolves():
    fresh()
    doc = {'schema': 1, 'revision': 5, 'layouts': {'scores.desktop': {'columns': [{'id': 'disparue', 'visible': True, 'width': None}, {'id': 'simple', 'visible': True, 'width': None}, {'id': 'name', 'visible': False, 'width': 9999}],
                                                                       'sort': [{'key': 'disparue', 'dir': 'asc'}], 'filters': {'verdict': 'nimporte'}}}}
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('table_layouts', %s, NOW())", (json.dumps(doc),))
        conn.commit()
    finally:
        conn.close()
    c = read()['layouts']['scores.desktop']
    ids = [x['id'] for x in c['columns']]
    assert ids[:2] == ['simple', 'name'] and set(ids) == {x['id'] for x in CATALOG['scores']['columns']}            # inconnue ignorée, nouvelles colonnes ajoutées en fin
    assert next(x for x in c['columns'] if x['id'] == 'name')['visible'] is True and next(x for x in c['columns'] if x['id'] == 'name')['width'] is None
    assert c['sort'] == [] and c['filters']['verdict'] == 'all'
