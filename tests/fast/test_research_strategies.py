"""Pistes d'amélioration du Momentum 6-1 : paniers, poids, filtre de marché, rotation, verdict, bout en bout."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'fast'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

from test_research_panel import make_dir, build                    # noqa: E402
import research_analyses as ra                                      # noqa: E402
import research_strategies as st                                    # noqa: E402


def data_for(tmp_path):
    days = make_dir(tmp_path, titles=130, days_n=1100)
    return ra.Data(build(tmp_path, days))


def first_valid_date(data, scen='usd_1M'):
    return next(ti for ti in range(len(data.dates)) if len(data.eligible(ti, 0, scen)) >= st.MIN_POOL)


def test_protocol_constants_are_frozen():
    assert len(st.VARIANTS) == 8 and st.BONFERRONI == 0.05 / 8 and st.TOP == 20 and st.LAG == 1
    assert st.RECENT_WINNERS_CUT == 0.90 and st.EXTREME_VOL_CUT == 0.80 and st.MAIN_COST == 30


def test_baskets_have_unit_weights_and_use_only_eligible_titles(tmp_path):
    data = data_for(tmp_path)
    ti = first_valid_date(data)
    elig = data.eligible(ti, 0, 'usd_1M')
    for v in ('mom_6_1',) + st.VARIANTS[:-1]:
        w = st.basket(data, ti, v, 'usd_1M')
        if w:
            assert abs(sum(w.values()) - 1.0) < 1e-9 and set(w) <= elig and len(w) <= 20, v


def test_inverse_volatility_weights_and_same_titles_as_the_reference(tmp_path):
    data = data_for(tmp_path)
    ti = first_valid_date(data)
    base, inv = st.basket(data, ti, 'mom_6_1', 'usd_1M'), st.basket(data, ti, 'mom_vol_inverse', 'usd_1M')
    assert set(inv) <= set(base)
    vol = data.c['vol126']
    a, b = sorted(inv)[:2]
    assert abs(inv[a] / inv[b] - vol[b] / vol[a]) < 1e-9                  # poids inversement proportionnels à la volatilité


def test_recent_winner_and_extreme_volatility_exclusions(tmp_path):
    data = data_for(tmp_path)
    ti = first_valid_date(data)
    elig = [i for i in data.eligible(ti, 0, 'usd_1M') if data.c['m61'][i] == data.c['m61'][i] and data.c['m1'][i] == data.c['m1'][i]]
    cut = st.quantile([data.c['m1'][i] for i in elig], 0.90)
    assert all(data.c['m1'][i] <= cut for i in st.basket(data, ti, 'mom_sans_hausse_recente', 'usd_1M'))
    pool = [i for i in data.eligible(ti, 0, 'usd_1M') if data.c['m61'][i] == data.c['m61'][i] and data.c['vol126'][i] == data.c['vol126'][i]]
    vcut = st.quantile([data.c['vol126'][i] for i in pool], 0.80)
    assert all(data.c['vol126'][i] <= vcut for i in st.basket(data, ti, 'mom_sans_vol_extreme', 'usd_1M'))


def test_market_filter_goes_to_cash_when_the_median_trend_is_negative(tmp_path):
    data = data_for(tmp_path)
    ti = len(data.dates) - 5                                              # date tardive : le momentum 12-1 est calculable
    elig = data.eligible(ti, 0, 'usd_1M')
    med = sorted(data.c['m121'][i] for i in elig if data.c['m121'][i] == data.c['m121'][i])
    median = med[len(med) // 2]
    w = st.basket(data, ti, 'mom_filtre_marche', 'usd_1M')
    assert bool(w) == (median > 0)


def test_series_costs_follow_the_traded_weights(tmp_path):
    data = data_for(tmp_path)
    rows = st.run_variant(data, 'mom_6_1', 'usd_1M', 30)
    assert rows and abs(rows[0]['net'] - (rows[0]['pick'] - 0.30 * 1.0)) < 1e-9        # première période : achat de 100 % seulement (0,3 %)
    for r in rows[1:]:
        assert 0 <= r['turnover'] <= 1 and abs(r['net'] - (r['pick'] - 0.60 * r['turnover'])) < 1e-9
    free = st.run_variant(data, 'mom_6_1', 'usd_1M', 0)
    assert all(abs(r['net'] - r['pick']) < 1e-9 for r in free)


def test_verdict_follows_the_preregistered_definitions():
    base = {'cvar95': -20.0, 'ratio': 0.20}
    good = {'ci_low': 0.5, 'ci_high': 2.0, 'p_block': 0.001}
    flat = {'ci_low': -1.0, 'ci_high': 1.0, 'p_block': 0.4}
    ok_periods = {'a': 1.0, 'b': 0.5, 'c': -0.2}
    assert st.verdict(good, ok_periods, {'cvar95': -20.0, 'ratio': 0.25}, base) == 'améliore le rendement'
    assert st.verdict(flat, ok_periods, {'cvar95': -15.0, 'ratio': 0.21}, base) == 'meilleur compromis rendement/risque'
    assert st.verdict(flat, ok_periods, {'cvar95': -15.0, 'ratio': 0.10}, base) == 'réduit le risque mais coûte du rendement'
    assert st.verdict(flat, {'a': -1.0, 'b': -0.5, 'c': 0.2}, {'cvar95': -15.0, 'ratio': 0.21}, base) == 'pas mieux'      # instable
    assert st.verdict(flat, ok_periods, {'cvar95': -19.0, 'ratio': 0.30}, base) == 'pas mieux'                             # CVaR améliorée de 5 % seulement
    assert st.verdict(None, {}, base, base) == 'données insuffisantes'


def test_end_to_end_report_has_every_variant_and_the_caveats(tmp_path):
    data = data_for(tmp_path)
    report = {'usd_1M': st.analyse(data, 'usd_1M')}
    names = {v['variant'] for v in report['usd_1M']['variants']}
    assert names <= set(st.VARIANTS) and len(names) >= 6
    for v in report['usd_1M']['variants']:
        assert v['verdict'] in ('améliore le rendement', 'meilleur compromis rendement/risque', 'réduit le risque mais coûte du rendement', 'pas mieux', 'données insuffisantes')
    text = st.render(report)
    assert 'Momentum 6-1 (référence)' in text and 'biais de survie' in text and 'Verdict' in text
