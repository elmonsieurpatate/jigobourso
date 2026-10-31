"""Outils statistiques de recherche : corrélations de rang, régression, bootstrap par blocs, VaR/CVaR, drawdown."""
import importlib.util
import math
import os
import random
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', f'{name}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rs = load('research_stats')


def test_ranks_average_ties_and_spearman_is_monotone_invariant():
    assert rs.ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert round(rs.spearman(a, [x ** 3 for x in a]), 9) == 1.0
    assert round(rs.spearman(a, [-x for x in a]), 9) == -1.0
    assert rs.spearman([1, 2], [1, 2]) is None and rs.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None


def test_partial_spearman_removes_a_shared_driver():
    rng = random.Random(4)
    control = [rng.gauss(0, 1) for _ in range(400)]
    signal = [c + rng.gauss(0, 0.3) for c in control]
    future = [c + rng.gauss(0, 0.3) for c in control]                    # signal et futur ne dépendent que du contrôle
    assert rs.spearman(signal, future) > 0.7
    assert abs(rs.partial_spearman(signal, future, [control])) < 0.2


def test_residuals_are_orthogonal_to_the_regressors():
    rng = random.Random(1)
    x = [rng.random() for _ in range(100)]
    y = [3 * v + rng.gauss(0, 0.1) for v in x]
    res = rs.residuals(y, [x])
    assert abs(sum(res)) < 1e-8 and abs(sum(r * v for r, v in zip(res, x))) < 1e-8
    assert rs.residuals([1.0, 2.0, 3.0, 4.0], [[1.0, 1.0, 1.0, 1.0]])                 # colonne constante : pas d'erreur


def test_block_bootstrap_interval_covers_the_mean_and_is_reproducible():
    rng = random.Random(2)
    values = [rng.gauss(1.0, 3.0) for _ in range(120)]
    m, lo, hi = rs.block_bootstrap_mean(values, 6)
    assert lo < m < hi and (lo, hi) == rs.block_bootstrap_mean(values, 6)[1:]
    zero = [rng.gauss(0.0, 3.0) for _ in range(120)]
    assert rs.block_bootstrap_p(zero, 6) > 0.05 > rs.block_bootstrap_p([v + 3 for v in zero], 6)


def test_autocorrelated_series_gets_a_wider_interval_with_blocks():
    rng = random.Random(3)
    x, values = 0.0, []
    for _ in range(300):
        x = 0.9 * x + rng.gauss(0, 1)
        values.append(x)
    _, lo1, hi1 = rs.block_bootstrap_mean(values, 1)
    _, lo2, hi2 = rs.block_bootstrap_mean(values, 20)
    assert (hi2 - lo2) > 1.5 * (hi1 - lo1)                                  # ignorer la dépendance rend l'intervalle trop étroit


def test_block_length_and_spacing_follow_the_horizon():
    assert rs.block_length(5) == 3 and rs.block_length(63) == 6 and rs.block_length(126) == 12
    assert rs.spacing(21) == 1 and rs.spacing(63) == 3 and rs.spacing(126) == 6


def test_var_cvar_and_drawdown():
    returns = [-10.0, -5.0, -2.0, 0.0] + [1.0] * 16
    var, cvar = rs.var_cvar(returns, 0.95)
    assert var == -10.0 and cvar == -10.0
    var, cvar = rs.var_cvar(returns, 0.90)
    assert var == -5.0 and cvar == statistics.fmean([-10.0, -5.0])
    assert round(rs.max_drawdown([10.0, -20.0, -25.0, 100.0]), 6) == -40.0
    assert rs.max_drawdown([1.0, 2.0]) == 0.0


def test_summary_reports_effective_sample_sizes():
    s = rs.summary([1.0, -0.5, 2.0, 0.3, 1.1, -0.2, 0.9, 1.4, 0.2, 0.8, -1.0, 0.5], 63)
    assert s['dates'] == 12 and s['independent'] == 4 and s['ci_low'] < s['mean'] < s['ci_high']
    assert rs.summary([], 21) is None
