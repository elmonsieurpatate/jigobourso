"""Permanent financial regression tests; disposable MariaDB only."""
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

def portfolio(a,pf):
    return a.call('portfolio',params=f'&id={pf}')[1]

def account(world):
    a=login(world,'alice','alice-secret-1234')
    return a,a.call('portfolio/create',{'name':'Numerical cases'})[1]['id']

def test_deleting_or_reducing_old_buy_cannot_invalidate_later_sale(world):
    a,pf=account(world)
    buy=add(a,pf,'buy',10,100)[1]['id']
    assert add(a,pf,'sell',7,120,'2026-10-02')[0]==200
    assert a.call('tx/delete',{'id':buy})[0]==422
    assert a.call('tx/update',{'id':buy,'side':'buy','quantity':6,'unit_price':100,'trade_at':'2026-10-01'})[0]==422
    assert portfolio(a,pf)['positions'][0]['qty']==3

def test_valid_retroactive_edit_recomputes_average_cost_and_fees(world):
    a,pf=account(world)
    buy=add(a,pf,'buy',10,100,fees=10)[1]['id']
    assert add(a,pf,'buy',10,200,'2026-10-02',fees=10)[0]==200
    assert add(a,pf,'sell',5,180,'2026-10-03',fees=5)[0]==200
    # 3020/20 =151 EUR average; 900-5 - 5*151 =140 EUR realized.
    v=portfolio(a,pf);assert v['totals']['realized']==pytest.approx(140)
    assert v['positions'][0]['cost']==pytest.approx(2265)
    assert a.call('tx/update',{'id':buy,'side':'buy','quantity':10,'unit_price':120,'fees':10,'trade_at':'2026-10-01'})[0]==200
    v=portfolio(a,pf) # 3220/20=161; realized895-805=90; remaining2415
    assert v['totals']['realized']==pytest.approx(90)
    assert v['positions'][0]['cost']==pytest.approx(2415)
    assert v['totals']['fees']==pytest.approx(25)

def test_change_date_revalidates_all_later_positions(world):
    a,pf=account(world);buy=add(a,pf,'buy',1,100)[1]['id']
    assert add(a,pf,'sell',1,110,'2026-10-02')[0]==200
    assert a.call('tx/update',{'id':buy,'side':'buy','quantity':1,'unit_price':100,'trade_at':'2026-10-03'})[0]==422
    assert portfolio(a,pf)['totals']['realized']==pytest.approx(10)

def test_usd_partial_sale_cost_and_fees_use_each_historical_rate(world):
    a,pf=account(world)
    base={'portfolio_id':pf,'symbol':'US','currency':'USD','quantity':10,'unit_price':100,'trade_at':'2026-10-01','side':'buy','fx_to_eur':.9,'fees':10}
    assert a.call('tx/add',base)[0]==200 # 910 EUR
    assert a.call('tx/add',dict(base,quantity=4,unit_price=120,side='sell',trade_at='2026-10-02',fx_to_eur=.8,fees=4))[0]==200
    v=portfolio(a,pf)
    assert v['totals']['realized']==pytest.approx(16) # 4*120*.8-4 -4*91=16
    assert v['positions'][0]['cost']==pytest.approx(546)

@pytest.mark.parametrize('fx',[0,-1])
def test_nonpositive_fx_is_refused(world,fx):
    a,pf=account(world)
    assert a.call('tx/add',{'portfolio_id':pf,'symbol':'US','currency':'USD','side':'buy','quantity':1,'unit_price':100,'trade_at':'2026-10-01','fx_to_eur':fx})[0] in (400,422)

def test_missing_historical_rate_is_not_replaced_by_future_rate(world):
    a,pf=account(world);con=connect()
    with con.cursor() as c:c.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD','2026-10-29',0.9)")
    con.commit();con.close()
    assert a.call('tx/add',{'portfolio_id':pf,'symbol':'US','currency':'USD','side':'buy','quantity':1,'unit_price':100,'trade_at':'2026-10-01'})[0]==422
    assert portfolio(a,pf)['transactions']==0

@pytest.mark.parametrize('unit,price,fx',[('GBp',100,.012),('GBX',100,.012),('GBP',1,1.2)])
def test_pence_and_pounds_have_same_economic_cost(world,unit,price,fx):
    a,pf=account(world)
    assert a.call('tx/add',{'portfolio_id':pf,'symbol':'UK','currency':unit,'side':'buy','quantity':1,'unit_price':price,'fx_to_eur':fx,'trade_at':'2026-10-01'})[0]==200
    v=portfolio(a,pf)
    assert v['positions'][0]['cost']==pytest.approx(1.2)
    assert v['transactions_list'][0]['currency']==('GBP' if unit=='GBP' else 'GBX')

def test_legacy_missing_fx_is_visible_not_silently_revalued(world):
    a,pf=account(world);con=connect()
    with con.cursor() as c:
        c.execute("INSERT INTO portfolio_transactions(portfolio_id,symbol,side,quantity,unit_price,currency,trade_at,created_at) VALUES (%s,'OLD','buy',1,100,'USD','2026-10-01',NOW())",(pf,))
    con.commit();con.close()
    v=portfolio(a,pf)
    assert not v['integrity']['ok']
    assert v['totals']['cost'] is None and v['positions'][0]['cost'] is None      # le seul titre est incomplet : rien de calculable
    assert v['totals']['partial'] and v['totals']['excluded'] == ['OLD']
    assert v['transactions_list'][0]['fx_to_eur'] is None

@pytest.fixture(autouse=True)
def fixed_market_clock(monkeypatch):
    from engine.market import hours
    monkeypatch.setattr(hours, 'utcnow', lambda: dt.datetime(2026,10,29,12,tzinfo=dt.timezone.utc))


def test_concurrent_sales_serialize_and_only_one_can_spend_same_share(world):
    import subprocess
    from tests.integ.test_api import ROOT
    a,pf=account(world)
    assert add(a,pf,'buy',1,100)[0]==200
    con=connect()
    with con.cursor() as c:
        c.execute('SELECT user_id FROM portfolios WHERE id=%s',(pf,)); uid=c.fetchone()['user_id']
    con.close()
    code = "require " + repr(ROOT+'/app/services/transactions.php') + "; try { write_transaction("+str(uid)+","+str(pf)+", function($rows) { usleep(150000); q(\"INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,currency,fx_to_eur,trade_at,created_at) VALUES (?,1,'A.DE','sell',1,120,'EUR',1,'2026-10-02',NOW())\", ["+str(pf)+"]); return []; }); exit(0); } catch (ApiError $e) { exit($e->status === 422 ? 42 : 43); }"
    # Separate PHP processes/connections; the built-in HTTP server itself is single-threaded.
    procs=[subprocess.Popen(['php','-r',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    results=[p.communicate(timeout=15) for p in procs]
    assert sorted(p.returncode for p in procs)==[0,42],results
    v=portfolio(a,pf)
    assert v['transactions']==2 and not v['positions']
    assert v['totals']['realized']==pytest.approx(20)

@pytest.mark.parametrize('when',['2026-02-30','not-a-date'])
def test_invalid_trade_dates_are_not_silently_normalized(world,when):
    a,pf=account(world)
    assert add(a,pf,'buy',1,100,when)[0]==422

def test_full_disposal_net_cash_identity_includes_all_fees(world):
    a,pf=account(world)
    assert add(a,pf,'buy',3,100,fees=2)[0]==200
    assert add(a,pf,'sell',1,110,'2026-10-02',fees=1)[0]==200
    assert add(a,pf,'sell',2,120,'2026-10-03',fees=3)[0]==200
    v=portfolio(a,pf)
    assert not v['positions']
    assert v['totals']['realized']==pytest.approx(44) #109+237-302
    assert v['totals']['proceeds_total']-v['totals']['invested_total']==pytest.approx(44)
    assert v['totals']['fees']==pytest.approx(6)
