"""Additional review cases on the disposable runner DB only."""
import datetime as dt, os
import pytest
if not os.environ.get('JIGO_TEST_DATABASE'):pytest.skip('disposable DB only',allow_module_level=True)
from tests.integ.test_api import server,world,login
from engine.shared.db import connect
from engine.analytics.compute import compute_all
from engine.analytics.service import instrument_sheet

def add(a,pf,side,qty,price,date='2026-10-01',**extra):
    return a.call('tx/add',dict(portfolio_id=pf,listing_id=1,side=side,quantity=qty,unit_price=price,trade_at=date,**extra))

def test_edit_sale_must_reject_overselling(world):
    a=login(world,'alice','alice-secret-1234');pf=a.call('portfolio/create',{'name':'Audit'})[1]['id']
    assert add(a,pf,'buy',1,100)[0]==200
    sale=add(a,pf,'sell',1,120,'2026-10-02')[1]['id']
    status,data=a.call('tx/update',{'id':sale,'side':'sell','quantity':10,'unit_price':120,'trade_at':'2026-10-02'})
    assert status==422,(status,data,a.call('portfolio',params=f'&id={pf}')[1]['totals'])

def test_backdated_sale_must_not_precede_its_funding_purchase(world):
    a=login(world,'alice','alice-secret-1234');pf=a.call('portfolio/create',{'name':'Audit'})[1]['id']
    assert add(a,pf,'buy',1,100,'2026-10-02')[0]==200
    status,data=add(a,pf,'sell',1,120,'2026-10-01')
    assert status==422,(status,data,a.call('portfolio',params=f'&id={pf}')[1]['totals'])

def test_historical_purchase_cost_must_not_change_with_today_fx(world):
    a=login(world,'alice','alice-secret-1234');pf=a.call('portfolio/create',{'name':'Audit'})[1]['id'];con=connect()
    with con.cursor() as c:c.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD','2026-10-01',0.9)")
    con.commit()
    assert a.call('tx/add',{'portfolio_id':pf,'symbol':'MANUAL','currency':'USD','side':'buy','quantity':1,'unit_price':100,'trade_at':'2026-10-01'})[0]==200
    before=a.call('portfolio',params=f'&id={pf}')[1]['positions'][0]['cost']
    with con.cursor() as c:c.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD','2026-10-02',0.8)")
    con.commit();con.close()
    after=a.call('portfolio',params=f'&id={pf}')[1]['positions'][0]['cost']
    assert before==after,f'Historical cost changed from {before} to {after} without a transaction'

def test_sheet_metrics_must_use_same_adjustments_as_strategy_verdict(world):
    con=connect();dates=[];d=dt.date(2026,10,28)
    while len(dates)<90:
        if d.weekday()<5:dates.append(d)
        d-=dt.timedelta(days=1)
    dates.reverse()
    with con.cursor() as c:
        c.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px) VALUES (%s,%s,%s,%s)',[(1,d,100*1.002**i/(2 if i>=75 else 1),100*1.002**i/2) for i,d in enumerate(dates)])
        c.execute("INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (1,%s,'split',2)",(dates[75],))
    con.commit();compute_all(con,dt.datetime(2026,10,29,tzinfo=dt.timezone.utc))
    sheet=instrument_sheet(con,{'listing_id':1})
    con.close()
    assert sheet['verdict']['status']=='retained',sheet['verdict']
    assert sheet['measures']['21'] is not None and sheet['measures']['21']['perf']>0, sheet['measures']

def test_london_pence_purchase_must_not_be_interpreted_as_pounds(world):
    a=login(world,'alice','alice-secret-1234');pf=a.call('portfolio/create',{'name':'Audit'})[1]['id'];con=connect()
    with con.cursor() as c:
        c.execute("UPDATE listings SET currency='GBP',mic='XLON' WHERE id=1")
        c.execute("UPDATE latest_prices SET currency='GBp',price=100 WHERE listing_id=1")
        c.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('GBP','2026-10-29',1.2)")
    con.commit();con.close()
    assert add(a,pf,'buy',1,100,'2026-10-29')[0]==200
    pos=a.call('portfolio',params=f'&id={pf}')[1]['positions'][0]
    assert abs(pos['cost']-1.2)<1e-8, {'cost':pos['cost'],'current_value':pos['value'],'unrealized':pos['unrealized']}
