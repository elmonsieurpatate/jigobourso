"""Analyses statistiques du panel de recherche (scripts/research_panel.py). LECTURE SEULE, aucun réseau, aucune base, aucune modification de l'application.

Protocole : research/PROTOCOLE.md (figé avant tout résultat). Tout ce qui n'est pas dans la « famille principale » est exploratoire.

  python3 scripts/research_analyses.py rank       --panel .../panel.pkl.gz --universe ~/tmp-history-long/universe.csv --out .../out
  ... ic | deciles | risk | horizons | candidates
Chaque sous-commande écrit un JSON (<nom>.json) et un résumé lisible (<nom>.md) dans --out.
"""
import argparse
import bisect
import csv
import gzip
import json
import math
import os
import pickle
import random
import statistics
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

import research_stats as rs                                       # noqa: E402
from research_panel import CURRENCIES, GROUPS, HORIZONS, PRESETS  # noqa: E402

COST_BPS = (10, 30, 60)
MAIN_COST = 30
MIN_POOL = {'equity': 100, 'etf': 50}
MIN_CURRENCY_POOL = 20
SCENARIOS = {'equity': ('aucun', 'usd_1M', 'relatif_50%'), 'etf': ('aucun', 'usd_1M')}
REFERENCE_SCENARIO = 'usd_1M'
TOPS = (1, 5, 10, 20, 50)
SLICE_NAMES = {(0, 1): 'Top 1', (0, 5): 'Top 5', (0, 10): 'Top 10', (0, 20): 'Top 20', (0, 50): 'Top 50', (5, 10): 'rangs 6-10', (10, 20): 'rangs 11-20', (20, 50): 'rangs 21-50'}
SLICE_LIST = ((0, 1), (0, 5), (0, 10), (0, 20), (0, 50), (5, 10), (10, 20), (20, 50))
PERIODS = (('P1 1993-2007', '1993-01-01', '2007-12-31'), ('P2 2008-2015', '2008-01-01', '2015-12-31'), ('P3 2017-2026', '2017-01-01', '2026-12-31'))
USD_THRESHOLD = 1_000_000.0
DRAWS = 500
SEED = 1
SIGNALS = ('m61', 'm121', 'm31', 'm1', 'vol126', 'slope', 'r2', 'hi', 'mdd252', 'ma200', 'ma50', 'vtr', 'liq')
SIGNAL_LABELS = {'m61': 'momentum 6-1', 'm121': 'momentum 12-1', 'm31': 'momentum 3-1', 'm1': 'rendement du dernier mois (retournement si négatif)', 'vol126': 'volatilité 6 mois',
                 'slope': 'pente de tendance', 'r2': 'régularité (R²)', 'hi': 'distance au plus haut 12 mois', 'mdd252': 'pire baisse sur 12 mois', 'ma200': 'écart à la moyenne 200 j',
                 'ma50': 'écart à la moyenne 50 j', 'vtr': 'évolution des volumes', 'liq': 'valeur échangée (taille)'}
CAVEAT = ("Univers des titres encore cotés en 2026 (biais de survie, très marqué avant 2005) ; pas de taux de change ; pas de secteur ni de capitalisation ; périodes déjà consultées "
          "(exploratoire, pas une validation vierge).")


def nan(x):
    return x != x


class Data:
    def __init__(self, panel, meta=None):
        self.c, self.dates, self.ranked = panel['cols'], list(panel['dates']), panel['ranked']
        self.meta = meta or {}
        self.n = len(self.c['ti'])
        self.by = defaultdict(list)
        ti, grp = self.c['ti'], self.c['grp']
        for i in range(self.n):
            self.by[(ti[i], grp[i])].append(i)
        self._eligible, self._order, self._rowof = {}, {}, {}

    # ───────── éligibilité (mêmes règles que backtest_liquidity.py) ─────────
    def eligible(self, ti, grp, scen):
        key = (ti, grp, scen)
        if key in self._eligible:
            return self._eligible[key]
        rows = self.by.get((ti, grp), [])
        c = self.c
        if scen == 'aucun':
            out = set(rows)
        else:
            ok = [i for i in rows if c['status'][i] == 0 and not nan(c['liq'][i])]
            if scen == 'usd_1M':
                out = {i for i in ok if c['ccy'][i] == 0 and c['liq'][i] >= USD_THRESHOLD}
            else:
                pools = defaultdict(list)
                for i in ok:
                    pools[c['ccy'][i]].append((c['liq'][i], i))
                out = set()
                for items in pools.values():
                    if len(items) < MIN_CURRENCY_POOL:
                        continue
                    values = sorted(v for v, _ in items)
                    cut = values[min(len(values) - 1, int(0.5 * len(values)))]
                    out |= {i for v, i in items if v >= cut}
        self._eligible[key] = out
        return out

    def rowof(self, ti, grp):
        key = (ti, grp)
        if key not in self._rowof:
            self._rowof[key] = {self.c['key'][i]: i for i in self.by.get(key, [])}
        return self._rowof[key]

    # ───────── stratégies : liste ordonnée (meilleur d'abord) parmi les titres éligibles ─────────
    def order(self, strat, ti, grp, scen, limit=60):
        key = (strat, ti, grp, scen)
        if key in self._order:
            return self._order[key]
        elig = self.eligible(ti, grp, scen)
        out = ORDERERS[strat](self, ti, grp, elig)[:limit]
        self._order[key] = out
        return out

    def date_period(self, ti):
        d = self.dates[ti]
        for name, a, b in PERIODS:
            if a <= d <= b:
                return name
        return None


def _sorted_by(data, rows, score):
    scored = [(score(i), data.c['key'][i], i) for i in rows]
    scored = [(s, k, i) for s, k, i in scored if s is not None and not nan(s) and math.isfinite(s)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, _, i in scored]


def col_score(name, sign=1.0):
    return lambda data, ti, grp, elig: _sorted_by(data, elig, lambda i: sign * data.c[name][i])


def preset_orderer(name):
    def order(data, ti, grp, elig):
        keys = data.ranked.get((data.dates[ti], name, GROUPS[grp]), [])
        rowof = data.rowof(ti, grp)
        return [rowof[k] for k in keys if k in rowof and rowof[k] in elig]               # filtre de négociabilité APRÈS le classement, ordre conservé
    return order


def _median_filter(col, above=True):
    def keep(data, rows):
        vals = [data.c[col][i] for i in rows if not nan(data.c[col][i])]
        if not vals:
            return []
        med = statistics.median(vals)
        return [i for i in rows if not nan(data.c[col][i]) and (data.c[col][i] >= med if above else data.c[col][i] <= med)]
    return keep


def _mom_if(filter_fn):
    return lambda data, ti, grp, elig: _sorted_by(data, filter_fn(data, [i for i in elig if not nan(data.c['m61'][i])]), lambda i: data.c['m61'][i])


def c3_filter(data, rows):
    return [i for i in rows if not nan(data.c['m121'][i]) and data.c['m121'][i] > 0]


def c5(data, ti, grp, elig):
    c = data.c
    rows = [i for i in elig if not nan(c['m121'][i]) and not nan(c['m1'][i]) and c['m121'][i] > 0 and -0.10 <= c['m1'][i] <= 0.0]
    return _sorted_by(data, rows, lambda i: c['m121'][i])


def c6(data, ti, grp, elig):
    c = data.c
    rows = [i for i in elig if not nan(c['hi'][i]) and not nan(c['m31'][i]) and not nan(c['ma50'][i]) and c['hi'][i] <= -0.30 and c['m31'][i] > 0 and c['ma50'][i] > 0]
    return _sorted_by(data, rows, lambda i: c['m31'][i])


ORDERERS = {
    'regular': preset_orderer('regular'), 'fast': preset_orderer('fast'), 'recovery': preset_orderer('recovery'), 'low_volatility': preset_orderer('low_volatility'),
    'mom_6_1': col_score('m61'), 'mom_12_1': col_score('m121'), 'low_vol_126': col_score('vol126', -1.0), 'near_high': col_score('hi'),
    'smooth_mom': lambda data, ti, grp, elig: _sorted_by(data, elig, lambda i: None if nan(data.c['slope'][i]) or nan(data.c['r2'][i]) else data.c['slope'][i] * data.c['r2'][i]),
    'C1_regularite': _mom_if(_median_filter('r2', True)), 'C2_faible_vol': _mom_if(_median_filter('vol126', False)), 'C3_tendance_longue': _mom_if(c3_filter),
    'C4_volumes': _mom_if(_median_filter('vtr', True)), 'C5_correction_moderee': c5, 'C6_rebond_confirme': c6,
}
STRATEGIES = ('regular', 'fast', 'recovery', 'low_volatility', 'mom_6_1')
STRAT_LABELS = {'regular': 'Régulière', 'fast': 'Rapide', 'recovery': 'Rebond', 'low_volatility': 'Faible volatilité', 'mom_6_1': 'Momentum 6-1', 'mom_12_1': 'Momentum 12-1',
                'low_vol_126': 'Faible volatilité (règle simple)', 'near_high': 'Proche du plus haut', 'smooth_mom': 'Pente × R²',
                'C1_regularite': 'C1 momentum + régularité', 'C2_faible_vol': 'C2 momentum + faible volatilité', 'C3_tendance_longue': 'C3 momentum + tendance longue',
                'C4_volumes': 'C4 momentum + volumes en hausse', 'C5_correction_moderee': 'C5 tendance longue + correction modérée', 'C6_rebond_confirme': 'C6 rebond confirmé'}
CANDIDATES = ('C1_regularite', 'C2_faible_vol', 'C3_tendance_longue', 'C4_volumes', 'C5_correction_moderee', 'C6_rebond_confirme')
CLOSEST = {'C1_regularite': 'regular', 'C2_faible_vol': 'regular', 'C3_tendance_longue': 'regular', 'C4_volumes': 'regular', 'C5_correction_moderee': 'recovery', 'C6_rebond_confirme': 'recovery'}


# ───────── séries par date ─────────
def column(data, h, lag):
    return data.c[f"{'fg'[lag]}{h}"]


def date_rows(data, strat, grp, scen, lo, hi, h, lag, min_pool=None):
    """[(ti, rendement moyen de la sélection, rendement moyen de l'univers éligible, k, pool, médiane écart)] : une ligne par date valide. Univers = titres éligibles AVEC rendement connu."""
    col = column(data, h, lag)
    min_pool = MIN_POOL[GROUPS[grp]] if min_pool is None else min_pool
    out = []
    for ti in range(len(data.dates)):
        elig = data.eligible(ti, grp, scen)
        if len(elig) < min_pool:
            continue
        ordered = data.order(strat, ti, grp, scen)
        sel = ordered[lo:hi]
        got = [col[i] for i in sel if not nan(col[i])]
        need = max(1, math.ceil(0.5 * (hi - lo)))
        if len(got) < need:
            continue
        pool = [col[i] for i in elig if not nan(col[i])]
        if len(pool) < max(2 * len(got), min_pool):
            continue
        out.append((ti, statistics.fmean(got), statistics.fmean(pool), len(got), pool, statistics.median(got) - statistics.median(pool)))
    return out


def period_means(data, rows, values):
    out = {}
    for name, _, _ in PERIODS:
        vs = [v for r, v in zip(rows, values) if data.date_period(r[0]) == name]
        out[name] = {'dates': len(vs), 'mean': statistics.fmean(vs) if vs else None}
    return out


def rank_block(data, strat, grp, scen, lo, hi, h, lag, draws=DRAWS):
    rows = date_rows(data, strat, grp, scen, lo, hi, h, lag)
    if len(rows) < 8:
        return None
    excess = [r[1] - r[2] for r in rows]
    costs = {c: [e - 2 * c / 100.0 for e in excess] for c in COST_BPS}
    sp = rs.spacing(h)
    indep_idx = list(range(0, len(rows), sp))
    rng = random.Random(SEED)
    p_random = None
    if len(indep_idx) >= 3:
        observed = statistics.fmean(excess[i] for i in indep_idx)
        sims = []
        for _ in range(draws):
            sims.append(statistics.fmean(statistics.fmean(rng.sample(rows[i][4], rows[i][3])) - rows[i][2] for i in indep_idx))
        p_random = (1 + sum(1 for s in sims if s >= observed)) / (draws + 1)
    picks = [r[1] for r in rows]
    best = sorted(picks, reverse=True)
    positive_total = sum(p for p in picks if p > 0)
    return {'dates': len(rows), 'pick_mean': statistics.fmean(picks), 'pick_median': statistics.median(picks), 'universe_mean': statistics.fmean(r[2] for r in rows),
            'dispersion_dates': statistics.pstdev(picks), 'excess_gross': rs.summary(excess, h), 'excess_net': {str(c): statistics.fmean(v) for c, v in costs.items()},
            'net30': rs.summary(costs[MAIN_COST], h), 'share_positive_net30': 100.0 * sum(1 for v in costs[MAIN_COST] if v > 0) / len(rows),
            'median_gap_mean': statistics.fmean(r[5] for r in rows), 'p_random': p_random, 'avg_k': statistics.fmean(r[3] for r in rows),
            'best5pct_share_of_gains': (sum(best[:max(1, len(best) // 20)]) / positive_total) if positive_total > 0 else None,
            'periods_gross': period_means(data, rows, excess), 'periods_net30': period_means(data, rows, costs[MAIN_COST])}


# ───────── Analyse 1 : qualité du classement ─────────
def analysis_rank(data, strategies=STRATEGIES, horizons=(5, 21, 63), groups=('equity', 'etf'), lags=(0, 1), slices=SLICE_LIST):
    out = []
    for strat in strategies:
        for gname in groups:
            grp = GROUPS.index(gname)
            for scen in SCENARIOS[gname]:
                for lo, hi in slices:
                    for h in horizons:
                        for lag in lags:
                            if lag == 1 and (scen != REFERENCE_SCENARIO and not (gname == 'etf' and scen == 'aucun')):
                                continue                                              # sensibilité à l'exécution : scénario de référence seulement
                            block = rank_block(data, strat, grp, scen, lo, hi, h, lag)
                            if block:
                                out.append(dict(block, strategy=strat, group=gname, scenario=scen, slice=SLICE_NAMES[(lo, hi)], lo=lo, hi=hi, horizon=h, lag=lag))
    return out


# ───────── Analyse 2 : pouvoir prédictif (IC) ─────────
def date_signal_arrays(data, ti, grp, scen, sig, h, lag=0):
    col, s = column(data, h, lag), data.c[sig]
    rows = [i for i in data.eligible(ti, grp, scen) if not nan(s[i]) and not nan(col[i])]
    return rows, [s[i] for i in rows], [col[i] for i in rows]


def analysis_ic(data, horizons=(5, 21, 63), groups=('equity', 'etf'), min_rows=30):
    out, controls = [], {'m61': ('vol126',), 'vol126': ('m61',)}
    for gname in groups:
        grp = GROUPS.index(gname)
        for scen in SCENARIOS[gname]:
            for h in horizons:
                col = column(data, h, 0)
                for sig in SIGNALS:
                    ics, partials, dates_used = [], [], []
                    ctrl = controls.get(sig, ('m61', 'vol126'))
                    for ti in range(len(data.dates)):
                        rows = [i for i in data.eligible(ti, grp, scen) if not nan(data.c[sig][i]) and not nan(col[i])]
                        if len(rows) < min_rows:
                            continue
                        ic = rs.spearman([data.c[sig][i] for i in rows], [col[i] for i in rows])
                        if ic is None:
                            continue
                        ics.append(ic)
                        dates_used.append(ti)
                        crow = [i for i in rows if all(not nan(data.c[k][i]) for k in ctrl)]
                        if len(crow) >= min_rows:
                            pic = rs.partial_spearman([data.c[sig][i] for i in crow], [col[i] for i in crow], [[data.c[k][i] for i in crow] for k in ctrl])
                            if pic is not None:
                                partials.append((ti, pic))
                    if len(ics) < 8:
                        continue
                    out.append({'signal': sig, 'label': SIGNAL_LABELS[sig], 'group': gname, 'scenario': scen, 'horizon': h, 'ic': rs.summary(ics, h),
                                'partial_ic': rs.summary([p for _, p in partials], h) if len(partials) >= 8 else None, 'controls': list(ctrl),
                                'periods': {name: (statistics.fmean([v for t, v in zip(dates_used, ics) if data.date_period(t) == name]) if any(data.date_period(t) == name for t in dates_used) else None) for name, _, _ in PERIODS}})
    return out


def redundancy(data, group='equity', scen=REFERENCE_SCENARIO, max_dates=120, min_rows=30):
    """Corrélation de rang moyenne entre signaux (mêmes titres, même date) : mesurent-ils la même chose ?"""
    grp = GROUPS.index(group)
    total, count = defaultdict(float), defaultdict(int)
    step = max(1, len(data.dates) // max_dates)
    for ti in range(0, len(data.dates), step):
        elig = list(data.eligible(ti, grp, scen))
        for a_i, a in enumerate(SIGNALS):
            for b in SIGNALS[a_i + 1:]:
                rows = [i for i in elig if not nan(data.c[a][i]) and not nan(data.c[b][i])]
                if len(rows) < min_rows:
                    continue
                r = rs.spearman([data.c[a][i] for i in rows], [data.c[b][i] for i in rows])
                if r is not None:
                    total[(a, b)] += r
                    count[(a, b)] += 1
    return [{'a': a, 'b': b, 'mean_rank_correlation': total[(a, b)] / count[(a, b)], 'dates': count[(a, b)]} for (a, b) in sorted(count)]


# ───────── Analyse 3 : déciles ─────────
def decile_split(values, groups=10):
    """Indices (0..groups-1) par ordre croissant de valeur, effectifs égaux (ex æquo départagés par position)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    n = len(order)
    out = [0] * n
    for rank, i in enumerate(order):
        out[i] = min(groups - 1, rank * groups // n)
    return out


def analysis_deciles(data, horizons=(5, 21, 63), groups=('equity', 'etf'), min_rows=100, signals=SIGNALS, include_presets=True):
    out = []
    for gname in groups:
        grp = GROUPS.index(gname)
        for scen in SCENARIOS[gname]:
            if gname == 'equity' and scen == 'relatif_50%':
                continue
            for h in horizons:
                col = column(data, h, 0)
                names = list(signals) + (list(PRESETS) if include_presets else [])
                for sig in names:
                    means, medians = [[] for _ in range(10)], [[] for _ in range(10)]
                    spreads, by_tercile = [], {t: [] for t in range(3)}
                    ti_used = []
                    for ti in range(len(data.dates)):
                        if sig in PRESETS:
                            keys = data.ranked.get((data.dates[ti], sig, GROUPS[grp]), [])
                            rowof, elig = data.rowof(ti, grp), data.eligible(ti, grp, scen)
                            rows = [rowof[k] for k in keys if k in rowof and rowof[k] in elig and not nan(col[rowof[k]])]
                            values = [-p for p in range(len(rows))]                      # meilleur rang = valeur la plus haute
                        else:
                            rows = [i for i in data.eligible(ti, grp, scen) if not nan(data.c[sig][i]) and not nan(col[i])]
                            values = [data.c[sig][i] for i in rows]
                        if len(rows) < min_rows:
                            continue
                        ds = decile_split(values)
                        buckets = [[] for _ in range(10)]
                        for r, d in zip(rows, ds):
                            buckets[d].append(col[r])
                        for d in range(10):
                            means[d].append(statistics.fmean(buckets[d]))
                            medians[d].append(statistics.median(buckets[d]))
                        spreads.append(means[9][-1] - means[0][-1])
                        ti_used.append(ti)
                        if sig not in PRESETS:
                            liqs = [data.c['liq'][r] for r in rows]
                            if all(not nan(x) for x in liqs):
                                terc = decile_split(liqs, 3)
                                for q in range(3):
                                    sub = [(v, col[r]) for v, r, t in zip(values, rows, terc) if t == q]
                                    if len(sub) >= 50:
                                        qs = decile_split([v for v, _ in sub], 5)
                                        top = [x for (v, x), d in zip(sub, qs) if d == 4]
                                        bot = [x for (v, x), d in zip(sub, qs) if d == 0]
                                        by_tercile[q].append(statistics.fmean(top) - statistics.fmean(bot))
                    if len(spreads) < 8:
                        continue
                    avg = [statistics.fmean(m) for m in means]
                    out.append({'signal': sig, 'label': SIGNAL_LABELS.get(sig) or STRAT_LABELS.get(sig, sig), 'group': gname, 'scenario': scen, 'horizon': h, 'dates': len(spreads),
                                'decile_mean': avg, 'decile_median': [statistics.fmean(m) for m in medians],
                                'spread_d10_d1': rs.summary(spreads, h), 'share_dates_d10_above_d1': 100.0 * sum(1 for s in spreads if s > 0) / len(spreads),
                                'monotonicity': rs.spearman(list(range(10)), avg),
                                'tercile_spread_q5_q1': {str(q + 1): (rs.summary(v, h) if len(v) >= 8 else None) for q, v in by_tercile.items()},
                                'periods_spread': {name: (statistics.fmean([s for t, s in zip(ti_used, spreads) if data.date_period(t) == name]) if any(data.date_period(t) == name for t in ti_used) else None) for name, _, _ in PERIODS}})
    return out


# ───────── Analyses 4-5 : portefeuille chronologique rééquilibré ─────────
def portfolio_series(data, strat, grp, scen, top=20, every=1, h=None, lag=0, cost_bps=MAIN_COST, min_pool=None):
    """Portefeuille Top `top` rééquilibré toutes les `every` dates de décision (21 séances × every), détention de `h` séances (h = 21 × every par défaut). Chaque ligne :
    date, rendement brut, rendement de l'univers éligible, turnover réel (part des titres remplacés), rendement net (frais sur le turnover réel). Dates sans chevauchement."""
    h = h or 21 * every
    col = column(data, h, lag)
    min_pool = MIN_POOL[GROUPS[grp]] if min_pool is None else min_pool
    rows, previous = [], None
    for ti in range(0, len(data.dates), every):
        elig = data.eligible(ti, grp, scen)
        if len(elig) < min_pool:
            continue
        ordered = data.order(strat, ti, grp, scen)[:top]
        got = [col[i] for i in ordered if not nan(col[i])]
        pool = [col[i] for i in elig if not nan(col[i])]
        if len(got) < max(1, math.ceil(0.5 * top)) or len(pool) < max(2 * top, min_pool):
            previous = None
            continue
        keys = {data.c['key'][i] for i in ordered}
        turnover = 1.0 if previous is None else 1 - len(keys & previous) / max(1, len(keys))
        previous = keys
        gross, uni = statistics.fmean(got), statistics.fmean(pool)
        rows.append({'ti': ti, 'date': data.dates[ti], 'pick': gross, 'universe': uni, 'turnover': turnover, 'keys': sorted(keys), 'k': len(got),
                     'net': gross - 2 * cost_bps / 100.0 * turnover})
    return rows


def risk_block(data, rows, h):
    from analyze_momentum_risk import drawdown_episodes, loss_streaks, segments
    if len(rows) < 12:
        return None
    net = [r['net'] for r in rows]
    uni = [r['universe'] for r in rows]
    dates = [r['date'] for r in rows]
    var, cvar = rs.var_cvar(net)
    uvar, ucvar = rs.var_cvar(uni)
    dd = drawdown_episodes(dates, net)
    udd = drawdown_episodes(dates, uni)
    seg = segments([{'date': r['date'], 'v': r['net']} for r in rows])
    streaks = loss_streaks(seg, lambda r: r['v'])
    excess = [n - u for n, u in zip(net, uni)]
    periods_per_year = 252.0 / h
    return {'periods': len(rows), 'mean_net': statistics.fmean(net), 'universe_mean': statistics.fmean(uni), 'median_net': statistics.median(net),
            'sd': statistics.pstdev(net), 'universe_sd': statistics.pstdev(uni), 'sd_annualized': statistics.pstdev(net) * math.sqrt(periods_per_year),
            'max_drawdown': rs.max_drawdown(net), 'universe_max_drawdown': rs.max_drawdown(uni), 'var95': var, 'cvar95': cvar, 'universe_var95': uvar, 'universe_cvar95': ucvar,
            'worst': min(net), 'universe_worst': min(uni), 'share_negative': 100.0 * sum(1 for v in net if v < 0) / len(net), 'turnover_mean': statistics.fmean(r['turnover'] for r in rows),
            'excess_net': rs.summary(excess, h), 'longest_loss_streak': streaks['longest'], 'loss_streak_counts': streaks['counts'],
            'drawdowns': dd[:3], 'universe_drawdowns': udd[:1]}


def analysis_risk(data, strategies=STRATEGIES, scenarios=('aucun', 'usd_1M', 'relatif_50%')):
    out = []
    for strat in strategies:
        for scen in scenarios:
            for lag in (0, 1):
                if lag == 1 and scen != REFERENCE_SCENARIO:
                    continue
                rows = portfolio_series(data, strat, 0, scen, 20, 1, 21, lag)
                block = risk_block(data, rows, 21)
                if block:
                    out.append(dict(block, strategy=strat, group='equity', scenario=scen, lag=lag, rebalance='21 séances'))
    return out


def worst_episodes(data, rows, symbols, n=6, h=21):
    """Pires périodes d'un portefeuille chronologique : date, titres responsables (contribution), performance du portefeuille et de l'univers, conditions de marché observables."""
    col = column(data, h, 0)
    out = []
    for r in sorted(rows, key=lambda r: r['net'])[:n]:
        ti = r['ti']
        rowof = data.rowof(ti, 0)
        movers = sorted(((col[rowof[k]], k) for k in r['keys'] if k in rowof and not nan(col[rowof[k]])))[:3]
        elig = list(data.eligible(ti, 0, REFERENCE_SCENARIO))
        m61 = [data.c['m61'][i] for i in elig if not nan(data.c['m61'][i])]
        v126 = [data.c['vol126'][i] for i in elig if not nan(data.c['vol126'][i])]
        out.append({'date': r['date'], 'portfolio': r['net'], 'universe': r['universe'], 'movers': [(symbols.get(k, str(k)), v) for v, k in movers],
                    'market_median_momentum_6_1': 100 * statistics.median(m61) if m61 else None, 'market_median_volatility_daily': 100 * statistics.median(v126) if v126 else None})
    return out


def concentration(data, rows, symbols_meta):
    """Part moyenne du pays, de la devise (et du secteur si l'univers en contient) le plus représenté dans les 20 titres, et renouvellement moyen."""
    out = {}
    for field in ('country', 'currency', 'category'):
        shares = []
        for r in rows:
            vals = [(symbols_meta.get(k) or {}).get(field) or None for k in r['keys']]
            lab = [v for v in vals if v]
            if len(lab) >= 0.8 * len(vals) and lab:
                shares.append(max(Counter(lab).values()) / len(lab))
        if shares:
            out[field] = {'top_share_mean': 100 * statistics.fmean(shares), 'top_share_max': 100 * max(shares), 'dates': len(shares)}
    return out


def analysis_horizons(data, strategies=STRATEGIES, scen=REFERENCE_SCENARIO):
    """(a) sélection initiale conservée N séances : TOUS les horizons ; (b) portefeuille réellement rééquilibré tous les 21 et 63 séances (turnover réel). Jamais mélangés."""
    held, rebalanced, persistence = [], [], []
    for strat in strategies:
        for h in HORIZONS:
            block = rank_block(data, strat, 0, scen, 0, 20, h, 0, draws=200)
            if block:
                held.append({'strategy': strat, 'horizon': h, 'dates': block['dates'], 'pick_mean': block['pick_mean'], 'universe_mean': block['universe_mean'],
                             'excess_gross': block['excess_gross'], 'net30': block['net30'], 'dispersion_dates': block['dispersion_dates'],
                             'net_per_21_sessions': block['net30']['mean'] * 21.0 / h})
        for every in (1, 3):
            rows = portfolio_series(data, strat, 0, scen, 20, every, 21 * every, 0)
            if len(rows) >= 8:
                excess = [r['net'] - r['universe'] for r in rows]
                rebalanced.append({'strategy': strat, 'rebalance_sessions': 21 * every, 'periods': len(rows), 'turnover_mean': statistics.fmean(r['turnover'] for r in rows),
                                   'gross_excess': statistics.fmean(r['pick'] - r['universe'] for r in rows), 'net_excess': rs.summary(excess, 21 * every), 'risk': risk_block(data, rows, 21 * every)})
        base = portfolio_series(data, strat, 0, scen, 20, 1, 21, 0)
        by_ti = {r['ti']: set(r['keys']) for r in base}
        for gap in (1, 3):
            shares = [len(by_ti[t] & by_ti[t + gap]) / max(1, len(by_ti[t])) for t in by_ti if t + gap in by_ti]
            if shares:
                persistence.append({'strategy': strat, 'gap_sessions': 21 * gap, 'common_share_mean': statistics.fmean(shares), 'pairs': len(shares)})
    return {'held': held, 'rebalanced': rebalanced, 'persistence': persistence}


# ───────── Analyse 6 : candidates, critères de réussite fixés d'avance ─────────
def analysis_candidates(data, scen=REFERENCE_SCENARIO):
    results, tests = [], 12
    threshold = 0.05 / tests
    base_rows = {}
    for h in (21, 63):
        base_rows[h] = date_rows(data, 'mom_6_1', 0, scen, 0, 20, h, 0)
    base_risk = risk_block(data, portfolio_series(data, 'mom_6_1', 0, scen, 20, 1, 21, 0), 21)
    for cand in CANDIDATES:
        entry = {'candidate': cand, 'label': STRAT_LABELS[cand], 'closest_existing': CLOSEST[cand], 'horizons': {}}
        verdict_parts = []
        for h in (21, 63):
            rows = date_rows(data, cand, 0, scen, 0, 20, h, 0)
            by_ti_base = {r[0]: r for r in base_rows[h]}
            diff, diff_ti = [], []
            for r in rows:
                b = by_ti_base.get(r[0])
                if b:
                    diff.append((r[1] - b[1]))
                    diff_ti.append(r[0])
            block = rank_block(data, cand, 0, scen, 0, 20, h, 0, draws=200)
            closest = rank_block(data, CLOSEST[cand], 0, scen, 0, 20, h, 0, draws=200)
            base = rank_block(data, 'mom_6_1', 0, scen, 0, 20, h, 0, draws=200)
            summ = rs.summary(diff, h) if len(diff) >= 8 else None
            per = {}
            for name, _, _ in PERIODS:
                vs = [d for d, t in zip(diff, diff_ti) if data.date_period(t) == name]
                per[name] = statistics.fmean(vs) if vs else None
            entry['horizons'][str(h)] = {'candidate': block, 'mom_6_1': base, 'closest': closest, 'difference_vs_mom_6_1': summ, 'difference_periods': per, 'dates_common': len(diff)}
            positive_net = bool(summ and summ['mean'] > 0)
            significant = bool(summ and summ['p_block'] is not None and summ['p_block'] < threshold and summ['ci_low'] is not None and summ['ci_low'] > 0)
            periods_ok = sum(1 for v in per.values() if v is not None and v > 0) >= 2
            verdict_parts.append((positive_net, significant, periods_ok))
        cand_risk = risk_block(data, portfolio_series(data, cand, 0, scen, 20, 1, 21, 0), 21)
        # CVaR négative : « pas pire de plus de 10 % » = cvar_cand >= cvar_base × 1,10 (moins négative ou pas plus de 10 % plus négative)
        risk_ok = bool(cand_risk and base_risk and cand_risk['cvar95'] is not None and base_risk['cvar95'] is not None and cand_risk['cvar95'] >= base_risk['cvar95'] * 1.10)
        entry['risk'] = cand_risk
        entry['criteria'] = {'net_positive_21_and_63': all(p[0] for p in verdict_parts), 'significant_bonferroni_12_both': all(p[1] for p in verdict_parts),
                             'at_least_2_of_3_periods_both': all(p[2] for p in verdict_parts), 'cvar_not_worse_than_10pct': risk_ok}
        c = entry['criteria']
        entry['verdict'] = 'retenue (exploratoire)' if all(c.values()) else ('écartée' if not c['net_positive_21_and_63'] else 'non concluante')
        results.append(entry)
    return {'candidates': results, 'base_risk': base_risk, 'bonferroni_tests': tests, 'threshold': threshold}


# ───────── métadonnées et sorties ─────────
def load_meta(path):
    meta = {}
    if path and os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as fh:
            for u in csv.DictReader(fh):
                meta[int(u['key'])] = {'symbol': u.get('symbol'), 'country': u.get('country') or None, 'currency': u.get('currency') or None, 'category': u.get('category') or None}
    return meta


def load_data(panel_path, universe_path=None):
    with gzip.open(os.path.expanduser(panel_path), 'rb') as fh:
        panel = pickle.load(fh)
    return Data(panel, load_meta(os.path.expanduser(universe_path) if universe_path else None))


def fmt(x, digits=2, signed=True):
    return '—' if x is None else f"{x:{'+' if signed else ''}.{digits}f}"


def render_rank(results):
    L = ['# Analyse 1 : qualité du classement', '', f'*{CAVEAT}*', '']
    for gname in ('equity', 'etf'):
        for scen in SCENARIOS[gname]:
            for h in (5, 21, 63):
                rows = [r for r in results if r['group'] == gname and r['scenario'] == scen and r['horizon'] == h and r['lag'] == 0]
                if not rows:
                    continue
                L += [f'## {"Actions" if gname == "equity" else "ETF"} · {scen} · {h} séances (entrée à la clôture de t)', '',
                      '| Stratégie | Sélection | Dates | Moy. sél. | Médiane | Univers | Excès brut [IC95 blocs] | Net 30 pb | % dates + | p hasard |', '|---|---|---|---|---|---|---|---|---|---|']
                for r in sorted(rows, key=lambda r: (STRATEGIES.index(r['strategy']) if r['strategy'] in STRATEGIES else 9, r['lo'], r['hi'])):
                    g = r['excess_gross']
                    L.append(f"| {STRAT_LABELS.get(r['strategy'], r['strategy'])} | {r['slice']} | {r['dates']} | {fmt(r['pick_mean'])} | {fmt(r['pick_median'])} | {fmt(r['universe_mean'])} | "
                             f"{fmt(g['mean'])} [{fmt(g['ci_low'])} ; {fmt(g['ci_high'])}] | {fmt(r['excess_net']['30'])} | {r['share_positive_net30']:.0f} | {fmt(r['p_random'], 3, False)} |")
                L.append('')
    return '\n'.join(L)


def write_outputs(out_dir, name, payload, markdown):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, default=lambda o: None if o != o else str(o))
    with open(os.path.join(out_dir, f'{name}.md'), 'w', encoding='utf-8') as fh:
        fh.write(markdown + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('analysis', choices=('rank', 'ic', 'deciles', 'risk', 'horizons', 'candidates'))
    ap.add_argument('--panel', required=True)
    ap.add_argument('--universe')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    data = load_data(args.panel, args.universe)
    out = os.path.expanduser(args.out)
    if args.analysis == 'rank':
        res = analysis_rank(data)
        write_outputs(out, 'rank', res, render_rank(res))
    elif args.analysis == 'ic':
        res = {'ic': analysis_ic(data), 'redundancy': redundancy(data)}
        write_outputs(out, 'ic', res, f"# Analyse 2 : pouvoir prédictif\n\n{len(res['ic'])} lignes (voir ic.json)")
    elif args.analysis == 'deciles':
        res = analysis_deciles(data)
        write_outputs(out, 'deciles', res, f"# Analyse 3 : déciles\n\n{len(res)} lignes (voir deciles.json)")
    elif args.analysis == 'risk':
        res = analysis_risk(data)
        extra = {}
        for scen in ('usd_1M', 'aucun'):
            rows = portfolio_series(data, 'mom_6_1', 0, scen, 20, 1, 21, 0)
            extra[scen] = {'episodes': worst_episodes(data, rows, {k: v['symbol'] for k, v in data.meta.items()}), 'concentration': concentration(data, rows, data.meta)}
        write_outputs(out, 'risk', {'portfolios': res, 'momentum_episodes': extra}, f"# Analyse 4 : risques\n\n{len(res)} portefeuilles (voir risk.json)")
    elif args.analysis == 'horizons':
        res = analysis_horizons(data)
        write_outputs(out, 'horizons', res, f"# Analyse 5 : horizons\n\n{len(res['held'])} lignes (voir horizons.json)")
    else:
        res = analysis_candidates(data)
        write_outputs(out, 'candidates', res, f"# Analyse 6 : candidates\n\n{len(res['candidates'])} candidates (voir candidates.json)")
    print(f'{args.analysis} : terminé', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
