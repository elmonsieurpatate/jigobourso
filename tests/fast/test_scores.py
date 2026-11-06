"""Scores V4 : formules, poids de 1 à 6 granularités, données manquantes, indépendance vis-à-vis des filtres, liquidité, mesures d'entrée."""
import math
import pytest
from engine.analytics import scores as SC, score_inputs as SI, liquidity as LQ, explorer_config as C, strategy as S, score_service as SS


def M(slope, r2, up, spike, vol, dd, accel=None, r2p=None):
    return dict(slope=slope, r2=r2, up_fraction=up, spike_share=spike, volatility=vol, drawdown=dd, accel=accel, r2_prev=r2p)


def P(*sessions):
    names = {1: 'day', 5: 'week', 21: 'month', 63: 'quarter', 126: 'half', 252: 'year'}
    return [dict(id=names.get(n, 'p%d' % n), sessions=n) for n in sessions]


# Valeurs de référence calculées avec le prototype validé sur les données réelles (variants.py / v8.py, 2026-11-06).
GOLDEN = {
    'full_two': (dict(inputs={5: M(1.1, .82, .7, .35, 2.4, 3.0, .6, .5), 21: M(.75, .9, .62, .28, 2.1, 6.0, .3, .7)}, turn=20e6), (5, 21), (5, 21),
                 dict(simple=26.77894246259532, complex=59.06218524301239, ss='ok', cs='ok')),
    'no_accel_month': (dict(inputs={5: M(.9, .7, .6, .5, 3.0, 4.0), 21: M(.5, .85, .6, .3, 2.5, 8.0)}, turn=8e6), (5, 21), (5, 21),
                       dict(simple=15.640446460882732, complex=38.745666323877295, ss='partiel', cs='ok')),
    'four_periods': (dict(inputs={5: M(1.2, .8, .7, .3, 2.2, 2.5, .4, .6), 21: M(.7, .9, .65, .25, 2.0, 5.0, .2, .8), 63: M(.4, .75, .6, .35, 2.3, 9.0, .1, .7),
                                  126: M(.25, .8, .58, .3, 2.4, 14.0, .05, .6)}, turn=3e6), (5, 21, 63, 126), (5, 21),
                     dict(simple=24.20505960412955, complex=49.64925352715027, ss='ok', cs='ok')),
    'declining_no_liquidity': (dict(inputs={5: M(-.5, .4, .4, 1.0, 3.5, 6.0, -.8, .5), 21: M(.05, .3, .5, .6, 3.1, 10.0, -.2, .4)}, turn=None), (5, 21), (5, 21),
                               dict(simple=0.23718314813635621, complex=0.711702252992812, ss='ok', cs='partiel')),   # liquidité inconnue : poids renormalisés (V4.2), ni zéro ni bonus,
    'optional_week_missing': (dict(inputs={5: None, 21: M(.6, .88, .65, .25, 1.8, 5.0, .1, .8), 63: M(.35, .7, .58, .3, 2.0, 12.0, .05, .6)}, turn=30e6), (5, 21, 63), (21,),
                              dict(simple=21.07068751413848, complex=55.31844002403962, ss='partiel', cs='partiel')),   # semaine sans historique : calculé sur mois + trimestre (V4.2),
}


@pytest.mark.parametrize('name', sorted(GOLDEN))
def test_scores_match_validated_prototype(name):
    case, sessions, required, want = GOLDEN[name]
    names = {5: 'week', 21: 'month', 63: 'quarter', 126: 'half'}
    r = SC.score_title(case['inputs'], {'turnover_eur': case['turn'], 'source': 'daily'}, P(*sessions), required=[names[n] for n in required])
    assert r['simple']['status'] == want['ss'] and r['complex']['status'] == want['cs']
    for key in ('simple', 'complex'):
        if want[key] is None:
            assert r[key]['score'] is None
        else:
            assert r[key]['score'] == pytest.approx(want[key], rel=1e-9, abs=1e-9)


def test_automatic_weights_reproduce_v1_week_month_split():
    w = SC.auto_weights([5, 21])
    assert w[5] == pytest.approx(0.416, abs=0.0005) and w[21] == pytest.approx(0.584, abs=0.0005)


@pytest.mark.parametrize('sessions', [(21,), (5, 21), (5, 21, 63), (5, 21, 63, 126), (5, 21, 63, 126, 252), (5, 10, 21, 63, 126, 252), (3, 7, 40)])
def test_any_number_of_granularities_from_one_to_six(sessions):
    w = SC.auto_weights(sessions)
    assert len(w) == len(sessions) and sum(w.values()) == pytest.approx(1) and all(x > 0 for x in w.values())
    inputs = {n: M(.6, .85, .65, .25, 2.0, 6.0, .1, .8) for n in sessions}
    r = SC.score_title(inputs, {'turnover_eur': 20e6, 'source': 'daily'}, P(*sessions))
    assert r['simple']['status'] == 'ok' and 0 <= r['simple']['score'] <= 100 and 0 <= r['complex']['score'] <= 100
    assert set(r['weights']) == {p['id'] for p in P(*sessions)}


def test_disabled_period_has_no_implicit_weight():
    r = SC.score_title({5: M(1, .8, .7, .3, 2, 3), 21: M(.7, .9, .6, .3, 2, 5), 63: M(.4, .8, .6, .3, 2, 9)}, {'turnover_eur': 10e6}, P(5, 21))
    assert set(r['weights']) == {'week', 'month'} and sum(r['weights'].values()) == pytest.approx(1)
    assert 'quarter' not in r['periods']


def test_custom_weights_are_normalised_and_override_automatic():
    periods = P(5, 21)
    periods[0]['weight'], periods[1]['weight'] = 1, 3
    assert SC.resolve_weights(periods) == pytest.approx({'week': .25, 'month': .75})
    periods[1]['weight'] = None                    # une valeur manquante : retour aux poids automatiques, jamais un poids inventé
    assert SC.resolve_weights(periods)['week'] == pytest.approx(0.416, abs=0.0005)


def test_day_granularity_is_never_scored():
    r = SC.score_title({1: M(3, None, 1, 1, None, 0)}, {'turnover_eur': 10e6}, P(1))
    assert r['simple']['status'] == 'inconnu' and 'aucune période active' in r['simple']['why']


def test_required_period_missing_no_longer_blocks_the_score():
    """V4.2 : une période « obligatoire » manquante ne supprime plus la note ; elle est calculée sur ce qui existe et signalée."""
    r = SC.score_title({5: None, 21: M(.7, .9, .6, .3, 2, 5)}, {'turnover_eur': 10e6}, P(5, 21), required=['week'])
    assert r['simple']['score'] is not None and r['complex']['score'] is not None
    assert r['simple']['status'] == r['complex']['status'] == 'partiel' and r['complex']['reliable'] is False
    assert r['missing']['required_periods'] == ['week'] and r['weights_effective'] == pytest.approx({'month': 1.0})


def test_impossible_computation_is_unknown_with_explicit_reason():
    r = SC.score_title({5: None, 21: None}, {'turnover_eur': 10e6}, P(5, 21))
    assert r['simple']['score'] is None and r['complex']['score'] is None and 'impossible' in r['simple']['why']
    nor2 = SC.score_title({21: M(.7, None, .6, .3, 2, 5)}, {'turnover_eur': 10e6}, P(21))
    assert nor2['simple']['score'] is None and 'R²' in nor2['simple']['why']       # jamais un 0 inventé
    assert nor2['complex']['score'] is not None                                      # le complexe existe : composantes disponibles renormalisées


def test_missing_component_is_neutral_not_a_penalty():
    """Renormalisation : une composante absente ne vaut ni 0 (pénalité) ni un bonus. Titre à notes uniformes = même note avec ou sans la composante manquante."""
    full = {21: M(.7, .9, .6, .3, 2, 5, None, None)}
    a = SC.score_title(full, {'turnover_eur': 20e6}, P(21), complex_weights={'liquidity': 0})
    b = SC.score_title(full, {'turnover_eur': None}, P(21))
    assert b['complex']['score'] == pytest.approx(a['complex']['score'])
    assert b['complex']['contributions']['liquidity']['unavailable'] is True and b['complex']['status'] == 'partiel'


def test_optional_period_missing_is_partial_and_distinct_from_secondary_missing():
    inputs = {5: M(1, .8, .7, .3, 2, 3), 21: M(.7, .9, .6, .3, 2, 5, None, None), 63: None, 126: M(.3, .8, .6, .3, 2, 9, .1, .7)}
    r = SC.score_title(inputs, {'turnover_eur': 10e6}, P(5, 21, 63, 126), required=['week', 'month'], threshold=0.5)
    assert r['missing']['optional_periods'] == ['quarter'] and r['missing']['required_periods'] == []
    assert 'month:acceleration' in r['missing']['secondary']
    assert r['complex']['status'] == 'partiel' and r['complex']['coverage'] < 1


def test_unknown_value_is_never_a_measured_zero():
    base = {5: M(1, .8, .7, .3, 2, 3, None, None), 21: M(.7, .9, .6, .3, 2, 5, None, None)}
    absent = SC.score_title(base, {'turnover_eur': 10e6}, P(5, 21))
    flat = SC.score_title({5: M(1, .8, .7, .3, 2, 3, 0.0, .8), 21: M(.7, .9, .6, .3, 2, 5, 0.0, .8)}, {'turnover_eur': 10e6}, P(5, 21))
    assert absent['simple']['status'] == 'partiel' and flat['simple']['status'] == 'ok'          # accélération absente ≠ accélération nulle
    assert absent['simple']['acceleration'] is None and flat['simple']['acceleration'] == pytest.approx(50)
    no_liq = SC.score_title(base, {'turnover_eur': None}, P(5, 21))
    zero_liq = SC.score_title(base, {'turnover_eur': 1.0}, P(5, 21))
    assert no_liq['complex']['status'] == 'partiel' and zero_liq['complex']['status'] == 'ok'        # liquidité inconnue ≠ liquidité mesurée très faible


def test_coverage_threshold_is_a_reliability_flag_not_a_filter():
    inputs = {5: None, 21: M(.7, .9, .6, .3, 2, 5, .1, .8)}            # la semaine (41,6 %) n'a pas d'historique
    strict = SC.score_title(inputs, {'turnover_eur': 10e6}, P(5, 21), threshold=0.75)
    assert strict['simple']['score'] is not None and strict['complex']['score'] is not None            # jamais écarté
    assert strict['simple']['status'] == strict['complex']['status'] == 'partiel'
    assert strict['simple']['reliable'] is False and strict['complex']['reliable'] is False
    assert strict['simple']['coverage'] == pytest.approx(0.584, abs=0.001)
    lenient = SC.score_title(inputs, {'turnover_eur': 10e6}, P(5, 21), threshold=0.5)
    assert lenient['simple']['reliable'] is True and lenient['simple']['score'] == pytest.approx(strict['simple']['score'])   # le seuil ne change aucune note


def test_liquidity_is_a_global_indicator_counted_once():
    one = SC.score_title({21: M(.7, .9, .6, .3, 2, 5, .1, .8)}, {'turnover_eur': 20e6}, P(21))
    three = SC.score_title({n: M(.7, .9, .6, .3, 2, 5, .1, .8) for n in (5, 21, 63)}, {'turnover_eur': 20e6}, P(5, 21, 63))
    assert one['complex']['contributions']['liquidity']['points'] == pytest.approx(three['complex']['contributions']['liquidity']['points'])


def test_liquidity_scale_is_absolute_and_logarithmic():
    assert SC.liquidity_note(2e6) == pytest.approx(0) and SC.liquidity_note(50e6) == pytest.approx(100)
    assert SC.liquidity_note(10e6) == pytest.approx(100 * math.log10(5) / math.log10(25))
    assert SC.liquidity_note(None) is None and SC.liquidity_note(0) is None and SC.liquidity_note(1e9) == 100


def test_recent_anchor_is_progressive_not_brutal():
    def at(week_slope):
        return SC.score_title({5: M(week_slope, .8, .7, .3, 2, 3, 0, .8), 21: M(.7, .9, .6, .3, 2, 5, 0, .8)}, {'turnover_eur': 20e6}, P(5, 21))['complex']
    strong, weak, flat = at(1.2), at(.45), at(0.0)
    assert strong['anchor'] == pytest.approx(1.0) and 0.5 <= flat['anchor'] < weak['anchor'] < 1.0
    assert flat['anchor'] == pytest.approx(0.5)                # un arrêt complet de la semaine retire au plus la moitié, pas tout


def test_isolated_spike_in_the_week_is_penalised_in_the_simple_score():
    smooth = {5: M(1.0, .85, .7, .3, 2, 3), 21: M(.7, .9, .65, .25, 2, 5)}
    spiky = {5: M(1.0, .85, .7, 1.0, 2, 3), 21: M(.7, .9, .65, .25, 2, 5)}
    a = SC.score_title(smooth, {'turnover_eur': 10e6}, P(5, 21))['simple']['score']
    b = SC.score_title(spiky, {'turnover_eur': 10e6}, P(5, 21))['simple']['score']
    assert b < a * 0.9                                           # la pénalité de concentration d'une fenêtre courte n'est pas diluée par sa fiabilité R²


def test_regular_trend_beats_equally_fast_irregular_trend():
    regular = {5: M(1, .92, .75, .2, 1.5, 2), 21: M(.7, .95, .7, .2, 1.5, 3)}
    irregular = {5: M(1, .5, .5, .6, 4.5, 9), 21: M(.7, .55, .5, .6, 4.5, 12)}
    for kind in ('simple', 'complex'):
        assert SC.score_title(regular, {'turnover_eur': 10e6}, P(5, 21))[kind]['score'] > SC.score_title(irregular, {'turnover_eur': 10e6}, P(5, 21))[kind]['score']


def test_scores_are_bounded_and_stable_for_extreme_inputs():
    wild = {5: M(50, 1.0, 1.0, 0.0, 0.0, 0.0, 99, 1.0), 21: M(80, 1.0, 1.0, 0.0, 0.0, 0.0, 99, 1.0)}
    r = SC.score_title(wild, {'turnover_eur': 1e12}, P(5, 21))
    assert r['simple']['score'] <= 100 and r['complex']['score'] <= 100.0000001
    bad = {5: M(-100, 0.0, 0.0, 1.0, 50, 100, -99, 0.0), 21: M(-60, 0.0, 0.0, 1.0, 50, 100, -99, 0.0)}
    r = SC.score_title(bad, {'turnover_eur': 1.0}, P(5, 21))
    assert r['simple']['score'] >= 0 and r['complex']['score'] >= 0


def test_ranks_use_all_scored_titles_and_ignore_unknown():
    scores = {1: 50.0, 2: 70.0, 3: None, 4: 70.0}
    assert SC.rank_positions(scores) == {2: 1, 4: 2, 1: 3}
    assert SC.rank_positions({k: v for k, v in scores.items() if k != 1}) == {2: 1, 4: 2}


def test_window_inputs_follow_v1_definitions():
    closes = [100, 102, 101, 105, 106, 107]
    got = SI.path_inputs(closes)
    steps = [closes[i] / closes[i - 1] - 1 for i in range(1, 6)]
    assert got['up_fraction'] == pytest.approx(4 / 5)
    assert got['spike_share'] == pytest.approx(math.log1p(max(steps)) / math.log(107 / 100))
    assert SI.path_inputs([100, 99, 98, 97])['spike_share'] == 1.0          # fenêtre sans hausse nette : concentration maximale


def test_window_inputs_need_complete_windows_and_compute_acceleration():
    dates = [f'2026-01-{d:02d}' for d in range(1, 13)]
    obs = {d: 100 * 1.01 ** i for i, d in enumerate(dates)}
    out = SI.window_inputs(dates[6:12], dates[0:6], obs)
    assert out['accel'] == pytest.approx(0, abs=1e-9) and out['r2_prev'] == pytest.approx(1.0)
    obs_hole = dict(obs); del obs_hole[dates[9]]
    assert SI.window_inputs(dates[6:12], dates[0:6], obs_hole) == {'up_fraction': None, 'spike_share': None, 'accel': None, 'r2_prev': None}
    accelerating = {d: 100 * (1.01 ** i if i < 6 else 1.01 ** 6 * 1.03 ** (i - 6)) for i, d in enumerate(dates)}
    assert SI.window_inputs(dates[6:12], dates[0:6], accelerating)['accel'] > 1.5


# ── Liquidité ──
def test_daily_turnover_ignores_missing_volume_and_never_uses_zero_for_unknown():
    bars = [(10.0, 1000)] * 17 + [(10.0, None)] * 3
    value, days = LQ.daily_turnover(bars, 1.0)
    assert days == 17 and value == pytest.approx(10000)
    value, days = LQ.daily_turnover([(10.0, 1000)] * 10 + [(10.0, None)] * 10, 1.0)
    assert value is None and days == 10                                  # trop peu de volumes réels : pas de valeur « réelle »


def test_liquidity_prefers_real_volumes_then_estimate_and_flags_the_source():
    bars = [(10.0, 2000)] * 20
    assert LQ.liquidity(bars, 10.0, 1500, 0.9) == {'turnover_eur': pytest.approx(10 * 2000 * 0.9), 'days': 20, 'source': 'daily'}
    est = LQ.liquidity([(10.0, None)] * 20, 10.0, 1500, 0.9)
    assert est['source'] == 'estimated' and est['turnover_eur'] == pytest.approx(10 * 1500 * 0.9)
    assert LQ.liquidity([], None, None, 1.0)['source'] is None


@pytest.mark.parametrize('bad', [-1, float('nan'), float('inf'), 1e20, True, 'x'])
def test_implausible_volumes_are_unknown(bad):
    assert LQ.valid_volume(bad) is None
    assert LQ.valid_volume(0) == 0.0


# ── Configuration et conformité ──
def test_growth_v1_profile_uses_historical_v1_thresholds_all_configurable():
    c = C.growth_v1()
    by = {p['id']: p for p in c['periods']}
    assert (by['week']['min_return'], by['month']['min_return'], by['month']['min_r2'], by['month']['max_spike_share'], by['month']['max_volatility']) == (3.0, 8.0, .6, .45, 7.0)
    assert c['liquidity']['min_turnover_eur'] == 2e6 and c['liquidity']['min_turnover_eur_us'] == 5e6
    assert c['ranking'] == {'mode': 'scores', 'weights': {}, 'sort': 'simple'}
    assert C.validate(c) == c


def test_last_negative_day_is_a_configurable_criterion_not_a_hard_exclusion():
    c = C.growth_v1()
    measures = {1: {'perf': -1.5, 'slope': -1.5, 'r2': None, 'volatility': None}, 5: {'perf': 6.0, 'slope': 1.0, 'r2': .8, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0},
                21: {'perf': 20.0, 'slope': .8, 'r2': .9, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0}}
    tech = {'turnover_eur': 9e6, 'us_listing': False}
    assert S.judge(c, measures, tech, {})['status'] == 'rejected'
    next(p for p in c['periods'] if p['id'] == 'day')['min_return'] = None            # désactivable
    verdict = S.judge(c, measures, tech, {})
    assert verdict['status'] == 'retained' and not any(r['period'] == 'day' for r in verdict['reasons'])


def test_turnover_threshold_differs_for_us_listings_and_reports_the_source():
    c = C.growth_v1()
    measures = {n: {'perf': 20.0, 'slope': .8, 'r2': .9, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0} for n in (1, 5, 21)}
    tech = {'turnover_eur': 3e6, 'turnover_source': 'estimated'}
    assert S.judge(c, measures, dict(tech, us_listing=False), {})['status'] == 'retained'
    us = S.judge(c, measures, dict(tech, us_listing=True), {})
    assert us['status'] == 'rejected'
    reason = next(r for r in us['reasons'] if r['criterion'] == 'min_turnover_eur')
    assert reason['threshold'] == 5e6 and reason['source'] == 'estimated' and reason['result'] == 'fail'
    assert S.judge(c, measures, dict(tech, turnover_eur=None), {})['status'] == 'unknown'      # inconnu ≠ échec


def test_scoring_block_validation():
    c = C.growth_v1()
    c['scoring'] = {'kappa': 0.5, 'weights': {'week': 1, 'month': 3}, 'complex_weights': {'acceleration': 10}, 'threshold': 0.6}
    assert C.validate(c)['scoring'] == {'kappa': 0.5, 'weights': {'week': 1.0, 'month': 3.0}, 'complex_weights': {'acceleration': 10.0}, 'threshold': 0.6}
    for bad in ({'kappa': 1.0}, {'weights': {'nope': 1}}, {'complex_weights': {'nope': 1}}, {'weights': {'week': -1}}, {'threshold': 2}):
        c['scoring'] = bad
        with pytest.raises(ValueError):
            C.validate(c)


def test_every_existing_configuration_gets_default_scoring_without_changing_its_filters():
    old = S.preset('fast')
    up = C.upgrade(old)
    assert up['scoring'] == {'kappa': 0.7, 'weights': {}, 'complex_weights': {}, 'threshold': 0.75}
    assert up['ranking']['mode'] == 'performance'                  # le classement historique est conservé tel quel


def test_score_parameters_ignore_every_compliance_threshold():
    """Clé de cache et paramètres de score : identiques quand seuls des critères de conformité changent."""
    a, b = C.growth_v1(), C.growth_v1()
    for p in b['periods']:
        p.update(min_return=None if p['min_return'] is None else p['min_return'] + 5, min_r2=0.2 if p['min_r2'] is not None else None)
    b['liquidity']['min_turnover_eur'] = 99e6
    b['selection']['require_fresh'] = False
    assert SS._key(a, 'x') == SS._key(b, 'x')
    assert SS.params_for(a, 'equity') == SS.params_for(b, 'equity')
    b['periods'][3]['enabled'] = True                              # activer le trimestre change la GRANULARITÉ (paramètre de score), pas un filtre
    assert SS._key(a, 'x') != SS._key(b, 'x')


def test_score_does_not_depend_on_other_titles_in_the_universe():
    mine = {5: M(1, .85, .7, .3, 2, 3, .2, .8), 21: M(.7, .9, .6, .3, 2, 5, .1, .8)}
    alone = SC.score_title(mine, {'turnover_eur': 10e6}, P(5, 21))
    for _ in range(3):
        SC.score_title({5: M(2, .95, .9, .1, 1, 1), 21: M(1.5, .97, .8, .1, 1, 1)}, {'turnover_eur': 40e6}, P(5, 21))
    again = SC.score_title(mine, {'turnover_eur': 10e6}, P(5, 21))
    assert alone['simple']['score'] == again['simple']['score'] and alone['complex']['score'] == again['complex']['score']


def test_spike_share_criterion_in_path_metrics():
    from engine.analytics.explorer_metrics import path_metrics
    m = path_metrics([100, 101, 140, 141, 142])
    assert m['spike_share'] == pytest.approx(math.log1p(140 / 101 - 1) / math.log(1.42))
    assert path_metrics([100, 99, 98])['spike_share'] == 1.0
