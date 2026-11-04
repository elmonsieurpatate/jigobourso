import copy
import os
import pytest
from engine.analytics import growth as G, growth_service as GS, service
from engine.shared.db import connect
from tests.integ.test_tracking_cache import seed,NOW
from tests.integ.test_api import world,server,login

pytestmark=pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):pytest.skip('base jetable requise',allow_module_level=True)


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setattr(service.hours,'utcnow',lambda:NOW)
    c=connect();seed(c);yield c;c.close()


def run(conn,**view):return service.explore(conn,dict(config=G.preset(),view=dict(status='all',**view)))


def test_integrated_two_scores_all_categories_and_pagination(conn):
    first=run(conn);assert first['counts']['available']==3 and first['counts']['secondary_masked']==0
    assert first['counts']['retained']==2 and first['counts']['rejected']==1
    assert first['total']==3
    assert run(conn)==first  # Cold/warm cache use identical public shapes.
    for row in first['rows']:
        if row['status']=='retained':
            assert row['scores']['complex'] is not None
            assert sum(p['contribution'] for p in row['scores']['parts']['simple'])==pytest.approx(row['score'])
            assert row['badges']['avg_volume']['id']=='unknown'
    paged=run(conn,page_size=1)
    assert paged['rows'][0]['scores']==first['rows'][0]['scores']
    sheet=service.instrument_sheet(conn,dict(listing_id=paged['rows'][0]['id'],config=G.preset(),fetch_profile=False))
    assert sheet['growth']['scores']==paged['rows'][0]['scores']


def test_secondary_filters_and_categories_never_change_scores_or_compute(conn,monkeypatch):
    first=run(conn);version=first['data_version']
    monkeypatch.setattr(service,'judge_universe',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('recalcul interdit')))
    filtered=run(conn,kind='equity',secondary={'avg_volume':['unknown']})
    assert filtered['data_version']==version
    assert filtered['counts']['secondary_masked']==0
    by={r['id']:r['scores'] for r in first['rows']}
    assert all(r['scores']==by[r['id']] for r in filtered['rows'])
    params=G.defaults();params['categories']['volatility']['bounds']=[.000001,.000002,.000003]
    GS.administration(conn,dict(action='save',settings=params))
    changed=run(conn);assert {r['id']:r['scores'] for r in changed['rows']}==by
    masked=run(conn,secondary={'avg_volume':[]});assert masked['total']==0 and masked['counts']['secondary_masked']==3


def test_history_repair_invalidates_without_a_job_and_unknown_is_not_zero(conn):
    first=run(conn)
    with conn.cursor() as q:
        q.execute("INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,'2026-11-20',999)")
        q.execute("UPDATE series_state SET last_close_date='2026-11-20' WHERE listing_id=1")
    conn.commit();future=run(conn)
    before={r['id']:r['scores'] for r in first['rows']}
    assert all(r['scores']==before[r['id']] for r in future['rows'])
    assert any(x['criterion']=='future_data' for r in future['rows'] if r['id']==1 for x in r['reasons'])
    with conn.cursor() as q:
        q.execute("DELETE FROM daily_prices WHERE listing_id=1 AND price_date='2026-11-20'")
        q.execute('SELECT MAX(price_date) d FROM daily_prices WHERE listing_id=1');day=q.fetchone()['d']
        q.execute('DELETE FROM daily_prices WHERE listing_id=1 AND price_date=%s',(day,))
    conn.commit();after=run(conn)
    assert first['data_version']!=after['data_version']
    row=next(r for r in after['rows'] if r['id']==1)
    assert row['status']=='unknown' and row['scores']['simple'] is None


def test_excluded_search_explains_technical_origin(conn):
    with conn.cursor() as q:q.execute("UPDATE listings SET status='excluded',excluded_reason='préfiltre : liquidité faible' WHERE id=1")
    conn.commit();result=run(conn,q='A.DE')
    row=result['rows'][0];assert row['status']=='technical'
    assert 'liquidité' in row['reasons'][0]['origin'] and result['counts']['technical']==1


def test_admin_preview_permissions_defaults_and_archives(world):
    alice=login(world,'alice','alice-secret-1234');bob=login(world,'bob','bob-secret-12345')
    assert bob.call('admin/explorer')[0]==403
    status,r=alice.call('admin/explorer');assert status==200,r
    proposed=r['settings'];assert proposed['periods']['quarter']['enabled'] is False
    bad=copy.deepcopy(proposed);bad['weights']['simple']['force']=90
    assert alice.call('admin/explorer',dict(action='save',settings=bad))[0] in (400,422)
    draft=copy.deepcopy(proposed);draft['periods']['week']['min_slope']=.12
    assert alice.call('admin/explorer',dict(action='preview',settings=draft))[0]==200
    assert alice.call('explorer/settings')[1]['preset']['periods'][1]['min_slope']==.08
    assert alice.call('admin/explorer',dict(action='save',settings=draft))[0]==200
    cfg=alice.call('explorer/settings')[1]['preset'];assert cfg['periods'][1]['min_slope']==.12
    assert alice.call('explore',dict(config=cfg,view={'secondary':{},'status':'all'}))[0]==200
    assert alice.call('explore',dict(config=cfg,view={'country':'Germany'}))[0]==422  # Never silently ignored.
    status,saved=alice.call('explorer/library/save',dict(kind='strategy',name='V4 conservée',payload={'config':cfg}));assert status==200,saved
    id=saved['id']
    assert bob.call('explorer/library/state',dict(id=id,active=True,archived=True))[0]==404
    for archived,active in [(True,True),(False,False),(False,True)]:
        assert alice.call('explorer/library/state',dict(id=id,archived=archived,active=active))[0]==200
        item=next(i for i in alice.call('explorer/library')[1]['items'] if i['id']==id)
        assert item['archived']==archived and item['active']==active and item['payload']['config']==cfg
    assert alice.call('explorer/library/state',dict(id='builtin:momentum',active=True,archived=False))[0]==200
    assert alice.call('admin/explorer',dict(action='reset'))[0]==200
    assert next(i for i in alice.call('explorer/library')[1]['items'] if i['id']==id)['payload']['config']==cfg


def test_additive_migration_and_rollback_preserve_data(conn):
    from scripts.rollback_growth_v4 import rollback
    from scripts.migrate import statements
    from pathlib import Path
    with conn.cursor() as q:
        q.execute("INSERT INTO users(username,pass_hash,created_at) VALUES ('rollback-growth','not-a-login',NOW())")
        uid=q.lastrowid
        q.execute("INSERT INTO explorer_states(user_id,item_key,active,archived,updated_at) VALUES (%s,'builtin:momentum',0,1,NOW())",(uid,))
    conn.commit()
    with pytest.raises(ValueError):rollback(conn)
    with conn.cursor() as q:
        q.execute('SELECT archived FROM explorer_states WHERE user_id=%s',(uid,));assert q.fetchone()['archived']==1
        q.execute('DELETE FROM explorer_states WHERE user_id=%s',(uid,))
    conn.commit();rollback(conn)
    with conn.cursor() as q:
        for sql in statements(Path('db/migrations/20261105_explorer_states.sql').read_text()):q.execute(sql)
    conn.commit()
