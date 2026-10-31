"""Relecture du résultat de scripts/backtest_liquidity.py (fichier JSON) : mêmes données, deux corrections de comparabilité. Bibliothèque standard seulement, aucune base, aucun réseau.

1. `--from` / `--to` : restreint les dates (par exemple 1993-01-01 pour la période « 1993-2015 » : le test d'origine, faute de date de début, remontait jusqu'en 1984).
2. DATES COMMUNES : un scénario strict écarte les dates où l'univers éligible compte moins de 100 titres, un scénario large les garde. Comparer des scénarios sur des dates différentes
   mélange l'effet de la liquidité et celui de la période. Le second tableau ne garde, pour chaque période et horizon, que les dates valables pour TOUS les scénarios.

Pour chaque ligne : moyenne de la sélection et de l'univers éligible, excès brut, excès net à 10, 30 et 60 points de base par sens, part de dates positives, t-stat sur les dates sans
chevauchement, et intervalle de confiance à 95 % de l'excès net (10 pb) obtenu en rééchantillonnant ces dates (il tient compte de la variation d'une date à l'autre, ce que ne fait pas
la p-valeur « hasard » du test d'origine, qui ne compare que des tirages à une même date).

Usage : python3 scripts/summarize_liquidity.py --json ~/tmp-backtest/result-liquidity.json [--from 1993-01-01] [--to 2015-12-31]
"""
import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict

COSTS_BPS = (10, 30, 60)
STEP = 21
BOOTSTRAP = 4000
SEED = 1


def tstat(values):
    if len(values) < 3:
        return None
    sd = statistics.stdev(values)
    return None if sd == 0 else statistics.fmean(values) / (sd / math.sqrt(len(values)))


def analyse(rows, horizon, seed=SEED):
    """rows : [(date, sélection, univers)] triées. Renvoie les statistiques ou None s'il n'y a rien."""
    if not rows:
        return None
    rows = sorted(rows)
    excess = [p - u for _, p, u in rows]
    spacing = max(1, math.ceil(horizon / STEP))
    indep = excess[::spacing]                                  # sous-échantillon sans chevauchement
    cost = 2 * COSTS_BPS[0] / 100.0
    net_indep = [e - cost for e in indep]
    low = high = None
    if len(net_indep) >= 3:
        rng = random.Random(seed)
        means = sorted(statistics.fmean(rng.choices(net_indep, k=len(net_indep))) for _ in range(BOOTSTRAP))
        low, high = means[int(0.025 * BOOTSTRAP)], means[int(0.975 * BOOTSTRAP) - 1]
    return {'dates': len(rows), 'indep': len(indep), 'pick': statistics.fmean(p for _, p, _ in rows), 'universe': statistics.fmean(u for _, _, u in rows),
            'gross': statistics.fmean(excess), 'net': {c: statistics.fmean(excess) - 2 * c / 100.0 for c in COSTS_BPS},
            'positive': 100 * sum(1 for e in excess if e - cost > 0) / len(excess), 't': tstat(net_indep), 'low': low, 'high': high}


def collect(data, start=None, end=None):
    """{(période, horizon): {scénario: {date: (sélection, univers)}}}, dates restreintes à [start, end]."""
    groups = defaultdict(dict)
    for r in data['results']:
        if not r.get('by_date'):
            continue
        rows = {d['date']: (d['pick'], d['universe']) for d in r['by_date'] if (start is None or d['date'] >= start) and (end is None or d['date'] <= end)}
        groups[(r['period'], r['horizon'])][r['scenario']] = rows
    return groups


def fmt(x, width, signed=False):
    return f"{'—':>{width}}" if x is None else f"{x:>{width}{'+' if signed else ''}.2f}"


def table(title, scenarios, horizon):
    head = (f"{'scénario':<13}{'dates':>6}{'indép.':>7}{'sélection':>10}{'univers':>9}{'excès brut':>11}" + ''.join(f"{'net ' + str(c) + 'pb':>10}" for c in COSTS_BPS)
            + f"{'% dates+':>9}{'t net':>7}{'IC95% net 10pb':>20}")
    lines = [title, head, '-' * len(head)]
    for name, rows in scenarios:
        a = analyse(rows, horizon)
        if a is None:
            lines.append(f'{name:<13}  aucune date')
            continue
        ci = '—' if a['low'] is None else f"[{a['low']:+.2f} ; {a['high']:+.2f}]"
        lines.append(f"{name:<13}{a['dates']:>6}{a['indep']:>7}{a['pick']:>9.2f}%{a['universe']:>8.2f}%{a['gross']:>10.2f}%" + ''.join(f"{a['net'][c]:>9.2f}%" for c in COSTS_BPS)
                     + f"{a['positive']:>8.0f}%{fmt(a['t'], 7)}{ci:>20}")
    return lines


def pooled_tables(groups):
    """Toutes périodes ensemble : pour chaque horizon et scénario, les dates COMMUNES à tous les scénarios de chaque période, mises bout à bout. Une seule estimation, un seul intervalle."""
    lines = []
    horizons = sorted({h for _, h in groups})
    for horizon in horizons:
        parts = [scen for (_, h), scen in groups.items() if h == horizon and scen]
        names = list(parts[0]) if parts else []
        pooled = {}
        for name in names:
            rows = []
            for scen in parts:
                common = set.intersection(*(set(r) for r in scen.values()))
                rows += [(d, *scen[name][d]) for d in sorted(common)]
            pooled[name] = rows
        count = len(next(iter(pooled.values()), []))
        lines += table(f'── TOUTES PÉRIODES ENSEMBLE · {horizon} séances · dates communes de chaque période ({count} dates) ──', [(n, pooled[n]) for n in names], horizon) + ['']
    comparisons = len(horizons) * max((len(scen) for scen in groups.values()), default=0)
    if comparisons:
        threshold = round(statistics.NormalDist().inv_cdf(1 - 0.025 / comparisons), 2)          # test bilatéral à 5 % divisé par le nombre de lignes
        lines.append(f'Comparaisons multiples : {comparisons} lignes (scénarios × horizons) ; pour garder un risque de faux positif de 5 % sur l\'ensemble (Bonferroni), un t net devrait dépasser environ {threshold}.')
    return lines


def render(data, start=None, end=None, pooled=False, pooled_only=False):
    groups = collect(data, start, end)
    span = ' · '.join(x for x in (f'dates ≥ {start}' if start else '', f'dates ≤ {end}' if end else '') if x) or 'toutes les dates'
    lines = [f'Relecture du test de liquidité · {span}', '']
    for (period, horizon) in ([] if pooled_only else sorted(groups, key=lambda k: (k[0], k[1]))):
        scen = groups[(period, horizon)]
        order = list(scen)
        lines += table(f'── {period} · {horizon} séances · dates propres à chaque scénario ──', [(n, [(d, *v) for d, v in scen[n].items()]) for n in order], horizon) + ['']
        common = set.intersection(*(set(rows) for rows in scen.values())) if scen else set()
        lines += table(f'── {period} · {horizon} séances · DATES COMMUNES à tous les scénarios ({len(common)} dates) ──',
                       [(n, [(d, *scen[n][d]) for d in sorted(common)]) for n in order], horizon) + ['']
    if pooled or pooled_only:
        lines += pooled_tables(groups)
    lines += ["Lecture : « excès » = sélection moins univers éligible, en points sur l'horizon ; « net » = excès moins l'aller-retour (2 × coût). « t net » et l'intervalle utilisent les dates sans",
             "chevauchement (une sur trois à 63 séances). Un intervalle qui contient 0 signifie que l'avantage n'est pas établi statistiquement, même si la moyenne est positive."]
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json', required=True, help='fichier produit par backtest_liquidity.py --json')
    ap.add_argument('--from', dest='start', help='AAAA-MM-JJ : première date gardée')
    ap.add_argument('--to', dest='end', help='AAAA-MM-JJ : dernière date gardée')
    ap.add_argument('--pooled', action='store_true', help='ajoute les tableaux « toutes périodes ensemble »')
    ap.add_argument('--pooled-only', action='store_true', help='affiche seulement les tableaux « toutes périodes ensemble »')
    args = ap.parse_args(argv)
    with open(args.json, encoding='utf-8') as fh:
        data = json.load(fh)
    print(render(data, args.start, args.end, args.pooled, args.pooled_only))
    return 0


if __name__ == '__main__':
    sys.exit(main())
