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
