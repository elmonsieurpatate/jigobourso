"""Deux fenêtres de cours indépendantes de la date d'achat ; aucun accès réseau/DB."""

import datetime as dt
import math
import pytest
from engine.analytics.portfolio import dynamics as D

NOW = dt.datetime(2026, 11, 18, 23, tzinfo=dt.timezone.utc)
DAYS = [(dt.date(2017, 1, 1) + dt.timedelta(days=i)).isoformat() for i in range((NOW.date() - dt.date(2017, 1, 1)).days + 1) if (dt.date(2017, 1, 1) + dt.timedelta(days=i)).weekday() < 5]


def calc(bars, splits=(), days=DAYS):
    return D.measure(bars, splits, 'XNYS', NOW, days)


def series(rate=0.001):
    return [(day, 10 * (1 + rate) ** i, None) for i, day in enumerate(DAYS)]


@pytest.mark.parametrize('rate', [0.001, -0.001, 0])
def test_all_eleven_windows_are_adjacent_and_use_compounded_returns(rate):
    result = calc(series(rate))
    assert len(result['cells']) == 11
    obs = dict((d, c) for d, c, _ in series(rate))
    for c in result['cells'].values():
        assert c['return'] == pytest.approx(100 * (obs[c['end']] / obs[c['start']] - 1))
        assert c['previous'] == pytest.approx(100 * (obs[c['start']] / obs[c['previous_start']] - 1))
        assert c['previous_start'] < c['start'] < c['end']
        assert c['delta'] == pytest.approx(c['return'] - c['previous'])
        if rate == 0:
            assert c['heat'] == 'neutral' and c['arrow'] == 'flat'


@pytest.mark.parametrize('prices,sign,arrow', [([100, 106.3, 110.7646], 1, 'down'), ([100, 98, 97.02], -1, 'up')])
def test_price_direction_is_independent_of_dynamics(prices, sign, arrow):
    c = calc([(d, p, None) for d, p in zip(DAYS[-3:], prices)])['cells']['1d']
    assert math.copysign(1, c['return']) == sign
    assert c['arrow'] == arrow
    assert c['delta'] == pytest.approx(-2.1 if sign == 1 else 1)


def test_insufficient_comparison_keeps_current_performance():
    c = calc(series()[-700:])['cells']['2y']
    assert c['return'] is not None and c['delta'] is None
    assert c['previous_reason'] == 'history'
    assert calc(series()[-20:])['cells']['1m']['return'] is None


def test_missing_inside_window_does_not_shift_the_window():
    b = series()
    del b[-3]
    c = calc(b)['cells']['1w']
    assert c['reason'] == 'missing' and c['return'] is None
    assert c['end'] == DAYS[-1] and c['start'] == DAYS[-6]


def test_short_collection_lag_ends_windows_at_last_known_close():
    c = calc(series()[:-2])['cells']['1d']
    assert c['reason'] is None and c['end'] == DAYS[-3]


def test_long_collection_lag_is_not_silently_replaced_by_older_close():
    c = calc(series()[: -(D.MAX_LAG + 1)])['cells']['1d']
    assert c['reason'] == 'missing' and c['return'] is None


def test_month_boundaries_are_calendar_months_and_clamped_independently():
    assert D.shift_months(dt.date(2024, 3, 31), 1) == dt.date(2024, 2, 29)
    assert D.shift_months(dt.date(2024, 3, 31), 2) == dt.date(2024, 1, 31)
    c = calc(series())['cells']['1m']
    assert c['start'] == '2026-10-16'  # 18 octobre : dimanche, séance antérieure
    assert c['previous_start'] == '2026-09-18'


def test_known_split_uses_existing_adjustment_without_economic_loss():
    days = DAYS[-3:]
    c = calc([(days[0], 100, None), (days[1], 50, None), (days[2], 50, None)], [(days[1], 2)])['cells']['1d']
    assert c['return'] == c['previous'] == c['delta'] == 0


def test_unknown_split_invalidates_only_crossing_window():
    days = DAYS[-3:]
    c = calc([(d, p, None) for d, p in zip(days, [100, 50, 51])], [(days[1], None)])['cells']['1d']
    assert c['return'] == pytest.approx(2)
    assert c['previous_reason'] == 'break' and c['delta'] is None


def test_complete_adjusted_series_is_preferred_and_never_mixed():
    days = DAYS[-3:]
    r = calc([(d, p, 90) for d, p in zip(days, [100, 90, 90])])
    assert r['basis'] == 'adjusted' and r['cells']['1d']['previous'] == 0
    r = calc([(d, p, a) for d, p, a in zip(days, [100, 90, 90], [90, None, 90])])
    assert r['basis'] == 'raw' and r['cells']['1d']['previous'] == pytest.approx(-10)


def test_current_session_excluded_and_prices_scale_independent():
    b = series()
    # now before US close, use a calendar ending the previous session.
    now = NOW.replace(hour=15)
    short = DAYS[:-1]
    r = D.measure(b, [], 'XNYS', now, short)
    assert r['as_of'] == short[-1]
    a = calc(b)['cells']
    foreign = calc([(d, p * 100, a) for d, p, a in b])['cells']
    for k in a:
        assert foreign[k]['return'] == pytest.approx(a[k]['return'])


def test_heat_thresholds_scale_by_horizon_and_arrow_neutral_keeps_numbers():
    assert D.heat(2, 1) == 'gain'
    assert D.heat(2, 252) == 'gain-soft'
    assert {D.heat(v, 1) for v in [4, 2, 0.5, 0, -0.5, -2, -4]} == {'gain-strong', 'gain', 'gain-soft', 'neutral', 'loss-soft', 'loss', 'loss-strong'}
    c = calc([(d, p, None) for d, p in zip(DAYS[-3:], [100, 100.01, 100.03])])['cells']['1d']
    assert c['arrow'] == 'flat' and c['delta'] != 0


def test_unknown_calendar_explicitly_unavailable():
    r = D.measure(series(), [], 'UNKNOWN', NOW)
    assert all(c['reason'] == 'calendar' for c in r['cells'].values())
