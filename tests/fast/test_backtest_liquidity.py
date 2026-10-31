"""Momentum 6-1 et liquidité historique (scripts/backtest_liquidity.py) : protocole figé, aucune donnée postérieure à la date, couverture, splits, devises, frais."""
import datetime
import importlib.util
import json
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


bl = load('backtest_liquidity')
eh = load('export_history')


def business_days(n, start=datetime.date(2008, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def candidate(key, days, drift=0.0, sigma=0.01, volume=1_000_000, currency='USD', seed=0, skip=(), split_at=None, group='equity', price=100.0):
    """Titre synthétique : `skip` = indices de séances sans donnée ; `split_at` = indice d'un split non ajusté (le cours BRUT saute, le cours ajusté reste continu)."""
    rnd, adj, bars, volumes = random.Random(seed * 1000 + key if isinstance(key, int) else seed), price, [], []
    for i, d in enumerate(days):
        adj *= math.exp(rnd.gauss(drift, sigma))
        if i in skip:
            continue
        raw = adj * (2.0 if split_at is not None and i < split_at else 1.0)
        bars.append((d, raw, adj))
        volumes.append(int(volume * (0.8 + 0.4 * rnd.random())))
    return {'key': key, 'symbol': f'S{key}', 'group': group, 'mic': 'XNYS', 'currency': currency, 'bars': bars, 'volumes': volumes, 'split_dates': []}


def study_for(cands, days, indices):
    study = bl.LiquidityStudy(days, [days[i] for i in indices], horizons=(21,))
    study.add(cands)
    return study


# ───────── protocole figé ─────────
def test_protocol_is_frozen_before_any_result():
    """Garde-fou : changer un seuil APRÈS avoir vu les résultats doit au moins faire échouer ce test et laisser une trace dans l'historique Git."""
    assert (bl.WINDOW, bl.MIN_COVERAGE, bl.MIN_POOL, bl.MIN_CURRENCY_POOL, bl.TOP, bl.STEP, bl.DRAWS) == (63, 0.80, 100, 20, 20, 21, 1000)
    assert bl.HORIZONS == (21, 63) and bl.COSTS_BPS == (10, 30, 60) and bl.SIGNAL == 'mom_6_1'
    assert bl.SCENARIOS == (('aucun', None), ('usd_0,25M', ('usd', 250_000.0)), ('usd_1M', ('usd', 1_000_000.0)), ('usd_5M', ('usd', 5_000_000.0)),
                            ('relatif_50%', ('rel', 0.50)), ('relatif_25%', ('rel', 0.25)))
    assert bl.PERIODS == (('1993-2015', None, '2015-12-31'), ('2017-2026', '2017-01-01', None))


# ───────── aucune donnée postérieure à la date, fenêtre antérieure ─────────
def test_liquidity_window_excludes_the_selection_date_and_the_future():
    days = business_days(300)
    base = candidate(1, days, volume=1_000_000)
    t = 200
    ref = study_for([base], days, [t]).liq[days[t]][1]
    assert ref[1] == 'ok' and ref[0] > 0
    altered = dict(base, volumes=[1 if bars_i >= t else v for bars_i, v in enumerate(base['volumes'])])            # volumes de t et de l'avenir bouleversés
    assert study_for([altered], days, [t]).liq[days[t]][1] == ref
    inside = dict(base, volumes=[10 if t - bl.WINDOW <= i < t else v for i, v in enumerate(base['volumes'])])      # fenêtre antérieure modifiée : la liquidité change
    assert study_for([inside], days, [t]).liq[days[t]][1][0] < ref[0] / 1000


def test_scores_and_liquidity_ignore_everything_after_t():
    days = business_days(330)
    cands = [candidate(i, days, drift=0.001 * (i % 3), seed=1) for i in range(20)]
    t = 220
    before = study_for(cands, days, [t])
    rnd = random.Random(7)
    future = []
    for c in cands:
        bars = [(d, p * (1 if d <= days[t] else math.exp(rnd.gauss(0, 0.5))), a * (1 if d <= days[t] else math.exp(rnd.gauss(0, 0.5)))) for d, p, a in c['bars']]
        vols = [v if d <= days[t] else v * 1000 for (d, _, _), v in zip(c['bars'], c['volumes'])]
        future.append(dict(c, bars=bars, volumes=vols))
    after = study_for(future, days, [t])
    assert before.liq[days[t]] == after.liq[days[t]] and before.score[days[t]] == after.score[days[t]]
    assert before.liq[days[t]]


# ───────── dates manquantes ─────────
def test_missing_sessions_in_the_window_make_the_title_ineligible():
    days = business_days(300)
    t = 200
    window = range(t - bl.WINDOW, t)
    ten_percent = {i for i in window if (i - t) % 10 == 0}                         # ≈ 10 % de séances sans donnée : toléré
    forty_percent = {i for i in window if i % 5 in (0, 1)}                         # ≈ 40 % : exclu
    ok = study_for([candidate(1, days, skip=ten_percent)], days, [t]).liq[days[t]][1]
    bad = study_for([candidate(2, days, skip=forty_percent)], days, [t]).liq[days[t]][2]
    assert ok[1] == 'ok' and bad[1] == 'coverage' and bad[0] is None


def test_session_without_volume_counts_as_missing():
    days = business_days(300)
    c = candidate(1, days)
    c['volumes'] = [None if 140 <= i < 200 else v for i, v in enumerate(c['volumes'])]
    assert study_for([c], days, [200]).liq[days[200]][1][1] == 'coverage'


# ───────── splits ─────────
def test_unadjusted_split_inside_the_window_makes_the_title_ineligible():
    days = business_days(320)
    t = 250
    inside = study_for([candidate(1, days, split_at=t - 20)], days, [t])
    before = study_for([candidate(2, days, split_at=t - 100)], days, [t])
    after = study_for([candidate(3, days, split_at=t + 5)], days, [t])
    assert inside.liq[days[t]][1][1] == 'split' and 1 in inside.split_titles
    assert before.liq[days[t]][2][1] == 'ok' and after.liq[days[t]][3][1] == 'ok'      # avant la fenêtre ou après la date : sans effet sur la décision


# ───────── devises et scénarios ─────────
def currency_universe(days):
    cands = []
    for i in range(30):
        cands.append(candidate(i, days, volume=1_000 * (i + 1), currency='USD', seed=1))          # valeur échangée ≈ 100 × volume : de 0,1 M à 3 M
    for i in range(30):
        cands.append(candidate(100 + i, days, volume=1_000 * (i + 1), currency='EUR', seed=2))
    return cands


def test_absolute_thresholds_use_only_dollar_titles_and_relative_ones_work_within_each_currency():
    days = business_days(330)
    study = study_for(currency_universe(days), days, [220])
    t = days[220]
    usd_1m = study.eligible(t, ('usd', 1_000_000.0))
    assert usd_1m and all(k < 100 for k in usd_1m)                                    # aucun titre en euros, aucun taux de change
    assert all(study.liq[t][k][0] >= 1_000_000.0 for k in usd_1m)
    half = study.eligible(t, ('rel', 0.50))
    assert {k for k in half if k < 100} and {k for k in half if k >= 100}             # les deux devises contribuent
    usd_half = sorted(study.liq[t][k][0] for k in half if k < 100)
    usd_rest = [study.liq[t][k][0] for k in range(30) if k not in half]
    assert usd_half[0] >= max(usd_rest)                                               # la moitié retenue est bien la plus liquide de SA devise
    assert abs(len([k for k in half if k < 100]) - 15) <= 1
    quarter = study.eligible(t, ('rel', 0.25))
    assert quarter < half and 6 <= len([k for k in quarter if k >= 100]) <= 9
    assert study.eligible(t, None) == set(study.liq[t])                                # « aucun » : tout le monde


def test_small_currency_groups_get_no_relative_threshold():
    days = business_days(330)
    cands = [candidate(i, days, volume=1_000 * (i + 1), currency='USD', seed=3) for i in range(30)] + [candidate(100 + i, days, currency='JPY', seed=4) for i in range(5)]
    study = study_for(cands, days, [220])
    assert not [k for k in study.eligible(days[220], ('rel', 0.5)) if k >= 100]       # 5 titres en yens < 20 : pas de seuil relatif


# ───────── sélection, tirages et frais ─────────
def test_picks_and_random_pool_come_only_from_eligible_titles():
    days = business_days(330)
    study = study_for(currency_universe(days), days, [220, 241])
    t = days[220]
    rule = ('usd', 1_000_000.0)
    eligible = study.eligible(t, rule)
    assert eligible and set(study.picks(t, rule)) <= eligible and len(study.picks(t, rule)) <= bl.TOP
    row = study.results('usd_1M', rule, [days[220], days[241]], 21, 'essai', top=5, min_pool=1, draws=50)
    expected = statistics.fmean(r[21] for k, r in study.fwd[t].items() if k in eligible and 21 in r)
    assert abs(row['by_date'][0]['universe'] - round(expected, 2)) < 1e-9               # l'univers de comparaison = les éligibles, pas tout le monde


def test_cost_levels_and_dropped_dates_are_reported():
    days = business_days(330)
    study = study_for(currency_universe(days), days, [220, 241, 262])
    dates = [days[220], days[241], days[262]]
    row = study.results('aucun', None, dates, 21, 'essai', min_pool=1, draws=50)
    for cost in bl.COSTS_BPS:
        assert abs(row['excess_net'][str(cost)] - (row['excess_gross'] - 2 * cost / 100)) < 0.011       # aller-retour = 2 × coût
    assert row['dates_total'] == 3 and row['dates_used'] + row['dates_dropped'] == 3
    strict = study.results('aucun', None, dates, 21, 'essai', min_pool=10_000, draws=50)
    assert strict['dates_used'] == 0 and strict['dates_dropped'] == 3 and 'pick_mean' not in strict      # univers trop petit : rien de comparé, mais compté


def test_random_draws_have_no_edge_without_signal():
    days = business_days(400)
    cands = [candidate(i, days, drift=0.0, sigma=0.012, volume=50_000, seed=5) for i in range(120)]
    study = bl.LiquidityStudy(days, [days[i] for i in range(130, 330, 21)], horizons=(21,))
    study.add(cands)
    row = study.results('aucun', None, list(study.dates), 21, 'essai', min_pool=50, draws=400)
    assert abs(row['random_mean_excess']) < 0.6 and row['p_random'] > 0.001           # un tirage au hasard ne bat pas l'univers


# ───────── de bout en bout ─────────
def test_cli_runs_the_whole_protocol_and_prints_every_scenario(tmp_path, capsys):
    days = business_days(1300)
    cands = [candidate(i, days, drift=0.0004, sigma=0.012, volume=2_000 + 900 * i, currency='USD' if i < 40 else 'EUR', seed=9) for i in range(70)]
    for c in cands:
        eh.write_history(str(tmp_path), c['key'], [(d, p, a, v) for (d, p, a), v in zip(c['bars'], c['volumes'])])
    eh.write_universe(str(tmp_path), [{'key': c['key'], 'symbol': c['symbol'], 'mic': 'XNYS', 'kind': 'equity', 'country': '', 'currency': c['currency']} for c in cands])
    out_json = str(tmp_path / 'r.json')
    cut = days[700]
    rc = bl.main(['--csv-dir', str(tmp_path), '--period', f'ancienne,,{cut}', '--period', f'recente,{days[760]},', '--min-pool', '20', '--min-titles', '0', '--json', out_json])
    text = capsys.readouterr().out
    assert rc == 0 and 'DÉJÀ été consultées' in text
    for name, _ in bl.SCENARIOS:
        assert name in text
    assert text.index('ancienne') < text.index('recente')
    saved = json.load(open(out_json, encoding='utf-8'))
    assert len(saved['results']) == 2 * len(bl.HORIZONS) * len(bl.SCENARIOS)           # TOUS les scénarios, y compris les défavorables
    assert all(d['date'] <= cut for r in saved['results'] if r['period'].startswith('ancienne') for d in r.get('by_date', []))
    assert set(saved['meta']['currencies']) == {'USD', 'EUR'}
