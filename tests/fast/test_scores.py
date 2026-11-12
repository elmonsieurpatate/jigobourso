"""Scores V4 : formules, poids de 1 à 6 granularités, données manquantes, indépendance vis-à-vis des filtres, liquidité, mesures d'entrée."""
import math
import pytest
from engine.analytics.scoring import scores as SC
from engine.analytics.scoring import score_inputs as SI
from engine.analytics.series import liquidity as LQ
from engine.analytics.explorer import explorer_config as C
from engine.analytics.explorer import strategy as S
from engine.analytics.scoring import score_service as SS


def M(slope, r2, up, spike, vol, dd, accel=None, r2p=None):
    return dict(slope=slope, r2=r2, up_fraction=up, spike_share=spike, volatility=vol, drawdown=dd, accel=accel, r2_prev=r2p)


def P(*sessions):
    names = {1: 'day', 5: 'week', 21: 'month', 63: 'quarter', 126: 'half', 252: 'year'}
    return [dict(id=names.get(n, 'p%d' % n), sessions=n) for n in sessions]


# Valeurs de référence calculées avec le prototype validé sur les données réelles (variants.py / v8.py, 2026-11-06).
GOLDEN = {
    'full_two': (dict(inputs={5: M(1.1, .82, .7, .35, 2.4, 3.0, .6, .5), 21: M(.75, .9, .62, .28, 2.1, 6.0, .3, .7)}, turn=20e6), (5, 21), (5, 21),
                 dict(simple=36.809943022618114, complex=59.06218524301239, ss='ok', cs='ok')),
    'no_accel_month': (dict(inputs={5: M(.9, .7, .6, .5, 3.0, 4.0), 21: M(.5, .85, .6, .3, 2.5, 8.0)}, turn=8e6), (5, 21), (5, 21),
                       dict(simple=24.18366857517898, complex=38.745666323877295, ss='ok', cs='ok')),
    'four_periods': (dict(inputs={5: M(1.2, .8, .7, .3, 2.2, 2.5, .4, .6), 21: M(.7, .9, .65, .25, 2.0, 5.0, .2, .8), 63: M(.4, .75, .6, .35, 2.3, 9.0, .1, .7),
                                  126: M(.25, .8, .58, .3, 2.4, 14.0, .05, .6)}, turn=3e6), (5, 21, 63, 126), (5, 21),
                     dict(simple=34.17178042837239, complex=49.64925352715027, ss='ok', cs='ok')),
    'declining_no_liquidity': (dict(inputs={5: M(-.5, .4, .4, 1.0, 3.5, 6.0, -.8, .5), 21: M(.05, .3, .5, .6, 3.1, 10.0, -.2, .4)}, turn=None), (5, 21), (5, 21),
                               dict(simple=0.5407443885922528, complex=0.711702252992812, ss='ok', cs='partiel')),   # liquidité inconnue : poids renormalisés (V4.2), ni zéro ni bonus,
    'optional_week_missing': (dict(inputs={5: None, 21: M(.6, .88, .65, .25, 1.8, 5.0, .1, .8), 63: M(.35, .7, .58, .3, 2.0, 12.0, .05, .6)}, turn=30e6), (5, 21, 63), (21,),
                              dict(simple=29.910954194152865, complex=55.31844002403962, ss='partiel', cs='partiel')),   # semaine sans historique : calculé sur mois + trimestre (V4.2),
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
    assert absent['simple']['score'] == pytest.approx(flat['simple']['score'])                    # V4.3 : l'accélération n'entre plus dans le simple
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
    assert SC.liquidity_note(None) is None and SC.liquidity_note(1e9) == 100


def test_liquidity_note_distinguishes_positive_known_zero_and_unknown():
    assert SC.liquidity_note(10e6) > 0                                    # liquidité positive : note normale
    assert SC.liquidity_note(0) == 0.0 and SC.liquidity_note(0.0) == 0.0   # zéro réel (volumes connus, aucun échange) : note 0, pas « inconnu »
    for unknown in (None, float('nan'), float('inf'), -1.0):               # absent, invalide ou négatif : inconnu
        assert SC.liquidity_note(unknown) is None


def test_known_zero_liquidity_counts_in_the_complex_score_but_unknown_is_left_out():
    P_ = P(21)
    inputs = {21: M(.7, .9, .6, .3, 2, 5, .1, .8)}
    zero = SC.score_title(inputs, {'turnover_eur': 0.0, 'source': 'daily'}, P_)['complex']
    unknown = SC.score_title(inputs, {'turnover_eur': None, 'source': None}, P_)['complex']
    assert zero['contributions']['liquidity']['value'] == 0.0 and not zero['contributions']['liquidity'].get('unavailable')
    assert unknown['contributions']['liquidity'].get('unavailable')
    assert zero['score'] < unknown['score']                                # le zéro réel pèse (poids conservé) ; l'inconnu est renormalisé, ni bonus ni pénalité


def test_recent_anchor_is_progressive_not_brutal():
    def at(week_slope):
        return SC.score_title({5: M(week_slope, .8, .7, .3, 2, 3, 0, .8), 21: M(.7, .9, .6, .3, 2, 5, 0, .8)}, {'turnover_eur': 20e6}, P(5, 21))['complex']
    strong, weak, flat = at(1.2), at(.45), at(0.0)
    assert strong['anchor'] == pytest.approx(1.0) and 0.5 <= flat['anchor'] < weak['anchor'] < 1.0
    assert flat['anchor'] == pytest.approx(0.5)                # un arrêt complet de la semaine retire au plus la moitié, pas tout


def test_simple_score_uses_only_slope_and_r2():
    """V4.3 : pics, séances positives, accélération, volatilité, drawdown et liquidité ne changent pas le score simple ; ils changent le complexe."""
    base = {5: M(1.0, .85, .7, .3, 2, 3, .2, .8), 21: M(.7, .9, .65, .25, 2, 5, .1, .8)}
    other = {5: M(1.0, .85, .3, 1.0, 6, 25, -.5, .8), 21: M(.7, .9, .2, .9, 6, 30, -.5, .8)}
    a, b = SC.score_title(base, {'turnover_eur': 50e6}, P(5, 21)), SC.score_title(other, {'turnover_eur': None}, P(5, 21))
    assert a['simple']['score'] == pytest.approx(b['simple']['score'])
    assert b['complex']['score'] < a['complex']['score'] * 0.8
    assert set(a['simple']['parts']['week']) == {'weight', 'dynamics', 'slope', 'r2', 'r2_reliability'}


def test_simple_score_separates_regular_irregular_flat_and_falling():
    liq = {'turnover_eur': 10e6}
    reg = SC.score_title({5: M(1.0, .92, .7, .3, 2, 3), 21: M(.7, .95, .7, .3, 2, 3)}, liq, P(5, 21))['simple']['score']
    irr = SC.score_title({5: M(1.0, .45, .7, .3, 2, 3), 21: M(.7, .5, .7, .3, 2, 3)}, liq, P(5, 21))['simple']['score']
    flat = SC.score_title({5: M(0.01, .2, .5, .3, 1, 1), 21: M(0.0, .1, .5, .3, 1, 1)}, liq, P(5, 21))['simple']['score']
    down = SC.score_title({5: M(-0.8, .9, .3, .3, 2, 9), 21: M(-.5, .9, .3, .3, 2, 9)}, liq, P(5, 21))['simple']['score']
    assert reg > irr > flat >= down == 0.0 and reg > 2 * irr * 0.9


def test_simple_coverage_counts_periods_with_measured_r2_and_status_is_partial_without_them():
    r = SC.score_title({5: M(1.0, None, .7, .3, 2, 3), 21: M(.7, .9, .65, .25, 2, 5)}, {'turnover_eur': 10e6}, P(5, 21))
    assert r['simple']['status'] == 'partiel' and r['simple']['coverage'] == pytest.approx(0.584, abs=0.001) and r['simple']['score'] is not None


def test_anchor_is_configurable_and_neutral_at_zero():
    inputs = {5: M(0.3, .8, .7, .3, 2, 3, 0, .8), 21: M(.7, .9, .6, .3, 2, 5, 0, .8)}          # semaine lente : g_court < 1
    liq = {'turnover_eur': 20e6}
    off = SC.score_title(inputs, liq, P(5, 21), anchor=0)['complex']
    half = SC.score_title(inputs, liq, P(5, 21), anchor=0.5)['complex']
    full = SC.score_title(inputs, liq, P(5, 21), anchor=1)['complex']
    assert off['anchor'] == 1.0 and off['score'] == pytest.approx(off['raw_total'])             # neutralisé : aucune pénalité
    assert off['score'] > half['score'] > full['score'] and half['raw_total'] == pytest.approx(off['raw_total'])
    assert half['anchor'] == pytest.approx(1 - 0.5 * (1 - half['anchor_gate'])) and 0 <= half['anchor_gate'] < 1
    fast = SC.score_title({5: M(1.5, .8, .7, .3, 2, 3, 0, .8), 21: M(.7, .9, .6, .3, 2, 5, 0, .8)}, liq, P(5, 21), anchor=1)['complex']
    assert fast['anchor'] == pytest.approx(1.0)                                                 # semaine vive : jamais de pénalité

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
def growth_v1_fixture():
    """Configuration riche (jour, semaine, mois, concentration, volatilité, liquidité) pour éprouver les critères de conformité : ce n'est plus une stratégie du produit."""
    c = C.empty()
    by = {p['id']: p for p in c['periods']}
    by['day'].update(enabled=True, min_return=0.0)
    by['week'].update(enabled=True, require_history=True, min_return=3.0)
    by['month'].update(enabled=True, require_history=True, min_return=8.0, min_r2=0.60, max_spike_share=0.45, max_volatility=7.0)
    c['selection'] = {'combine': 'all', 'missing': 'unknown', 'require_fresh': True}
    c['liquidity'] = {'min_quoted_volume': None, 'min_turnover_eur': 2e6, 'min_turnover_eur_us': 5e6}
    c['ranking'] = {'mode': C.SCORES_MODE, 'sort': 'simple'}
    c['scoring'] = {'kappa': 0.7, 'weights': {}, 'complex_weights': {}, 'threshold': 0.75}
    return C.validate(c)



def test_rich_compliance_fixture_keeps_every_threshold_configurable():
    c = growth_v1_fixture()
    by = {p['id']: p for p in c['periods']}
    assert (by['week']['min_return'], by['month']['min_return'], by['month']['min_r2'], by['month']['max_spike_share'], by['month']['max_volatility']) == (3.0, 8.0, .6, .45, 7.0)
    assert c['liquidity']['min_turnover_eur'] == 2e6 and c['liquidity']['min_turnover_eur_us'] == 5e6
    assert c['ranking'] == {'mode': 'scores', 'weights': {}, 'sort': 'simple'}
    assert C.validate(c) == c


def test_last_negative_day_is_a_configurable_criterion_not_a_hard_exclusion():
    c = growth_v1_fixture()
    measures = {1: {'perf': -1.5, 'slope': -1.5, 'r2': None, 'volatility': None}, 5: {'perf': 6.0, 'slope': 1.0, 'r2': .8, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0},
                21: {'perf': 20.0, 'slope': .8, 'r2': .9, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0}}
    tech = {'turnover_eur': 9e6, 'us_listing': False}
    assert S.judge(c, measures, tech, {})['status'] == 'rejected'
    next(p for p in c['periods'] if p['id'] == 'day')['min_return'] = None            # désactivable
    verdict = S.judge(c, measures, tech, {})
    assert verdict['status'] == 'retained' and not any(r['period'] == 'day' for r in verdict['reasons'])


def test_turnover_threshold_differs_for_us_listings_and_reports_the_source():
    c = growth_v1_fixture()
    measures = {n: {'perf': 20.0, 'slope': .8, 'r2': .9, 'volatility': 2, 'spike_share': .2, 'coverage': 1.0} for n in (1, 5, 21)}
    tech = {'turnover_eur': 3e6, 'turnover_source': 'estimated'}
    assert S.judge(c, measures, dict(tech, us_listing=False), {})['status'] == 'retained'
    us = S.judge(c, measures, dict(tech, us_listing=True), {})
    assert us['status'] == 'rejected'
    reason = next(r for r in us['reasons'] if r['criterion'] == 'min_turnover_eur')
    assert reason['threshold'] == 5e6 and reason['source'] == 'estimated' and reason['result'] == 'fail'
    assert S.judge(c, measures, dict(tech, turnover_eur=None), {})['status'] == 'unknown'      # inconnu ≠ échec


def test_scoring_block_validation():
    c = growth_v1_fixture()
    c['scoring'] = {'kappa': 0.5, 'weights': {'week': 1, 'month': 3}, 'complex_weights': {'acceleration': 10}, 'threshold': 0.6}
    assert C.validate(c)['scoring'] == {'kappa': 0.5, 'weights': {'week': 1.0, 'month': 3.0}, 'complex_weights': {'acceleration': 10.0}, 'threshold': 0.6, 'anchor': 0.5, 'sat_a': 17.0, 'accel_ref': 0.4, 'vol_mode': 'absolute', 'momentum_horizon': '6m'}
    for bad in ({'kappa': 1.0}, {'weights': {'nope': 1}}, {'complex_weights': {'nope': 1}}, {'weights': {'week': -1}}, {'threshold': 2}):
        c['scoring'] = bad
        with pytest.raises(ValueError):
            C.validate(c)


def test_every_existing_configuration_gets_default_scoring_without_changing_its_filters():
    old = S.preset('fast')
    up = C.upgrade(old)
    assert up['scoring'] == {'kappa': 0.7, 'weights': {}, 'complex_weights': {}, 'threshold': 0.75, 'anchor': 0.5, 'sat_a': 17.0, 'accel_ref': 0.4, 'vol_mode': 'absolute', 'momentum_horizon': '6m'}
    assert up['ranking']['mode'] == 'performance'                  # le classement historique est conservé tel quel


def test_score_parameters_ignore_every_compliance_threshold():
    """Clé de cache et paramètres de score : identiques quand seuls des critères de conformité changent."""
    a, b = growth_v1_fixture(), growth_v1_fixture()
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
    from engine.analytics.explorer.explorer_metrics import path_metrics
    m = path_metrics([100, 101, 140, 141, 142])
    assert m['spike_share'] == pytest.approx(math.log1p(140 / 101 - 1) / math.log(1.42))
    assert path_metrics([100, 99, 98])['spike_share'] == 1.0


def test_real_zero_volumes_give_a_known_zero_turnover_not_unknown():
    bars = [(10.0, 0)] * 20
    r = LQ.liquidity(bars, 10.0, 500000, 1.0)
    assert r == {'turnover_eur': 0.0, 'days': 20, 'source': 'daily'}      # 20 séances à volume nul : liquidité réelle nulle, pas l'estimation
    few = LQ.liquidity([(10.0, 0)] * 5, 10.0, 500000, 1.0)
    assert few['source'] == 'estimated' and few['turnover_eur'] == 10.0 * 500000   # moins de 15 séances à volume réel : repli sur l'estimation
    nothing = LQ.liquidity([(10.0, None)] * 20, None, None, 1.0)
    assert nothing['turnover_eur'] is None and nothing['source'] is None   # aucune donnée : inconnue


# ───────────── réglages de normalisation propres à chaque stratégie (saturation, accélération, volatilité, momentum) ─────────────

def _m(slope, accel=None, r2=0.9, r2p=0.9, vol=1.0):
    return {'slope': slope, 'r2': r2, 'volatility': vol, 'drawdown': 3.0, 'up_fraction': 0.8, 'spike_share': 0.3, 'accel': accel, 'r2_prev': r2p}


def test_sat_a_default_keeps_previous_behaviour_and_higher_value_separates_strong_moves():
    assert SC.saturation(5) == 17.0 and SC.saturation(5, 40.0) == 40.0
    strong, extreme = _m(3.5), _m(10.7)
    d17 = [SC.period_components(x, 5)['dynamics'] for x in (strong, extreme)]
    assert d17 == [100.0, 100.0]                                             # comportement actuel : saturé
    d40 = [SC.period_components(x, 5, sat_a=40.0)['dynamics'] for x in (strong, extreme)]
    assert d40[0] < 60 < d40[1] and d40[1] == 100.0                           # SAT_A = 40 : l'intensité redevient visible
    d21 = [SC.period_components(x, 21, sat_a=40.0)['dynamics'] for x in (_m(1.0), _m(3.2))]
    assert d21[0] < d21[1]                                                    # toutes granularités : la saturation suit (n/5)^0,52


def test_accel_ref_coefficient_changes_the_acceleration_note_only():
    a, b = SC.period_components(_m(3.0, accel=2.0), 5, accel_ref=0.4), SC.period_components(_m(3.0, accel=2.0), 5, accel_ref=2.0)
    assert a['acceleration'] == pytest.approx(100.0) and b['acceleration'] < 100.0
    assert a['dynamics'] == b['dynamics']
    # garde-fou de régularité explicite
    irregular = SC.period_components(_m(3.0, accel=5.0, r2=0.3, r2p=0.9), 5)
    assert irregular['accel_reliability'] == pytest.approx(0.5) and irregular['acceleration'] == pytest.approx(75.0)


def test_acceleration_edge_cases():
    neg = SC.period_components(_m(1.0, accel=-3.0), 5)
    assert neg['acceleration'] == pytest.approx(0.0, abs=1e-9) or neg['acceleration'] < 50          # retournement : note < 50, jamais favorable
    assert SC.period_components(_m(1.0, accel=None), 5)['acceleration'] is None                     # historique insuffisant : absent, pas 0
    assert SC.period_components(_m(1.0, accel=2.0, r2=None), 5)['acceleration'] is None             # R² indisponible : absent
    assert SC.period_components(_m(-2.0, accel=-1.0), 5)['dynamics'] == 0.0


def test_relative_volatility_mode_rewards_strong_smooth_moves_and_keeps_guards():
    assert SC.vol_note(2.0, 0.1, 'relative') == 0.0 or SC.vol_note(2.0, 0.1, 'relative') < 1        # pente quasi nulle : plancher, aucune division instable
    assert SC.vol_note(4.0, 8.0, 'relative') == 100.0 and SC.vol_note(4.0, 8.0, 'absolute') == 25.0
    assert SC.vol_note(4.0, -2.0, 'relative') == 0.0                                                # pente négative : jamais favorable
    assert SC.vol_note(None, 3.0, 'relative') is None and SC.vol_note(2.0, None, 'relative') is None
    # le drawdown et la liquidité restent notés indépendamment
    liq = {'turnover_eur': 1e5}
    exp = {5: _m(8.0, accel=2.0, vol=4.0), 21: _m(3.0, accel=1.0, vol=4.0)}
    rel = SC.score_title(exp, liq, P(5, 21), vol_mode='relative')['complex']
    ab = SC.score_title(exp, liq, P(5, 21), vol_mode='absolute')['complex']
    assert rel['score'] > ab['score']
    assert rel['contributions']['liquidity']['value'] == ab['contributions']['liquidity']['value'] == 0.0 or rel['contributions']['liquidity']['value'] < 10


def test_momentum_component_zero_by_default_and_horizons():
    inputs = {5: _m(1.0, accel=0.1), 21: _m(0.6, accel=0.1)}
    base = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21))['complex']
    assert 'momentum' not in base['contributions']                                                    # poids 0 par défaut : rien ne change
    cw = {'dynamics': 50, 'momentum': 50}
    s6 = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights=dict(cw, r2=0, up_days=0, concentration=0, volatility=0, drawdown=0, liquidity=0), momentum={'6m': 30.0, '12m': 100.0}, momentum_horizon='6m')['complex']
    assert s6['contributions']['momentum']['value'] == pytest.approx(50.0)
    s12 = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights=dict(cw, r2=0, up_days=0, concentration=0, volatility=0, drawdown=0, liquidity=0), momentum={'6m': 30.0, '12m': 100.0}, momentum_horizon='12m')['complex']
    assert s12['contributions']['momentum']['value'] == pytest.approx(100.0)
    assert SC.momentum_note({'6m': -20.0}, '6m') == 0.0 and SC.momentum_note({}, 'blend') is None
    miss = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights={'dynamics': 50, 'momentum': 50}, momentum=None)['complex']
    assert miss['contributions']['momentum'].get('unavailable')                                       # donnée absente : sort du calcul, ni 0 ni bonus


def test_validate_scoring_bounds_for_new_parameters():
    ok = C.validate_scoring({'sat_a': 40, 'accel_ref': 1.2, 'vol_mode': 'relative', 'momentum_horizon': 'blend'}, [])
    assert (ok['sat_a'], ok['accel_ref'], ok['vol_mode'], ok['momentum_horizon']) == (40.0, 1.2, 'relative', 'blend')
    for bad in ({'sat_a': 1}, {'sat_a': 1000}, {'accel_ref': 0}, {'accel_ref': 99}, {'vol_mode': 'x'}, {'momentum_horizon': '3m'}):
        with pytest.raises(ValueError):
            C.validate_scoring(bad, [])


def test_recovery_note_rewards_a_half_year_that_has_not_progressed():
    assert SC.recovery_note(-15.0) == 100.0 and SC.recovery_note(20.0) == 0.0 and SC.recovery_note(60.0) == 0.0
    assert SC.recovery_note(5.0) == pytest.approx(50.0) and SC.recovery_note(None) is None
    inputs = {5: _m(2.0, accel=1.0), 21: _m(1.0, accel=0.5)}
    cw = dict(dynamics=50, recovery=50, r2=0, up_days=0, concentration=0, volatility=0, drawdown=0, liquidity=0, acceleration=0)
    flat = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights=cw, recovery_perf=-5.0)['complex']
    ran = SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights=cw, recovery_perf=40.0)['complex']
    assert flat["score"] > ran["score"] and flat["contributions"]["recovery"]["value"] == pytest.approx(SC.recovery_note(-5.0))
    assert SC.score_title(inputs, {'turnover_eur': 2e7}, P(5, 21), complex_weights=cw)['complex']['contributions']['recovery'].get('unavailable')


# ───────────── score complexe : dénominateur cohérent avec le numérateur (V4.5) ─────────────

LIQ = {'turnover_eur': 20e6, 'source': 'daily'}


def legacy_complex(res):
    """Ancienne normalisation (≤ V4.4), reconstruite depuis les contributions : le dénominateur pondérait chaque composante par la part de périodes mesurées,
    le numérateur non. Sert uniquement à prouver la différence de rang avec la version corrigée."""
    ct = res['complex']['contributions']
    av = [v for v in ct.values() if v.get('value') is not None]
    return sum(v['points'] for v in av) / sum(v['weight'] * v.get('coverage', 1.0) for v in av) * res['complex']['anchor']


def test_complex_with_partial_components_is_a_plain_weighted_average():
    inputs = {5: M(.7, .85, None, None, None, None, .1, .8), 21: M(.8, .88, .8, .1, 1.2, 2.0, .1, .8)}      # séances positives, pics, volatilité, drawdown : mois seulement
    r = SC.score_title(inputs, LIQ, P(5, 21))
    c = r['complex']
    eff, per, ct = r['weights_effective'], r['periods'], c['contributions']
    notes = {}
    for key, v in ct.items():
        if v.get('value') is None:
            continue
        if key == 'liquidity':
            notes[key] = (v['weight'], r['liquidity']['note'])
            continue
        num = den = 0.0
        for pid, comp in per.items():
            if comp is None or comp.get(key) is None:
                continue
            gate = 1.0 if key in ('dynamics', 'acceleration') else comp['gate']
            num += eff[pid] * gate * comp[key]; den += eff[pid]
        notes[key] = (v['weight'], num / den)                      # note de la composante = moyenne sur les seules périodes mesurées
    expected = sum(w * s for w, s in notes.values()) / sum(w for w, _ in notes.values())          # puis moyenne pondérée par le poids ENTIER de chaque composante
    assert c['raw_total'] == pytest.approx(expected, rel=1e-12)
    assert c['score'] == pytest.approx(expected * c['anchor'], rel=1e-12)
    assert c['status'] == 'partiel' and c['coverage'] < 1                # la fiabilité continue de signaler les données partielles


def test_effective_weights_and_points_add_up_to_the_raw_total():
    r = SC.score_title({5: M(.7, .85, None, None, None, None, .1, .8), 21: M(.8, .88, .8, .1, 1.2, 2.0, .1, .8)}, LIQ, P(5, 21))
    ct = [v for v in r['complex']['contributions'].values() if v.get('value') is not None]
    assert sum(v['weight_effective'] for v in ct) == pytest.approx(1.0)
    assert sum(v['points_effective'] for v in ct) == pytest.approx(r['complex']['raw_total'])


def test_full_data_scores_are_unchanged_by_the_correction():
    inputs = {5: M(1.0, .85, .6, .3, 2.2, 6.0, .1, .8), 21: M(.8, .88, .62, .3, 2.0, 7.0, .1, .8)}
    r = SC.score_title(inputs, LIQ, P(5, 21))
    assert r['complex']['score'] == pytest.approx(legacy_complex(r), rel=1e-12)


def test_partial_data_can_no_longer_outrank_a_complete_title_by_inflation():
    complete = SC.score_title({5: M(1.0, .85, .6, .3, 2.2, 6.0, .1, .8), 21: M(.8, .88, .62, .3, 2.0, 7.0, .1, .8)}, LIQ, P(5, 21))
    partial = SC.score_title({5: M(.7, .85, None, None, None, None, .1, .8), 21: M(.8, .88, .8, .1, 1.2, 2.0, .1, .8)}, LIQ, P(5, 21))
    assert legacy_complex(partial) > complete['complex']['score']                  # avant : le titre incomplet passait devant (64,1 contre 55,9)
    assert partial['complex']['score'] < complete['complex']['score']              # après : l'ordre des deux titres s'inverse (54,7 contre 55,9)
    assert partial['complex']['score'] == pytest.approx(54.73, abs=0.01) and legacy_complex(partial) == pytest.approx(64.06, abs=0.01)


def test_complex_score_stays_within_0_and_100_whatever_data_is_missing():
    import random
    rng = random.Random(20261107)
    keys = list(SC.COMPLEX_WEIGHTS)
    worst = 0.0
    for _ in range(4000):
        sessions = rng.choice([(5, 21), (21, 63), (5, 21, 63), (126, 252), (5, 21, 63, 126, 252)])
        inputs = {}
        for n in sessions:
            if rng.random() < .1:
                inputs[n] = None
                continue
            m = M(rng.uniform(-1.5, 12), rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(.1, 8), rng.uniform(0, 40), rng.uniform(-3, 3), rng.uniform(0, 1))
            for k in ('r2', 'up_fraction', 'spike_share', 'volatility', 'drawdown', 'accel', 'r2_prev'):
                if rng.random() < .3:
                    m[k] = None
            inputs[n] = m
        cw = {k: rng.choice([0, 0, 5, 10, 40, 80]) for k in keys}
        r = SC.score_title(inputs, {'turnover_eur': rng.choice([None, 0, 3e6, 80e6]), 'source': 'daily'}, P(*sessions), complex_weights=cw,
                           momentum=rng.choice([None, {'6m': rng.uniform(-30, 80), '12m': rng.uniform(-30, 150)}]), momentum_horizon=rng.choice(['6m', '12m', 'blend']),
                           recovery_perf=rng.choice([None, rng.uniform(-40, 60)]), vol_mode=rng.choice(['absolute', 'relative']))
        s = r['complex']['score']
        if s is None:
            continue
        assert math.isfinite(s) and -1e-9 <= s <= 100 + 1e-9, (sessions, inputs, cw, s)
        worst = max(worst, s)
    assert worst > 50          # le test a bien exercé des scores élevés


def test_score_version_changes_so_cached_scores_are_recomputed():
    assert SC.VERSION >= 5


def test_rank_order_shares_rank_only_for_strictly_identical_raw_scores():
    scores = {1: 50.0, 2: 50.0, 3: 50.004, 4: 10.0, 5: None}
    order, ranks = SC.rank_order(scores)
    assert order == [3, 1, 2, 4]
    assert ranks == {3: 1, 1: 2, 2: 2, 4: 4}          # 50.004 et 50.0 s'affichent pareil mais ne sont pas ex æquo


def test_rank_order_secondary_score_then_numeric_id_make_the_order_deterministic():
    scores = {10: 40.0, 9: 40.0, 11: 40.0}
    order, _ = SC.rank_order(scores, {10: 5.0, 9: 5.0, 11: 80.0})
    assert order == [11, 9, 10]                         # autre score d'abord, puis identifiant numérique (9 avant 10)
    assert SC.rank_order(dict(reversed(list(scores.items()))), {10: 5.0, 9: 5.0, 11: 80.0})[0] == order


def test_rank_positions_stays_the_legacy_position_rank():
    assert SC.rank_positions({2: 9.0, 4: 7.0, 1: 7.0, 3: None}) == {2: 1, 1: 2, 4: 3}
