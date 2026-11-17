"""Formules du Score 2 confinées aux séances de chaque période."""

import pytest

from engine.analytics.scoring.score_inputs import period_path_inputs, recent_exclusion, recovery_input, window_inputs
from engine.analytics.scoring.scores import period_momentum_note, saturation
from engine.analytics.series.liquidity import period_turnover
from engine.analytics.explorer import explorer_config as C
from engine.analytics.scoring import scores as SC
from engine.analytics.scoring import scores_profiles


@pytest.mark.parametrize('n,excluded', [(3, 1), (21, 2), (63, 5), (126, 11), (252, 21), (756, 21), (1260, 21)])
def test_momentum_uses_only_its_period_and_scales_with_measured_duration(n, excluded):
    assert recent_exclusion(n) == excluded
    measured = n - excluded
    closes = [100 * (1.01 ** (i / measured)) for i in range(n + 1)]
    result = period_path_inputs(closes)
    assert result['momentum_perf'] == pytest.approx(1)
    assert period_momentum_note(saturation(measured), measured) == 100
    assert period_momentum_note(-5, measured) == 0
    assert 0 <= period_momentum_note(1, measured) <= 100
    changed = closes + [999999] * n
    assert period_path_inputs(changed[: n + 1]) == result


@pytest.mark.parametrize(
    'closes,want',
    [
        ([100, 90, 80, 90, 100], 100),
        ([100, 95, 90, 85, 80], 0),
        ([100, 105, 110, 115, 120], 0),
        ([100, 99.9, 100, 105, 110], 1),
    ],
)
def test_recovery_requires_a_real_internal_fall_and_subsequent_rise(closes, want):
    assert recovery_input(closes) == pytest.approx(want)


def test_acceleration_uses_internal_halves_and_missing_is_unknown():
    closes = [100 * (1.01**i if i <= 6 else 1.01**6 * 1.03 ** (i - 6)) for i in range(13)]
    result = period_path_inputs(closes)
    assert result['accel'] > 1.5 and result['r2_prev'] == pytest.approx(1)
    assert period_path_inputs([100, 101, 102, 103])['accel'] is None
    dates = [str(i) for i in range(13)]
    observed = dict(zip(dates, closes))
    del observed[dates[5]]
    assert window_inputs(dates, [], observed)['accel'] is None
    assert window_inputs(dates, [], observed)['momentum_perf'] is None


@pytest.mark.parametrize('n', [6, 21, 63, 126, 756, 1260])
def test_acceleration_normalization_is_bounded_across_durations(n):
    half = n // 2
    closes = [100 * (1.001**i if i <= half else 1.001**half * 1.002 ** (i - half)) for i in range(n + 1)]
    raw = period_path_inputs(closes)
    component = SC.period_components({'slope': 0.15, 'r2': 0.9, 'accel': raw['accel'], 'r2_prev': raw['r2_prev']}, n)
    assert raw['accel'] > 0
    assert 50 <= component['acceleration'] <= 100


def test_period_liquidity_is_real_and_requires_75_percent_coverage():
    assert period_turnover([(10, 200)] * 3, 1)[0] == 2000
    assert period_turnover([(10, 200)] * 15 + [(10, None)] * 5, 1) == (2000, 15)
    assert period_turnover([(10, 200)] * 14 + [(10, None)] * 6, 1) == (None, 14)
    assert period_turnover([(10, 0)] * 3, 1)[0] == 0
    assert period_turnover([(10, None)] * 3, 1)[0] is None


def test_custom_periods_are_private_to_their_strategy_and_scores_use_only_active_inputs():
    a = C.empty()
    a['periods'].append(dict(id='custom_alpha', sessions=100, enabled=True, require_history=False, **{f: None for f in C.BOUNDS}))
    a['periods'].append(dict(id='custom_beta', sessions=400, enabled=True, require_history=False, **{f: None for f in C.BOUNDS}))
    a['scoring'] = {'weights': {'custom_alpha': 25, 'custom_beta': 75}}
    a = C.validate(a)
    b = C.validate(C.empty())
    assert {p['id'] for p in a['periods']} - {p['id'] for p in b['periods']} == {'custom_alpha', 'custom_beta'}
    cleaned = scores_profiles.clean_profile(scores_profiles.profile_of(a))
    applied = scores_profiles.apply_profile(b, cleaned)
    assert {p['id'] for p in applied['periods']} - {p['id'] for p in b['periods']} == {'custom_alpha', 'custom_beta'}
    measurements = {
        n: {'slope': 0.1, 'r2': 0.8, 'up_fraction': 0.6, 'spike_share': 0.2, 'volatility': 1, 'drawdown': 5, 'momentum_perf': 5, 'recovery': 30, 'turnover_eur': 10e6} for n in (100, 400, 1260)
    }
    periods = [{'id': 'custom_alpha', 'sessions': 100, 'weight': 25}, {'id': 'custom_beta', 'sessions': 400, 'weight': 75}]
    first = SC.score_title(measurements, {}, periods)
    measurements[1260] = {k: None for k in measurements[1260]}
    second = SC.score_title(measurements, {}, periods)
    assert first['simple']['score'] == second['simple']['score']
    assert first['complex']['score'] == second['complex']['score']
    assert first['weights'] == {'custom_alpha': 0.25, 'custom_beta': 0.75}


def test_removed_personal_period_is_not_restored_by_an_old_score_profile():
    old = C.empty()
    old['name'] = 'ct:1:personal'
    old['periods'].append(dict(id='custom_old', sessions=400, enabled=True, require_history=False, **{f: None for f in C.BOUNDS}))
    profile = scores_profiles.profile_of(C.validate(old))
    profile['periods']['month']['enabled'] = True
    current = C.empty()
    current['name'] = 'ct:1:personal'
    current['periods'][2]['enabled'] = True
    applied = scores_profiles.apply_profile(C.validate(current), scores_profiles.clean_profile(profile))
    assert 'custom_old' not in {p['id'] for p in applied['periods']}


def test_five_year_score_needs_no_older_input():
    measurements = {
        756: {'slope': 0.05, 'r2': 0.85, 'up_fraction': 0.6, 'spike_share': 0.2, 'volatility': 1.5, 'drawdown': 10, 'momentum_perf': 20, 'recovery': 50, 'turnover_eur': 10e6},
        1260: {'slope': 0.04, 'r2': 0.8, 'up_fraction': 0.55, 'spike_share': 0.3, 'volatility': 1.7, 'drawdown': 15, 'momentum_perf': 30, 'recovery': 40, 'turnover_eur': 8e6},
    }
    periods = [{'id': 'three_year', 'sessions': 756, 'weight': 40}, {'id': 'five_year', 'sessions': 1260, 'weight': 60}]
    score = SC.score_title(measurements, {}, periods, complex_weights={'momentum': 20, 'recovery': 20, 'acceleration': 0})
    assert score['simple']['score'] is not None
    assert score['complex']['score'] is not None
    assert score['simple']['status'] == 'ok'
    assert score['complex']['status'] == 'ok'


def _rows_21_126(older):
    """Barres (date, clôture, ajustée) et volumes sur 127 séances XETR, précédées de `older` séances de cours sans rapport."""
    from engine.market.calendar import session_dates

    days = session_dates('XETR', '2026-10-27', 127 + older)
    assert days and len(days) == 127 + older
    closes = [80 + 7 * ((i * 37) % 11) / 11 for i in range(older)] + [100 * 1.0015**i * (1 + 0.01 * (-1) ** i) for i in range(127)]
    bars = [(d, c, None) for d, c in zip(days, closes)]
    volumes = [(d, c, 50_000) for d, c in zip(days, closes)]
    return days, bars, volumes


def _score_rows_21_126(older):
    from engine.analytics.series import compute
    from engine.market.calendar import window_calendars

    days, bars, volumes = _rows_21_126(older)
    windows = [21, 126]
    score_rows = []
    compute._compute_one(
        1, 'XETR', bars, (), windows, {'XETR': days[-1]}, None, [], [], days[-1], window_calendars('XETR', days[-1], windows), None, score_rows=score_rows, volume_bars=volumes, eur_factor=1.0
    )
    return score_rows


def test_strategy_21_plus_126_reads_nothing_beyond_126_sessions():
    exact, with_older = _score_rows_21_126(0), _score_rows_21_126(300)
    assert sorted(r[1] for r in exact) == [21, 126]
    by = {r[1]: r for r in exact}
    assert by[21][9] == 21 and by[126][9] == 126  # séances de volume : celles de la période seulement
    assert exact == with_older  # 300 séances plus anciennes ne changent aucune entrée de score


def test_strategy_21_plus_126_scores_use_only_those_two_periods():
    from engine.analytics.series import compute
    from engine.analytics.series.measures import dated_window_metrics
    from engine.market.calendar import window_calendars

    days, bars, volumes = _rows_21_126(300)
    windows = [21, 126]
    score_rows = []
    compute._compute_one(
        1, 'XETR', bars, (), windows, {'XETR': days[-1]}, None, [], [], days[-1], window_calendars('XETR', days[-1], windows), None, score_rows=score_rows, volume_bars=volumes, eur_factor=1.0
    )
    obs = {d: c for d, c, _ in bars}
    cal = window_calendars('XETR', days[-1], windows)
    inputs = {}
    for lid, n, up, spike, accel, r2p, mom, rec, turn, vd in score_rows:
        m = dated_window_metrics(cal[n], obs)[0]
        inputs[n] = dict(
            m, up_fraction=float(up), spike_share=float(spike), accel=float(accel), r2_prev=float(r2p), momentum_perf=float(mom), recovery=float(rec), turnover_eur=float(turn), volume_days=vd
        )
    periods = [{'id': 'month', 'sessions': 21, 'weight': 40}, {'id': 'half', 'sessions': 126, 'weight': 60}]
    res = SC.score_title(inputs, {}, periods)
    assert res['simple']['status'] == 'ok' and res['complex']['status'] == 'ok'
    assert set(res['periods']) == {'month', 'half'}
    assert res['weights'] == {'month': 0.4, 'half': 0.6}
    for comp in res['periods'].values():
        assert all(comp[k] is not None for k in ('momentum', 'acceleration', 'recovery', 'liquidity'))
    # une mesure parasite hors des deux périodes (252, 1260) ne change aucune note
    extra = {**inputs, 252: dict(inputs[126], momentum_perf=-90, recovery=0, turnover_eur=1, accel=-5), 1260: dict(inputs[126], slope=-1)}
    again = SC.score_title(extra, {}, periods)
    assert again['simple']['score'] == res['simple']['score'] and again['complex']['score'] == res['complex']['score']


def test_title_sheet_labels_every_period_including_custom_ones():
    from engine.analytics.admin.title_sheet import _period_label

    assert _period_label({'id': 'half', 'sessions': 126}) == 'Six mois'
    assert _period_label({'id': 'two_year', 'sessions': 504}) == '2 ans'
    assert _period_label({'id': 'custom_x', 'sessions': 400}) == '400 séances'


def test_history_depth_classification_and_bounded_loading():
    import datetime

    from engine.analytics.series.compute import history_since
    from engine.market import history_depth as H

    now = datetime.datetime(2026, 11, 17, 12, tzinfo=datetime.timezone.utc)
    cal = H.Calendars(now).get('XNYS')
    gap = cal['dates'][-500]
    have = set(cal['dates']) - {gap}
    assert H.classify(cal, have, set(), cal['dates'][0], None) == ('incomplete', 1, 1)
    assert H.classify(cal, have, {gap}, cal['dates'][0], None) == ('complete', 0, 0)  # fermeture exceptionnelle : pas un trou
    young = set(cal['dates'][-300:])
    assert H.classify(cal, young, set(), cal['dates'][-300], cal['dates'][-300])[0] == 'recent'
    # la lecture du calcul couvre toujours la fenêtre la plus longue demandée, mais pas davantage que nécessaire
    assert history_since([1, 21, 252], now) == now.date() - datetime.timedelta(days=610)
    assert history_since([1, 21, 1260], now) <= cal['start']


def test_general_data_outage_is_never_taken_for_a_market_closure():
    import datetime

    from engine.market import history_depth as hd

    d = lambda n: datetime.date(2025, 1, n)
    # un jour signalé par 3 places sur 4 : panne générale ; un jour propre à une seule place : vraie fermeture
    out = hd._reject_outages({'XNYS': [d(9), d(20)], 'XETR': [d(20)], 'XPAR': [d(20)], 'XLON': []})
    assert out == {'XNYS': [d(9)], 'XETR': [], 'XPAR': [], 'XLON': []}
    # une place qui cumule trop de jours est suspecte : rien n'est retenu pour elle
    many = [datetime.date(2025, 1, 1) + datetime.timedelta(days=i) for i in range(hd.CLOSED_MAX_PER_PLACE + 1)]
    assert hd._reject_outages({'XNYS': many}) == {}
