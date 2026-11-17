"""Tolérance aux données imparfaites : une règle unique (couverture ≥ MIN_COVERAGE, aucune interruption > MAX_GAP) pour toutes les mesures d'une fenêtre.
Historiques réalistes : complets, une ou plusieurs séances manquantes, jours fériés inconnus du calendrier, interruptions longues, titre récent, splits."""

import math
import random

import pytest

from engine.analytics.scoring import score_inputs as SI
from engine.analytics.scoring import scores as SC
from engine.analytics.series import measures as M
from engine.analytics.series.series import analyze_series


def _calendar(n, start='2021-11-10'):
    """n+1 séances ISO consécutives (lundi-vendredi) : un calendrier de place simplifié."""
    import datetime as dt

    d, out = dt.date.fromisoformat(start), []
    while len(out) < n + 1:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _path(dates, seed=7, drift=0.0004, vol=0.013):
    rng, price, out = random.Random(seed), 100.0, {}
    for d in dates:
        price *= math.exp(rng.gauss(drift, vol))
        out[d] = price
    return out


def _legacy_inputs(closes):
    """Définitions d'avant la tolérance (fenêtre complète uniquement) : la référence des résultats à préserver."""
    n = len(closes) - 1
    steps = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    total = math.log(closes[-1] / closes[0])
    out = {'up_fraction': sum(1 for s in steps if s > 0) / len(steps), 'spike_share': (math.log1p(max(steps)) / total) if total > 0 else 1.0}
    cut = n // 2
    if cut >= 3 and n - cut >= 3:
        first, second = M.window_metrics(closes[: cut + 1]), M.window_metrics(closes[cut:])
        out['accel'], out['r2_prev'] = second['slope'] - first['slope'], min(first['r2'], second['r2'])
    out['momentum_perf'] = 100 * (closes[n - SI.recent_exclusion(n)] / closes[0] - 1)
    out['recovery'] = SI.recovery_input(closes)
    return out


@pytest.mark.parametrize('n', [5, 21, 63, 126, 252, 504, 756, 1260])
def test_complete_histories_keep_exactly_their_previous_results(n):
    dates = _calendar(n)
    obs = _path(dates, seed=n)
    closes = [obs[d] for d in dates]
    new = SI.window_inputs(dates, [], obs)
    old = _legacy_inputs(closes)
    for key, value in old.items():
        assert new[key] == pytest.approx(value, rel=1e-12, abs=1e-12), key
    metrics, info = M.dated_window_metrics(dates, obs)
    ref = M.window_metrics(closes)
    assert info['status'] == 'ok' and metrics['coverage'] == 1.0
    for key in ('perf', 'slope', 'slope_log', 'r2', 'volatility', 'drawdown', 'er'):
        assert metrics[key] == ref[key]  # chemin historique inchangé : égalité exacte
    gap = M.gap_metrics(list(enumerate(closes)), n)  # la formule généralisée coïncide avec l'historique sur données complètes
    for key in ('perf', 'slope', 'r2', 'volatility', 'drawdown', 'er'):
        if ref[key] is not None:
            assert gap[key] == pytest.approx(ref[key], rel=1e-12, abs=1e-12), key


@pytest.mark.parametrize('n', [21, 252, 756, 1260])
def test_one_missing_session_keeps_the_window_usable_with_nearly_identical_results(n):
    dates = _calendar(n)
    full = _path(dates, seed=n + 1)
    holed = {d: v for k, (d, v) in enumerate(full.items()) if k != n // 3}
    a, b = SI.window_inputs(dates, [], full), SI.window_inputs(dates, [], holed)
    assert all(b[k] is not None for k in ('up_fraction', 'spike_share', 'momentum_perf', 'recovery')), b
    assert b['up_fraction'] == pytest.approx(a['up_fraction'], abs=2 / n)
    ma, mb = M.dated_window_metrics(dates, full)[0], M.dated_window_metrics(dates, holed)[0]
    assert mb['volatility'] == pytest.approx(ma['volatility'], rel=0.08)  # le pas manquant est un rendement sur 2 séances, pas une séance ordinaire
    assert mb['slope'] == pytest.approx(ma['slope'], abs=0.01) and mb['perf'] == pytest.approx(ma['perf'], abs=1.0)
    if n >= 252:
        assert b['mrar'] is not None and b['mrar'] == pytest.approx(a['mrar'], rel=0.02, abs=0.5)


def test_several_scattered_missing_sessions_and_unknown_holidays_are_tolerated():
    n = 756
    dates = _calendar(n)
    full = _path(dates, seed=3)
    rng = random.Random(11)
    missing = set(rng.sample(range(1, n), 25))  # ≈ 3 % de clôtures absentes, dispersées (jours fériés inconnus du calendrier, omissions Yahoo)
    holed = {d: v for k, (d, v) in enumerate(full.items()) if k not in missing}
    got = SI.window_inputs(dates, [], holed)
    metrics, info = M.dated_window_metrics(dates, holed)
    assert info['status'] == 'ok' and info['missing_sessions'] == len(missing) and info['coverage'] > 0.96
    assert all(got[k] is not None for k in ('up_fraction', 'accel', 'momentum_perf', 'mrar')) and metrics['volatility'] is not None
    assert got['mrar'] == pytest.approx(SI.window_inputs(dates, [], full)['mrar'], rel=0.05, abs=1.0)


def test_the_first_close_missing_is_the_1260_sessions_needing_1261_closes_case():
    n = 1260
    dates = _calendar(n)
    obs = {d: v for d, v in _path(dates, seed=5).items() if d != dates[0]}  # 1 260 clôtures disponibles pour 1 261 attendues
    got = SI.window_inputs(dates, [], obs)
    metrics, info = M.dated_window_metrics(dates, obs)
    assert info['status'] == 'ok' and info['max_gap'] == 1
    assert got['mrar'] is not None and got['up_fraction'] is not None and metrics['volatility'] is not None
    assert metrics['sessions'] == 1260


@pytest.mark.parametrize('hole', [(300, 311), (50, 80), (0, 30)])
def test_a_long_interruption_is_excluded_and_reported(hole):
    n = 756
    dates = _calendar(n)
    obs = {d: v for k, (d, v) in enumerate(_path(dates, seed=9).items()) if not hole[0] <= k < hole[1]}
    out = SI.window_inputs(dates, [], obs)
    metrics, info = M.dated_window_metrics(dates, obs)
    assert info['max_gap'] > M.MAX_GAP and info['status'] in ('gap', 'history')
    assert all(v is None for v in out.values()) and metrics['slope'] is None and metrics['volatility'] is None


def test_a_recent_title_has_no_long_period_but_keeps_its_short_ones():
    dates = _calendar(756)
    obs = {d: v for k, (d, v) in enumerate(_path(dates, seed=2).items()) if k >= 600}  # coté depuis 156 séances
    assert M.dated_window_metrics(dates, obs)[1]['status'] == 'history' and SI.window_inputs(dates, [], obs)['mrar'] is None
    short = dates[-253:]
    assert M.dated_window_metrics(short[-64:], obs)[1]['status'] == 'ok' and M.dated_window_metrics(short[-64:], obs)[0]['volatility'] is not None


def test_a_session_gap_counts_for_its_duration_in_volatility_and_up_fraction():
    n = 40
    dates = _calendar(n)
    drift = {d: 100 * math.exp(0.01 * i) for i, d in enumerate(dates)}
    gapped = {d: v for i, (d, v) in enumerate(drift.items()) if i not in (10, 11, 12)}  # 4 séances en un seul intervalle observé
    m, _ = M.dated_window_metrics(dates, gapped)
    assert m['volatility'] == pytest.approx(0.0, abs=1e-9)  # hausse régulière : l'intervalle de 4 séances n'est pas une séance « extraordinaire »
    assert SI.window_inputs(dates, [], gapped)['up_fraction'] == pytest.approx(1.0)  # pondérée par la durée
    steady_down = {d: 100 * math.exp(-0.01 * i) for i, d in enumerate(dates)}
    flat_gap = {d: v for i, (d, v) in enumerate(steady_down.items()) if i not in (10, 11, 12)}
    assert SI.window_inputs(dates, [], flat_gap)['up_fraction'] == pytest.approx(0.0)


def test_splits_are_a_separate_problem_breaks_still_exclude_the_window_not_the_gaps():
    n = 63
    dates = _calendar(n)
    px = _path(dates, seed=4)
    halved = {d: (v / 2 if k >= 30 else v) for k, (d, v) in enumerate(px.items())}  # split 2:1 non déclaré : rupture de cours
    bars = [(d, v, None) for k, (d, v) in enumerate(halved.items()) if k != 20]  # + une séance manquante
    _, _, _, breaks, measures, missing, _ = analyze_series(bars, [63], session_windows={63: dates})
    assert breaks and missing.get(63) == 'break' and measures[63] is None
    # le même split connu (ratio 2:1 confirmé) est corrigé : la fenêtre trouée redevient mesurable
    _, _, _, breaks, measures, missing, _ = analyze_series(bars, [63], splits=[(dates[30], 2.0)], session_windows={63: dates})
    assert not breaks and missing == {} and measures[63]['volatility'] is not None


def test_scores_use_the_tolerated_measures_and_report_the_coverage():
    n = 756
    dates = _calendar(n)
    full = _path(dates, seed=8)
    holed = {d: v for k, (d, v) in enumerate(full.items()) if k not in (100, 400)}
    metrics, info = M.dated_window_metrics(dates, holed)
    metrics = dict(metrics, **SI.window_inputs(dates, [], holed))
    comps = SC.period_components(metrics, n)
    assert comps['volatility'] is not None and comps['drawdown'] is not None and comps['risk_adjusted'] is not None
    assert info['coverage'] == pytest.approx(755 / 757)


def test_spike_share_of_a_nearly_flat_long_window_fits_the_decimal_column():
    """Non-régression : 756 séances à gain net minuscule donnent un rapport énorme ; il débordait DECIMAL(10,6) (erreur 1264) et faisait échouer tout le calcul."""
    from engine.analytics.series.compute import SPIKE_SHARE_CAP, bounded_spike_share

    n = 756
    dates = _calendar(n)
    obs = {d: 100.0 * (1 + 1e-9 * i) * (1.02 if i == 300 else 1.0) * (1 / 1.02 if i == 301 else 1.0) for i, d in enumerate(dates)}
    raw = SI.window_inputs(dates, [], obs)['spike_share']
    assert raw is not None and raw > 10_000  # sans plafond : valeur hors colonne
    stored = bounded_spike_share(raw)
    assert stored == SPIKE_SHARE_CAP < 10_000 and bounded_spike_share(None) is None
    assert bounded_spike_share(0.4) == 0.4  # en dessous du plafond : inchangé
