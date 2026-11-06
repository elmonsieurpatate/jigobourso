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


def profile():
    p = A.profile_of(A.base_config('growth_v1'))
    for x in p['periods'].values():
        x.pop('sessions')
    return dict(p, name='growth_v1')


def row(state, name='growth_v1'):
    return next(s for s in state['strategies'] if s['name'] == name)


def test_defaults_are_design_values():
    st = A.state(None)
    assert st['global'] == {'kappa': 0.7, 'threshold': 0.75, 'customised': False, 'saved_at': None}
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
    assert labels['growth_v1'] == ('Croissance rapide (V4)', 'v4')
    assert labels['regular'] == ('Croissance régulière', 'historic') and labels['momentum12'][1] == 'historic'
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
    cfg = S.apply_admin(None, C.growth_v1())
    params = S.params_for(cfg, 'equity')
    assert [x['id'] for x in params['periods']] == ['week', 'month', 'quarter'] and params['kappa'] == 0.5 and params['threshold'] == 0.8
    assert SC.resolve_weights(params['periods'], params['kappa'])['quarter'] == pytest.approx(0.5)


def test_reset_profile_global_and_all(memory):
    p = profile()
    p['periods']['quarter']['enabled'] = True
    A.save(None, {'profile': p, 'global': {'kappa': 0.4, 'threshold': 0.9}})
    A.save(None, {'reset': 'profile', 'name': 'growth_v1'})
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
    c = C.growth_v1()
    c['scoring']['kappa'] = 0.3
    assert S.apply_admin(None, c)['scoring']['kappa'] == 0.3


def test_conformity_thresholds_never_change_scores_cache_key(memory):
    base = S._key(C.growth_v1(), 1)
    p = profile()
    p['periods']['week']['min_slope'] = 0.3
    p['periods']['month']['min_r2'] = 0.9
    p['periods']['month']['min_return'] = 25
    A.save(None, {'profile': p})
    assert S._key(S.apply_admin(None, C.growth_v1()), 1) == base
    p['periods']['quarter']['enabled'] = True                                           # une granularité de plus : les notes changent
    A.save(None, {'profile': p})
    assert S._key(S.apply_admin(None, C.growth_v1()), 1) != base


def test_complex_weights_per_profile_change_the_key_but_not_conformity(memory):
    p = profile()
    p['complex_weights'] = dict(SC.COMPLEX_WEIGHTS, dynamics=30, liquidity=20)
    A.save(None, {'profile': p})
    cfg = S.apply_admin(None, C.growth_v1())
    assert cfg['liquidity'] == C.growth_v1()['liquidity'] and cfg['scoring']['complex_weights']['liquidity'] == 20


def test_historic_strategies_are_untouched_by_profiles(memory):
    A.save(None, {'profile': profile()})
    from engine.analytics import strategy
    cfg = C.editable(strategy.preset('regular'))
    assert S.apply_admin(None, cfg) == S.apply_global(None, cfg)


def test_preview_returns_percentages():
    out = A.preview(None, {'kappa': 0.7, 'periods': ['month', 'week', 'inconnue']})
    assert set(out['weights']) == {'week', 'month'} and sum(out['weights'].values()) == pytest.approx(100)
