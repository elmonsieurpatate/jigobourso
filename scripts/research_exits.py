"""Règles de sortie et durée de conservation, pour les cinq stratégies de Jigobourso. LECTURE SEULE : aucune base, aucun réseau, aucune modification de l'application.

Protocole figé avant tout résultat : research/PROTOCOLE_SORTIES.md (règles, seuils, verdicts). Mêmes sélections initiales (Top 20, actions négociables ≥ 1 M$/jour) pour toutes les variantes,
entrée à la clôture de la séance suivant la date de décision, signal calculé avec les seules données du jour, vente à la clôture de la séance suivante, durée maximale 126 séances.

Usage :
  python3 scripts/research_exits.py --panel ~/tmp-backtest/research/out/panel/panel.pkl.gz --csv-dir ~/tmp-history-long [--out sorties.md] [--json sorties.json]
(le panel est celui de scripts/research_panel.py ; PYTHONPATH doit pointer sur la racine du dépôt)
"""
import argparse
import bisect
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import backtest_walkforward as bw                                  # noqa: E402
import research_analyses as ra                                     # noqa: E402
import research_stats as rs                                        # noqa: E402

STRATEGIES = ('regular', 'fast', 'recovery', 'low_volatility', 'mom_6_1')
LABELS = {'regular': 'Régulière', 'fast': 'Rapide', 'recovery': 'Rebond', 'low_volatility': 'Faible volatilité', 'mom_6_1': 'Momentum 6-1'}
SCENARIO = 'usd_1M'
TOP = 20
MAX_HOLD = 126
FIXED = (21, 63, 126)
COST_BPS = (10, 30, 60)
MAIN_COST = 30
MIN_POOL = 100
MIN_POSITIONS = 10                       # positions complètes minimales par date (sur 20)
STOP = 0.20                              # R3 : stop suiveur à -20 % depuis le plus haut depuis l'entrée
RANK_LIMIT = 50                          # R1
R2_FLOOR = 1 - (2 / 3) ** 2              # seuil « souple » du profil Régulière (0,556)
VOL21_LIMIT = 2.25                       # % : 1,5 x la limite (1,5 %) du profil Faible volatilité
CHECK_EVERY = 5                          # règle R² contrôlée chaque semaine
GENERAL = ('rank50', 'mom_negative', 'trailing')
RULE_LABELS = {'rank50': 'Sortie du Top 50', 'mom_negative': 'Momentum négatif', 'trailing': 'Stop suiveur -20 %'}
SPECIFIC = {'regular': 'Perte de régularité (R² 63 s < 0,556)', 'fast': 'Ralentissement (rendement 21 s < 0)', 'recovery': 'Fin du rebond (sous la moyenne 50 j)',
            'low_volatility': 'Hausse de volatilité (21 s > 2,25 %)', 'mom_6_1': 'Ralentissement (rendement 63 s < 0)'}
BONFERRONI = 0.05 / 20
CVAR_GAIN = 0.10
BLOCK_HORIZON = 126


class Series:
    """Cours ajustés d'un titre et sommes cumulées (calculées une fois)."""
    def __init__(self, full):
        self.dates, self.closes, _, self.breaks = full
        self.n = len(self.closes)
        prefix = [0.0]
        for c in self.closes:
            prefix.append(prefix[-1] + c)
        self.prefix = prefix
        self.logs = [math.log(c) for c in self.closes]

    def ma(self, d, length):
        return (self.prefix[d + 1] - self.prefix[d + 1 - length]) / length if d + 1 >= length else None

    def r2(self, d, length):
        if d + 1 < length:
            return None
        ys = self.logs[d + 1 - length:d + 1]
        n = len(ys)
        mean_x = (n - 1) / 2.0
        sxx = sum((i - mean_x) ** 2 for i in range(n))
        mean_y = sum(ys) / n
        sxy = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(ys))
        syy = sum((y - mean_y) ** 2 for y in ys)
        return None if syy == 0 else (sxy * sxy) / (sxx * syy)

    def vol(self, d, length):
        if d < length:
            return None
        rets = [self.closes[i] / self.closes[i - 1] - 1 for i in range(d - length + 1, d + 1)]
        return 100 * statistics.pstdev(rets)

    def ret(self, d, length):
        return self.closes[d] / self.closes[d - length] - 1 if d >= length else None


def locate(series, date, stale=bw.MAX_STALE_DAYS):
    """Indice de la dernière séance <= date (None si le titre n'a pas coté récemment)."""
    base = bisect.bisect_right(series.dates, date) - 1
    if base < 0:
        return None
    import datetime
    if (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(series.dates[base])).days > stale:
        return None
    return base


def exit_signals(strategy, series, entry, end, rank_days, top_sets):
    """{variante: indice de séance de la VENTE}. Un signal à la clôture du jour d entraîne une vente à la clôture de d + 1 (plafonnée à `end`). rank_days : [(indice du jour du contrôle, index dans top_sets)]."""
    closes = series.closes
    found = {}
    peak = closes[entry]
    rank_at = {d: k for d, k in rank_days}
    for d in range(entry + 1, end):
        peak = max(peak, closes[d])
        if 'trailing' not in found and closes[d] <= (1 - STOP) * peak:
            found['trailing'] = d + 1
        if 'mom_negative' not in found:
            m = series.ret(d - 21, 105) if d - 126 >= 0 else None            # cours J-21 / cours J-126
            if m is not None and m < 0:
                found['mom_negative'] = d + 1
        if 'rank50' not in found and d in rank_at and not top_sets[rank_at[d]]:
            found['rank50'] = d + 1
        if 'specific' not in found:
            hit = False
            if strategy == 'regular':
                if (d - entry) % CHECK_EVERY == 0:
                    r2 = series.r2(d, 63)
                    hit = r2 is not None and r2 < R2_FLOOR
            elif strategy == 'fast':
                r = series.ret(d, 21)
                hit = r is not None and r < 0
            elif strategy == 'recovery':
                ma = series.ma(d, 50)
                hit = ma is not None and closes[d] < ma
            elif strategy == 'low_volatility':
                v = series.vol(d, 21)
                hit = v is not None and v > VOL21_LIMIT
            else:
                r = series.ret(d, 63)
                hit = r is not None and r < 0
            if hit:
                found['specific'] = d + 1
        if len(found) == 4:
            break
    return found


def simulate_position(strategy, series, decision_date, rank_checks):
    """Résultats de toutes les variantes pour une position, ou None si les 126 séances de suivi n'existent pas. rank_checks : [(date du calendrier, le titre est-il dans le Top 50 de sa stratégie à cette date)]"""
    base = locate(series, decision_date)
    if base is None:
        return None
    entry, end = base + 1, base + 1 + MAX_HOLD
    if end >= series.n or any(base < b <= end for b in series.breaks):
        return None
    p0 = series.closes[entry]
    rank_days, top_sets = [], []
    for cal_date, member in rank_checks:
        d = locate(series, cal_date)
        if d is not None and entry < d < end:
            rank_days.append((d, len(top_sets)))
            top_sets.append(member)
    exits = exit_signals(strategy, series, entry, end, rank_days, top_sets)
    peaks, dd, worst = p0, [], 0.0
    for j in range(entry, end + 1):
        peaks = max(peaks, series.closes[j])
        worst = min(worst, series.closes[j] / peaks - 1)
        dd.append(worst)
    out = {}
    plan = {f'fixe_{n}': entry + n for n in FIXED}
    for name in ('rank50', 'mom_negative', 'trailing', 'specific'):
        plan[name] = min(exits[name], end) if name in exits else end
    for name, x in plan.items():
        out[name] = {'ret': 100 * (series.closes[x] / p0 - 1), 'days': x - entry, 'mdd': 100 * dd[x - entry],
                     'after': 100 * (series.closes[end] / series.closes[x] - 1) if x < end else None}
    return out


def load_series(csv_dir, keys):
    universe = [u for u in bw.csv_universe(csv_dir) if int(u['key']) in keys]
    out = {}
    for lot in bw.csv_batches(csv_dir, universe, 0, 1, batch=100):
        for raw in lot:
            c = bw.prepare(raw)
            out[int(c['key'])] = Series(c['full'])
    return out


def selections(data, strategies=STRATEGIES, top=TOP):
    """{(stratégie, ti): [clés]} : Top 20 des actions négociables, dates où l'univers éligible atteint MIN_POOL."""
    sel = {}
    for strat in strategies:
        for ti in range(len(data.dates)):
            if len(data.eligible(ti, 0, SCENARIO)) < MIN_POOL:
                continue
            rows = data.order(strat, ti, 0, SCENARIO)[:top]
            if len(rows) >= MIN_POSITIONS:
                sel[(strat, ti)] = [int(data.c['key'][i]) for i in rows]
    return sel


def rank_sets(data, strat, ti):
    """[(date calendrier, ensemble des clés du Top 50 de la stratégie à cette date)] pour les 5 dates de décision suivantes."""
    out = []
    for k in range(1, 6):
        tj = ti + k
        if tj >= len(data.dates):
            break
        rows = data.order(strat, tj, 0, SCENARIO)[:RANK_LIMIT]
        out.append((data.dates[tj], {int(data.c['key'][i]) for i in rows}))
    return out


def run(data, series, strategies=STRATEGIES, log=lambda *_: None):
    sel = selections(data, strategies)
    results = defaultdict(list)           # (stratégie, ti) -> [résultats par position]
    t0, done = time.monotonic(), 0
    for (strat, ti), keys in sorted(sel.items()):
        checks = rank_sets(data, strat, ti)
        for key in keys:
            s = series.get(key)
            if s is None:
                continue
            member_checks = [(date, key in top) for date, top in checks]
            res = simulate_position(strat, s, data.dates[ti], member_checks)
            if res:
                results[(strat, ti)].append(res)
        done += 1
        if done % 200 == 0:
            log(f'{done}/{len(sel)} sélections · {time.monotonic() - t0:.0f} s')
    return results


def variants_for(strategy):
    return [f'fixe_{n}' for n in FIXED] + list(GENERAL) + ['specific']


def aggregate(data, results, strat, cost=MAIN_COST):
    """Pour une stratégie : séries par date (moyenne sur les positions) de chaque variante, plus statistiques de position."""
    cost_pts = 2 * cost / 100.0
    dates = sorted(ti for (s, ti) in results if s == strat and len(results[(s, ti)]) >= MIN_POSITIONS)
    per_date = {v: [] for v in variants_for(strat)}
    positions = {v: [] for v in per_date}
    meta = {v: {'early': 0, 'n': 0, 'days': [], 'mdd': [], 'after': [], 'premature': 0} for v in per_date}
    universe = []
    for ti in dates:
        pos = results[(strat, ti)]
        for v in per_date:
            nets = [p[v]['ret'] - cost_pts for p in pos]
            per_date[v].append(statistics.fmean(nets))
            positions[v].extend(nets)
            m = meta[v]
            for p in pos:
                m['n'] += 1
                m['days'].append(p[v]['days'])
                m['mdd'].append(p[v]['mdd'])
                if p[v]['after'] is not None and p[v]['days'] < MAX_HOLD:
                    m['early'] += 1
                    m['after'].append(p[v]['after'])
                    m['premature'] += 1 if p[v]['after'] > 0 else 0
        col = data.c['g126']
        uni = [col[i] for i in data.eligible(ti, 0, SCENARIO) if col[i] == col[i]]
        universe.append(statistics.fmean(uni) if uni else float('nan'))
    return dates, per_date, positions, meta, universe


def cvar(values, level=0.95):
    return rs.var_cvar(values, level)[1]


def verdict(diff, cvar_rule, cvar_fixed):
    """Verdict réglé d'avance (PROTOCOLE_SORTIES.md)."""
    if not diff:
        return 'données insuffisantes'
    improved = cvar_rule is not None and cvar_fixed is not None and cvar_rule >= cvar_fixed * (1 - CVAR_GAIN if cvar_fixed < 0 else 1 + CVAR_GAIN)
    if diff['ci_low'] is not None and diff['ci_low'] > 0 and diff['p_block'] is not None and diff['p_block'] < BONFERRONI:
        return 'améliore le rendement'
    if improved and diff['ci_high'] is not None and diff['ci_high'] >= 0:
        return 'réduit le risque sans coût détecté'
    if improved and diff['ci_high'] is not None and diff['ci_high'] < 0:
        return 'réduit le risque mais coûte du rendement'
    return "pas d'effet détecté"


def analyse(data, results, cost=MAIN_COST):
    out = {}
    for strat in STRATEGIES:
        dates, per_date, positions, meta, universe = aggregate(data, results, strat, cost)
        if len(dates) < 20:
            continue
        fixed126 = per_date['fixe_126']
        cv_fixed = cvar(fixed126)
        rows = []
        for v in per_date:
            m = meta[v]
            days = statistics.fmean(m['days'])
            equiv = min(FIXED, key=lambda n: abs(n - days))
            diff126 = [a - b for a, b in zip(per_date[v], fixed126)]
            diff_eq = [a - b for a, b in zip(per_date[v], per_date[f'fixe_{equiv}'])]
            s126 = rs.summary(diff126, BLOCK_HORIZON) if v != 'fixe_126' else None
            periods = {}
            for name, _, _ in ra.PERIODS:
                vs = [d for ti, d in zip(dates, diff126) if data.date_period(ti) == name]
                periods[name] = statistics.fmean(vs) if vs else None
            rows.append({'variant': v, 'label': variant_label(strat, v), 'dates': len(dates), 'positions': m['n'],
                         'mean_net': statistics.fmean(per_date[v]), 'median_date': statistics.median(per_date[v]), 'p5_positions': rs.var_cvar(positions[v], 0.95)[0],
                         'cvar95_dates': cvar(per_date[v]), 'mean_mdd': statistics.fmean(m['mdd']), 'early_share': 100.0 * m['early'] / m['n'], 'days_mean': days,
                         'premature_share': (100.0 * m['premature'] / m['early']) if m['early'] else None, 'after_mean': statistics.fmean(m['after']) if m['after'] else None,
                         'after_median': statistics.median(m['after']) if m['after'] else None,
                         'diff_vs_126': s126, 'equivalent_fixed': equiv, 'diff_vs_equivalent': rs.summary(diff_eq, BLOCK_HORIZON) if v != f'fixe_{equiv}' else None,
                         'periods_diff_vs_126': periods,
                         'verdict': verdict(s126, cvar(per_date[v]), cv_fixed) if (v in GENERAL or v == 'specific') else None})
        out[strat] = {'rows': rows, 'universe_mean_126': statistics.fmean(u for u in universe if u == u), 'dates': len(dates)}
    return out


def variant_label(strat, v):
    if v.startswith('fixe_'):
        return f'Conserver {v[5:]} séances'
    return SPECIFIC[strat] if v == 'specific' else RULE_LABELS[v]


def f(x, d=2, signed=True):
    return '—' if x is None else f"{x:{'+' if signed else ''}.{d}f}"


def render(report, cost=MAIN_COST):
    L = ['# Règles de sortie et durée de conservation', '',
         f"*Sélections Top 20 (actions négociables ≥ 1 M$/jour), entrée à la clôture suivante, frais {cost} pb par sens, argent en liquidités après une sortie, fenêtre de 126 séances. "
         "Univers des titres encore cotés en 2026 (biais de survie) ; périodes déjà consultées : exploratoire. Protocole : research/PROTOCOLE_SORTIES.md.*", '']
    for strat, block in report.items():
        L += [f"## {LABELS[strat]} · {block['dates']} dates · univers éligible tenu 126 séances : {f(block['universe_mean_126'])} % (brut)", '',
              '| Variante | Rendement net moyen | Pire 5 % des positions | CVaR 95 % des dates | Baisse max. moyenne | Sorties anticipées | Jours détenus | Ventes prématurées | Variation après vente | Écart vs conserver 126 s [IC95 blocs] | Écart vs durée fixe équivalente | Verdict |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|']
        for r in block['rows']:
            d, e = r['diff_vs_126'], r['diff_vs_equivalent']
            L.append(f"| {r['label']} | {f(r['mean_net'])} | {f(r['p5_positions'], 1)} | {f(r['cvar95_dates'], 1)} | {f(r['mean_mdd'], 1)} | {r['early_share']:.0f} % | {r['days_mean']:.0f} | "
                     f"{f(r['premature_share'], 0, False) + ' %' if r['premature_share'] is not None else '—'} | {f(r['after_mean'])} | "
                     f"{(f(d['mean']) + ' [' + f(d['ci_low']) + ' ; ' + f(d['ci_high']) + '] p=' + f(d['p_block'], 3, False)) if d else '—'} | "
                     f"{(f(e['mean']) + ' vs ' + str(r['equivalent_fixed']) + ' s [' + f(e['ci_low']) + ' ; ' + f(e['ci_high']) + ']') if e else '—'} | {r['verdict'] or ''} |")
        L += ['', 'Stabilité (écart moyen vs conserver 126 séances, par sous-période) : ' + ' ; '.join(
            f"{r['label']} → " + ', '.join(f"{k.split()[0]} {f(v)}" for k, v in r['periods_diff_vs_126'].items()) for r in block['rows'] if r['verdict'] is not None), '']
    L += ['## Lecture', '',
          '- **Rendement net** : moyenne par position sur 126 séances, frais déduits, argent à 0 % après une sortie. Une règle qui sort tôt immobilise moins longtemps le capital mais renonce à la suite de la hausse.',
          '- **Ventes prématurées** : part des sorties anticipées dont le cours est plus haut à la séance 126 qu\'au moment de la vente. **Variation après vente** : moyenne de cette variation (positive = gain manqué, négative = perte évitée).',
          '- **Verdict** : fixé d\'avance (Bonferroni sur 20 tests, p < 0,0025 ; CVaR améliorée d\'au moins 10 %). « pas d\'effet détecté » ne veut pas dire « inutile » : l\'échantillon est limité et exploratoire.',
          '- Limites : titres encore cotés en 2026 uniquement ; clôtures seulement (un stop peut être exécuté plus bas) ; pas de réinvestissement ; positions étudiées une à une.']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--panel', required=True)
    ap.add_argument('--csv-dir', required=True)
    ap.add_argument('--universe', help='universe.csv (défaut : celui de --csv-dir)')
    ap.add_argument('--out')
    ap.add_argument('--json')
    args = ap.parse_args(argv)
    csv_dir = os.path.expanduser(args.csv_dir)
    data = ra.load_data(args.panel, args.universe or os.path.join(csv_dir, 'universe.csv'))
    sel = selections(data)
    keys = {k for ks in sel.values() for k in ks}
    print(f'{len(sel)} sélections · {len(keys)} titres à charger', file=sys.stderr)
    series = load_series(csv_dir, keys)
    results = run(data, series, log=lambda m: print(m, file=sys.stderr, flush=True))
    report = analyse(data, results)
    if not report:
        print('Pas assez de données.', file=sys.stderr)
        return 3
    text = render(report)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    if args.json:
        with open(os.path.expanduser(args.json), 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == '__main__':
    sys.exit(main())
