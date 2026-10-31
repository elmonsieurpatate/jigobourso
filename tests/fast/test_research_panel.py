"""Panel de recherche et analyses : aucune information future, décalage d'exécution, éligibilité, classements des profils, analyses de bout en bout sur données synthétiques."""
import gzip
import importlib.util
import math
import os
import pickle
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'fast'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

from test_backtest_liquidity import business_days, candidate, eh   # noqa: E402
import research_panel as rp                                         # noqa: E402
import research_analyses as ra                                      # noqa: E402


def make_dir(tmp_path, titles=130, days_n=900, mutate=None):
    days = business_days(days_n)
    cands = [candidate(i, days, drift=0.0003 + 0.00003 * (i % 6), sigma=0.012 + 0.0004 * (i % 4), volume=60_000 + 700 * i, currency='USD' if i % 5 else 'EUR', seed=7) for i in range(titles)]
    if mutate:
        mutate(cands, days)
    for c in cands:
        eh.write_history(str(tmp_path), c['key'], [(d, p, a, v) for (d, p, a), v in zip(c['bars'], c['volumes'])])
    eh.write_universe(str(tmp_path), [{'key': c['key'], 'symbol': c['symbol'], 'mic': 'XNYS', 'kind': 'equity', 'country': 'US', 'currency': c['currency']} for c in cands])
    return days


def build(tmp_path, days, name='panel'):
    out = str(tmp_path / name)
    assert rp.main(['build', '--csv-dir', str(tmp_path), '--out', out, '--start', days[130], '--min-titles', '0', '--batch', '50']) == 0
    assert rp.main(['merge', '--out', out]) == 0
    with gzip.open(os.path.join(out, 'panel.pkl.gz'), 'rb') as fh:
        return pickle.load(fh)


def test_indicators_use_only_the_visible_closes():
    base = [100.0 * (1.001 ** i) for i in range(300)]
    ind = rp.indicators(base)
    assert round(ind['m61'], 9) == round(base[-22] / base[-127] - 1, 9)
    assert round(ind['m121'], 9) == round(base[-22] / base[-253] - 1, 9)
    assert round(ind['m1'], 9) == round(base[-1] / base[-22] - 1, 9)
    assert ind['hi'] == 0.0 and ind['mdd252'] == 0.0 and ind['r2'] > 0.99
    short = rp.indicators(base[:100])
    assert math.isnan(short['m61']) and math.isnan(short['m121']) and not math.isnan(short['m1'])


def test_forward_returns_enter_at_t_or_the_next_close():
    dates = business_days(60)
    closes = [100.0 + i for i in range(60)]
    full = (dates, closes, None, [])
    t = dates[20]
    assert round(rp.forward(full, t, 5, 0), 9) == round(100 * (closes[25] / closes[20] - 1), 9)
    assert round(rp.forward(full, t, 5, 1), 9) == round(100 * (closes[26] / closes[21] - 1), 9)
    assert rp.forward(full, dates[57], 5, 0) is None                      # l'historique s'arrête avant
    assert rp.forward((dates, closes, None, [23]), t, 5, 0) is None       # rupture de cours non expliquée traversée


def test_features_and_ranks_at_t_do_not_change_when_only_the_future_changes(tmp_path):
    days = make_dir(tmp_path, titles=40)
    first = build(tmp_path, days, 'a')
    cut = days.index(first['dates'][20])                                  # on réécrit tout ce qui suit la 41e date de décision

    def wreck(cands, d):
        for c in cands:
            bars = []
            for k, (day, p, a) in enumerate(c['bars']):
                f = 3.0 if day > first['dates'][20] else 1.0
                bars.append((day, p * f, a * f))
            c['bars'] = bars
    other = tmp_path / 'b'
    other.mkdir()
    make_dir(other, titles=40, mutate=wreck)
    second = build(other, days, 'p')
    mask = [i for i in range(first['rows']) if first['cols']['ti'][i] <= 20]
    mask2 = [i for i in range(second['rows']) if second['cols']['ti'][i] <= 20]
    assert len(mask) == len(mask2) > 0
    for name in ('m61', 'm121', 'm31', 'm1', 'vol126', 'slope', 'r2', 'hi', 'ma200', 'ma50', 'liq', 'vtr'):
        a = [first['cols'][name][i] for i in mask]
        b = [second['cols'][name][i] for i in mask2]
        assert all((x == y) or (x != x and y != y) or math.isclose(x, y, rel_tol=1e-9) for x, y in zip(a, b)), name
    for key in first['ranked']:
        if key[0] <= first['dates'][19]:
            assert first['ranked'][key] == second['ranked'].get(key), key   # le classement des profils ne voit pas l'avenir
    assert cut > 130


def test_eligibility_scenarios_follow_the_liquidity_rules(tmp_path):
    days = make_dir(tmp_path, titles=130)
    panel = build(tmp_path, days)
    data = ra.Data(panel)
    ti = len(data.dates) // 2
    rows = data.by[(ti, 0)]
    some = data.eligible(ti, 0, 'aucun')
    usd = data.eligible(ti, 0, 'usd_1M')
    rel = data.eligible(ti, 0, 'relatif_50%')
    assert some == set(rows) and usd <= some and rel <= some
    assert all(data.c['ccy'][i] == 0 and data.c['liq'][i] >= 1_000_000 for i in usd)             # dollars seulement, seuil absolu
    assert 0 < len(rel) < len(some)


def test_rank_analysis_runs_and_reports_every_requested_slice(tmp_path):
    days = make_dir(tmp_path, titles=130)
    data = ra.Data(build(tmp_path, days))
    res = ra.analysis_rank(data, strategies=('mom_6_1', 'regular'), horizons=(21,), groups=('equity',), lags=(0, 1))
    names = {(r['strategy'], r['scenario'], r['slice'], r['lag']) for r in res}
    assert ('mom_6_1', 'usd_1M', 'Top 20', 0) in names and ('mom_6_1', 'usd_1M', 'rangs 21-50', 1) in names
    for r in res:
        assert r['excess_gross']['independent'] <= r['excess_gross']['dates'] and r['excess_gross']['ci_low'] <= r['excess_gross']['ci_high']
        assert r['excess_net']['10'] > r['excess_net']['30'] > r['excess_net']['60']             # plus de frais, moins de rendement
    assert 'Top 20' in ra.render_rank(res)


def test_ic_deciles_and_redundancy_run_on_the_panel(tmp_path):
    days = make_dir(tmp_path, titles=130)
    data = ra.Data(build(tmp_path, days))
    ic = ra.analysis_ic(data, horizons=(21,), groups=('equity',))
    assert {r['signal'] for r in ic} >= {'m61', 'vol126', 'r2'}
    assert all(-1 <= r['ic']['mean'] <= 1 for r in ic)
    deciles = ra.analysis_deciles(data, horizons=(21,), groups=('equity',), signals=('m61',), include_presets=False)
    assert deciles and len(deciles[0]['decile_mean']) == 10
    red = ra.redundancy(data, max_dates=10)
    assert any({r['a'], r['b']} == {'m61', 'm121'} and r['mean_rank_correlation'] > 0.2 for r in red)         # deux momentums proches mesurent en partie la même chose


def test_portfolio_turnover_costs_and_risk_block(tmp_path):
    days = make_dir(tmp_path, titles=130)
    data = ra.Data(build(tmp_path, days))
    rows = ra.portfolio_series(data, 'mom_6_1', 0, 'aucun', 20, 1, 21, 0)
    assert rows and rows[0]['turnover'] == 1.0 and all(0 <= r['turnover'] <= 1 for r in rows)
    assert all(abs(r['net'] - (r['pick'] - 2 * ra.MAIN_COST / 100.0 * r['turnover'])) < 1e-9 for r in rows)
    block = ra.risk_block(data, rows, 21)
    assert block['max_drawdown'] <= 0 and block['cvar95'] <= block['var95'] and block['periods'] == len(rows)


def test_candidates_apply_the_preregistered_criteria(tmp_path):
    days = make_dir(tmp_path, titles=130)
    data = ra.Data(build(tmp_path, days))
    res = ra.analysis_candidates(data)
    assert res['bonferroni_tests'] == 12 and abs(res['threshold'] - 0.05 / 12) < 1e-12
    assert [c['candidate'] for c in res['candidates']] == list(ra.CANDIDATES)
    for c in res['candidates']:
        assert c['verdict'] in ('retenue (exploratoire)', 'écartée', 'non concluante')
        if c['verdict'] == 'retenue (exploratoire)':
            assert all(c['criteria'].values())                              # aucun verdict favorable sans les quatre critères
