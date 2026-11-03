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


def test_foreign_currency_uses_the_daily_rate_and_never_invents_a_quote():
    bars = {1: [('2026-01-06', 20.0, None)]}
    fx = {'USD': [('2026-01-01', 0.9), ('2026-01-06', 0.8)]}
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 20, fx=0.9, cur='USD')], bars, {}, {1: 'USD'}, fx, {}, datetime.date(2026, 1, 6))
    assert r['dates'] == ['2026-01-05', '2026-01-06'] and r['value'] == [None, 160.0] and r['gain'] == [None, -20.0]
    assert r['unpriced'] == [1, 0] and r['notes']


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


def test_gross_purchases_survive_partial_and_full_sales():
    r = h.build([tx(1, '2026-01-05', 'buy', 10, 10, fees=1),
                 tx(2, '2026-01-06', 'buy', 10, 20, fees=2),
                 tx(3, '2026-01-07', 'sell', 20, 25, fees=3)], BARS, {}, {1: 'EUR'}, {}, {}, TODAY)
    assert r['purchases'] == [101, 303, 303, 303, 303]
    assert r['lines'][0]['purchases'] == r['purchases']
    assert r['gain'][-1] == 194 and r['value'][-1] == 0


def test_missing_quote_is_unavailable_in_daily_and_intraday_totals():
    trades = [tx(1, '2026-01-05', 'buy', 1, 10), tx(2, '2026-01-05', 'buy', 1, 20, lid=2)]
    r = h.build(trades, BARS, {}, {1: 'EUR', 2: 'EUR'}, {}, {}, TODAY,
                bars15={1: [('2026-01-09T14:30:00', 12.0), ('2026-01-09T14:45:00', 13.0)]})
    assert r['value'][-1] is None and r['gain'][-1] is None and r['unpriced'][-1] == 1
    assert r['intraday']['value'] == [None, None]
    assert next(l for l in r['lines'] if l['symbol'] == 'A' and l['key'] == '2')['values'][-1] is None


def test_quote_without_daily_history_and_sold_unpriced_position():
    r = h.build([tx(1, '2026-01-05', 'buy', 2, 10)], {}, {}, {1: 'EUR'}, {},
                {1: {'price': 12, 'price_time': datetime.datetime(2026, 1, 9, 12)}}, TODAY)
    assert r['value'][-1] == 24 and r['gain'][-1] == 4
    r = h.build([tx(1, '2026-01-05', 'buy', 2, 10), tx(2, '2026-01-06', 'sell', 2, 12)], {}, {}, {1: 'EUR'}, {}, {}, TODAY)
    assert r['value'][-1] == 0 and r['gain'][-1] == 4


def test_market_history_precedes_purchase_and_keeps_true_trade_details():
    r = h.build([tx(1, '2026-01-07', 'buy', 2, 12, fees=1), tx(2, '2026-01-08', 'buy', 1, 9, fees=.5), tx(3, '2026-01-09', 'sell', 1, 10)], BARS, {}, {1:'EUR'}, {}, {}, TODAY)
    assert r['market']['dates'][0] == '2026-01-05'
    assert r['dates'][0] == '2026-01-07'
    assert r['market']['lines'][0]['prices'] == [10,11,12,9]
    assert r['trades'][0]['first_buy'] is True
    assert r['trades'][1]['first_buy'] is False
    assert r['trades'][0]['quantity'] == 2
    assert r['trades'][0]['fees_eur'] == 1
    assert r['trades'][0]['unit_price'] == 12
    assert r['trades'][0]['key'] == '1'
    assert r['lines'][0]['gain'][-1] == -6.5  # 18 value - 24.5 net flows


def test_market_split_and_partial_sale_do_not_change_price_series():
    bars={1:[('2026-01-05',100,None),('2026-01-06',50,None),('2026-01-07',52,None)]}
    r=h.build([tx(1,'2026-01-05','buy',2,100),tx(2,'2026-01-07','sell',1,52)],bars,{1:[('2026-01-06',2)]},{1:'EUR'},{},{},datetime.date(2026,1,7))
    assert r['market']['lines'][0]['prices']==[50,50,52]
    assert r['market']['lines'][0]['break_dates']==[]
    assert r['value'][-1]==156
    assert r['gain'][-1]==8
    assert r['trades'][0]['quantity']==2  # historical unadjusted transaction
    assert r['trades'][0]['unit_price']==100


def test_market_keeps_currency_missing_observations_and_actual_quote_date():
    m={1:{'price':12,'price_time':'2026-01-08 13:00:00'},2:{}}
    r=h.build([tx(1,'2026-01-07','buy',1,12,cur='USD',fx=.9),tx(2,'2026-01-07','buy',1,10,lid=2,sym='B')],
        {1:BARS[1],2:[('2026-01-05',10,None)]},{},{1:'USD',2:'EUR'},{'USD':[('2026-01-05',.8)]},m,TODAY)
    a,b=r['market']['lines']
    assert a['currency']=='USD' and a['prices'][0]==10
    assert a['last_date']=='2026-01-08' and '2026-01-09' not in r['market']['dates']
    assert b['prices']==[10,None,None,None]
    assert r['trades'][0]['fx_to_eur']==.9
    assert r['lines'][0]['gain'][-1] is not None


def test_market_excludes_sold_holdings_and_uses_only_latest_intraday_session():
    r=h.build([tx(1,'2026-01-05','buy',1,10),tx(2,'2026-01-07','sell',1,12)],BARS,{},{1:'EUR'},{},{},TODAY)
    assert r['market']['lines']==[]
    assert r['gain'][-1]==2
    r=h.build([tx(1,'2026-01-07','buy',1,12)],BARS,{},{1:'EUR'},{},{},TODAY,
        bars15={1:[('2026-01-08T09:00:00',9),('2026-01-09T09:00:00',10),('2026-01-09T09:15:00',11)]})
    assert r['market']['intraday']['dates']==['2026-01-09T09:00:00','2026-01-09T09:15:00']
    assert r['market']['intraday']['lines'][0]['prices']==[10,11]


def test_holding_intervals_are_exposed_without_changing_realised_results():
    r=h.build([tx(1,'2026-01-05','buy',1,10),tx(2,'2026-01-06','sell',1,11),tx(3,'2026-01-08','buy',1,9)],BARS,{},{1:'EUR'},{},{},TODAY)
    line=r['lines'][0]
    assert line['quantities']==[1,0,0,1,1]
    assert line['gain']==[0,1,1,1,1]


def test_market_euro_prices_use_dated_fx_not_transaction_conversion():
    r=h.build([tx(1,'2026-01-07','buy',1,12,fx=.9,cur='USD')],BARS,{},{1:'USD'},
              {'USD':[('2026-01-05',.8)]},{},TODAY)
    m=r['market']['lines'][0]
    assert m['prices'][0]==10 and m['prices_eur'][0]==8
    assert r['trades'][0]['fx_to_eur']==.9
    assert m['prices_eur'][-1]==7.2
