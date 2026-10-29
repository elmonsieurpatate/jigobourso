import math

import pytest

from engine.analytics import strategy
from engine.analytics.measures import dated_window_metrics, window_metrics
from engine.analytics.series import analyze_series
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
    assert got['slope'] == pytest.approx(100 * math.expm1(.01))
    assert got['r2'] == pytest.approx(1.0)
    assert got['perf'] == pytest.approx(100 * math.expm1(.05))
    assert got['volatility'] is None and got['drawdown'] is None and got['er'] is None


def test_isolated_hole_can_still_pass_trend_but_not_fabricated_risk_metrics():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 * math.exp(.005 * i) for i, d in enumerate(dates) if i != 9}
    metrics, info = dated_window_metrics(dates, prices)
    metrics.update(info)
    regular = strategy.preset('regular')
    regular['periods'] = [p for p in regular['periods'] if p['id'] == 'month']
    r = strategy.judge(regular, {21: metrics}, {}, {})
    assert r['status'] == 'retained'
    assert any(x['criterion'] == 'coverage' and x['result'] == 'warning' for x in r['reasons'])

    low_vol = strategy.preset('low_volatility')
    low_vol['periods'] = [p for p in low_vol['periods'] if p['id'] == 'month']
    r = strategy.judge(low_vol, {21: metrics}, {}, {})
    assert r['status'] == 'unknown'
    assert any(x['criterion'] == 'max_volatility' and x['result'] == 'missing' for x in r['reasons'])


def test_multiple_missing_sessions_below_sample_floor_are_not_evaluable():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 + i for i, d in enumerate(dates) if i not in (8, 9, 10, 11, 12)}
    got, info = dated_window_metrics(dates, prices)
    assert info['coverage'] < .80
    assert got['slope'] is None and got['r2'] is None and got['perf'] is None


def test_missing_boundary_still_allows_supported_regression_but_not_endpoint_return():
    dates = [f'd{i:03d}' for i in range(22)]
    prices = {d: 100 * math.exp(.005 * i) for i, d in enumerate(dates) if i != 0}
    got, info = dated_window_metrics(dates, prices)
    assert info['coverage'] >= .80
    assert got['slope'] == pytest.approx(100 * math.expm1(.005))
    assert got['r2'] == pytest.approx(1.0)
    assert got['perf'] is None


def test_long_gap_never_becomes_one_observed_daily_move():
    dates = [f'd{i:03d}' for i in range(64)]
    # Reference dimensions of WHCA.AS: 52 observed closes in a 64-close window.
    prices = {d: math.exp(i * .002 + (.14 if i % 2 else -.14)) for i, d in enumerate(dates)
              if not 20 <= i < 32}
    got, info = dated_window_metrics(dates, prices)
    assert info['observations'] == 52 and info['expected_closes'] == 64
    assert info['coverage'] == pytest.approx(52 / 64)
    assert got['r2'] is not None and got['r2'] < strategy.R2_LEVELS['flexible']
    cfg = strategy.preset('regular')
    cfg['periods'] = [p for p in cfg['periods'] if p['id'] == 'quarter']
    # Exercise the actual existing R² gate: corrected time-indexed R² fails it.
    verdict = strategy.judge(cfg, {63: got}, {}, {})
    assert verdict['status'] == 'rejected'
    assert got['volatility'] is None and got['drawdown'] is None and got['er'] is None


def test_analyze_series_uses_expected_sessions_and_does_not_fill_missing_prices():
    dates = [f'd{i:03d}' for i in range(6)]
    bars = [(d, 100 * math.exp(.01 * i), None) for i, d in enumerate(dates) if i != 2]
    _, closes, _, _, measures, missing, _ = analyze_series(bars, [5], session_windows={5: dates})
    assert len(closes) == 5
    assert measures[5]['coverage'] == pytest.approx(5 / 6)
    assert measures[5]['slope'] == pytest.approx(100 * math.expm1(.01))
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
