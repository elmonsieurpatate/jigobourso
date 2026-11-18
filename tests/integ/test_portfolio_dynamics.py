"""Matrice authentifiée + registre existant, base jetable uniquement."""

import os
import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)
from engine.shared.db import connect
from engine.market import hours
from engine.market.calendar import session_dates
from tests.integ.test_api import Client, login, server, world  # noqa: F401
from tests.integ.test_portfolio_cash import create, buy, cash

pytestmark = pytest.mark.integration


def seed_closes():
    days = session_dates('XETR', str(hours.latest_settled('XETR', hours.utcnow())), 40)
    conn = connect()
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)', [(d, 100 + i) for i, d in enumerate(days)])
    conn.commit()
    conn.close()
    return days


@pytest.mark.parametrize('legacy', [False, True])
def test_authentication_open_positions_and_identical_market_data_for_any_purchase_date(world, legacy):
    a, b = login(world, 'alice', 'alice-secret-1234'), login(world, 'bob', 'bob-secret-12345')
    pf = a.call('portfolio/create', {'name': 'Ancien'})[1]['id'] if legacy else create(a, capital=10000)
    assert buy(a, pf, 5, 100, fees=2)[0] == 200
    assert buy(a, pf, 5, 110, date='2026-05-05', fees=3)[0] == 200
    assert buy(a, pf, 4, 130, date='2026-05-06', side='sell', fees=1)[0] == 200
    detail = a.call('portfolio', params=f'&id={pf}')[1]
    pos = detail['positions'][0]
    assert pos['qty'] == 6 and pos['cost'] == pytest.approx(633)
    assert pos['unrealized'] == pytest.approx(87)
    assert detail['totals']['realized'] == pytest.approx(97)
    if not legacy:
        assert cash(a, pf)['cash']['balance'] + detail['totals']['value'] - 10000 == pytest.approx(184)
    seed_closes()
    assert Client(world).call('portfolio/dynamics', params=f'&id={pf}')[0] == 401
    assert b.call('portfolio/dynamics', params=f'&id={pf}')[0] == 404
    status, result = a.call('portfolio/dynamics', params=f'&id={pf}')
    assert status == 200, result
    assert len(result['horizons']) == 11 and set(result['listings']) == {'1'}
    assert result['listings']['1']['cells']['1d']['return'] == pytest.approx(100 * (139 / 138 - 1))
    assert result['listings']['1']['cells']['4y']['return'] is None
    assert a.call('portfolio/dynamics', params=f'&id={pf}')[1] == result  # cache
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('UPDATE daily_prices SET close_px=140 WHERE listing_id=1 AND price_date=(SELECT x.d FROM (SELECT MAX(price_date) d FROM daily_prices WHERE listing_id=1) x)')
    conn.commit()
    conn.close()
    updated = a.call('portfolio/dynamics', params=f'&id={pf}')[1]
    assert updated['listings']['1']['cells']['1d']['return'] != result['listings']['1']['cells']['1d']['return']
    assert buy(a, pf, 6, 120, date='2026-05-07', side='sell')[0] == 200
    assert a.call('portfolio/dynamics', params=f'&id={pf}')[1]['listings'] == {}  # totalement vendu
    d = a.call('portfolio', params=f'&id={pf}')[1]
    assert not d['positions'] and d['closed'] and d['totals']['realized'] == pytest.approx(184)
    assert len(d['transactions_list']) == 4


def test_unlinked_positions_do_not_trigger_market_fetch(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = create(a)
    assert a.call('tx/add', dict(portfolio_id=pf, symbol='MANUEL', name='Manuel', side='buy', quantity=1, unit_price=10, currency='EUR', trade_at='2026-05-04'))[0] == 200
    data = a.call('portfolio/dynamics', params=f'&id={pf}')[1]
    assert data['listings'] == {} and len(data['horizons']) == 11
