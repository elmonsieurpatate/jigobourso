"""Administration des scores : un moteur commun, des profils de stratégie validés, des réglages communs superposés sans jamais toucher à la conformité."""
import copy

import pytest

from engine.analytics.explorer import explorer_config as C
from engine.analytics.scoring import score_service as S
from engine.analytics.scoring import scores as SC
from engine.analytics.admin import scores_admin as A
from engine.shared import settings


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    store = {}
    monkeypatch.setattr(settings, 'get', lambda conn, name, default=None: store.get(name, default))
    monkeypatch.setattr(settings, 'put', lambda conn, name, value: store.__setitem__(name, copy.deepcopy(value)))
    monkeypatch.setattr(settings, 'saved_at', lambda conn, name: None)
    return store


def profile(name='growth_v4'):
    p = A.profile_of(A.base_config(name))
    for x in p['periods'].values():
        x.pop('sessions')
    return dict(p, name=name)


def row(state, name='growth_v4'):
    return next(s for s in state['strategies'] if s['name'] == name)


def test_defaults_are_design_values():
    st = A.state(None)
    assert st['global'] == {'kappa': 0.7, 'threshold': 0.75, 'anchor': 0.5, 'customised': False, 'saved_at': None}
    g = row(st)
    assert g['current']['complex_weights'] == SC.COMPLEX_WEIGHTS and g['current']['weights_mode'] == 'auto' and not g['customised']
    assert [k for k, x in g['current']['periods'].items() if x['enabled']] == ['week', 'month']


def test_auto_weights_follow_kappa_and_active_set():
    w = A.auto_weights(0.7, ['week', 'month'])
    assert round(w['week'], 1) == 41.6 and round(w['month'], 1) == 58.4
    for n in range(1, 6):
        ids = [p for p in A.SCORING_PERIODS if p != 'day'][:n]
        assert sum(A.auto_weights(0.7, ids).values()) == pytest.approx(100)
        assert A.auto_weights(0.7, ['day'] + ids) == {'day': 0.0, **A.auto_weights(0.7, ids)}      # Jour n'a jamais de poids automatique et ne déplace aucun autre poids
    assert A.auto_weights(0.5, ['week', 'month'])['week'] < A.auto_weights(0.7, ['week', 'month'])['week']      # κ plus bas : poids aux longues périodes
    assert A.auto_weights(0.7, []) == {}


def test_state_exposes_exactly_the_seven_v4_strategies_and_no_legacy_engine():
    sts = A.state(None)['strategies']
    labels = {s['name']: s['label'] for s in sts}
    assert list(labels) == ['growth_regular', 'growth_v4', 'rebound', 'calm_rise', 'momentum_6m', 'momentum_12m', 'momentum_risk']
    assert all(s['engine'] == 'v4' for s in sts)
    assert len({v for v in labels.values()}) == len(labels)                        # aucun libellé en double
    assert [v for v in labels.values() if v.startswith('Croissance rapide')] == ['Croissance rapide']      # une seule « Croissance rapide »
    assert 'growth_v1' not in labels


def test_historic_strategies_have_distinct_real_settings():
    built = {n: A.base_config(n)['scoring'] for n in A.V4_STRATEGIES}
    cw = {n: tuple(sorted(c['complex_weights'].items())) for n, c in built.items()}
    assert len(set(cw.values())) == len(cw) - 1 or len(set(cw.values())) == len(cw)      # growth_v4 : poids de conception ({}), les six autres ont les leurs
    assert built['growth_v4']['sat_a'] == 17.0 and built['growth_v4']['accel_ref'] == 0.4 and built['growth_v4']['complex_weights'] == {}      # Croissance rapide inchangée
    assert built['rebound']['accel_ref'] < 0.4 and built['rebound']['complex_weights']['acceleration'] == 20 and built['rebound']['complex_weights']['recovery'] == 25
    assert built['calm_rise']['complex_weights']['volatility'] == 35 and built['growth_regular']['complex_weights']['r2'] == 35
    assert built['momentum_6m']['momentum_horizon'] == '6m' and built['momentum_12m']['momentum_horizon'] == '12m' and built['momentum_risk']['momentum_horizon'] == 'blend'
    for n, c in built.items():
        if n != 'growth_v4':
            assert abs(sum(c['complex_weights'].values()) - 100) < 1e-9, n
    active = {n: tuple(p['id'] for p in A.base_config(n)['periods'] if p['enabled']) for n in A.V4_STRATEGIES}
    assert active['growth_v4'] == ('week', 'month') and active['growth_regular'] == ('month', 'quarter') and active['momentum_12m'] == ('half', 'year')
    for n in A.V4_STRATEGIES:                                                     # chaque profil par défaut est enregistrable tel quel
        A.clean_profile(A.profile_of(A.base_config(n)))


def test_profile_validation():
    p = profile()
    assert A.clean_profile(p)['weights_mode'] == 'auto'
    for bad in (dict(p, periods={k: dict(v, enabled=False) for k, v in p['periods'].items()}),
                dict(p, weights_mode='custom', weights={'week': 20, 'month': 30}),
                dict(p, complex_weights=dict(p['complex_weights'], dynamics=50)),
                dict(p, complex_weights={'dynamics': 100}),
                dict(p, weights_mode='autre')):
        with pytest.raises(ValueError):
            A.clean_profile(bad)
    good = dict(p, weights_mode='custom', weights={'week': 30, 'month': 70})
    assert A.clean_profile(good)['weights'] == {'week': 30, 'month': 70}


def test_save_roundtrip_and_overlay(memory):
    p = profile()
    p['periods']['quarter']['enabled'] = True
    p['periods']['week']['min_slope'] = 0.2
    p.update(weights_mode='custom', weights={'week': 20, 'month': 30, 'quarter': 50})
    A.save(None, {'profile': p, 'global': {'kappa': 0.5, 'threshold': 0.8}})
    g = row(A.state(None))
    assert g['customised'] and g['current']['weights'] == {'week': 20, 'month': 30, 'quarter': 50} and g['current']['periods']['week']['min_slope'] == 0.2
    assert A.state(None)['global']['kappa'] == 0.5
    cfg = S.apply_admin(None, A.growth_v4())
    params = S.params_for(cfg, 'equity')
    assert [x['id'] for x in params['periods']] == ['week', 'month', 'quarter'] and params['kappa'] == 0.5 and params['threshold'] == 0.8
    assert SC.resolve_weights(params['periods'], params['kappa'])['quarter'] == pytest.approx(0.5)


def test_reset_profile_global_and_all(memory):
    p = profile()
    p['periods']['quarter']['enabled'] = True
    A.save(None, {'profile': p, 'global': {'kappa': 0.4, 'threshold': 0.9}})
    A.save(None, {'reset': 'profile', 'name': 'growth_v4'})
    st = A.state(None)
    assert not row(st)['customised'] and st['global']['kappa'] == 0.4                    # le profil seul est restauré
    A.save(None, {'reset': 'global'})
    assert A.state(None)['global']['kappa'] == 0.7
    A.save(None, {'profile': p, 'global': {'kappa': 0.4}})
    A.save(None, {'reset': 'all'})
    st = A.state(None)
    assert not row(st)['customised'] and st['global']['kappa'] == 0.7
    with pytest.raises(ValueError):
        A.save(None, {'reset': 'profile', 'name': 'regular'})


def test_invalid_save_is_rejected_and_stores_nothing(memory):
    p = profile()
    p['complex_weights']['dynamics'] = 70
    with pytest.raises(ValueError):
        A.save(None, {'profile': p})
    assert A.PROFILES not in memory
    with pytest.raises(ValueError):
        A.save(None, {'global': {'kappa': 2}})
    with pytest.raises(ValueError):
        A.save(None, {'profile': dict(profile(), name='regular')})


def test_strategy_own_global_value_wins(memory):
    A.save(None, {'global': {'kappa': 0.5}})
    c = A.growth_v4()
    c['scoring']['kappa'] = 0.3
    assert S.apply_admin(None, c)['scoring']['kappa'] == 0.3


def test_conformity_thresholds_never_change_scores_cache_key(memory):
    base = S._key(A.growth_v4(), 1)
    p = profile()
    p['periods']['week']['min_slope'] = 0.3
    p['periods']['month']['min_r2'] = 0.9
    p['periods']['month']['min_return'] = 25
    A.save(None, {'profile': p})
    assert S._key(S.apply_admin(None, A.growth_v4()), 1) == base
    p['periods']['quarter']['enabled'] = True                                           # une granularité de plus : les notes changent
    A.save(None, {'profile': p})
    assert S._key(S.apply_admin(None, A.growth_v4()), 1) != base


def test_complex_weights_per_profile_change_the_key_but_not_conformity(memory):
    p = profile()
    p['complex_weights'] = dict(SC.COMPLEX_WEIGHTS, dynamics=30, liquidity=20)
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, A.growth_v4())
    assert cfg['liquidity'] == A.growth_v4()['liquidity'] and cfg['scoring']['complex_weights']['liquidity'] == 20


def test_historic_strategies_are_untouched_by_profiles(memory):
    A.save(None, {'profile': profile()})
    from engine.analytics.explorer import strategy
    cfg = C.editable(strategy.preset('regular'))
    assert S.apply_admin(None, cfg) == S.apply_global(None, cfg)


def test_preview_returns_percentages():
    out = A.preview(None, {'kappa': 0.7, 'periods': ['month', 'week', 'inconnue']})
    assert set(out['weights']) == {'week', 'month'} and sum(out['weights'].values()) == pytest.approx(100)


def test_simple_mode_defaults_impose_nothing_hidden():
    p = profile()
    on = {k: v for k, v in p['periods'].items() if v['enabled']}
    assert set(on) == {'week', 'month'}
    for x in on.values():                                                         # mode simple : seulement pente et R², aucun critère avancé
        assert x['min_slope'] == A.SLOPE['very_strong'] and x['min_r2'] is None             # Croissance rapide : pente seule, pas de R²
        assert all(x[f] is None for f in A.ADVANCED)
    assert not p['day_filter']['enabled'] and p['liquidity'] == {'min_turnover_eur': None, 'min_turnover_eur_us': None}


def test_balanced_reference_is_the_v4_default_and_has_no_hidden_threshold():
    ref = A.references()
    assert ref['balanced'] == A.profile_of(A.base_config('growth_v4')) and ref['balanced']['periods']['week']['min_return'] is None
    assert 'v1' not in ref


def test_advanced_criteria_and_day_filter_roundtrip_and_never_change_scores(memory):
    key = S._key(A.growth_v4(), 1)
    p = profile()
    p['periods']['month'].update(min_return=8.0, max_spike_share=0.45, max_volatility=7.0, min_up_fraction=0.5, max_drawdown=20.0)
    p['periods']['day'].update(enabled=True, min_return=0.0)
    p['liquidity'] = {'min_turnover_eur': 2e6, 'min_turnover_eur_us': 5e6}
    p['filters'] = {'enabled': True}
    A.save(None, {'profile': p})
    cur = row(A.state(None))['current']
    assert cur['periods']['month']['max_drawdown'] == 20.0 and cur['day_filter']['enabled'] and cur['liquidity']['min_turnover_eur_us'] == 5e6
    cfg = S.apply_admin(None, A.growth_v4())
    day = next(x for x in cfg['periods'] if x['id'] == 'day')
    assert day['enabled'] and day['min_return'] == 0.0
    assert S._key(cfg, 1) == key                                                  # ni Jour à 0 % ni les critères avancés ne changent les notes
    assert [x['id'] for x in S.params_for(cfg, 'equity')['periods']] == ['week', 'month']       # Jour sans poids n'entre dans aucun calcul


def test_last_day_filter_can_be_disabled_again(memory):
    p = profile('growth_v4')
    p['periods']['day'].update(enabled=True, min_return=0.0)
    A.save(None, {'profile': p})
    assert A.stored_profiles(None)['growth_v4']['periods']['day']['enabled'] and A.stored_profiles(None)['growth_v4']['day_filter']['enabled']
    p['periods']['day'].update(enabled=False, min_return=None)
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, A.base_config('growth_v4'))
    day = next(x for x in cfg['periods'] if x['id'] == 'day')
    assert not day['enabled'] and day['min_return'] is None


def test_invalid_advanced_values_are_rejected():
    for f, v in (('max_spike_share', 2), ('min_up_fraction', -1), ('max_drawdown', 500), ('min_r2', 3)):
        p = profile()
        p['periods']['week'][f] = v
        with pytest.raises(ValueError):
            A.clean_profile(p)
    p = profile()
    p['liquidity']['min_turnover_eur'] = -5
    with pytest.raises(ValueError):
        A.clean_profile(p)


def test_technical_settings_are_separate_from_thresholds(memory):
    p = profile()
    p['technical']['require_fresh'] = False
    p['periods']['month']['require_history'] = False
    p['filters'] = {'enabled': True}
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, A.growth_v4())
    assert cfg['selection']['require_fresh'] is False
    assert S.params_for(cfg, 'equity')['required'] == ['week']                    # la période obligatoire est un réglage technique, pas un seuil de croissance


def test_filters_are_off_by_default_and_remove_no_title_from_the_ranking():
    cfg = S.apply_admin(None, A.growth_v4())
    for pid in ('week', 'month'):
        x = next(p for p in cfg['periods'] if p['id'] == pid)
        assert x['enabled'] and not x['require_history'] and all(x[f] is None for f in A.THRESHOLDS)       # notées, jamais filtrées
    assert not next(p for p in cfg['periods'] if p['id'] == 'day')['enabled']
    assert cfg['liquidity']['min_turnover_eur'] is None and cfg['liquidity']['min_turnover_eur_us'] is None
    cur = row(A.state(None))['current']
    assert cur['filters'] == {'enabled': False} and cur['periods']['week']['min_slope'] == A.SLOPE['very_strong']       # valeurs conservées, prêtes à être activées


def test_enabling_filters_applies_thresholds_but_never_changes_scores():
    p = profile()
    p['filters'] = {'enabled': True}
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, A.growth_v4())
    wk = next(x for x in cfg['periods'] if x['id'] == 'week')
    assert wk['min_slope'] == A.SLOPE['very_strong'] and wk['require_history']
    assert S._key(cfg, 1) == S._key(S.apply_admin(None, A.growth_v4()), 1)
    assert S._key(cfg, 1) == S._key(A.neutral(A.growth_v4()), 1)          # même notation avec ou sans filtres


def test_anchor_is_a_common_setting_validated_persisted_and_part_of_the_cache_key(memory):
    base = S._key(S.apply_admin(None, A.growth_v4()), 1)
    p = profile()
    A.save(None, {'global': {'kappa': 0.7, 'threshold': 0.75, 'anchor': 0.0}, 'profile': p})
    assert A.state(None)['global']['anchor'] == 0.0 and S.params_for(S.apply_admin(None, A.growth_v4()), 'equity')['anchor'] == 0.0
    assert S._key(S.apply_admin(None, A.growth_v4()), 1) != base                    # l'ancrage change les notes complexes : il change la clé
    for bad in (-0.1, 1.5):
        with pytest.raises(ValueError):
            A.save(None, {'global': {'kappa': 0.7, 'threshold': 0.75, 'anchor': bad}})
    A.save(None, {'reset': 'global'})
    assert A.state(None)['global']['anchor'] == 0.5 and S._key(S.apply_admin(None, A.growth_v4()), 1) == base


def test_strategies_current_profile_always_carries_sessions():
    from engine.analytics.admin import scores_admin as A
    cur = A.clean_profile(A.profile_of(A.base_config('growth_v4')))
    assert 'sessions' not in cur['periods']['week']                    # clean_profile ne le garde pas : strategies() doit le rajouter


def test_classement_proposes_every_v4_strategy():
    """Chaque stratégie V4 de l'administration a son entrée dans le Classement ; ses critères de recherche viennent du moteur (V4_STRATEGIES), pas d'une copie dans la page."""
    import os
    from engine.analytics.scoring import ranking_table as R
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert sorted(A.CT_BUILTIN.values()) == sorted(A.V4_STRATEGIES)
    php = open(os.path.join(root, 'app', 'services', 'ct_strategies.php'), encoding='utf-8').read()
    js = open(os.path.join(root, 'app', 'public', 'assets', 'classement-test.js'), encoding='utf-8').read()
    crit = R.criteria()['criteria']
    assert 'ranking/criteria' in js and '.3,.6' not in js and '[.07,.56]' not in js         # aucune valeur de critère recopiée dans la page
    for ct_id, name in A.CT_BUILTIN.items():
        label = A.V4_STRATEGIES[name]['label']
        assert f"'{ct_id}' => '{label}'" in php
        assert f"{ct_id}:'{label}'" in js
        engine = {p['id']: p for p in A.V4_STRATEGIES[name]['build']()['periods'] if p['enabled']}
        assert set(crit[ct_id]['periods']) == set(engine), ct_id                              # mêmes périodes actives
        for k, p in engine.items():
            expected = {f: p[m] for m, f in R.CRITERIA_FIELDS.items() if p.get(m) is not None}
            assert crit[ct_id]['periods'][k] == expected, (ct_id, k)                          # mêmes critères historiques
    assert crit['fast']['periods'] == {'week': {'slope': 0.27543703768897265}, 'month': {'slope': 0.27543703768897265}}           # pente « très forte », pas de R²
    assert crit['regular']['periods'] == {k: {'slope': 0.06878824951818499, 'r2': 0.5555555555555556} for k in ('month', 'quarter')}
    assert crit['calm']['periods'] == {k: {'slope': 0.034388212013465085, 'r2': 0.5555555555555556} for k in ('month', 'quarter')}      # volatilité et drawdown : plus des seuils
    assert crit['rebound']['periods'] == {'week': {'slope': 0.034388212013465085, 'r2': 0.5555555555555556}, 'month': {'slope': 0.034388212013465085, 'r2': 0.5555555555555556}, 'half': {}}
    assert all(set(v) <= {'slope', 'r2'} for ct in crit.values() for v in ct['periods'].values())   # critères de recherche : pente et R² seulement
    assert all(not v for ct in ('mom6', 'mom12', 'momrisk') for v in crit[ct]['periods'].values())   # Momentum : aucun critère


SPEC_SCORES = {   # (poids complexes dynamique, r2, jours positifs, concentration, volatilité, drawdown, liquidité, accélération, momentum, rebond), poids des granularités, saturation, référence d'accélération, score par défaut
    'growth_v4': ((40, 15, 5, 7, 15, 8, 10, 0, 0, 0), {}, 17.0, 0.4, 'simple'),
    'growth_regular': ((20, 35, 15, 10, 5, 5, 10, 0, 0, 0), {}, 10.0, 0.4, 'complex'),
    'calm_rise': ((10, 10, 10, 5, 35, 20, 10, 0, 0, 0), {}, 10.0, 0.4, 'complex'),
    'rebound': ((15, 10, 5, 5, 10, 5, 5, 20, 0, 25), {'week': 50, 'month': 50, 'half': 0}, 17.0, 0.25, 'complex'),
    'momentum_6m': ((15, 10, 0, 0, 5, 10, 10, 0, 50, 0), {'quarter': 30, 'half': 70}, 17.0, 0.4, 'complex'),
    'momentum_12m': ((15, 10, 0, 0, 5, 10, 10, 0, 50, 0), {'half': 30, 'year': 70}, 17.0, 0.4, 'complex'),
    'momentum_risk': ((0, 0, 0, 0, 10, 10, 0, 0, 80, 0), {'half': 40, 'year': 60}, 17.0, 0.4, 'complex'),
}
KEYS = ('dynamics', 'r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'liquidity', 'acceleration', 'momentum', 'recovery')


def test_the_seven_strategies_keep_their_scoring_part_and_have_search_criteria_apart():
    """Deux parties séparées : SCORES (barème, poids, saturation, score par défaut) et STRATÉGIE (granularités, pente, R²). Aucun rendement, volatilité ni drawdown n'est un seuil."""
    from engine.analytics.scoring import score_service as SS
    from engine.analytics.scoring import scores as SC
    for name, (cw, weights, sat, accel, sort) in SPEC_SCORES.items():
        cfg = A.V4_STRATEGIES[name]['build']()
        params = SS.params_for(cfg, 'equity')
        assert tuple(params['complex_weights'][k] for k in KEYS) == tuple(float(x) for x in cw), name
        assert {k: v for k, v in (cfg['scoring']['weights'] or {}).items()} == {k: float(v) for k, v in weights.items()}, name
        assert params['sat_a'] == sat and params['accel_ref'] == accel and cfg['ranking']['sort'] == sort, name
        assert (params['kappa'], params['threshold'], params['anchor']) == (SC.KAPPA, SC.COVERAGE_THRESHOLD, SC.ANCHOR_LAMBDA), name
        for p in cfg['periods']:
            assert all(p.get(f) is None for f in A.ADVANCED), (name, p['id'])                      # jamais de seuil de rendement, volatilité ou drawdown
    assert (SC.LIQUIDITY_FLOOR_EUR, SC.LIQUIDITY_CEIL_EUR, SC.GATE_FLOOR, SC.SAT_A, SC.ACCEL_REF) == (2e6, 5e7, 32.0, 17.0, 0.4)


def test_rebound_keeps_the_half_year_loaded_as_context_so_the_rebound_note_works():
    """Le semestre n'a ni pente ni R² (poids 0), mais il doit rester une période chargée : la note « contexte de rebond » lit son rendement."""
    from engine.analytics.scoring import score_service as SS
    from engine.analytics.scoring import scores as SC
    cfg = A.V4_STRATEGIES['rebound']['build']()
    half = next(p for p in cfg['periods'] if p['id'] == 'half')
    assert half['enabled'] and half['min_slope'] is None and half['min_r2'] is None and half['max_return'] is None
    assert 126 in {p['sessions'] for p in SS.params_for(cfg, 'equity')['periods']}                # sa mesure est chargée pour la note de rebond
    # la note distingue une reprise après baisse d'une croissance continue (même hausse récente)
    after_fall, continuous = SC.recovery_note(-10.0), SC.recovery_note(30.0)
    assert after_fall == 100 and continuous == 0
