import math
from engine.analytics.measures import window_metrics, technical_state
from engine.analytics.series import usable_closes, find_breaks, clean_window


def geometric(rate, n, start=100.0):
    return [start * (1 + rate) ** i for i in range(n + 1)]


def test_perfect_exponential_growth():
    m = window_metrics(geometric(0.01, 21))
    assert math.isclose(m['slope'], 1.0, rel_tol=1e-9)
    assert math.isclose(m['r2'], 1.0)
    assert math.isclose(m['er'], 1.0)
    assert m['drawdown'] == 0 and m['volatility'] < 1e-9


def test_decline_has_negative_slope_and_er():
    m = window_metrics(geometric(-0.01, 21))
    assert m['slope'] < 0 and m['er'] < 0 and m['perf'] < 0


def test_round_trip_is_not_efficient():
    m = window_metrics([100, 110, 100, 110, 100])
    assert abs(m['er']) < 1e-9 and m['drawdown'] > 9


def test_log_symmetry_up_down_cancels():
    m = window_metrics([100, 110, 100])
    assert math.isclose(m['perf'], 0, abs_tol=1e-9)


def test_short_windows():
    one = window_metrics([100, 103])
    assert math.isclose(one['perf'], 3) and one['r2'] is None and one['er'] is None
    two = window_metrics([100, 101, 103])
    assert two['r2'] is not None and two['volatility'] is None


def test_invalid_inputs():
    assert window_metrics([100]) is None
    assert window_metrics([100, 0, 101]) is None
    assert window_metrics([100, float('nan')]) is None


def test_price_scale_invariance():
    a = window_metrics([5, 5.2, 5.1, 5.4, 5.6])
    b = window_metrics([500, 520, 510, 540, 560])
    for k in ('slope', 'r2', 'er', 'volatility', 'drawdown', 'perf'):
        assert math.isclose(a[k], b[k], rel_tol=1e-9)


def test_technical_state():
    closes = [float(i) for i in range(1, 61)]
    t = technical_state(closes)
    assert t['ma20'] == sum(range(41, 61)) / 20
    assert t['ma50'] > t['ma50_prev']
    assert math.isclose(t['daily_change'], 100 * (60 / 59 - 1))


def test_adjusted_used_only_if_complete():
    bars = [('d1', 10, 5), ('d2', 11, 5.5), ('d3', 12, None)]
    assert usable_closes(bars)[2] == 'raw'
    bars[2] = ('d3', 12, 6)
    assert usable_closes(bars)[2] == 'adjusted'


def test_break_detection_and_split_explanation():
    dates = [f'd{i}' for i in range(6)]
    closes = [100, 101, 50, 50.5, 51, 52]
    assert find_breaks(dates, closes, 'raw') == [2]
    assert find_breaks(dates, closes, 'raw', split_dates=['d2']) == []
    assert find_breaks(dates, closes, 'adjusted', split_dates=['d2']) == [2]


def test_window_crossing_break_is_refused():
    closes = [100, 101, 50, 50.5, 51, 52]
    w, why = clean_window(closes, 5, [2])
    assert w is None and why == 'break'
    w, why = clean_window(closes, 3, [2])
    assert w is not None
    assert clean_window(closes, 9, [])[1] == 'history'
