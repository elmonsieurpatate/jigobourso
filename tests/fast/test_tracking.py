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


def test_summarize_edge_against_benchmark():
    s = summarize([('d1', 2.0), ('d1', -1.0), ('d2', 3.0)], {'d1': 0.5, 'd2': 1.0})
    assert s['n'] == 3 and abs(s['mean'] - 4 / 3) < 1e-9 and s['median'] == 2.0
    assert abs(s['win_pct'] - 200 / 3) < 1e-9
    assert abs(s['edge'] - ((1.5 - 1.5 + 2.0) / 3)) < 1e-9 and abs(s['beat_pct'] - 200 / 3) < 1e-9
    assert summarize([], {}) is None
