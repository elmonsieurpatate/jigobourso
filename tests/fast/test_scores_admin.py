"""Administration des scores : réglages globaux validés, superposés aux stratégies sans réglage propre, jamais aux critères de conformité."""
import pytest

from engine.analytics import explorer_config as C, score_service as S, scores_admin as A
from engine.shared import settings


class Store:
    data = {}


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    store = {}
    monkeypatch.setattr(settings, 'get', lambda conn, name, default=None: store.get(name, default))
    monkeypatch.setattr(settings, 'put', lambda conn, name, value: store.__setitem__(name, value))
    monkeypatch.setattr(A, 'coverage', lambda conn: {'universe': 0, 'daily': 0, 'estimated': 0, 'unknown': 0, 'computed_at': None, 'volume_checked_at': None, 'score_inputs': 0})
    return store


def test_defaults_are_design_values():
    st = A.state(None)
    assert st['current']['kappa'] == 0.7 and st['current']['threshold'] == 0.75 and not st['customised']
    assert st['current']['complex_weights']['dynamics'] == 40


def test_save_validates_and_overlays(memory):
    A.save(None, {'kappa': 0.5, 'threshold': 0.8, 'complex_weights': {'dynamics': 50}})
    cfg = S.apply_admin(None, C.growth_v1())
    assert cfg['scoring']['kappa'] == 0.5 and cfg['scoring']['threshold'] == 0.8 and cfg['scoring']['complex_weights'] == {'dynamics': 50}


def test_strategy_own_value_wins(memory):
    A.save(None, {'kappa': 0.5})
    c = C.growth_v1()
    c['scoring']['kappa'] = 0.3
    assert S.apply_admin(None, c)['scoring']['kappa'] == 0.3


def test_invalid_rejected():
    with pytest.raises(ValueError):
        A.save(None, {'kappa': 2})
    with pytest.raises(ValueError):
        A.save(None, {'complex_weights': {'inconnu': 3}})
    with pytest.raises(ValueError):
        A.save(None, {'complex_weights': {k: 0 for k in A.SC.COMPLEX_WEIGHTS}})


def test_reset(memory):
    A.save(None, {'kappa': 0.5})
    A.save(None, {'reset': True})
    assert A.state(None)['current']['kappa'] == 0.7


def test_conformity_thresholds_untouched(memory):
    A.save(None, {'kappa': 0.5})
    c = C.growth_v1()
    out = S.apply_admin(None, c)
    assert out['liquidity'] == c['liquidity'] and out['periods'] == c['periods']
