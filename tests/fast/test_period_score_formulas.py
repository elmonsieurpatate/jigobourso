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
    tolerated = window_inputs(dates, [], observed)  # une clôture isolée manquante : mesures calculées sur les clôtures observées, jamais comblées
    assert tolerated['accel'] is not None and tolerated['momentum_perf'] is not None
    for k in range(3, 11):
        observed.pop(dates[k], None)  # longue interruption (> MAX_GAP ou couverture insuffisante) : indisponible
    assert window_inputs(dates, [], observed)['accel'] is None and window_inputs(dates, [], observed)['momentum_perf'] is None


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
    assert by[21][10] == 21 and by[126][10] == 126  # séances de volume : celles de la période seulement
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
    for lid, n, up, spike, accel, r2p, mom, rec, mrar, turn, vd in score_rows:
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


# ───────── rendement ajusté du risque (MRAR) ─────────
def _sessions(n, start='2022-01-03'):
    import datetime

    out, d = [], datetime.date.fromisoformat(start)
    while len(out) < n + 1:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def _monthly_path(dates, monthly):
    """Clôtures dont le rendement de chaque mois calendaire est `monthly[i % len]` (réparti à parts égales sur ses séances)."""
    closes, price, last, k = [], 100.0, None, -1
    for i, d in enumerate(dates):
        month = d[:7]
        if month != last:
            k += 1
            last = month
            size = sum(1 for x in dates if x[:7] == month)
        price *= (1 + monthly[k % len(monthly)]) ** (1 / size)
        closes.append(price)
    return closes


def test_monthly_returns_use_complete_calendar_months_only():
    from engine.analytics.scoring.score_inputs import monthly_returns

    dates = _sessions(756)
    returns = monthly_returns(dates, [100.0] * len(dates))
    assert 33 <= len(returns) <= 36 and all(r == 0 for r in returns)
    # le dernier mois (non terminé) et le premier (commencé avant la fenêtre) ne donnent aucun rendement
    first_month, last_month = dates[0][:7], dates[-1][:7]
    closes = [100.0 if d[:7] == first_month else 200.0 for d in dates]
    assert max(monthly_returns(dates, closes)) == pytest.approx(1.0)  # un seul saut, à la fin du premier mois
    closes = [100.0 if d[:7] != last_month else 5000.0 for d in dates]
    assert monthly_returns(dates, closes) == [0.0] * len(monthly_returns(dates, closes))


def test_mrar_of_a_constant_monthly_return_is_its_annualised_value_and_variability_is_penalised():
    from engine.analytics.scoring.score_inputs import mrar_input

    dates = _sessions(756)
    steady = mrar_input(dates, _monthly_path(dates, [0.01]))
    assert steady == pytest.approx(100 * (1.01**12 - 1), rel=2e-3)
    wild = mrar_input(dates, _monthly_path(dates, [0.11, -0.09]))  # même rendement moyen, beaucoup plus de variabilité
    assert wild is not None and wild < steady
    lossy = mrar_input(dates, _monthly_path(dates, [-0.01]))
    assert lossy < 0 and lossy > -100


def test_mrar_is_absent_when_the_window_is_too_short_or_incomplete():
    from engine.analytics.scoring.score_inputs import mrar_input, window_inputs, window_mrar

    for n in (21, 63, 126, 251):
        d = _sessions(n)
        assert mrar_input(d, _monthly_path(d, [0.01])) is None  # moins d'un an : jamais de valeur artificielle
    d = _sessions(252)
    assert mrar_input(d, _monthly_path(d, [0.01])) is not None  # un an : 10 rendements mensuels complets au moins
    obs = dict(zip(d, _monthly_path(d, [0.01])))
    assert window_mrar(d, obs) is not None
    full = window_mrar(d, obs)
    obs.pop(d[100])  # un trou isolé : toléré, le MRAR est calculé sur les clôtures observées (mêmes valeurs ici : trajectoire mensuelle régulière)
    assert window_mrar(d, obs) is not None and window_mrar(d, obs) == pytest.approx(full, rel=1e-3)
    for k in range(101, 115):
        obs.pop(d[k])  # 15 séances consécutives sans cotation : interruption, aucune mesure
    assert window_mrar(d, obs) is None and window_inputs(d, [], obs)['mrar'] is None
    assert mrar_input(d, [100.0] * 5) is None and mrar_input([], []) is None


def test_extreme_returns_stay_finite_and_inside_the_storage_bound():
    from engine.analytics.scoring.score_inputs import MRAR_CAP, mrar_input

    d = _sessions(756)
    value = mrar_input(d, _monthly_path(d, [30.0, 40.0]))
    assert value is not None and value <= MRAR_CAP
    assert mrar_input(d, _monthly_path(d, [-0.9, -0.95])) > -100


def test_risk_adjusted_note_is_an_affine_scale_of_the_annualised_mrar_and_absent_under_a_year():
    from engine.analytics.scoring.scores import period_risk_adjusted_note

    assert period_risk_adjusted_note(None, 756) is None and period_risk_adjusted_note(50.0, 126) is None
    assert period_risk_adjusted_note(-30.0, 756) == 0 and period_risk_adjusted_note(20.0, 756) == 100  # bornes par défaut −30 / +20
    assert period_risk_adjusted_note(-5.0, 756) == pytest.approx(50.0) and period_risk_adjusted_note(-60.0, 1260) == 0 and period_risk_adjusted_note(1e6, 1260) == 100
    assert period_risk_adjusted_note(-5.0, 252) == period_risk_adjusted_note(-5.0, 1260)  # même échelle pour toutes les périodes mesurables
    assert period_risk_adjusted_note(-10.0, 756, -20.0, 10.0) == pytest.approx(100 / 3)  # bornes réglables
    # les valeurs négatives ne sont plus toutes à 0 : le classement parmi les titres en perte est conservé
    assert period_risk_adjusted_note(-25.0, 756) < period_risk_adjusted_note(-5.0, 756)
    # sat_a n'intervient plus : la note ne dépend que de l'échelle affine
    assert SC.period_components({**_flat_metrics(), 'mrar': -5.0}, 756, sat_a=5.0)['risk_adjusted'] == SC.period_components({**_flat_metrics(), 'mrar': -5.0}, 756, sat_a=100.0)['risk_adjusted']


def _flat_metrics():
    return dict(
        slope=0.05,
        r2=0.8,
        volatility=1.5,
        drawdown=12.0,
        up_fraction=0.55,
        spike_share=0.2,
        accel=0.001,
        r2_prev=0.7,
        momentum_perf=20.0,
        recovery=30.0,
        coverage=1.0,
        turnover_eur=5e6,
        volume_days=756,
    )


def test_risk_adjusted_weight_zero_leaves_both_scores_unchanged_and_weight_positive_uses_it():
    def M(n):
        return dict(
            slope=0.05,
            r2=0.8,
            volatility=1.5,
            drawdown=12.0,
            up_fraction=0.55,
            spike_share=0.2,
            accel=0.001,
            r2_prev=0.7,
            momentum_perf=20.0,
            recovery=30.0,
            coverage=1.0,
            turnover_eur=5e6,
            volume_days=n,
        )

    periods = [{'id': 'three_year', 'sessions': 756}, {'id': 'five_year', 'sessions': 1260}]
    base = {n: M(n) for n in (756, 1260)}
    with_mrar = {n: dict(M(n), mrar=12.0) for n in (756, 1260)}
    ref = SC.score_title(base, {}, periods)
    same = SC.score_title(with_mrar, {}, periods)  # poids par défaut : 0
    assert same['simple']['score'] == ref['simple']['score'] and same['complex']['score'] == ref['complex']['score']
    assert same['complex']['contributions'].keys() == ref['complex']['contributions'].keys()
    weighted = SC.score_title(with_mrar, {}, periods, complex_weights={'dynamics': 20, 'risk_adjusted': 20})
    assert 'risk_adjusted' in weighted['complex']['contributions'] and weighted['complex']['contributions']['risk_adjusted']['value'] is not None
    assert weighted['simple']['score'] == ref['simple']['score']  # le Score 1 ne change jamais
    # sans mesure (titre trop récent) : la composante sort du calcul, son poids est renormalisé (jamais 0 ni bonus)
    missing = SC.score_title(base, {}, periods, complex_weights={'dynamics': 20, 'risk_adjusted': 20})['complex']
    assert missing['contributions']['risk_adjusted']['unavailable'] and 0 <= missing['score'] <= 100


def test_profiles_saved_before_the_component_stay_valid_with_weight_zero():
    config = C.validate(__import__('engine.analytics.scoring.scores_specs', fromlist=['x']).V4_STRATEGIES['growth_regular']['build']())
    profile = scores_profiles.profile_of(config)
    assert profile['complex_weights']['risk_adjusted'] == 0 and 'risk_adjusted' in SC.COMPLEX_LABELS
    old = dict(profile, complex_weights={k: v for k, v in profile['complex_weights'].items() if k != 'risk_adjusted'})
    assert scores_profiles.clean_profile(old)['complex_weights']['risk_adjusted'] == 0


# ───────── échelles des périodes longues : aucune modification jusqu'à 252 séances, transition continue ensuite ─────────
def _old_drawdown_note(dd):
    return 100 * SC.clamp((15 - dd) / 15)


def _old_relative_vol_note(vol, slope):
    return 100 * SC.clamp((4.0 - vol / max(slope, 0.3)) / (4.0 - 1.0))


@pytest.mark.parametrize('n', [3, 5, 21, 63, 126, 189, 252])
def test_notes_up_to_252_sessions_are_exactly_the_historical_ones(n):
    import random

    rng = random.Random(n)
    for _ in range(300):
        m = dict(_flat_metrics(), drawdown=rng.uniform(0, 80), volatility=rng.uniform(0.1, 8), slope=rng.uniform(-1, 8))
        for mode in ('absolute', 'relative'):
            c = SC.period_components(m, n, vol_mode=mode)
            assert c['drawdown'] == _old_drawdown_note(m['drawdown'])  # égalité exacte, pas approchée
            assert c['volatility'] == (_old_relative_vol_note(m['volatility'], m['slope']) if mode == 'relative' else 100 * SC.clamp((5 - m['volatility']) / 4))
        # le réglage des périodes longues n'a aucun effet sur elles
        assert SC.period_components(m, n, vol_mode='relative', dd_ref_long=25.0)['drawdown'] == SC.period_components(m, n, vol_mode='relative')['drawdown']
    assert SC.drawdown_reference(n) == 15.0 and SC.vol_ratio_scale(n) == (1.0, 4.0, 0.3)


def test_transition_between_252_and_504_sessions_is_continuous_monotone_and_exact_at_both_ends():
    assert SC.long_weight(252) == 0 and SC.long_weight(504) == 1 and SC.long_weight(1260) == 1
    assert SC.drawdown_reference(504) == pytest.approx(60 * (504 / 756) ** 0.25) and SC.vol_ratio_scale(504) == (10.0, 150.0, 0.001)
    prev = SC.drawdown_reference(252)
    for n in range(253, 2001):
        ref = SC.drawdown_reference(n)
        assert ref >= prev - 1e-12  # monotone : un horizon plus long n'exige jamais un repli plus petit
        assert ref / prev - 1 < 0.012  # aucune marche : au plus 1,2 % de variation de la référence d'une séance à la suivante
        prev = ref
    assert SC.drawdown_reference(253) - 15 < 0.01  # dérivée nulle en 252 : 253 séances restent presque à 15 %
    scales = [SC.vol_ratio_scale(n) for n in range(252, 506)]
    assert all(b >= a - 1e-12 and w >= v - 1e-12 and f <= g + 1e-12 for (a, v, g), (b, w, f) in zip(scales, scales[1:]))
    # la note d'un même titre varie peu d'une séance à l'autre sur toute la transition (aucune marche à 252 ni à 504)
    m = dict(_flat_metrics(), drawdown=20.0, volatility=1.5, slope=0.4)
    for field, step in (('drawdown', 0.8), ('volatility', 1.5)):  # la note passe de 8 à 100 sur 250 séances : au plus 1,4 point par séance
        notes = [SC.period_components(m, n, vol_mode='relative')[field] for n in range(252, 520)]
        assert all(abs(b - a) < step for a, b in zip(notes, notes[1:])), field
    assert abs(SC.period_components(m, 253, vol_mode='relative')['volatility'] - SC.period_components(m, 252, vol_mode='relative')['volatility']) < 0.05


def test_long_period_scales_spread_notes_that_the_historical_scale_flattened_and_dd_ref_long_is_configurable():
    deep = dict(_flat_metrics(), drawdown=35.0)
    mild = dict(_flat_metrics(), drawdown=20.0)
    assert SC.period_components(deep, 252)['drawdown'] == 0 == SC.period_components(mild, 252)['drawdown']  # échelle historique : indiscernables
    a, b = SC.period_components(deep, 756)['drawdown'], SC.period_components(mild, 756)['drawdown']
    assert 0 < a < b < 100  # échelle longue : ordonnés
    assert SC.period_components(deep, 756, dd_ref_long=30.0)['drawdown'] == 0 < SC.period_components(deep, 756, dd_ref_long=90.0)['drawdown']
    # volatilité relative longue : pente ≤ 0 → 0 ; hausse régulière → bonne note ; plus de plancher de 0,3 qui écrase tout
    flat_down = SC.period_components(dict(_flat_metrics(), slope=-0.01), 756, vol_mode='relative')['volatility']
    steady = SC.period_components(dict(_flat_metrics(), slope=0.12, volatility=1.2), 756, vol_mode='relative')['volatility']
    weak = SC.period_components(dict(_flat_metrics(), slope=0.02, volatility=1.5), 756, vol_mode='relative')['volatility']
    assert flat_down == 0 and steady > weak > 0
    assert SC.period_components(dict(_flat_metrics(), slope=0.12, volatility=1.2), 756, vol_mode='absolute')['volatility'] == 100 * SC.clamp((5 - 1.2) / 4)  # mode absolu inchangé


def test_new_tunings_are_validated_with_their_ranges_and_default_to_the_proposed_values():
    ok = C.validate_scoring(None, [])
    assert (ok['dd_ref_long'], ok['mrar_lo'], ok['mrar_hi']) == (60.0, -30.0, 20.0)
    ok = C.validate_scoring({'dd_ref_long': 50, 'mrar_lo': -20, 'mrar_hi': 10}, [])
    assert (ok['dd_ref_long'], ok['mrar_lo'], ok['mrar_hi']) == (50.0, -20.0, 10.0)
    for bad in ({'dd_ref_long': 5}, {'dd_ref_long': 500}, {'mrar_lo': 0}, {'mrar_lo': -500}, {'mrar_hi': 0}, {'mrar_hi': 500}, {'mrar_lo': 'x'}):
        with pytest.raises(ValueError):
            C.validate_scoring(bad, [])
    design = scores_profiles.design()
    assert design['tuning']['dd_ref_long'] == 60.0 and design['tuning_ranges']['mrar_lo'] == [-100.0, -1.0] and 'long' in scores_profiles.formula()


def test_profiles_saved_before_the_new_tunings_keep_their_scores():
    config = C.validate(__import__('engine.analytics.scoring.scores_specs', fromlist=['x']).V4_STRATEGIES['growth_regular']['build']())
    profile = scores_profiles.clean_profile(scores_profiles.profile_of(config))
    old = dict(profile, tuning={k: v for k, v in profile['tuning'].items() if k in ('sat_a', 'accel_ref', 'vol_mode')})
    assert scores_profiles.clean_profile(old)['tuning'] == profile['tuning']  # valeurs par défaut complétées, aucun changement de note
