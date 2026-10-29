import datetime as dt
import math
import pytest
from engine.analytics import etf
from engine.market.etf_profile import parse_profile


def dates(n=130):
    d = dt.date(2026, 5, 1)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def vector(n=120):
    return {f'{i:03}/x': math.sin(i * .43) * .02 for i in range(n)}


def test_correlation_expected_positive_negative_and_scale():
    a = vector()
    assert etf.correlate(a, {k: v * 3 + .002 for k, v in a.items()})['coefficient'] == 1
    assert etf.correlate(a, {k: -v for k, v in a.items()})['coefficient'] == -1
    assert etf.correlate(a, {k: 0 for k in a}) is None
    assert etf.correlate(a, vector(99)) is None
    assert etf.correlate(a, vector(100))['sessions'] == 100


def test_identical_dates_but_different_intervals_not_compared():
    a = vector()
    assert etf.correlate(a, {k.replace('/x', '/y'): v for k, v in a.items()}) is None


def test_currency_is_converted_at_each_historical_date():
    days = dates()
    eur = [(d, 100 + i + 2 * math.sin(i), None) for i, d in enumerate(days)]
    fx = {'USD': {d: .8 + .001 * i for i, d in enumerate(days)}}
    usd = [(d, c / fx['USD'][d], None) for d, c, _ in eur]
    a = etf.returns_eur(eur, [], 'EUR', {}, dt.date(2026, 5, 1))
    b = etf.returns_eur(usd, [], 'USD', fx, dt.date(2026, 5, 1))
    assert etf.correlate(a, b)['coefficient'] == 1
    assert not etf.returns_eur(usd, [], 'USD', {}, dt.date(2026, 5, 1))
    assert not etf.returns_eur(usd, [], 'USD', {'USD': {'2025-01-01': 1}}, dt.date(2026, 5, 1))


def test_pence_and_pounds_have_same_returns():
    ds = dates()
    pounds = [(d, 10 + i * .1 + math.sin(i) * .01, None) for i, d in enumerate(ds)]
    pence = [(d, p * 100, None) for d, p, _ in pounds]
    fx = {'GBP': {d: 1.2 for d in ds}}
    a = etf.returns_eur(pounds, [], 'GBP', fx, dt.date(2026, 5, 1))
    b = etf.returns_eur(pence, [], 'GBX', fx, dt.date(2026, 5, 1))
    assert etf.correlate(a, b)['coefficient'] == 1


def test_split_corrected_and_unknown_split_not_used():
    ds = dates()
    raw = [(d, (100 + i + math.sin(i)) / (2 if i >= 60 else 1), None) for i, d in enumerate(ds)]
    clean = [(d, 100 + i + math.sin(i), None) for i, d in enumerate(ds)]
    a = etf.returns_eur(raw, [(ds[60], 2)], 'EUR', {}, dt.date(2026, 5, 1))
    b = etf.returns_eur(clean, [], 'EUR', {}, dt.date(2026, 5, 1))
    assert etf.correlate(a, b)['coefficient'] == 1
    unknown = etf.returns_eur(raw, [(ds[60], None)], 'EUR', {}, dt.date(2026, 5, 1))
    assert ds[59] + '/' + ds[60] not in unknown


def test_missing_values_are_not_zero_and_partial_not_top10():
    p = etf.profile_data({'holdings': [{'symbol': 'X', 'weight': None}], 'expense_ratio': None})
    assert p['holdings'][0]['weight'] is None and p['expense_ratio'] is None
    assert p['top10_weight'] is None
    p = etf.profile_data({'holdings': [{'weight': 0}] * 10, 'expense_ratio': 0})
    assert p['top10_weight'] == 0 and p['expense_ratio'] == 0
    p = parse_profile({'quoteSummary': {'result': [{'fundProfile': {'family': 'A'}, 'topHoldings': {'holdings': [{'symbol': 'A'}]}}]}})
    assert p['holdings'][0]['weight'] is None


def test_sector_weights_refer_to_equity_sleeve_not_all_assets():
    p = etf.exposure({'category': 'Energy'}, {'sectors': {'Énergie': 100}, 'stock_position': 40})
    assert p['label'] == 'Énergie (actions)' and p['sectors']['Énergie'] == 40
    assert not etf.exposure({}, {'sectors': {'Énergie': 100}})['sectors']
    assert etf.exposure({'category': 'Commodities'}, {})['label'] == 'Matières premières (hors actions)'
    assert not etf.profile_data({'sectors': {'A': 80, 'B': 80}})['sectors']


def test_six_months_and_no_future_price_fill():
    assert etf.six_months(dt.date(2026, 8, 31)) == dt.date(2026, 2, 28)
    assert etf.six_months(dt.date(2026, 1, 31)) == dt.date(2025, 7, 31)


def test_portfolio_value_weighted_unknown_and_pair(monkeypatch):
    cache = {1: {'exposure': {'sectors': {'Énergie': 50}}, 'returns': vector(), 'stale': False},
             2: {'exposure': {'sectors': {'Énergie': 100}}, 'returns': vector(), 'stale': False}}
    monkeypatch.setattr(etf, 'load', lambda *a: cache)
    p = [{'listing_id': 1, 'kind': 'etf', 'symbol': 'A', 'value': 100}, {'listing_id': 2, 'kind': 'etf', 'symbol': 'B', 'value': 300}, {'kind': 'equity', 'value': 100}]
    r = etf.portfolio(None, p)
    assert r['total_priced_eur'] == 500 and r['known_eur'] == 350
    assert r['unknown_eur'] == 150 and r['unknown_percent'] == 30
    assert r['sectors'][0]['percent'] == 70
    assert r['similar_pairs'][0]['coefficient'] == 1
    p.append({'value': None})
    r = etf.portfolio(None, p)
    assert r['unknown_percent'] is None and r['sectors'][0]['percent'] is None
    cache[1]['stale'] = True
    r = etf.portfolio(None, p)
    assert r['known_eur'] == 300 and r['unavailable_pairs'] == 1
