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

spec2 = importlib.util.spec_from_file_location('export_history', os.path.join(ROOT, 'scripts', 'export_history.py'))
eh = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(eh)

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
    assert results and {r['strategy'] for r in results} <= set(PRESETS) | set(bt.DEFAULT_SIGNALS)
    assert set(bt.DEFAULT_SIGNALS) <= {r['strategy'] for r in results} | {'mix_mom_lowvol'}
    for r in results:
        assert abs((r['excess_gross'] - r['excess_net']) - 0.2) < 0.02          # 2 × 10 pb = 0,2 point par rééquilibrage
        assert 0 < r['p_random'] <= 1 and r['dates'] <= len(dates)
        k = r['risk']
        assert 0 <= k['pick_negative'] <= 100 and 0 <= k['universe_negative'] <= 100 and k['pick_p10'] <= k['pick_spread'] * 10 + 100
        assert len(r['by_date']) == r['dates'] and 'excess_median' in r
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


def test_overlapping_dates_give_no_p_value():
    """À 63 séances avec un pas de 21, seules une date sur trois est indépendante : trop peu de dates pour une p-valeur ou une t-stat."""
    study, _ = study_for(series(120, 330, 0.2, 0.002, 0.015, 5), horizons=(63,), dates=4)
    rows = [r for r in study.results(top=10, step=21, draws=50) if r['strategy'] in PRESETS]
    assert rows and all(r['independent_dates'] <= 2 and r['p_random'] is None and r['t_net'] is None for r in rows)


def test_periods_partition_the_dates():
    study, dates = study_for(series(100, 380, 0.2, 0.002, 0.015, 7), dates=8)
    parts = bt.split_periods(dates, dates[4])
    assert [len(p) for _, p in parts] == [4, 4] and parts[0][0] == 'calibration' and parts[1][0] == 'validation'
    out = study.results(top=10, draws=50, only_dates=parts[1][1], period='validation')
    assert out and all(r['period'] == 'validation' and r['dates'] <= 4 for r in out)
    assert all(d >= dates[4] for r in out for d in (x['date'] for x in r['by_date']))
    text = bt.render(out, {'titles': 100, 'dates': dates, 'top': 10, 'cost_bps': 10, 'split_date': dates[4]})
    assert '── validation' in text and 'Risque des sélections' in text


def test_csv_source_gives_the_same_study_as_the_candidates_it_was_built_from(tmp_path):
    cands = series(80, 340, 0.2, 0.002, 0.015, 9)
    for c in cands:                                           # cours ajusté = cours brut × 0,99 : la base « ajustée » est utilisée par le moteur
        c['bars'] = [(d, p, p * 0.99) for d, p, _ in c['bars']]
        eh.write_history(str(tmp_path), c['key'], [(d, p, a, None) for d, p, a in c['bars']])
    eh.write_universe(str(tmp_path), [{'key': c['key'], 'symbol': c['symbol'], 'mic': 'XNYS', 'kind': 'equity', 'country': '', 'currency': 'USD'} for c in cands])
    universe = bt.csv_universe(str(tmp_path))
    assert len(universe) == 80
    calendar = bt.csv_calendar(str(tmp_path), universe)
    assert calendar == bt.reference_dates([bt.prepare(c) for c in cands])
    loaded = [c for lot in bt.csv_batches(str(tmp_path), universe, batch=30) for c in lot]
    assert len(loaded) == 80 and loaded[0]['bars'][0][2] == pytest_approx(cands[0]['bars'][0][2])
    chosen = bt.pick_dates(calendar, (21,), 21, 3)
    direct, from_csv = bt.Study(PRESETS, (21,), chosen), bt.Study(PRESETS, (21,), chosen)
    direct.add(bt.prepare(c) for c in cands)
    from_csv.add(bt.prepare(c) for c in loaded)
    key = lambda r: (r['strategy'], r['group'], r['horizon'])        # noqa: E731
    a = {key(r): (r['pick_mean'], r['universe_mean']) for r in direct.results(top=10, draws=20)}
    b = {key(r): (r['pick_mean'], r['universe_mean']) for r in from_csv.results(top=10, draws=20)}
    assert a == b


def pytest_approx(value):
    import pytest
    return pytest.approx(value)


def fn(name):
    return bt.SIGNALS[name][0]


def test_signal_formulas_on_known_series():
    up = [100 * 1.01 ** i for i in range(300)]
    assert abs(fn('mom_12_1')(up) - (1.01 ** 231 - 1)) < 1e-9           # de il y a 252 à il y a 21 séances
    assert abs(fn('mom_6_1')(up) - (1.01 ** 105 - 1)) < 1e-9
    assert abs(fn('reversal_1m')(up) + (1.01 ** 21 - 1)) < 1e-9           # les plus mauvais du mois en tête : score négatif sur une hausse
    assert fn('near_52w_high')(up) == 1.0
    assert fn('low_vol_126')(up) == 0 or abs(fn('low_vol_126')(up)) < 1e-12
    assert fn('smooth_mom')(up) > 0 and fn('trend_mom')(up) is not None and fn('dual_mom')(up) is not None
    down = [100 * 0.995 ** i for i in range(300)]
    assert fn('trend_mom')(down) is None and fn('dual_mom')(down) is None  # filtres : pas de signal en baisse
    assert all(f(up[:50]) is None for n, f in ((n, v[0]) for n, v in bt.SIGNALS.items()) if n not in ('mom_3_1', 'reversal_1m'))   # historique trop court


def test_low_volatility_ranks_smooth_above_choppy():
    rnd = random.Random(2)
    smooth = [100 * 1.001 ** i * math.exp(rnd.gauss(0, 0.002)) for i in range(300)]
    choppy = [100 * 1.001 ** i * math.exp(rnd.gauss(0, 0.03)) for i in range(300)]
    assert fn('low_vol_126')(smooth) > fn('low_vol_126')(choppy)


def test_signal_scores_ignore_the_future_and_composites_work():
    cands = series(60, 330, 0.3, 0.003, 0.015, 3)
    study, dates = study_for(cands, dates=3)
    t = dates[0]
    before = {k: dict(v) for k, v in study.scores.items() if k[0] == t}
    rnd = random.Random(5)
    changed = [dict(c, bars=[(d, p * (1 if d <= t else math.exp(rnd.gauss(0, 0.5))), a) for d, p, a in c['bars']]) for c in cands]
    after_study, _ = study_for(changed, dates=3)
    after = {k: dict(v) for k, v in after_study.scores.items() if k[0] == t}
    assert before and before == after
    picks = study.picks(top=10)
    assert any(k[1] == 'mix_mom_lowvol' for k in picks) and any(k[1] == 'mom_12_1' for k in picks)


def test_unknown_signal_is_refused_and_signals_can_be_chosen():
    import pytest
    with pytest.raises(ValueError):
        bt.Study(PRESETS, (21,), ['2026-01-01'], signals=('inconnu',))
    cands = series(60, 330, 0.2, 0.002, 0.015, 8)
    prepared = [bt.prepare(c) for c in cands]
    dates = bt.pick_dates(bt.reference_dates(prepared), (21,), 21, 3)
    study = bt.Study((), (21,), dates, signals=('mom_12_1',))
    study.add(prepared)
    assert {r['strategy'] for r in study.results(top=10, draws=20)} == {'mom_12_1'}
