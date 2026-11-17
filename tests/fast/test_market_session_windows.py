import math

import pytest

from engine.analytics.explorer import strategy
from engine.analytics.series.measures import dated_window_metrics, window_metrics
from engine.analytics.series.series import analyze_series
from engine.market.calendar import session_dates


def test_complete_calendar_window_preserves_existing_metrics_exactly():
    dates = [f'd{i:03d}' for i in range(22)]
    closes = [100 * math.exp(0.008 * i + 0.001 * math.sin(i)) for i in range(22)]
    got, info = dated_window_metrics(dates, dict(zip(dates, closes)))
    expected = window_metrics(closes)
    for key, value in expected.items():
        assert got[key] == pytest.approx(value, abs=1e-12)
    assert info['coverage'] == 1.0
    assert got['coverage'] == 1.0


def test_one_missing_weekly_close_does_not_compress_time_or_fake_path_indicators():
    dates = [f'd{i:03d}' for i in range(6)]
    prices = {d: 100 * math.exp(0.01 * i) for i, d in enumerate(dates) if i != 2}
    got, info = dated_window_metrics(dates, prices)
    assert info['observations'] == 5 and info['expected_closes'] == 6
    assert info['coverage'] == pytest.approx(5 / 6)
    assert got['slope'] == pytest.approx(100 * math.expm1(0.01))
    assert got['r2'] == pytest.approx(1.0)
    assert got['perf'] == pytest.approx(100 * math.expm1(0.05))
    # Règle de tolérance commune : les mesures de chemin portent sur les clôtures observées et leur rang réel (aucun cours inventé)
    assert got['volatility'] == pytest.approx(0.0, abs=1e-9) and got['drawdown'] == 0.0 and got['er'] == pytest.approx(1.0)


def test_isolated_hole_is_tolerated_and_risk_metrics_use_the_observed_closes():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 * math.exp(0.005 * i) for i, d in enumerate(dates) if i != 9}
    metrics, info = dated_window_metrics(dates, prices)
    metrics.update(info)
    regular = strategy.preset('regular')
    regular['periods'] = [p for p in regular['periods'] if p['id'] == 'month']
    r = strategy.judge(regular, {21: metrics}, {}, {})
    assert r['status'] == 'retained'
    assert any(x['criterion'] == 'coverage' and x['result'] == 'warning' for x in r['reasons'])

    assert metrics['volatility'] == pytest.approx(0.0, abs=1e-9) and metrics['drawdown'] == 0.0  # une séance manquante ne rend plus les mesures de risque indisponibles
    low_vol = strategy.preset('low_volatility')
    low_vol['periods'] = [p for p in low_vol['periods'] if p['id'] == 'month']
    r = strategy.judge(low_vol, {21: metrics}, {}, {})
    assert not any(x['criterion'] == 'max_volatility' and x['result'] == 'missing' for x in r['reasons'])


def test_multiple_missing_sessions_below_sample_floor_are_not_evaluable():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 + i for i, d in enumerate(dates) if i not in (8, 9, 10, 11, 12)}
    got, info = dated_window_metrics(dates, prices)
    assert info['coverage'] < 0.80
    assert got['slope'] is None and got['r2'] is None and got['perf'] is None


def test_missing_boundary_is_tolerated_and_the_return_uses_the_real_observed_endpoints():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 * math.exp(0.005 * i) for i, d in enumerate(dates) if i != 0}
    got, info = dated_window_metrics(dates, prices)
    assert info['coverage'] >= 0.80 and info['status'] == 'ok'
    assert got['slope'] == pytest.approx(100 * math.expm1(0.005))
    assert got['r2'] == pytest.approx(1.0)
    assert got['perf'] == pytest.approx(100 * math.expm1(0.005 * 20))  # de la première à la dernière clôture observées, sur leur durée réelle (20 séances)


def test_a_gap_inside_the_tolerance_never_becomes_one_ordinary_daily_move():
    dates = [f'd{i:03d}' for i in range(64)]
    prices = {d: math.exp(i * 0.002) for i, d in enumerate(dates) if not 20 <= i < 28}  # 8 séances sans cotation : tolérées (MAX_GAP = 10)
    got, info = dated_window_metrics(dates, prices)
    assert info['status'] == 'ok' and info['observations'] == 56 and info['max_gap'] == 8
    # hausse constante de 0,2 % par séance : l'intervalle de 9 séances compte pour 9 séances, la volatilité reste nulle (et non 8 séances de rendement en une seule)
    assert got['volatility'] == pytest.approx(0.0, abs=1e-9) and got['slope'] == pytest.approx(100 * math.expm1(0.002))


def test_a_long_interruption_is_flagged_and_excluded_instead_of_measured():
    dates = [f'd{i:03d}' for i in range(64)]
    # Dimensions de référence de WHCA.AS : 52 clôtures observées sur 64, dont 12 séances d'affilée sans cotation (interruption > MAX_GAP)
    prices = {d: math.exp(i * 0.002 + (0.14 if i % 2 else -0.14)) for i, d in enumerate(dates) if not 20 <= i < 32}
    got, info = dated_window_metrics(dates, prices)
    assert info['observations'] == 52 and info['expected_closes'] == 64 and info['coverage'] == pytest.approx(52 / 64)
    assert info['status'] == 'gap' and info['max_gap'] == 12
    assert all(got[k] is None for k in ('slope', 'r2', 'perf', 'volatility', 'drawdown', 'er'))


def test_a_young_title_is_reported_as_too_short_history_not_as_a_gap():
    dates = [f'd{i:03d}' for i in range(64)]
    prices = {d: math.exp(i * 0.002) for i, d in enumerate(dates) if i >= 30}
    got, info = dated_window_metrics(dates, prices)
    assert info['status'] == 'history' and got['slope'] is None


def test_analyze_series_uses_expected_sessions_and_does_not_fill_missing_prices():
    dates = [f'd{i:03d}' for i in range(6)]
    bars = [(d, 100 * math.exp(0.01 * i), None) for i, d in enumerate(dates) if i != 2]
    _, closes, _, _, measures, missing, _ = analyze_series(bars, [5], session_windows={5: dates})
    assert len(closes) == 5
    assert measures[5]['coverage'] == pytest.approx(5 / 6)
    assert measures[5]['slope'] == pytest.approx(100 * math.expm1(0.01))
    assert missing == {}


def test_calendar_observes_weekends_holidays_and_market_specific_holidays():
    # 7 September is Labor Day in the US, but an ordinary Monday in London.
    assert session_dates('XNYS', '2026-09-08', 2) == ['2026-09-04', '2026-09-08']
    assert session_dates('XLON', '2026-09-08', 2) == ['2026-09-07', '2026-09-08']
    # Thanksgiving is a US closure, while London remains open.
    assert session_dates('XNYS', '2026-11-27', 3) == ['2026-11-24', '2026-11-25', '2026-11-27']
    assert session_dates('XLON', '2026-11-27', 3) == ['2026-11-25', '2026-11-26', '2026-11-27']
    assert session_dates('XNYS', '2026-11-29', 2) == ['2026-11-25', '2026-11-27']


def test_unknown_or_unsupported_calendar_fails_closed():
    assert session_dates('UNKNOWN', '2026-10-29', 22) is None
    # This library version has no current Singapore holiday schedule; don't
    # invent weekdays for it or silently revert to observation-count windows.
    assert session_dates('XSES', '2026-10-29', 22) is None
