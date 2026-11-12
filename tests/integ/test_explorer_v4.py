"""Explorer V4: real SQL, the existing selection engine and authenticated PHP API."""
import copy
import os
import pytest
from engine.shared.db import connect
from engine.analytics.admin import service
from engine.analytics.admin import title_sheet
from engine.analytics.explorer import strategy
from engine.analytics.explorer import explorer_config as C
from tests.integ.test_api import server, world, login, Client  # noqa: F401  (fixtures)
from tests.integ.test_tracking_cache import seed, NOW

pytestmark=pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):pytest.skip('disposable database required',allow_module_level=True)


def config():
    c=C.empty();c['selection']['require_fresh']=False;c['periods'][2].update(enabled=True,min_return=0,min_up_fraction=0)
    c['ranking']['components']=[dict(id='growth',metric='perf',period='month',weight=2,enabled=True,kind='all',direction='higher',normalization='percentile',transform='identity',min=0,max=100,exponent=1)]
    return C.validate(c)


def test_full_scope_scores_are_identical_on_every_page_and_sheet(monkeypatch):
    monkeypatch.setattr(service.hours,'utcnow',lambda:NOW)
    c=connect();seed(c);cfg=config()
    with c.cursor() as q:q.execute('UPDATE daily_prices SET volume=1000')
    c.commit()
    req={'config':cfg,'view':{'tradable':False,'status':'retained','page_size':1}}
    first=service.explore(c,req);assert first['total']==3
    seen=[]
    for page in range(1,4):
        r=service.explore(c,{'config':cfg,'view':dict(req['view'],page=page)})
        assert len(r['rows'])==1
        row=r['rows'][0];seen.append(row['id'])
        parts=row['score_parts'];assert row['score']==pytest.approx(sum(p['contribution'] for p in parts),abs=.0001)
        assert row['measures']['21']['avg_volume']==1000
        sheet=title_sheet.instrument_sheet(c,{'listing_id':row['id'],'config':cfg,'view':req['view'],'fetch_profile':False})
        assert sheet['verdict']['score']==row['score']
        assert sheet['verdict']['score_parts']==parts
        assert len(sheet['analysis_windows']['21'])==22
    assert len(set(seen))==3
    assert service.explore(c,req)==first
    c.close()


def test_quoted_prices_do_not_change_last_day_closing_return(monkeypatch):
    monkeypatch.setattr(service.hours,'utcnow',lambda:NOW)
    c=connect();seed(c);cfg=C.empty();cfg['periods'][0].update(enabled=True,min_return=0)
    a=service.explore(c,{'config':cfg,'view':{'tradable':False,'status':'all'}})
    with c.cursor() as q:
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (1,.01,NOW(),'intraday','EUR') ON DUPLICATE KEY UPDATE price=.01,source='intraday'")
    c.commit()
    b=service.explore(c,{'config':cfg,'view':{'tradable':False,'status':'all'}})
    assert {r['id']:r['measures']['1']['perf'] for r in a['rows']}=={r['id']:r['measures']['1']['perf'] for r in b['rows']}
    assert {r['id']:r['status'] for r in a['rows']}=={r['id']:r['status'] for r in b['rows']}
    c.close()


def test_library_typed_saves_auth_and_validation(world):
    a=login(world,'alice','alice-secret-1234');b=login(world,'bob','bob-secret-12345');cfg=C.upgrade(strategy.preset('fast'))
    assert Client(world).call('explorer/library')[0]==401
    status,res=a.call('explorer/library/save',{'kind':'strategy','name':'Ma stratégie','payload':{'config':cfg,'universe':{'q':'SHOULD_NOT_LEAK'}}})
    assert status==200,res
    id=res['id'];items=a.call('explorer/library')[1]['items'];saved=next(i for i in items if i['id']==id)
    assert 'universe' not in saved['payload']
    assert isinstance(saved['payload']['config']['asset_rules'],dict)
    assert isinstance(saved['payload']['config']['ranking']['weights'],dict)
    assert b.call('explorer/library')[1]['items']==[]
    assert b.call('explorer/library/save',{'id':id,'kind':'strategy','name':'Vol','payload':{'config':cfg}})[0]==404
    assert b.call('explorer/library/delete',{'id':id})[0]==200
    assert any(i['id']==id for i in a.call('explorer/library')[1]['items'])
    assert a.call('explorer/library/save',{'id':id,'kind':'strategy','name':'Renommée','active':False,'payload':saved['payload']})[0]==200
    assert a.call('explorer/library/save',{'kind':'universe','name':'Pays','payload':{'universe':{'kind':'etf','currency':'EUR'},'config':cfg}})[0]==200
    universe=next(i for i in a.call('explorer/library')[1]['items'] if i['kind']=='universe')
    assert 'config' not in universe['payload'] and universe['payload']['universe']['currency']=='EUR'
    bad=copy.deepcopy(cfg);bad['periods'][0]['min_r2']=.8
    assert a.call('explorer/library/save',{'kind':'strategy','name':'Invalide','payload':{'config':bad}})[0] in (400,422)
    assert a.call('explorer/library/delete',{'id':id})[0]==200


def test_quoted_volume_selection_cache_invalidates_without_a_price_job(monkeypatch):
    monkeypatch.setattr(service.hours,'utcnow',lambda:NOW)
    c=connect();seed(c);cfg=C.empty();cfg['liquidity']['min_quoted_volume']=100
    req={'config':cfg,'view':{'tradable':False,'status':'retained'}}
    assert service.explore(c,req)['total']==0
    with c.cursor() as q:q.execute("INSERT INTO latest_prices(listing_id,price,currency,avg_volume_3m) VALUES (1,100,'EUR',1000)")
    c.commit()
    result=service.explore(c,req);assert result['total']==1 and result['rows'][0]['id']==1
    c.close()


def test_turnover_uses_raw_split_prices_volumes_and_dated_fx(monkeypatch):
    from engine.analytics.explorer.explorer_metrics import load
    from engine.market.calendar import session_dates
    monkeypatch.setattr(service.hours,'utcnow',lambda:NOW)
    conn=connect();seed(conn);dates=session_dates('XETR','2026-10-27',6)
    with conn.cursor() as q:
        q.execute('DELETE FROM daily_prices WHERE listing_id=1')
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px,volume) VALUES (1,%s,%s,50,%s)',[(d,100 if i<3 else 50,10 if i<3 else 20) for i,d in enumerate(dates)])
        q.execute("INSERT INTO corporate_events VALUES (1,%s,'split',2)",(dates[3],))
        q.execute("INSERT INTO fx_rates VALUES ('USD',%s,.5)",(dates[0],))
    conn.commit()
    universe=[dict(id=1,mic='XETR',currency='USD',price_currency='USD')]
    metric=load(conn,universe,[5],lambda c,m:'2026-10-27')[1][5]
    assert metric['turnover_eur']==pytest.approx(500)
    assert metric['current_drawdown']==pytest.approx(0) and metric['up_days']==0
    with conn.cursor() as q:q.execute('UPDATE daily_prices SET volume=NULL WHERE listing_id=1 AND price_date=%s',(dates[1],))
    conn.commit()
    metric=load(conn,universe,[5],lambda c,m:'2026-10-27')[1][5]
    assert metric['avg_volume'] is None and metric['turnover_eur'] is None
    conn.close()
