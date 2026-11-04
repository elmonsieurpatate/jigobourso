"""Reproductions P0 de l'audit V4, sans réseau ni base."""
import datetime
import math

import pytest

from engine.analytics import explorer_config as C, strategy as S
from engine.analytics.explorer_metrics import path_metrics
from engine.analytics.measures import dated_technical_state, technical_state
from engine.analytics.series import momentum_6_1, momentum_12_1


def dates(count):
    day = datetime.date(2025, 1, 2)
    result = []
    while len(result) < count:
        if day.weekday() < 5:
            result.append(day.isoformat())
        day += datetime.timedelta(days=1)
    return result


@pytest.mark.parametrize('window,measure', [(126, momentum_6_1), (252, momentum_12_1)])
@pytest.mark.parametrize('missing', ['all_but_three', 'endpoints_only', 'interior', 'last_month'])
def test_momentum_requires_every_expected_close(window, measure, missing):
    ds = dates(window + 1)
    keep = set(range(window + 1))
    if missing == 'all_but_three':
        keep = {0, window - 21, window}
    elif missing == 'endpoints_only':
        keep = {0, window - 21}
    else:
        keep.remove(7 if missing == 'interior' else window - 3)
    observed = [(d, 100 * math.exp(.001 * i)) for i, d in enumerate(ds) if i in keep]
    assert measure([d for d, _ in observed], [p for _, p in observed], [], ds) is None
    full = [100 * math.exp(.001 * i) for i in range(window + 1)]
    assert measure(ds, full, [], ds) == pytest.approx(100 * math.expm1(.001 * (window - 21)))


@pytest.mark.parametrize('name', ['momentum', 'momentum12'])
@pytest.mark.parametrize('modern', [False, True])
def test_sparse_momentum_can_never_be_retained_or_scored(name, modern):
    window = 126 if name == 'momentum' else 252
    ds = dates(window + 1)
    config = S.preset(name)
    if modern:
        config = C.editable(config)
    bars = [(ds[0], 100., None), (ds[window - 21], 110., None), (ds[-1], 111., None)]
    verdict = S.evaluate_one(config, dict(bars=bars, session_windows={window: ds}, expected_last_date=ds[-1]))
    verdict.update(key=1, symbol='SPARSE', group='equity')
    S.rank(config, [verdict])
    assert verdict['status'] == 'unknown'
    assert verdict['score'] is None and verdict['rank'] is None
    assert any(r['result'] == 'missing' for r in verdict['reasons'])


@pytest.mark.parametrize('modern', [False, True])
def test_old_stored_momentum_is_invalidated_by_incomplete_coverage(modern):
    config = S.preset('momentum')
    if modern:
        config = C.editable(config)
    metric = dict(sessions=126, coverage=3 / 127, observations=3,
                  expected_closes=127, missing_sessions=124)
    # Stored values from the former calculator must not bypass the new rule.
    result = S.judge(config, {126: metric}, {}, {}, momentum={'6m': 10., '12m': None} if modern else 10.)
    result.update(key=1, symbol='CACHED', group='equity')
    S.rank(config, [result])
    assert result['status'] == 'unknown' and result['score'] is None


@pytest.mark.parametrize('count', [0, 1, 19, 20, 49, 50, 55, 199, 200, 204, 205, 206])
def test_moving_averages_require_their_actual_number_of_closes(count):
    ds = dates(count)
    observations = dict.fromkeys(ds, 100.)
    dated = dated_technical_state(ds, observations)
    ordinary = technical_state([100.] * count)
    for result in (dated, ordinary):
        for key, needed in [('ma20', 20), ('ma50', 50), ('ma50_prev', 55),
                            ('ma200', 200), ('ma200_prev', 205)]:
            assert result.get(key) == (100. if count >= needed else None), (count, key)


@pytest.mark.parametrize('bad', [None, 0., -1., float('nan'), float('inf')])
def test_invalid_or_missing_close_never_becomes_a_moving_average(bad):
    ds = dates(205)
    observations = dict.fromkeys(ds, 100.)
    observations[ds[-50]] = bad
    result = dated_technical_state(ds, observations)
    assert result['ma50'] is None and result['ma200'] is None
    assert result['ma50_prev'] is None and result['ma200_prev'] is None


@pytest.mark.parametrize('bad', [None, -1., float('nan'), float('inf')])
def test_historical_volume_never_uses_bad_values_or_a_quoted_average(bad):
    metric = path_metrics([100, 101, 102], [10, bad], [1000, None])
    assert metric['avg_volume'] is None and metric['turnover_eur'] is None
    assert metric['volume_source'] == 'daily_prices.volume'
    assert metric['volume_observations'] == 1 and metric['volume_expected'] == 2
    assert metric['volume_coverage'] == .5


def test_zero_historical_volume_is_known_and_distinct_from_missing():
    zero = path_metrics([100, 101, 102], [0, 0], [0, 0])
    absent = path_metrics([100, 101, 102])
    assert zero['avg_volume'] == 0 and zero['volume_coverage'] == 1
    assert zero['turnover_eur'] == 0
    assert absent['avg_volume'] is None and absent['volume_coverage'] == 0


def test_momentum_guard_does_not_mutate_the_stored_input():
    original = {'6m': 10., '12m': 20.}
    metric = dict(sessions=126, coverage=3 / 127, observations=3,
                  expected_closes=127, missing_sessions=124)
    S.judge(C.editable(S.preset('momentum')), {126: metric}, {}, {}, momentum=original)
    assert original == {'6m': 10., '12m': 20.}
