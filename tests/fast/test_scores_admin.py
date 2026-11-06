"""Administration des scores : un moteur commun, des profils de stratégie validés, des réglages communs superposés sans jamais toucher à la conformité."""
import copy

import pytest

from engine.analytics import explorer_config as C, score_service as S, scores as SC, scores_admin as A
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
        ids = list(A.SCORING_PERIODS)[:n]
        assert sum(A.auto_weights(0.7, ids).values()) == pytest.approx(100)
    assert A.auto_weights(0.5, ['week', 'month'])['week'] < A.auto_weights(0.7, ['week', 'month'])['week']      # κ plus bas : poids aux longues périodes
    assert A.auto_weights(0.7, []) == {}


def test_state_labels_and_engines_are_distinguished():
    labels = {s['name']: (s['label'], s['engine']) for s in A.state(None)['strategies']}
    assert labels['growth_v4'] == ('Croissance rapide — V4 (moteur commun)', 'v4')
    assert labels['growth_v1'][1] == 'v4' and 'référence V1' in labels['growth_v1'][0]
    assert labels['fast'] == ('Croissance rapide — ancien moteur', 'historic') and labels['regular'][1] == 'historic'
    assert len({v[0] for v in labels.values()}) == len(labels)                    # aucun libellé en double
    assert all(s['engine'] in ('v4', 'historic') for s in A.state(None)['strategies'])


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
    from engine.analytics import strategy
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
        assert x['min_slope'] is not None and x['min_r2'] is not None
        assert all(x[f] is None for f in A.ADVANCED)
    assert not p['day_filter']['enabled'] and p['liquidity'] == {'min_turnover_eur': None, 'min_turnover_eur_us': None}


def test_v1_thresholds_are_a_reference_preset_not_the_simple_default():
    ref = A.references()
    assert ref['v1']['periods']['week']['min_return'] == 3.0 and ref['v1']['periods']['month']['min_return'] == 8.0 and ref['v1']['periods']['month']['max_spike_share'] == 0.45
    assert ref['v1']['day_filter']['enabled'] and ref['v1']['liquidity']['min_turnover_eur_us'] == 5e6
    assert ref['balanced'] == A.profile_of(A.base_config('growth_v4')) and ref['balanced']['periods']['week']['min_return'] is None


def test_advanced_criteria_and_day_filter_roundtrip_and_never_change_scores(memory):
    key = S._key(A.growth_v4(), 1)
    p = profile()
    p['periods']['month'].update(min_return=8.0, max_spike_share=0.45, max_volatility=7.0, min_up_fraction=0.5, max_drawdown=20.0)
    p['day_filter'] = {'enabled': True, 'min_return': 0.0}
    p['liquidity'] = {'min_turnover_eur': 2e6, 'min_turnover_eur_us': 5e6}
    p['filters'] = {'enabled': True}
    A.save(None, {'profile': p})
    cur = row(A.state(None))['current']
    assert cur['periods']['month']['max_drawdown'] == 20.0 and cur['day_filter']['enabled'] and cur['liquidity']['min_turnover_eur_us'] == 5e6
    cfg = S.apply_admin(None, A.growth_v4())
    day = next(x for x in cfg['periods'] if x['id'] == 'day')
    assert day['enabled'] and day['min_return'] == 0.0
    assert S._key(cfg, 1) == key                                                  # ni le filtre du dernier jour ni les critères avancés ne changent les notes
    assert [x['id'] for x in S.params_for(cfg, 'equity')['periods']] == ['week', 'month']       # le dernier jour n'est jamais une granularité de notation


def test_last_day_filter_can_be_disabled_again(memory):
    p = profile('growth_v1')
    assert p['day_filter']['enabled']
    p['day_filter']['enabled'] = False
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, C.growth_v1())
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
    assert cur['filters'] == {'enabled': False} and cur['periods']['week']['min_slope'] == 0.30       # valeurs conservées, prêtes à être activées


def test_enabling_filters_applies_thresholds_but_never_changes_scores():
    p = profile()
    p['filters'] = {'enabled': True}
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, A.growth_v4())
    wk = next(x for x in cfg['periods'] if x['id'] == 'week')
    assert wk['min_slope'] == 0.30 and wk['require_history']
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
    from engine.analytics import scores_admin as A
    cur = A.clean_profile(A.profile_of(A.base_config('growth_v4')))
    assert 'sessions' not in cur['periods']['week']                    # clean_profile ne le garde pas : strategies() doit le rajouter
