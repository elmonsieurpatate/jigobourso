import math

from engine.analytics.tracking import forward_returns, summarize


def bars(closes, start=1):
    return [(f'2026-10-{start + i:02d}', c, None) for i, c in enumerate(closes)]


def test_forward_returns_from_base_close():
    r = forward_returns(bars([100, 110, 121, 100, 90, 99]), '2026-10-01', (1, 3, 5))
    assert abs(r[1] - 10) < 1e-9 and abs(r[3] - 0) < 1e-9 and abs(r[5] + 1) < 1e-9


def test_horizon_not_yet_available_is_absent():
    r = forward_returns(bars([100, 101, 102]), '2026-10-01', (1, 3, 5))
    assert set(r) == {1}


def test_base_is_last_close_on_or_before_the_date():
    r = forward_returns(bars([100, 110, 120, 130]), '2026-10-02', (1,))
    assert abs(r[1] - (120 / 110 - 1) * 100) < 1e-9


def test_stale_series_is_not_evaluated():
    assert forward_returns(bars([100, 101, 102]), '2026-10-20', (1,)) == {}


def test_unexplained_jump_invalidates_the_horizon():
    r = forward_returns(bars([100, 101, 50, 51]), '2026-10-01', (1, 2, 3))
    assert set(r) == {1}      # le saut ×0,5 entre la 2e et la 3e clôture invalide les horizons 2 et 3


def test_forward_returns_uses_market_sessions_across_holiday_and_missing_close():
    # Thanksgiving (26 Nov) ferme New York : le lendemain est la séance +1.
    data = [('2026-11-25', 100, None), ('2026-11-30', 111, None),
            ('2026-12-01', 112, None), ('2026-12-02', 113, None)]
    r = forward_returns(data, '2026-11-25', (1, 2, 3), mic='XNYS')
    assert 1 not in r                         # clôture du 27 absente : pas de report vers le 30
    assert math.isclose(r[2], 11.0)            # séance +2, calculée à ses dates réelles
    assert math.isclose(r[3], 12.0)


def test_summarize_edge_against_benchmark():
    s = summarize([('d1', 2.0), ('d1', -1.0), ('d2', 3.0)], {'d1': 0.5, 'd2': 1.0})
    assert s['n'] == 3 and abs(s['mean'] - 4 / 3) < 1e-9 and s['median'] == 2.0
    assert abs(s['win_pct'] - 200 / 3) < 1e-9
    assert abs(s['edge'] - ((1.5 - 1.5 + 2.0) / 3)) < 1e-9 and abs(s['beat_pct'] - 200 / 3) < 1e-9
    assert summarize([], {}) is None


def test_edge_compares_mean_with_mean_when_the_universe_mean_is_known():
    # rendements asymétriques : la moyenne du groupe dépasse sa médiane sans aucun talent de sélection
    returns = [('2026-10-01', 10.0), ('2026-10-02', 0.0), ('2026-10-03', 0.0)]
    medians = {'2026-10-01': 0.0, '2026-10-02': 0.0, '2026-10-03': 0.0}
    means = {'2026-10-01': 10.0, '2026-10-02': 0.0, '2026-10-03': 0.0}
    old = summarize(returns, medians)
    new = summarize(returns, medians, means)
    assert old['edge'] > 3 and old['edge_basis'] == 'median'          # l'ancien calcul flatte
    assert new['edge'] == 0 and new['edge_basis'] == 'mean' and new['edge_median'] == 0
    assert new['days'] == 3
