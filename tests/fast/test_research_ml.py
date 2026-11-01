"""Score appris : rangs, ridge, absence d'information future, signal planté retrouvé, bout en bout sur un panel réel construit en test."""
import math
import os
import random
import sys
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'fast'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

import research_analyses as ra                                      # noqa: E402
import research_ml as ml                                            # noqa: E402
import research_panel as rp                                         # noqa: E402

NAN = float('nan')


def fake_panel(dates=90, titles=150, planted='m31', seed=3):
    """Panel synthétique : g21 = 5 × (rang de `planted`) + bruit ; tous les titres éligibles (USD, liquides)."""
    rng = random.Random(seed)
    cols = {name: array('l') if name in ('ti', 'key', 'grp', 'status', 'ccy') else array('d') for name in rp.COLUMNS}
    for ti in range(dates):
        for k in range(titles):
            row = {'ti': ti, 'key': k, 'grp': 0, 'status': 0, 'ccy': 0}
            for f in rp.FEATURES:
                row[f] = rng.gauss(0, 1)
            row['liq'] = 2e6 + rng.random() * 1e6
            if k % 17 == 0:
                row['vtr'] = NAN                                   # valeurs manquantes : rang médian
            for name in rp.FORWARD_COLUMNS:
                row[name] = rng.gauss(0, 3)
            row['g21'] = 5 * row[planted] + rng.gauss(0, 3)
            for name in rp.COLUMNS:
                cols[name].append(row[name])
    days = [f'{2000 + ti // 12}-{ti % 12 + 1:02d}-15' for ti in range(dates)]
    return ra.Data({'cols': cols, 'dates': days, 'ranked': {}, 'split_titles': [], 'rows': len(cols['ti'])})


def test_protocol_constants_are_frozen():
    assert ml.MODELS == ('lineaire', 'courbe') and ml.BONFERRONI == 0.025
    assert ml.EMBARGO == 2 and ml.MIN_TRAIN_DATES == 60 and ml.REFIT_EVERY == 12 and ml.RIDGE == 0.01
    assert ml.TOP == 20 and ml.LAG == 1 and ml.HORIZON == 21 and ml.MAIN_COST == 30 and ml.FEATURES == rp.FEATURES


def test_centered_ranks_and_missing_values():
    r = ml.centered_ranks([3.0, NAN, 1.0, 2.0])
    assert r == [0.5, 0.0, -0.5, 0.0]
    assert ml.centered_ranks([NAN, 1.0]) == [0.0, 0.0]


def test_solve_matches_a_known_system():
    a = [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]]
    x = ml.solve(a, [1.0, 2.0, 3.0])
    for row, b in zip(a, [1.0, 2.0, 3.0]):
        assert abs(sum(u * v for u, v in zip(row, x)) - b) < 1e-12


def test_planted_signal_is_found_and_ranked_first():
    data = fake_panel()
    prepared = ml.prepare_dates(data, 'usd_1M')
    scores, history = ml.learn_scores(data, prepared, 'lineaire')
    assert history and history[0]['train_dates'] >= ml.MIN_TRAIN_DATES
    table = ml.coefficient_table(history, 'lineaire')
    assert table[0]['variable'] == 'm31' and table[0]['last'] > 0 and table[0]['sign_stability'] == 100.0
    ic = ml.information(data, scores, 'usd_1M')
    assert ic['mean'] > 0.5


def test_no_future_information_is_used():
    """Changer les rendements cibles des dates ≥ (première décision − EMBARGO + 1) ne change pas les scores de la première décision."""
    data = fake_panel()
    prepared = ml.prepare_dates(data, 'usd_1M')
    scores, history = ml.learn_scores(data, prepared, 'courbe')
    t0 = history[0]['ti']
    g = data.c['g21']
    for i in range(len(g)):
        if data.c['ti'][i] > t0 - ml.EMBARGO:
            g[i] = -g[i] * 7 + 1
    again, _ = ml.learn_scores(data, ml.prepare_dates(data, 'usd_1M'), 'courbe')
    for i, s in scores[t0].items():
        assert math.isclose(again[t0][i], s, rel_tol=1e-12, abs_tol=1e-12)


def test_models_refit_on_schedule_and_never_before_enough_history():
    data = fake_panel()
    prepared = ml.prepare_dates(data, 'usd_1M')
    scores, history = ml.learn_scores(data, prepared, 'lineaire')
    fits = [h['ti'] for h in history]
    assert all(b - a == ml.REFIT_EVERY for a, b in zip(fits, fits[1:]))
    assert min(scores) == fits[0] == ml.MIN_TRAIN_DATES + ml.EMBARGO - 1          # dates 0 … 59 connues à la date 61


def test_portfolio_accounting_and_end_to_end_report():
    data = fake_panel()
    report = {'usd_1M': ml.analyse(data, 'usd_1M')}
    block = report['usd_1M']
    assert {m['model'] for m in block['models']} == set(ml.MODELS)
    for m in block['models']:
        assert m['common_dates'] > 0 and m['verdict'] in ('améliore le rendement', 'meilleur compromis rendement/risque', 'réduit le risque mais coûte du rendement', 'pas mieux')
        assert 0 <= m['metrics']['turnover'] <= 1
    text = ml.render(report)
    assert 'Score appris contre le Momentum 6-1' in text and 'M1' in text and 'M2' in text
