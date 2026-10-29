import datetime as dt
import math
import random

import pytest
from engine.analytics import etf, signals
from engine.market.etf_profile import parse_profile

START = dt.date(2025, 10, 6)           # un lundi


def weekdays(n_days):
    out, d = [], START
    while len(out) < n_days:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def noise(seed, n_days=380):
    rng = random.Random(seed)
    return {d: rng.gauss(0, .02) for d in weekdays(n_days)}          # rendements hebdomadaires synthétiques, un par date de fin (les dates de même jour de semaine sont espacées de 7 jours)


def test_correlation_expected_values_and_scale():
    a = noise(1)
    c = etf.correlate(a, {k: v * 3 + .002 for k, v in a.items()})
    assert c['coefficient'] == 1 and c['partitions'] == 5 and c['stable'] and c['weeks'] >= etf.MIN_WEEKS and c['method'] == 'weekly-eur'
    assert etf.correlate(a, {k: -v for k, v in a.items()})['coefficient'] == -1
    assert etf.correlate(a, {k: 0 for k in a}) is None                     # variance nulle : pas de corrélation
    assert etf.correlate(a, noise(2, 150)) is None                         # moins de 40 semaines indépendantes par jour de semaine
    assert abs(etf.correlate(a, noise(3))['coefficient']) < .3             # séries indépendantes : proche de zéro


def test_each_weekday_series_has_no_overlapping_windows():
    a = noise(4)
    keys = sorted(a)
    for wd in range(5):
        same = [dt.date.fromisoformat(k) for k in keys if dt.date.fromisoformat(k).weekday() == wd]
        assert all((y - x).days == 7 for x, y in zip(same, same[1:]))      # une semaine après l'autre : intervalles disjoints
    c = etf.correlate(a, a)
    assert c['weeks'] == min(sum(1 for k in keys if dt.date.fromisoformat(k).weekday() == wd) for wd in range(5))


def test_unstable_pairs_are_flagged_not_hidden():
    a = noise(5)
    mixed = {k: (v if dt.date.fromisoformat(k).weekday() < 3 else noise(6)[k]) for k, v in a.items()}     # lundi à mercredi identiques, jeudi et vendredi sans rapport
    c = etf.correlate(a, mixed)
    assert c['spread'] > etf.SPREAD_LIMIT and c['stable'] is False
    keys = sorted(a)
    half = {k: (v if k < keys[len(keys) // 2] else noise(7)[k]) for k, v in a.items()}               # première moitié identique, seconde sans rapport
    d = etf.correlate(a, half)
    assert d['halves'][0] > .99 and abs(d['halves'][0] - d['halves'][1]) > etf.HALF_LIMIT and d['stable'] is False


def test_tiers_use_fixed_thresholds():
    assert [etf.tier(x) for x in (.99, .95, .8, .3)] == ['quasi identiques', 'très proches', 'proches', 'distincts']


def bars(n_days=380, factor=1.0, drift=0.0004, seed=11, fx=None):
    rng = random.Random(seed)
    out, price = [], 100.0
    for d in weekdays(n_days):
        price *= math.exp(drift + rng.gauss(0, .01))
        out.append((d, price * factor / (fx[d] if fx else 1), None))
    return out


def test_weekly_returns_have_seven_day_intervals_and_no_fill():
    b = bars()
    r = etf.returns_eur(b, [], 'EUR', {}, dt.date(2025, 10, 6))
    assert len(r) > 300
    prices = {d: p for d, p, _ in b}
    for end, value in list(r.items())[:20]:
        prev = (dt.date.fromisoformat(end) - dt.timedelta(days=7)).isoformat()
        assert math.isclose(value, math.log(prices[end] / prices[prev]), rel_tol=1e-9)
    holes = [x for x in b if x[0] != '2026-01-02']                          # une clôture manque : ni cette date ni sa suivante à 7 jours n'ont de rendement
    h = etf.returns_eur(holes, [], 'EUR', {}, dt.date(2025, 10, 6))
    assert '2026-01-02' not in h and '2026-01-09' not in h and '2026-01-05' in h


def test_currency_is_converted_at_each_historical_date_and_never_with_today_rate():
    days = weekdays(380)
    fx = {'USD': {d: .8 + .0003 * i for i, d in enumerate(days)}}
    eur = bars(seed=12)
    usd = [(d, c / fx['USD'][d], None) for d, c, _ in eur]
    a = etf.returns_eur(eur, [], 'EUR', {}, dt.date(2025, 10, 6))
    b = etf.returns_eur(usd, [], 'USD', fx, dt.date(2025, 10, 6))
    assert etf.correlate(a, b)['coefficient'] == pytest.approx(1)
    assert not etf.returns_eur(usd, [], 'USD', {}, dt.date(2025, 10, 6))                          # change absent : observation absente
    assert not etf.returns_eur(usd, [], 'USD', {'USD': {'2020-01-01': 1}}, dt.date(2025, 10, 6))   # un taux de 2020 n'est pas appliqué à 2026


def test_pence_and_pounds_have_the_same_returns():
    pounds = bars(seed=13)
    pence = [(d, p * 100, None) for d, p, _ in pounds]
    fx = {'GBP': {d: 1.2 for d in weekdays(380)}}
    a = etf.returns_eur(pounds, [], 'GBP', fx, dt.date(2025, 10, 6))
    b = etf.returns_eur(pence, [], 'GBX', fx, dt.date(2025, 10, 6))
    assert etf.correlate(a, b)['coefficient'] == pytest.approx(1)


def test_declared_split_is_corrected_and_unknown_split_breaks_the_interval():
    ds = weekdays(380)
    clean = bars(seed=14)
    raw = [(d, p / (2 if d >= ds[200] else 1), None) for d, p, _ in clean]
    a = etf.returns_eur(raw, [(ds[200], 2)], 'EUR', {}, dt.date(2025, 10, 6))
    b = etf.returns_eur(clean, [], 'EUR', {}, dt.date(2025, 10, 6))
    assert etf.correlate(a, b)['coefficient'] == pytest.approx(1)
    unknown = etf.returns_eur(raw, [(ds[200], None)], 'EUR', {}, dt.date(2025, 10, 6))
    assert ds[200] not in unknown


def test_missing_values_are_not_zero_and_partial_not_top10():
    p = etf.profile_data({'holdings': [{'symbol': 'X', 'weight': None}], 'expense_ratio': None})
    assert p['holdings'][0]['weight'] is None and p['expense_ratio'] is None and p['top10_weight'] is None
    p = etf.profile_data({'holdings': [{'weight': 0}] * 10, 'expense_ratio': 0})
    assert p['top10_weight'] == 0 and p['expense_ratio'] == 0
    p = parse_profile({'quoteSummary': {'result': [{'fundProfile': {'family': 'A'}, 'topHoldings': {'holdings': [{'symbol': 'A'}]}}]}})
    assert p['holdings'][0]['weight'] is None and p['total_assets'] is None and p['yield'] is None     # inconnu reste inconnu


def test_assets_and_distribution_yield_are_read_without_inventing_zero():
    payload = {'quoteSummary': {'result': [{'fundProfile': {'family': 'A', 'feesExpensesInvestment': {'annualReportExpenseRatio': {'raw': 0.0015}}},
                                            'summaryDetail': {'totalAssets': {'raw': 1755074560}, 'yield': {'raw': 0.021}, 'currency': 'USD'},
                                            'topHoldings': {'holdings': [{'symbol': 'XOM', 'holdingName': 'Exxon', 'holdingPercent': {'raw': .2984}}]}}]}}
    p = parse_profile(payload)
    assert p['total_assets'] == 1755074560 and p['total_assets_currency'] == 'USD' and p['yield'] == 2.1 and p['expense_ratio'] == 0.15
    other = parse_profile({'quoteSummary': {'result': [{'fundProfile': {'family': 'B'}, 'defaultKeyStatistics': {'totalAssets': {'raw': 5e7}}}]}})
    assert other['total_assets'] == 5e7 and other['yield'] is None


def test_sector_weights_refer_to_equity_sleeve_not_all_assets():
    p = etf.exposure({'category': 'Energy'}, {'sectors': {'Énergie': 100}, 'stock_position': 40})
    assert p['label'] == 'Énergie (actions)' and p['sectors']['Énergie'] == 40
    assert not etf.exposure({}, {'sectors': {'Énergie': 100}})['sectors']
    assert etf.exposure({'category': 'Commodities'}, {})['label'] == 'Matières premières (hors actions)'
    assert not etf.profile_data({'sectors': {'A': 80, 'B': 80}})['sectors']


def cached_family():
    base = noise(20)
    twin = {k: v * 1.01 + .0002 for k, v in base.items()}
    return {1: {'returns': base, 'stale': False, 'meta': {'symbol': 'A', 'category': 'Energy'}, 'exposure': {'label': 'Énergie (actions)'}},
            2: {'returns': twin, 'stale': False, 'meta': {'symbol': 'B', 'category': 'Energy'}, 'exposure': {'label': 'Énergie (actions)'}},
            3: {'returns': {k: v * .98 for k, v in base.items()}, 'stale': False, 'meta': {'symbol': 'C', 'category': 'Commodities'}, 'exposure': {'label': 'Matières premières (hors actions)'}},
            4: {'returns': noise(21), 'stale': False, 'meta': {'symbol': 'D', 'category': 'Health Care'}, 'exposure': {'label': None}},
            5: {'returns': {}, 'stale': True, 'meta': {'symbol': 'E', 'category': 'Energy'}, 'exposure': {'label': None}}}


def test_families_group_look_alikes_and_leave_independent_etf_alone(monkeypatch):
    monkeypatch.setattr(etf, 'load', lambda *a: cached_family())
    c = etf.concentration(None, [1, 2, 3, 4, 5])
    assert c['sample'] == 5 and c['analysed'] == 4 and len(c['groups']) == 1
    g = c['groups'][0]
    assert g['id'] == 'A' and g['members'] == [1, 2, 3] and g['symbols'] == ['A', 'B', 'C'] and g['min_coefficient'] >= .9 and not g['unstable']
    assert 'Énergie (actions)' in g['label']
    assert c['unavailable_pairs'] == 4                                      # E est ancien : ses quatre paires sont « non comparables », jamais « sans lien »
    monkeypatch.setattr(etf, 'load', lambda *a: {i: v for i, v in cached_family().items() if i in (1, 2)})
    assert etf.concentration(None, [1, 2])['groups'] == []                  # deux ETF seulement : pas d'alerte de concentration (seuil : trois)


def test_holdings_overlap_is_partial_lower_bound_and_requires_known_weights():
    mk = lambda w: {'holdings': [{'symbol': s, 'name': s, 'weight': x} for s, x in w]}
    a = mk([('XOM', 30), ('CVX', 18), ('COP', 7), ('EOG', 4), ('SLB', 4), ('OXY', 3)])
    b = mk([('XOM', 29), ('CVX', 17), ('COP', 6), ('MPC', 5), ('PSX', 4), ('VLO', 3)])
    o = etf.holdings_overlap(a, b)
    assert o['shared_weight'] == 29 + 17 + 6 and [x['name'] for x in o['shared']] == ['XOM', 'CVX', 'COP']
    assert etf.holdings_overlap(a, mk([('XOM', None)] * 6)) is None          # poids inconnus : pas de chevauchement affiché
    assert etf.holdings_overlap(a, mk([('XOM', 30)])) is None                # moins de cinq lignes pondérées


def test_portfolio_value_weighted_families_and_unknown(monkeypatch):
    cache = cached_family()
    for i in (1, 2):
        cache[i]['exposure']['sectors'] = {'Énergie': 100}
        cache[i]['profile_usable'] = True
    monkeypatch.setattr(etf, 'load', lambda *a: cache)
    p = [{'listing_id': 1, 'kind': 'etf', 'symbol': 'A', 'value': 100}, {'listing_id': 2, 'kind': 'etf', 'symbol': 'B', 'value': 300}, {'listing_id': 4, 'kind': 'etf', 'symbol': 'D', 'value': 100}, {'kind': 'equity', 'value': 100}]
    r = etf.portfolio(None, p)
    assert r['total_priced_eur'] == 600 and r['known_eur'] == 400 and r['unknown_eur'] == 200 and round(r['unknown_percent'], 1) == 33.3
    assert r['families'][0]['symbols'] == ['A', 'B'] and r['families'][0]['value_eur'] == 400 and round(r['families'][0]['percent'], 1) == 66.7
    assert [x['symbol'] for x in r['etf_without_composition']] == ['D']
    levels = {s['key']: s['level'] for s in r['signals']}
    assert levels['family'] == 'bad' and levels['unknown_share'] == 'unknown'          # > 50 % dans une famille : rouge ; l'inconnu reste gris
    p.append({'value': None})
    r = etf.portfolio(None, p)
    assert r['unknown_percent'] is None and r['sectors'][0]['percent'] is None and r['families'][0]['percent'] is None
    cache[1]['stale'] = True
    r = etf.portfolio(None, p)
    assert r['families'] == [] and r['unavailable_pairs'] >= 1


def test_signals_use_existing_criteria_and_unknown_stays_grey():
    assert signals.regularity(.88)['level'] == 'ok' and signals.regularity(.6)['level'] == 'warn' and signals.regularity(.3)['level'] == 'bad' and signals.regularity(None)['level'] == 'unknown'
    assert signals.risk(1.2, 8)['level'] == 'ok' and signals.risk(2.4, 10)['level'] == 'warn' and signals.risk(3.5, 10)['level'] == 'bad' and signals.risk(None, None)['level'] == 'unknown'
    cfg = {'liquidity_etf': {'min_eur': 250_000.0}, 'liquidity_equity': {'min_eur': 1_000_000.0}}
    assert [signals.liquidity(v, 'etf', cfg)['level'] for v in (1_200_000, 600_000, 100_000, None)] == ['ok', 'warn', 'bad', 'unknown']
    assert signals.liquidity(2_000_000, 'equity', cfg)['level'] == 'warn'            # même volume : suffisant pour une action seulement au-delà de 4 M€
    assert signals.similarity(None)['level'] == 'unknown'
    assert signals.similarity({'similar': []})['level'] == 'unknown'                  # aucun jumeau détecté : jamais un vert
    assert signals.similarity({'similar': [{'symbol': 'X', 'coefficient': .99}]})['level'] == 'warn'
    assert signals.composition({'top10_weight': None})['level'] == 'unknown' and signals.composition({'top10_weight': 82})['level'] == 'bad' and signals.composition({'top10_weight': 20})['level'] == 'ok'
    assert signals.specific_risks('X', 'Equities')['level'] == 'unknown'             # « rien détecté » n'est pas « sans risque »
    assert 'ne signifie pas' in signals.specific_risks('X', 'Equities')['text']
    assert signals.specific_risks('X 3x', 'Equities', True)['level'] == 'bad' and signals.specific_risks('Oil Fund', 'Commodities')['level'] == 'warn'
    assert signals.family_share(None)['level'] == 'unknown' and signals.family_share(20)['level'] == 'ok' and signals.family_share(40)['level'] == 'warn' and signals.family_share(60)['level'] == 'bad'
    assert signals.data_quality('ok', [], False)['level'] == 'ok' and signals.data_quality('ok', [{'kind': 'unit'}], False)['level'] == 'warn'
    assert signals.data_quality('break', [], False)['level'] == 'bad' and signals.data_quality('insufficient', [], False)['level'] == 'unknown'
    for s in signals.row_signals({'r2': .9, 'volatility': 1, 'drawdown': 5, 'price_eur': 20, 'volume': 100000}, 'etf', 63, cfg):
        assert s['label'] and s['text']                                              # jamais une couleur sans mot


def test_reading_facts_describe_the_window_without_interpolation():
    closes = [100 + i + (5 if i == 7 else 0) for i in range(30)]
    f = signals.history_facts(closes, 20)
    assert f['up_days_percent'] == 100 or f['up_days_percent'] > 80
    assert 'best_day_share' in f and '% de séances en hausse' in signals.regularity_extra(f)
    assert signals.history_facts([100, 101], 20) == {}
