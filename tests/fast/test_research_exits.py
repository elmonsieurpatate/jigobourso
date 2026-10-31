"""Règles de sortie : aucune information future, exécution à la séance suivante, règles et seuils fixés, verdict, bout en bout sur données synthétiques."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'fast'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

from test_backtest_liquidity import business_days                  # noqa: E402
from test_research_panel import make_dir, build                    # noqa: E402
import research_analyses as ra                                      # noqa: E402
import research_exits as rx                                         # noqa: E402


def series_from(closes):
    days = business_days(len(closes))
    return rx.Series((days, closes, 'adj', []))


def base_path(n=400, drift=0.001):
    return [100.0 * math.exp(drift * i) for i in range(n)]


def test_protocol_constants_are_frozen():
    assert rx.STOP == 0.20 and rx.RANK_LIMIT == 50 and rx.MAX_HOLD == 126 and rx.FIXED == (21, 63, 126)
    assert round(rx.R2_FLOOR, 3) == 0.556 and rx.VOL21_LIMIT == 2.25 and rx.CHECK_EVERY == 5
    assert set(rx.SPECIFIC) == set(rx.STRATEGIES) and rx.BONFERRONI == 0.05 / 20


def test_trailing_stop_signals_on_the_close_and_sells_the_next_session():
    closes = base_path()
    entry, end = 200, 200 + 126
    for j in range(260, 270):
        closes[j] = closes[259] * 0.70                                  # chute de 30 % à partir de la séance 260
    s = series_from(closes)
    exits = rx.exit_signals('mom_6_1', s, entry, end, [], [])
    assert exits['trailing'] == 261                                      # signal à la clôture 260, vente à la clôture 261


def test_signal_uses_only_data_up_to_the_signal_day():
    closes = base_path()
    a = rx.exit_signals('fast', series_from(closes), 200, 326, [], [])
    changed = list(closes)
    for j in range(300, 400):
        changed[j] = changed[j] * 0.3                                    # on réécrit le futur lointain
    b = rx.exit_signals('fast', series_from(changed), 200, 326, [], [])
    assert {k: v for k, v in b.items() if v <= 300} == {k: v for k, v in a.items() if v <= 300}


def test_specific_rules_follow_each_profile():
    flat_then_drop = base_path()
    for j in range(250, 400):
        flat_then_drop[j] = flat_then_drop[249] * (1 - 0.004 * (j - 249))   # baisse régulière
    s = series_from(flat_then_drop)
    assert 'specific' in rx.exit_signals('fast', s, 200, 326, [], [])                       # rendement 21 séances < 0
    assert 'specific' in rx.exit_signals('recovery', s, 200, 326, [], [])                   # sous la moyenne 50 jours
    assert 'specific' in rx.exit_signals('mom_6_1', s, 200, 326, [], [])                    # rendement 63 séances < 0
    steady = series_from(base_path())
    for strat in rx.STRATEGIES:
        assert 'specific' not in rx.exit_signals(strat, steady, 200, 326, [], [])           # une hausse régulière ne déclenche rien
    noisy = base_path()
    for j in range(250, 400):
        noisy[j] = noisy[249] * (1.0 + (0.05 if j % 2 else -0.05))                        # volatilité quotidienne de 5 %
    assert 'specific' in rx.exit_signals('low_volatility', series_from(noisy), 200, 326, [], [])


def test_regularity_rule_checks_the_r2_weekly():
    zigzag = base_path()
    for j in range(240, 400):
        zigzag[j] = 150.0 * (1.12 if (j // 7) % 2 else 0.88)
    s = series_from(zigzag)
    assert s.r2(300, 63) < rx.R2_FLOOR
    assert 'specific' in rx.exit_signals('regular', s, 200, 326, [], [])
    assert s.r2(30, 63) is None


def test_rank_rule_sells_after_the_first_check_outside_the_top_50():
    s = series_from(base_path())
    exits = rx.exit_signals('regular', s, 200, 326, [(221, 0), (242, 1), (263, 2)], [True, False, False])
    assert exits['rank50'] == 243                                        # dans le Top 50 en 221, plus en 242 : vente en 243


def test_position_requires_the_full_follow_up_and_is_fixed_hold_consistent():
    closes = base_path(n=400, drift=0.001)
    s = series_from(closes)
    t = s.dates[199]
    res = rx.simulate_position('regular', s, t, [])
    assert abs(res['fixe_126']['ret'] - 100 * (closes[326] / closes[200] - 1)) < 1e-9          # entrée à la clôture suivante
    assert res['fixe_21']['days'] == 21 and res['fixe_126']['after'] is None and res['fixe_21']['after'] is not None
    assert rx.simulate_position('regular', series_from(closes[:300]), t, []) is None            # suivi incomplet : écarté pour toutes les variantes
    assert res['trailing']['days'] == 126                                                       # aucune règle déclenchée : tenu jusqu'au bout


def test_verdict_follows_the_preregistered_definitions():
    good = {'ci_low': 0.5, 'ci_high': 2.0, 'p_block': 0.001}
    flat = {'ci_low': -1.0, 'ci_high': 1.0, 'p_block': 0.4}
    bad = {'ci_low': -3.0, 'ci_high': -0.5, 'p_block': 0.001}
    assert rx.verdict(good, -20.0, -20.0) == 'améliore le rendement'
    assert rx.verdict(flat, -15.0, -20.0) == 'réduit le risque sans coût détecté'
    assert rx.verdict(bad, -15.0, -20.0) == 'réduit le risque mais coûte du rendement'
    assert rx.verdict(flat, -19.0, -20.0) == "pas d'effet détecté"                              # amélioration de 5 % seulement : insuffisante
    assert rx.verdict(None, 1, 1) == 'données insuffisantes'


def test_end_to_end_on_synthetic_history(tmp_path):
    days = make_dir(tmp_path, titles=130, days_n=1100)
    data = ra.Data(build(tmp_path, days))
    series = rx.load_series(str(tmp_path), {int(data.c['key'][i]) for i in range(data.n)})
    results = rx.run(data, series, strategies=('mom_6_1', 'regular'))
    report = rx.analyse(data, results)
    assert 'mom_6_1' in report
    rows = {r['variant']: r for r in report['mom_6_1']['rows']}
    assert set(rows) == {'fixe_21', 'fixe_63', 'fixe_126', 'rank50', 'mom_negative', 'trailing', 'specific'}
    assert rows['fixe_126']['early_share'] == 0.0 and rows['fixe_126']['verdict'] is None and rows['trailing']['verdict']
    assert all(r['mean_mdd'] <= 0 for r in rows.values())
    text = rx.render(report)
    assert 'Conserver 126 séances' in text and 'Verdict' in text and 'biais de survie' in text
