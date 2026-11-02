"""Évolution du portefeuille jour par jour : valeur, apports nets, résultat cumulé, ventes, splits, change."""
import datetime

from engine.analytics import history as h

TODAY = datetime.date(2026, 1, 9)


def tx(i, day, side, qty, price, lid=1, fx=1.0, fees=0.0, cur='EUR', sym='A'):
    return {'id': i, 'trade_at': f'{day} 12:00:00', 'side': side, 'quantity': qty, 'unit_price': price, 'fx_to_eur': fx, 'fees': fees, 'listing_id': lid, 'symbol': sym, 'currency': cur, 'name': None}


BARS = {1: [('2026-01-05', 10.0, None), ('2026-01-06', 11.0, None), ('2026-01-07', 12.0, None), ('2026-01-08', 9.0, None)]}


def test_value_net_in_and_gain_survive_a_sale():
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 10, fees=1), tx(2, '2026-01-07', 'sell', 10, 12, fees=1)], BARS, {}, {1: 'EUR'}, {}, {}, TODAY)
    assert r['dates'] == ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09']
    assert r['value'] == [100.0, 110.0, 0.0, 0.0, 0.0]
    assert r['net_in'] == [101.0, 101.0, -18.0, -18.0, -18.0]
    assert r['gain'] == [-1.0, 9.0, 18.0, 18.0, 18.0]                       # gain réalisé conservé après la vente : 120 − 1 − 101
    assert r['lines'][0]['values'] == [100.0, 110.0, 0.0, 0.0, 0.0]
    assert r['lines'][0]['gain'] == r['gain'] and r['lines'][0]['net_in'] == r['net_in']                 # un seul titre : son gain est celui du portefeuille


def test_split_converts_quantities_and_ignores_manual_free_buy():
    bars = {1: [('2026-01-05', 100.0, None), ('2026-01-06', 50.0, None), ('2026-01-07', 52.0, None)]}            # split 2 pour 1 le 06/01
    r = h.build([tx(1, '2026-01-05', 'buy', 1, 100), tx(2, '2026-01-06', 'buy', 1, 0)], bars, {1: [('2026-01-06', 2.0)]}, {1: 'EUR'}, {}, {}, datetime.date(2026, 1, 7))
    assert r['value'] == [100.0, 100.0, 104.0] and r['net_in'] == [100.0, 100.0, 100.0]
    assert r['trades'][1]['note'] == 'split saisi à la main'


def test_foreign_currency_uses_the_daily_rate_and_unknown_close_uses_the_purchase_price():
    bars = {1: [('2026-01-06', 20.0, None)]}
    fx = {'USD': [('2026-01-01', 0.9), ('2026-01-06', 0.8)]}
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 20, fx=0.9, cur='USD')], bars, {}, {1: 'USD'}, fx, {}, datetime.date(2026, 1, 6))
    assert r['dates'] == ['2026-01-05', '2026-01-06'] and r['value'] == [180.0, 160.0] and r['gain'] == [0.0, -20.0]


def test_lines_start_at_zero_and_missing_fx_is_reported():
    bars = {1: BARS[1], 2: [('2026-01-07', 5.0, None), ('2026-01-08', 6.0, None)]}
    r = h.build([tx(1, '2026-01-05', 'buy', 1, 10), tx(2, '2026-01-07', 'buy', 2, 5, lid=2, sym='B'), tx(3, '2026-01-07', 'buy', 1, 5, lid=2, fx=None, cur='USD', sym='B')],
                bars, {}, {1: 'EUR', 2: 'EUR'}, {}, {}, datetime.date(2026, 1, 8))
    b = next(l for l in r['lines'] if l['symbol'] == 'B')
    assert b['values'] == [0.0, 0.0, 10.0, 12.0] and len(r['notes']) == 1
    assert h.build([], {}, {}, {}, {}, {})['dates'] == []


def test_today_uses_the_latest_quote_when_newer_than_the_last_close():
    meta = {1: {'price': 13.0, 'price_time': datetime.datetime(2026, 1, 9, 15, 0)}}
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 10)], BARS, {}, {1: 'EUR'}, {}, meta, TODAY)
    assert r['dates'][-1] == '2026-01-09' and r['value'][-1] == 130.0 and r['value'][-2] == 90.0


def test_intraday_value_of_current_holdings():
    bars15 = {1: [('2026-01-08T14:30:00', 9.5), ('2026-01-09T14:30:00', 12.0), ('2026-01-09T14:45:00', 12.5)]}
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 10)], BARS, {}, {1: 'EUR'}, {}, {}, TODAY, bars15=bars15)
    assert r['intraday'] == {'t': ['2026-01-09T14:30:00', '2026-01-09T14:45:00'], 'value': [120.0, 125.0]}
    assert h.build([tx(1, '2026-01-05', 'buy', 10, 10)], BARS, {}, {1: 'EUR'}, {}, {}, TODAY)['intraday'] == {'t': [], 'value': []}
