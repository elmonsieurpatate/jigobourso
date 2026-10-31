"""Test chronologique des stratégies (scripts/backtest_walkforward.py) : pas de regard vers l'avenir, rendements futurs exacts, exécution de bout en bout."""
import datetime
import importlib.util
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('backtest_walkforward', os.path.join(ROOT, 'scripts', 'backtest_walkforward.py'))
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

PRESETS = ('regular', 'fast', 'recovery', 'low_volatility')


def business_days(n, start=datetime.date(2025, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def series(n_titles, n_days, trend_share, drift, sigma, seed):
    rnd, days, out = random.Random(seed), business_days(n_days), []
    for i in range(n_titles):
        trending, price, bars = rnd.random() < trend_share, 100.0, []
        for d in days:
            price *= math.exp(rnd.gauss(drift if trending else 0.0, sigma))
            bars.append((d, price, None))
        out.append({'key': i, 'symbol': f'S{i}', 'group': 'equity', 'bars': bars, 'split_dates': []})
    return out


def study_for(cands, horizons=(21,), dates=4):
    prepared = [bt.prepare(c) for c in cands]
    calendar = bt.reference_dates(prepared)
    chosen = bt.pick_dates(calendar, horizons, 21, dates)
    study = bt.Study(PRESETS, horizons, chosen)
    study.add(prepared)
    return study, chosen


def test_forward_return_exact():
    closes = [100 * 1.01 ** i for i in range(80)]
    days = business_days(80)
    full = (days, closes, 'raw', [])
    assert abs(bt.forward_return(full, days[30], 21) - 100 * (1.01 ** 21 - 1)) < 1e-9
    assert bt.forward_return(full, days[70], 21) is None             # la série s'arrête avant l'horizon
    assert bt.forward_return((days, closes, 'raw', [40]), days[30], 21) is None   # rupture traversée : invalide


def test_pick_dates_leave_room_for_the_horizon():
    calendar = business_days(400)
    dates = bt.pick_dates(calendar, (21, 63), 21, 6)
    assert len(dates) == 6 and dates == sorted(dates)
    assert calendar.index(dates[-1]) <= len(calendar) - 1 - 63
    assert calendar.index(dates[0]) >= 126


def test_no_look_ahead_decisions_ignore_the_future():
    """Les verdicts à la date t ne changent pas si l'on modifie tous les cours postérieurs à t."""
    cands = series(60, 330, 0.3, 0.003, 0.015, 3)
    study, dates = study_for(cands, dates=3)
    t = dates[0]
    before = {k: sorted((v['key'], round(v['measures'][21]['slope'], 9)) for v in vs) for k, vs in study.retained.items() if k[0] == t}
    rnd = random.Random(99)
    shuffled = []
    for c in cands:
        bars = [(d, p * (1 if d <= t else math.exp(rnd.gauss(0, 0.5))), a) for d, p, a in c['bars']]     # avenir bouleversé
        shuffled.append(dict(c, bars=bars))
    study2, _ = study_for(shuffled, dates=3)
    after = {k: sorted((v['key'], round(v['measures'][21]['slope'], 9)) for v in vs) for k, vs in study2.retained.items() if k[0] == t}
    assert before and before == after


def test_end_to_end_structure_and_costs():
    cands = series(120, 330, 0.2, 0.002, 0.015, 5)
    study, dates = study_for(cands, dates=4)
    results = study.results(top=10, cost_bps=10, step=21, draws=100, seed=1)
    assert results and {r['strategy'] for r in results} <= set(PRESETS) | {bt.BASELINE}
    for r in results:
        assert abs((r['excess_gross'] - r['excess_net']) - 0.2) < 0.02          # 2 × 10 pb = 0,2 point par rééquilibrage
        assert 0 < r['p_random'] <= 1 and r['dates'] <= len(dates)
    text = bt.render(results, {'titles': len(cands), 'dates': dates, 'top': 10, 'cost_bps': 10})
    assert 'Limites' in text and 'univers' in text.lower()


def test_real_trend_is_detected_and_noise_is_not():
    """Garde-fou de méthode : avec une vraie dérive, la sélection bat l'univers ; sans dérive, elle ne le bat pas de façon significative."""
    signal, _ = study_for(series(300, 360, 0.2, 0.0015, 0.015, 11), dates=6)
    noise, _ = study_for(series(300, 360, 0.0, 0.0, 0.015, 11), dates=6)
    best = max(r['excess_gross'] for r in signal.results(top=20, draws=200, seed=1) if r['strategy'] in ('regular', 'fast'))
    flat = [r for r in noise.results(top=20, draws=200, seed=1) if r['strategy'] in PRESETS]
    assert best > 0.5
    assert all(r['p_random'] > 0.001 for r in flat)         # aucun profil « significatif » par miracle sur 6 dates de bruit pur
