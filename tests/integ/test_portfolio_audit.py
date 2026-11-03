"""Regressions from the portfolio audit: disposable DB only, real PHP API."""
import datetime as dt
import os

import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('disposable DB only', allow_module_level=True)

from engine.shared.db import connect
from tests.integ.test_api import login, server, world  # noqa: F401

pytestmark = pytest.mark.integration


def account(world):
    client = login(world, 'alice', 'alice-secret-1234')
    pf = client.call('portfolio/create', {'name': 'Audit regressions'})[1]['id']
    return client, pf


def add(client, pf, side='buy', qty=10, price=100, date='2026-05-01', **extra):
    status, data = client.call('tx/add', dict(portfolio_id=pf, listing_id=1, side=side,
                                            quantity=qty, unit_price=price, trade_at=date, **extra))
    assert status == 200, data
    return data['id']


def portfolio(client, pf):
    status, data = client.call('portfolio', params=f'&id={pf}')
    assert status == 200, data
    return data


@pytest.mark.parametrize('ratio,sell,manual', [(2, False, False), (.1, False, False), (2, True, False), (2, False, True)])
def test_fifo_lots_follow_confirmed_split_through_today(world, ratio, sell, manual):
    a, pf = account(world)
    add(a, pf, fees=10)
    conn = connect()
    with conn.cursor() as q:
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,'2026-06-01',%s,%s,'confirmed',NOW())", (1 / ratio, ratio))
    conn.commit(); conn.close()
    if manual:
        add(a, pf, qty=10, price=0, date='2026-06-02')
    if sell:
        add(a, pf, side='sell', qty=5, price=60, date='2026-07-01', fees=1)
    d = portfolio(a, pf)
    expected = 20 if manual else 10 * ratio - (5 if sell else 0)
    assert d['positions'][0]['qty'] == pytest.approx(expected)
    assert sum(l['remaining'] for l in d['lots']) == pytest.approx(expected)
    assert d['totals']['cost'] == pytest.approx(757.5 if sell else 1010)
    assert d['totals']['realized'] == pytest.approx(46.5 if sell else 0)


def test_future_split_does_not_adjust_open_lots_early(world):
    a, pf = account(world); add(a, pf)
    conn = connect()
    with conn.cursor() as q:
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,%s,.5,2,'confirmed',NOW())", (dt.date.today() + dt.timedelta(days=7),))
    conn.commit(); conn.close()
    d = portfolio(a, pf)
    assert d['positions'][0]['qty'] == sum(l['remaining'] for l in d['lots']) == 10


def test_no_quote_is_unavailable_everywhere_but_cost_is_preserved(world):
    a, pf = account(world); add(a, pf, qty=2, price=10)
    conn = connect()
    with conn.cursor() as q: q.execute('DELETE FROM latest_prices WHERE listing_id=1')
    conn.commit(); conn.close()
    d = portfolio(a, pf)
    h = a.call('portfolio/history', params=f'&id={pf}')[1]
    assert d['positions'][0]['price'] is None and d['positions'][0]['value'] is None
    assert d['totals']['value'] is None and h['value'][-1] is None
    assert d['totals']['cost'] == 20 and d['totals']['invested_total'] == 20
    assert d['totals']['total_gain'] is None and h['gain'][-1] is None
    assert h['notes'] and h['unpriced'][-1] == 1
    b = a.call('bilan')[1]['totals']
    assert b['value'] is None and b['total_gain'] is None and b['cost'] == 20


def test_last_closing_price_is_dated_and_shared_with_history(world):
    a, pf = account(world); add(a, pf, qty=2, price=10)
    conn = connect()
    with conn.cursor() as q:
        q.execute('DELETE FROM latest_prices WHERE listing_id=1')
        q.execute("INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,'2026-05-04',12)")
    conn.commit(); conn.close()
    d = portfolio(a, pf); h = a.call('portfolio/history', params=f'&id={pf}')[1]
    assert d['totals']['value'] == h['value'][-1] == 24
    assert d['positions'][0]['price_source'] == 'daily'
    assert d['positions'][0]['price_time'].startswith('2026-05-04')


def test_history_exposes_gross_purchases_after_sale(world):
    a, pf = account(world)
    add(a, pf, qty=1, price=100, fees=1)
    add(a, pf, side='sell', qty=1, price=120, date='2026-05-04', fees=1)
    h = a.call('portfolio/history', params=f'&id={pf}')[1]
    d = portfolio(a, pf)
    assert h['purchases'][-1] == d['totals']['invested_total'] == 101
    assert h['net_in'][-1] == -18 and h['gain'][-1] == d['totals']['total_gain'] == 18
    assert h['lines'][0]['purchases'][-1] == 101


def test_momentum_alert_api_keeps_percentage_points(world):
    a, pf = account(world); buy = add(a, pf)
    conn = connect()
    with conn.cursor() as q:
        q.execute("INSERT INTO series_state(listing_id,computed_at,closes_count,close_px,momentum_6m) VALUES (1,NOW(),127,90,-10)")
    conn.commit(); conn.close()
    assert a.call('lot/settings', {'tx_id': buy, 'strategy': 'momentum'})[0] == 200
    alerts = portfolio(a, pf)['lots'][0]['alert']['alerts']
    alert = next(x for x in alerts if x['kind'] == 'momentum')
    assert alert['value'] == -10 and '-10,0 %' in alert['message']


def test_newer_closing_price_wins_over_an_old_quote_in_summary_and_history(world):
    a, pf = account(world); add(a, pf, qty=2, price=10)
    conn = connect()
    with conn.cursor() as q:
        q.execute("UPDATE latest_prices SET price=11,price_time='2026-05-02 12:00:00' WHERE listing_id=1")
        q.execute("INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,'2026-05-04',12)")
    conn.commit(); conn.close()
    d = portfolio(a, pf); h = a.call('portfolio/history', params=f'&id={pf}')[1]
    assert d['positions'][0]['price_source'] == 'daily'
    assert d['totals']['value'] == h['value'][-1] == 24
    assert d['totals']['total_gain'] == h['gain'][-1] == 4


@pytest.mark.parametrize('ratio,currency', [(1,'EUR'),(2,'EUR'),(1,'USD')])
def test_gain_protection_uses_real_acquisition_cost_and_split_units(world, ratio, currency):
    a,pf=account(world)
    buy=add(a,pf,fees=1 if currency=='USD' else 10, currency=currency, fx_to_eur=.9 if currency=='USD' else 1)
    conn=connect();now=dt.date.today();days=[];day=dt.date(2026,4,30)
    while day<now:
        if day.weekday()<5:days.append(day)
        day+=dt.timedelta(days=1)
    with conn.cursor() as q:
        if ratio!=1:
            q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,'2026-06-01',.5,2,'confirmed',NOW())")
            q.execute("INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (1,'2026-06-01','split',2)")
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)',[(d,(108 if d==dt.date(2026,5,4) else 100)/(ratio if d>=dt.date(2026,6,1) else 1))for d in days])
        q.execute('UPDATE latest_prices SET price=%s,currency=%s,price_time=NOW() WHERE listing_id=1',(104/ratio,currency))
        q.execute("INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma50,momentum_6m,quality) VALUES (1,NOW(),%s,%s,%s,%s,.1,'ok')",(days[-1],len(days),100/ratio,99/ratio))
        q.execute('INSERT INTO strategy_metrics(listing_id,sessions,slope,perf,volatility) VALUES (1,21,.05,4,.5)')
        if currency=='USD':
            q.executemany("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',%s,.8)",[(d,)for d in days])
            q.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',%s,.85)",(now,))
    conn.commit();conn.close()
    d=portfolio(a,pf);lot=d['lots'][0]['alert']['protection'];group=d['insights']['L1']['protection']
    assert lot['available'] and group['available']
    assert lot['cost_eur']==(901 if currency=='USD' else 1010)
    assert lot['gain_eur']==pytest.approx(-17 if currency=='USD' else 30)
    assert lot['drop_pct']==pytest.approx(100*(1-104/108))
    assert group['gain_eur']==pytest.approx(d['positions'][0]['unrealized'])
    assert a.call('lot/settings',{'tx_id':buy,'strategy':'recovery'})[0]==200
    d=portfolio(a,pf)
    assert d['lots'][0]['alert']['strategy']=='recovery'
    assert d['lots'][0]['alert']['protection']['cost_eur']==lot['cost_eur']

    if ratio == 1 and currency == 'EUR':
        conn=connect()
        with conn.cursor() as q: q.execute("UPDATE series_state SET quality='break' WHERE listing_id=1")
        conn.commit(); conn.close()
        unreliable=portfolio(a,pf)
        assert not unreliable['insights']['L1']['protection']['available']
        assert unreliable['insights']['L1']['status']=='unknown'
        assert unreliable['totals']['value']==d['totals']['value']


@pytest.mark.parametrize('ratio,currency,fx', [(1,'EUR',1), (2,'USD',.9)])
def test_analysis_market_precedes_purchase_and_markers_keep_transaction_units(world, ratio, currency, fx):
    a,pf=account(world)
    conn=connect()
    with conn.cursor() as q:
        q.execute('UPDATE listings SET currency=%s WHERE id=1',(currency,))
        q.execute('UPDATE latest_prices SET currency=%s WHERE listing_id=1',(currency,))
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)',
                      [('2026-04-01',100),('2026-05-01',110),('2026-06-01',120/ratio)])
        if ratio!=1:
            q.execute("INSERT INTO corporate_events VALUES (1,'2026-06-01','split',%s)",(ratio,))
            q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,'2026-06-01',%s,%s,'confirmed',NOW())",(1/ratio,ratio))
        if currency!='EUR':
            q.execute("INSERT INTO fx_rates VALUES ('USD','2026-04-01',.9),('USD',CURDATE(),.8)")
    conn.commit();conn.close()
    buy=add(a,pf,qty=2,price=110,date='2026-05-01',fees=2,currency=currency,fx_to_eur=fx)
    add(a,pf,qty=1,price=120/ratio,date='2026-06-01',fees=1,currency=currency,fx_to_eur=fx)
    add(a,pf,side='sell',qty=1,price=120/ratio,date='2026-06-02',fees=1,currency=currency,fx_to_eur=fx)
    status,r=a.call('portfolio/history',params=f'&id={pf}')
    assert status==200,r
    assert r['market']['dates'][0]=='2026-04-01'
    assert r['dates'][0]=='2026-05-01'
    line=r['market']['lines'][0]
    assert line['currency']==currency
    assert line['prices'][0]==pytest.approx(100/ratio)
    assert r['trades'][0]['id']==buy
    assert r['trades'][0]['first_buy'] is True
    assert r['trades'][1]['first_buy'] is False
    assert r['trades'][0]['quantity']==2
    assert r['trades'][0]['unit_price']==110
    assert r['lines'][0]['quantities'][-1]==pytest.approx(2*ratio)
    assert r['trades'][0]['fees_eur']==2
    assert r['trades'][0]['fx_to_eur']==fx
    assert sum(l['gain'][-1] for l in r['lines'])==pytest.approx(r['gain'][-1])


@pytest.mark.parametrize('intraday_trade', [False,True])
def test_stored_fifteen_minute_session_supports_only_reliable_calculations(world,intraday_trade):
    a,pf=account(world)
    today=dt.date.today().isoformat()
    add(a,pf,date=today+' 09:15:00' if intraday_trade else '2026-05-01')
    conn=connect()
    with conn.cursor() as q:
        q.executemany('INSERT INTO intraday_prices(listing_id,slot_start,close_px) VALUES (1,%s,%s)',[(today+' 09:00:00',100),(today+' 09:15:00',101)])
    conn.commit();conn.close()
    status,r=a.call('portfolio/history',params=f'&id={pf}')
    assert status==200,r
    assert r['session']['day']==today
    if intraday_trade:
        assert r['session']['gain'][-1] is None
        assert 'Transaction' in r['session']['lines'][0]['reason']
        assert r['market']['intraday']['lines'][0]['prices']==[100,101]
    else:
        assert r['session']['gain'][-1]==10
        assert r['session']['pct'][-1]==1
        assert r['session']['base']==1000


def test_targeted_history_refresh_checks_ownership_and_cooldown_without_network(world):
    import time
    from engine.shared import settings
    a,pf=account(world);add(a,pf)
    conn=connect();settings.put(conn,'portfolio_refresh_1',time.time());conn.close()
    status,r=a.call('portfolio/history-refresh',{'id':pf,'listing_id':1})
    assert status==200 and r['cooldown'] is True
    assert a.call('portfolio/history-refresh',{'id':pf,'listing_id':2})[0]==404
    bob=login(world,'bob','bob-secret-12345')
    assert bob.call('portfolio/history-refresh',{'id':pf,'listing_id':1})[0]==404


def test_normal_metric_refresh_preserves_transactions_and_prices(world):
    from scripts.prepare_financial_release import refresh_metrics
    a,pf=account(world);add(a,pf)
    conn=connect()
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) n FROM portfolio_transactions');before=q.fetchone()['n']
        q.execute("INSERT INTO strategy_metrics(listing_id,sessions,slope) VALUES (1,1,999)")
    conn.commit();conn.close()
    refresh_metrics()
    conn=connect()
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) n FROM portfolio_transactions');assert q.fetchone()['n']==before
        q.execute('SELECT price FROM latest_prices WHERE listing_id=1');assert float(q.fetchone()['price'])==120
        q.execute('SELECT slope FROM strategy_metrics WHERE listing_id=1 AND sessions=1');assert q.fetchone()['slope'] is None
        q.execute("SELECT status FROM jobs WHERE job_type='metrics' ORDER BY id DESC LIMIT 1");assert q.fetchone()['status']=='completed'
    conn.close()
