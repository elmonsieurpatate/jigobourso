import json
from datetime import datetime, timezone
from engine.market import hours, prefilter, yahoo


def test_prefilter_dvdg_excluded_and_liquid_selected():
    s, why = prefilter.decide('etf', 42.135, 131, 1.0)
    assert s == 'excluded' and 'liquidité' in why
    assert prefilter.decide('equity', 209.75, 2_367_090, 1.0) == ('selected', None)
    assert prefilter.decide('equity', 1.0, 9e9, 1.0)[0] == 'excluded'
    assert prefilter.decide('equity', None, 1, 1.0) == (None, None)
    assert prefilter.decide('etf', 50, 6000, 1.0) == ('selected', None)        # 300 k€ ≥ 250 k€


def test_hours():
    t = lambda *a: datetime(*a, tzinfo=timezone.utc)
    assert hours.is_open('XETR', t(2026, 10, 27, 10, 0))           # mardi 11h Berlin (CET)
    assert not hours.is_open('XETR', t(2026, 10, 24, 10, 0))       # samedi
    assert not hours.is_open('XNYS', t(2026, 10, 27, 12, 0))       # 8h New York
    assert str(hours.session_date('XETR', t(2026, 10, 26, 6, 0))) == '2026-10-23'   # lundi avant ouverture -> vendredi
    assert hours.expected_slots('XETR') == 34 and hours.expected_slots('XNYS') == 26
    assert hours.is_settled('XETR', datetime(2026, 10, 27).date(), t(2026, 10, 27, 17, 1))
    assert not hours.is_settled('XETR', datetime(2026, 10, 27).date(), t(2026, 10, 27, 16, 45))


def test_parse_spark_both_shapes_and_nulls():
    wrapped = {'spark': {'result': [{'symbol': 'A.DE', 'response': [{'meta': {'currency': 'EUR', 'exchangeTimezoneName': 'Europe/Berlin'},
              'timestamp': [1, 2, 3], 'indicators': {'quote': [{'close': [10.0, None, 11.0]}]}}]}]}}
    r = yahoo.parse_spark(wrapped, ['A.DE'])
    assert r['A.DE']['bars'] == [(1, 10.0), (3, 11.0)] and r['A.DE']['currency'] == 'EUR'
    legacy = {'A.DE': {'timestamp': [1, 2], 'close': [5.0, 0]}}
    assert yahoo.parse_spark(legacy, ['A.DE'])['A.DE']['bars'] == [(1, 5.0)]
    assert yahoo.parse_spark(wrapped, ['OTHER']) == {}


def test_parse_quotes():
    q = yahoo.parse_quotes({'quoteResponse': {'result': [{'symbol': 'DVDG.DE', 'regularMarketPrice': 42.1, 'averageDailyVolume3Month': 131, 'currency': 'EUR'},
                                                         {'symbol': 'X', 'regularMarketPrice': None}]}})
    assert list(q) == ['DVDG.DE'] and q['DVDG.DE']['avg_volume_3m'] == 131
