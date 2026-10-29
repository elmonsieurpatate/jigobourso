import math

import pytest
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
    assert find_breaks(dates, closes, 'raw', split_dates=['d2']) == [2]  # known split without adjustment is not a real return
    assert find_breaks(dates, closes, 'adjusted', split_dates=['d2']) == [2]


def test_window_crossing_break_is_refused():
    closes = [100, 101, 50, 50.5, 51, 52]
    w, why = clean_window(closes, 5, [2])
    assert w is None and why == 'break'
    w, why = clean_window(closes, 3, [2])
    assert w is not None
    assert clean_window(closes, 9, [])[1] == 'history'


# ── Corrections de données identifiables (changements d'unité, cours aberrants isolés) ──
from engine.analytics.series import data_corrections, drop_isolated_spikes, normalize_units, prepare_series  # noqa: E402


def _dates(n, start=(2026, 1, 5)):
    import datetime as dt
    d, out = dt.date(*start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def test_pence_to_pounds_switch_is_rescaled_and_keeps_the_real_move():
    dates = _dates(6)
    closes = [100.0, 101.0, 102.0, 1.03, 1.04, 1.05]               # livres à partir du 4e jour (÷100 ≈ 0,0101 -> unité)
    fixed, notes = normalize_units(dates, closes)
    assert notes == [{'kind': 'unit', 'date': dates[3], 'factor': 0.01}]
    assert fixed == pytest.approx([1.0, 1.01, 1.02, 1.03, 1.04, 1.05])      # la série reste dans l'unité de la dernière séance, rendements inchangés


def test_alternating_unit_flips_are_all_resolved_toward_the_latest_unit():
    dates = _dates(8)
    closes = [10.0, 10.1, 0.101, 0.102, 10.3, 10.4, 0.104, 0.105]   # pence, pence, livres, livres, pence, pence, livres, livres
    fixed, notes = normalize_units(dates, closes)
    assert len(notes) == 3
    assert fixed == pytest.approx([0.10, 0.101, 0.101, 0.102, 0.103, 0.104, 0.104, 0.105])


def test_a_real_big_move_or_a_declared_split_date_is_not_rescaled():
    dates = _dates(4)
    assert normalize_units(dates, [10.0, 10.5, 17.0, 17.5])[1] == []                 # +62 % : rupture, pas une unité
    assert normalize_units(dates, [1000.0, 1000.0, 10.0, 10.0], protected=[dates[2]])[1] == []     # split 100 pour 1 déclaré : traité comme tel


def test_isolated_bad_tick_is_dropped_but_a_persistent_move_is_not():
    dates = _dates(6)
    d, c, notes = drop_isolated_spikes(dates, [31.25, 31.0, 1.25, 22.7, 28.0, 27.0])        # cas réel GIBO : 1,25 entre 31 et 22,7
    assert len(c) == 5 and dates[2] not in d and notes[0]['date'] == dates[2]
    d, c, notes = drop_isolated_spikes(dates, [10.0, 10.0, 2.0, 2.1, 2.0, 2.2])              # chute durable de 80 % : vrai mouvement, conservé
    assert len(c) == 6 and notes == []
    d, c, notes = drop_isolated_spikes(dates, [10.0, 10.0, 5.0, 10.0, 10.0, 10.0])            # creux d'un jour de seulement 50 % : conservé (seuil ×4)
    assert len(c) == 6


def test_corrections_are_reported_and_the_series_becomes_evaluable():
    dates = _dates(30)
    closes = [100.0 + i for i in range(14)] + [1.14, 1.15] + [1.16 + 0.01 * i for i in range(14)]    # bascule pence -> livres à la 15e séance
    bars = [(d, c, None) for d, c in zip(dates, closes)]
    assert [n['kind'] for n in data_corrections(bars)] == ['unit']
    _, fixed, _, breaks = prepare_series(bars)
    assert breaks == [] and fixed[0] == pytest.approx(1.0)
