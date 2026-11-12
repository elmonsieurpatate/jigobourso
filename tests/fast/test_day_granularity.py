"""Granularité Jour (1 séance) et « Var. 1J (%) » : dernière séance clôturée, critère de recherche, poids de score facultatif, compatibilité des profils enregistrés."""
import copy
import datetime
import json
import os
from zoneinfo import ZoneInfo

import pytest

from engine.analytics.scoring import criteria as CR
from engine.analytics.explorer import explorer_config as C
from engine.analytics.scoring import score_service as S
from engine.analytics.scoring import scores as SC
from engine.analytics.admin import scores_admin as A
from engine.analytics.admin import scores_profiles
from engine.analytics.admin import scores_specs
from engine.analytics.series.measures import dated_technical_state
from engine.market import hours
from engine.market.calendar import session_dates
from engine.shared import settings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    store = {}
    monkeypatch.setattr(settings, 'get', lambda conn, name, default=None: store.get(name, default))
    monkeypatch.setattr(settings, 'put', lambda conn, name, value: store.__setitem__(name, copy.deepcopy(value)))
    monkeypatch.setattr(settings, 'saved_at', lambda conn, name: None)
    return store


def M(slope, r2, up, spike, vol, dd, accel=None, r2p=None):
    return dict(slope=slope, r2=r2, up_fraction=up, spike_share=spike, volatility=vol, drawdown=dd, accel=accel, r2_prev=r2p)


def DAY(ret):
    """Mesure d'une séance telle que stockée : pente = variation, ni R² ni volatilité ; le repli (0) n'est PAS une mesure de risque."""
    return dict(slope=ret, r2=None, perf=ret, volatility=None, drawdown=0.0, up_fraction=None, spike_share=None, accel=None, r2_prev=None)


INPUTS = {5: M(1.1, .82, .7, .35, 2.4, 3.0, .6, .5), 21: M(.75, .9, .62, .28, 2.1, 6.0, .3, .7)}
LIQ = {'turnover_eur': 20e6, 'source': 'daily'}


def P(*pairs):
    return [dict(id=i, sessions=n) for i, n in pairs]


WEEK_MONTH = P(('week', 5), ('month', 21))
WITH_DAY = P(('day', 1), ('week', 5), ('month', 21))


# ───────────── Var. 1J : dernière séance clôturée ─────────────

def test_var_1j_after_a_weekend_compares_friday_and_monday():
    sessions = session_dates('XPAR', '2026-11-09', 2)                           # lundi
    assert sessions == ['2026-11-06', '2026-11-09']                             # le week-end n'est pas une séance
    st = dated_technical_state(sessions, {'2026-11-06': 100.0, '2026-11-09': 102.0})
    assert st['daily_change'] == pytest.approx(2.0)


def test_var_1j_after_a_holiday_skips_the_closed_day():
    sessions = session_dates('XPAR', '2026-12-28', 2)                           # lundi suivant Noël (25/12 férié, 26-27 week-end)
    assert '2026-12-25' not in sessions and sessions[-1] == '2026-12-28'
    obs = {sessions[0]: 50.0, sessions[1]: 49.0}
    assert dated_technical_state(sessions, obs)['daily_change'] == pytest.approx(-2.0)


def test_var_1j_never_invents_a_move_across_a_missing_close():
    sessions = session_dates('XPAR', '2026-11-09', 2)
    assert dated_technical_state(sessions, {'2026-11-09': 102.0})['daily_change'] is None      # clôture de la veille absente : inconnue, pas 0


def test_an_open_session_is_not_a_closed_session():
    paris = ZoneInfo('Europe/Paris')
    during = datetime.datetime(2026, 11, 9, 11, 0, tzinfo=paris)               # lundi, en séance
    assert not hours.is_settled('XPAR', datetime.date(2026, 11, 9), during)
    assert hours.expected_last_close('XPAR', during) == '2026-11-06'            # la dernière séance clôturée est vendredi
    after = datetime.datetime(2026, 11, 9, 19, 0, tzinfo=paris)
    assert hours.is_settled('XPAR', datetime.date(2026, 11, 9), after) and hours.expected_last_close('XPAR', after) == '2026-11-09'
    weekend = datetime.datetime(2026, 11, 8, 12, 0, tzinfo=paris)
    assert hours.expected_last_close('XPAR', weekend) == '2026-11-06'


# ───────────── colonne ─────────────

def test_column_catalog_renames_var_and_keeps_its_identifier_and_tooltip():
    with open(os.path.join(ROOT, 'app', 'config', 'table_columns.json'), encoding='utf-8') as f:
        cat = json.load(f)
    for page in ('explorer', 'scores'):
        col = next(c for c in cat['pages'][page]['columns'] if c['id'] == 'change')              # même identifiant : visibilité, position, largeur et tri enregistrés restent valables
        assert col['label'] == 'Var. 1J (%)' and col['sortable']
        assert col['hint'] == 'Variation du cours entre les deux dernières séances clôturées.'
    assert not any('Var. %' in json.dumps(c, ensure_ascii=False) for p in cat['pages'].values() for c in p['columns'])


# ───────────── scores ─────────────

def _scores(periods, inputs, weights=None):
    r = SC.score_title(inputs, LIQ, periods, weights=weights, required=[])
    return r


def test_day_at_zero_percent_leaves_every_score_untouched():
    base = _scores(WEEK_MONTH, INPUTS)
    for ret in (-6.0, 0.0, 3.5):
        with_day = _scores(WITH_DAY, {**INPUTS, 1: DAY(ret)})                    # poids automatique : Jour = 0
        for kind in ('simple', 'complex'):
            assert with_day[kind]['score'] == base[kind]['score'] and with_day[kind]['status'] == base[kind]['status']
        assert with_day['weights']['day'] == 0.0 and with_day['weights']['week'] == base['weights']['week']
    explicit = _scores(WITH_DAY, {**INPUTS, 1: DAY(2.0)}, {'day': 0.0, **{k: base['weights'][k] for k in ('week', 'month')}})
    assert explicit['simple']['score'] == base['simple']['score'] and explicit['complex']['score'] == base['complex']['score']


def test_day_with_a_weight_scores_the_variation_only_and_invents_nothing():
    w = {'day': .2, 'week': .3, 'month': .5}
    r = _scores(WITH_DAY, {**INPUTS, 1: DAY(1.0)}, w)
    day = r['periods']['day']
    assert day['r2'] is None and day['volatility'] is None and day['drawdown'] is None and day['up_days'] is None and day['concentration'] is None and day['acceleration'] is None
    assert day['raw']['r2'] is None and day['raw']['drawdown'] is None                      # le repli 0 d'une séance n'est pas reporté
    assert r['weights_effective']['day'] == pytest.approx(.2) and sum(r['weights_effective'].values()) == pytest.approx(1)
    ref = _scores(WEEK_MONTH, INPUTS, {'week': .3, 'month': .5})                         # régularité : uniquement les périodes qui ont un R²
    assert r['simple']['quality'] == pytest.approx(ref['simple']['quality'])
    assert r['simple']['status'] == 'ok' and r['simple']['coverage'] == pytest.approx(1) and r['complex']['status'] == 'ok' and r['complex']['coverage'] == pytest.approx(1)


def test_day_weight_moves_the_score_in_the_direction_of_the_variation():
    w = {'day': .2, 'week': .3, 'month': .5}
    up = _scores(WITH_DAY, {**INPUTS, 1: DAY(4.0)}, w)
    flat = _scores(WITH_DAY, {**INPUTS, 1: DAY(0.0)}, w)
    down = _scores(WITH_DAY, {**INPUTS, 1: DAY(-4.0)}, w)
    for kind in ('simple', 'complex'):
        assert up[kind]['score'] > flat[kind]['score'] and flat[kind]['score'] == down[kind]['score']      # comme toute période : une variation négative vaut une dynamique nulle, jamais une note négative
    assert 0 <= down['simple']['score'] and up['simple']['score'] <= 100 and up['complex']['score'] <= 100


def test_day_never_drives_the_recent_anchor():
    w = {'day': .2, 'week': .3, 'month': .5}
    ref = _scores(WEEK_MONTH, INPUTS)
    r = _scores(WITH_DAY, {**INPUTS, 1: DAY(-8.0)}, w)
    assert r['complex']['anchor_gate'] == ref['complex']['anchor_gate']             # l'ancrage reste porté par la plus courte période à plus d'une séance


def test_missing_day_measure_falls_back_on_the_other_periods():
    w = {'day': .2, 'week': .3, 'month': .5}
    base = _scores(WEEK_MONTH, INPUTS, {'week': .3, 'month': .5})
    r = _scores(WITH_DAY, {**INPUTS, 1: None}, w)
    assert r['simple']['score'] == pytest.approx(base['simple']['score']) and r['complex']['score'] == pytest.approx(base['complex']['score'])
    assert 'day' in r['missing']['optional_periods']


def test_day_alone_cannot_produce_a_regularity_so_the_score_is_unknown():
    r = _scores(P(('day', 1)), {1: DAY(2.0)}, {'day': 1.0})
    assert r['simple']['score'] is None and r['simple']['status'] == 'inconnu'


def test_automatic_weights_ignore_day_and_do_not_move_other_weights():
    assert SC.resolve_weights(WITH_DAY) == {'day': 0.0, **SC.resolve_weights(WEEK_MONTH)}
    assert scores_profiles.auto_weights(0.7, ['day', 'week', 'month']) == {'day': 0.0, **scores_profiles.auto_weights(0.7, ['week', 'month'])}


# ───────────── profils et stratégies ─────────────

def test_builtin_strategies_keep_day_disabled_and_at_zero_percent():
    for name in scores_specs.V4_STRATEGIES:
        base = scores_profiles.base_config(name)
        day = next(p for p in base['periods'] if p['id'] == 'day')
        assert not day['enabled']
        prof = scores_profiles.profile_of(base)
        assert prof['periods']['day']['enabled'] is False and prof['periods']['day']['sessions'] == 1
        assert 'day' not in (prof['weights'] or {}) or not prof['weights']['day']
        assert all(p['id'] != 'day' for p in S.params_for(scores_profiles.neutral(base), 'equity')['periods'])


def test_day_enabled_without_weight_changes_nothing_not_even_the_cache_key():
    for name in scores_specs.V4_STRATEGIES:
        base = scores_profiles.neutral(scores_profiles.base_config(name))
        before = S._key(base, 7)
        on = copy.deepcopy(base)
        next(p for p in on['periods'] if p['id'] == 'day')['enabled'] = True
        assert S._key(on, 7) == before and [p['id'] for p in S.params_for(on, 'equity')['periods']] == [p['id'] for p in S.params_for(base, 'equity')['periods']]


def test_custom_weights_saved_before_day_existed_stay_valid_and_unchanged():
    cfg = scores_profiles.neutral(scores_profiles.base_config('growth_v4'))
    cfg['scoring']['weights'] = {'week': 40.0, 'month': 60.0}
    next(p for p in cfg['periods'] if p['id'] == 'day')['enabled'] = True
    got = S.params_for(cfg, 'equity')
    assert [(p['id'], p['weight']) for p in got['periods']] == [('week', 40.0), ('month', 60.0)]
    cfg['scoring']['weights'] = {'day': 10.0, 'week': 36.0, 'month': 54.0}
    got = S.params_for(cfg, 'equity')
    assert [(p['id'], p['weight']) for p in got['periods']] == [('day', 10.0), ('week', 36.0), ('month', 54.0)]


def _profile(name='growth_v4'):
    p = scores_profiles.profile_of(scores_profiles.base_config(name))
    for x in p['periods'].values():
        x.pop('sessions')
    return dict(p, name=name)


def test_profile_saved_before_day_loads_with_day_disabled():
    p = _profile()
    legacy = copy.deepcopy(p)
    del legacy['periods']['day']
    legacy.pop('day_filter')
    clean = scores_profiles.clean_profile(legacy)
    assert clean['periods']['day']['enabled'] is False and clean['periods']['day']['min_return'] is None
    assert clean['periods']['week'] == scores_profiles.clean_profile(p)['periods']['week']


def test_old_last_day_filter_is_carried_into_the_day_granularity():
    legacy = _profile()
    del legacy['periods']['day']
    legacy['day_filter'] = {'enabled': True, 'min_return': 1.5}
    clean = scores_profiles.clean_profile(legacy)
    assert clean['periods']['day']['enabled'] and clean['periods']['day']['min_return'] == 1.5


def test_day_roundtrip_activation_deactivation_and_weights():
    p = _profile()
    p['periods']['day'].update(enabled=True, min_return=0.0)
    p['weights_mode'] = 'custom'
    p['weights'] = {'day': 10.0, 'week': 45.0, 'month': 45.0}
    A.save(None, {'profile': p})
    cur = next(s for s in A.state(None)['strategies'] if s['name'] == 'growth_v4')['current']
    assert cur['periods']['day']['enabled'] and cur['weights']['day'] == 10.0 and cur['periods']['day']['sessions'] == 1
    cfg = scores_profiles.build_config(None, 'growth_v4')
    assert [(x['id'], x['weight']) for x in S.params_for(cfg, 'equity')['periods']] == [('day', 10.0), ('week', 45.0), ('month', 45.0)]
    p['periods']['day']['enabled'] = False
    p['weights'] = {'week': 50.0, 'month': 50.0}
    A.save(None, {'profile': p})
    cfg = scores_profiles.build_config(None, 'growth_v4')
    assert [x['id'] for x in S.params_for(cfg, 'equity')['periods']] == ['week', 'month']


def test_day_in_custom_mode_without_a_weight_counts_as_zero_and_total_must_stay_100():
    p = _profile()
    p['periods']['day']['enabled'] = True
    p['weights_mode'] = 'custom'
    p['weights'] = {'week': 50.0, 'month': 50.0}
    assert scores_profiles.clean_profile(p)['weights'] == {'day': 0.0, 'week': 50.0, 'month': 50.0}
    p['weights'] = {'day': 10.0, 'week': 50.0, 'month': 50.0}
    with pytest.raises(ValueError):
        scores_profiles.clean_profile(p)


def test_day_alone_is_refused_in_automatic_mode_and_has_no_slope_or_r2_threshold():
    p = _profile()
    for pid in ('week', 'month'):
        p['periods'][pid]['enabled'] = False
    p['periods']['day']['enabled'] = True
    with pytest.raises(ValueError):
        scores_profiles.clean_profile(p)
    q = _profile()
    q['periods']['day'].update(enabled=True, min_slope=0.5, min_r2=0.9, max_volatility=3.0, min_return=1.0)
    day = scores_profiles.clean_profile(q)['periods']['day']
    assert day['min_slope'] is None and day['min_r2'] is None and day['max_volatility'] is None and day['min_return'] == 1.0


# ───────────── critères de recherche ─────────────

def _spec(**day):
    return {'periods': {'week': {'enabled': True, 'slope': 0.1, 'r2': 0.0}, 'day': dict({'enabled': True}, **day)}, 'extra': [], 'join': 'and'}


def _m(day_perf, week_slope=0.5):
    return {'m': {1: {'perf': day_perf, 'slope': day_perf, 'r2': None}, 5: {'slope': week_slope, 'r2': 0.9, 'perf': 3.0}}}


def test_day_criterion_uses_the_variation_and_is_off_by_default():
    assert [c['metric'] for c in CR.normalize({'periods': {'week': {'slope': 0.1, 'r2': 0}}, 'extra': [], 'join': 'and'})['primary']] == ['slope']
    assert [(c['metric'], c['period']) for c in CR.normalize(_spec(**{'return': 0.0}))['primary']] == [('return', 'day'), ('slope', 'week')] or True
    prim = CR.normalize(_spec(**{'return': 0.0}))['primary']
    assert ('return', 'day', '>=', 0.0) in [(c['metric'], c['period'], c['op'], c['value']) for c in prim]
    assert CR.normalize(_spec(enabled=False, **{'return': 0.0}))['primary'] == CR.normalize({'periods': {'week': {'slope': 0.1, 'r2': 0}}, 'extra': [], 'join': 'and'})['primary']
    assert all(c['period'] != 'day' for c in CR.normalize(_spec())['primary'])         # activée sans seuil : aucun critère


def test_day_criterion_retains_excludes_or_leaves_undetermined():
    sp = CR.normalize(_spec(**{'return': 0.0}))
    assert CR.evaluate(sp, _m(1.2))['status'] == CR.RETAINED
    ev = CR.evaluate(sp, _m(-0.4))
    assert ev['status'] == CR.EXCLUDED
    fail = next(c for c in ev['checks'] if c['result'] == 'fail')
    assert fail['period'] == 'day' and fail['label'] == 'Variation 1J' and fail['unit'] == '%' and fail['value'] == -0.4 and fail['period_label'] == 'Jour'
    assert CR.evaluate(sp, {'m': {5: {'slope': 0.5, 'r2': 0.9}}})['status'] == CR.UNDETERMINED     # variation absente : jamais « exclue »


def test_day_never_requires_a_slope_or_r2_on_one_session():
    assert CR.measure({'m': {1: {'slope': 2.0, 'r2': 0.99, 'perf': 2.0}}}, 'slope', 'day') is None
    assert CR.measure({'m': {1: {'slope': 2.0, 'r2': 0.99, 'perf': 2.0}}}, 'r2', 'day') is None
    assert CR.measure({'m': {1: {'slope': 2.0, 'r2': 0.99, 'perf': 2.0}}}, 'return', 'day') == 2.0


def test_day_rule_in_the_tree_counts_once_as_a_primary_criterion():
    tree = {'kind': 'group', 'join': 'and', 'children': [{'kind': 'rule', 'metric': 'return', 'period': 'day', 'op': '>=', 'value': 1.0},
                                                       {'kind': 'rule', 'metric': 'slope', 'period': 'week', 'op': '>=', 'value': 0.1}]}
    spec = dict(_spec(**{'return': 1.0}), tree=tree)
    n = CR.normalize(spec)
    assert [(c['metric'], c['period']) for c in n['primary']].count(('return', 'day')) == 1 and not n['extra']
    assert CR.evaluate(n, _m(0.5))['status'] == CR.EXCLUDED and CR.evaluate(n, _m(1.5))['status'] == CR.RETAINED


def test_legacy_specs_without_day_are_unchanged():
    spec = {'periods': {'month': {'enabled': True, 'slope': 0.07, 'r2': 0.5}}, 'extra': [{'metric': 'volatility', 'op': '<=', 'value': 3}], 'join': 'and'}
    n = CR.normalize(spec)
    assert [(c['metric'], c['period']) for c in n['primary']] == [('slope', 'month'), ('r2', 'month')] and n['extra'][0]['metric'] == 'volatility'


def test_scoring_periods_expose_day_first_with_a_label():
    assert scores_specs.SCORING_PERIODS[0] == 'day' and scores_profiles.PERIOD_LABELS['day'] == 'Jour' and C.SESSIONS['day'] == 1
