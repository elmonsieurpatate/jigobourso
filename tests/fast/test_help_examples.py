"""Les chiffres de l'exemple « Zébulon » et des échelles de notes écrits dans l'aide (help-content.js, aide.js) doivent rester ceux du moteur : si une règle change, ce test échoue et l'aide est à mettre à jour."""
import pytest

from engine.analytics import scores as S, strategy as LEGACY


def slope_for(total, n):
    return 100 * ((1 + total / 100) ** (1 / n) - 1)


def meas(total, n, r2, vol, dd, up, spike):
    return {'slope': slope_for(total, n), 'r2': r2, 'volatility': vol, 'drawdown': dd, 'up_fraction': up, 'spike_share': spike, 'accel': None, 'r2_prev': None}


def test_zebulon_example_matches_the_engine():
    inputs = {5: meas(8, 5, 0.92, 1.8, 4, 0.70, 0.25), 21: meas(20, 21, 0.90, 1.8, 6, 0.62, 0.30)}
    r = S.score_title(inputs, {'turnover_eur': 20e6, 'source': 'daily'}, [{'id': 'week', 'sessions': 5}, {'id': 'month', 'sessions': 21}], kappa=0.7)
    assert round(r['periods']['week']['dynamics']) == 47 and round(r['periods']['month']['dynamics']) == 56
    assert r['weights']['week'] == pytest.approx(0.42, abs=0.01) and r['weights']['month'] == pytest.approx(0.58, abs=0.01)
    assert r['simple']['dynamics'] == pytest.approx(0.52, abs=0.01) and r['simple']['quality'] == pytest.approx(0.90, abs=0.01)
    assert round(r['simple']['score']) == 47
    assert round(r['complex']['score'], 1) == pytest.approx(66.5, abs=0.2)
    notes = {k: round(sum(r['weights'][p] * r['periods'][p][k] for p in ('week', 'month'))) for k in ('r2', 'up_days', 'concentration', 'volatility', 'drawdown')}
    assert notes == {'r2': 91, 'up_days': 63, 'concentration': 64, 'volatility': 80, 'drawdown': 66}
    assert round(S.liquidity_note(20e6)) == 72


def test_reference_growth_and_slope_levels_quoted_in_help():
    assert [round(S.saturation(n)) for n in (5, 21, 63)] == [17, 36, 63]
    very = LEGACY.SLOPE_LEVELS['very_strong']
    assert [round(100 * ((1 + very / 100) ** n - 1), 1) for n in (5, 21, 63)] == [1.4, 5.9, 18.9]
    assert [round(v, 3) for v in LEGACY.R2_LEVELS.values() if v is not None] == [0.556, 0.75, 0.889]


def test_note_scales_quoted_in_help():
    def note(**m):
        base = {'slope': 0.3, 'r2': 0.9, 'volatility': 2.0, 'drawdown': 5.0, 'up_fraction': 0.6, 'spike_share': 0.3, 'accel': None, 'r2_prev': None}
        return S.period_components(dict(base, **m), 21)
    ap = lambda v: pytest.approx(v, abs=1e-6)
    assert note(r2=0.5)['r2'] == ap(0) and note(r2=0.95)['r2'] == ap(100)
    assert note(up_fraction=0.4)['up_days'] == ap(0) and note(up_fraction=0.8)['up_days'] == ap(100)
    assert note(spike_share=0.10)['concentration'] == ap(100) and note(spike_share=0.60)['concentration'] == ap(0)
    assert note(volatility=1.0)['volatility'] == ap(100) and note(volatility=5.0)['volatility'] == ap(0)
    assert note(drawdown=0)['drawdown'] == ap(100) and note(drawdown=15)['drawdown'] == ap(0)
    assert S.liquidity_note(2e6) == ap(0) and S.liquidity_note(50e6) == ap(100)
    assert S.recovery_note(-10) == ap(100) and S.recovery_note(20) == ap(0)
    assert S.momentum_note({'6m': 60.0}, '6m') == ap(100) and S.momentum_note({'12m': 100.0}, '12m') == ap(100)
