"""Améliorations du Momentum 6-1 : huit variantes fixées d'avance (research/PROTOCOLE_STRATEGIES.md). LECTURE SEULE sur le panel de scripts/research_panel.py ; aucune modification de l'application.

Usage :
  PYTHONPATH=$PWD python3 scripts/research_strategies.py --panel ~/tmp-backtest/research/out/panel/panel.pkl.gz [--out strategies.md] [--json strategies.json]
"""
import argparse
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import research_analyses as ra                                     # noqa: E402
import research_stats as rs                                        # noqa: E402

TOP = 20
HORIZON = 21
LAG = 1                                  # entrée à la clôture de la séance suivante
COST_BPS = (10, 30, 60)
MAIN_COST = 30
MIN_POOL = 100
SCENARIOS = ('usd_1M', 'relatif_50%')
PRIMARY = 'usd_1M'
BASELINE = 'mom_6_1'
RECENT_WINNERS_CUT = 0.90                # V3 : on exclut le décile le plus haut du rendement du dernier mois
EXTREME_VOL_CUT = 0.80                   # V7 : on exclut le quintile le plus volatil
VARIANTS = ('mom_12_1', 'mom_compose', 'mom_sans_hausse_recente', 'proche_plus_haut', 'mom_vol_inverse', 'mom_filtre_marche', 'mom_sans_vol_extreme', 'trimestriel')
LABELS = {'mom_6_1': 'Momentum 6-1 (référence)', 'mom_12_1': 'V1 Momentum 12-1', 'mom_compose': 'V2 Momentum composite 6-1 + 12-1', 'mom_sans_hausse_recente': 'V3 Momentum sans hausse récente (hors décile haut du mois)',
          'proche_plus_haut': 'V4 Proche du plus haut annuel', 'mom_vol_inverse': 'V5 Momentum pondéré par 1/volatilité', 'mom_filtre_marche': 'V6 Momentum avec filtre de marché',
          'mom_sans_vol_extreme': 'V7 Momentum sans volatilité extrême (hors quintile haut)', 'trimestriel': 'V8 Momentum rééquilibré tous les 63 séances'}
BONFERRONI = 0.05 / len(VARIANTS)
CVAR_GAIN = 0.10


def nan(x):
    return x != x


def percentile_ranks(values):
    """{clé: rang percentile 0..1} pour un dict {clé: valeur}."""
    keys = list(values)
    r = rs.ranks([values[k] for k in keys])
    n = max(1, len(keys) - 1)
    return {k: (x - 1) / n for k, x in zip(keys, r)}


def quantile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def basket(data, ti, variant, scen):
    """{ligne du panel: poids} (somme 1) ou {} pour des liquidités. Seules les informations connues à la date ti servent."""
    c = data.c
    elig = data.eligible(ti, 0, scen)
    if variant in ('mom_6_1', 'mom_vol_inverse', 'mom_filtre_marche'):
        rows = data.order('mom_6_1', ti, 0, scen)[:TOP]
    elif variant == 'mom_12_1':
        rows = data.order('mom_12_1', ti, 0, scen)[:TOP]
    elif variant == 'proche_plus_haut':
        rows = data.order('near_high', ti, 0, scen)[:TOP]
    elif variant == 'mom_compose':
        both = [i for i in elig if not nan(c['m61'][i]) and not nan(c['m121'][i])]
        a = percentile_ranks({i: c['m61'][i] for i in both})
        b = percentile_ranks({i: c['m121'][i] for i in both})
        scored = sorted(both, key=lambda i: (-(a[i] + b[i]) / 2, c['key'][i]))
        rows = scored[:TOP]
    elif variant == 'mom_sans_hausse_recente':
        pool = [i for i in elig if not nan(c['m61'][i]) and not nan(c['m1'][i])]
        if len(pool) < MIN_POOL:
            return {}
        cut = quantile([c['m1'][i] for i in pool], RECENT_WINNERS_CUT)
        rows = sorted((i for i in pool if c['m1'][i] <= cut), key=lambda i: (-c['m61'][i], c['key'][i]))[:TOP]
    elif variant == 'mom_sans_vol_extreme':
        pool = [i for i in elig if not nan(c['m61'][i]) and not nan(c['vol126'][i])]
        if len(pool) < MIN_POOL:
            return {}
        cut = quantile([c['vol126'][i] for i in pool], EXTREME_VOL_CUT)
        rows = sorted((i for i in pool if c['vol126'][i] <= cut), key=lambda i: (-c['m61'][i], c['key'][i]))[:TOP]
    else:
        raise ValueError(variant)
    if len(rows) < math.ceil(0.5 * TOP):
        return {}
    if variant == 'mom_filtre_marche':
        med = [c['m121'][i] for i in elig if not nan(c['m121'][i])]
        if not med or statistics.median(med) <= 0:
            return {}
    if variant == 'mom_vol_inverse':
        inv = {i: 1.0 / c['vol126'][i] for i in rows if not nan(c['vol126'][i]) and c['vol126'][i] > 0}
        total = sum(inv.values())
        return {i: v / total for i, v in inv.items()} if total else {}
    return {i: 1.0 / len(rows) for i in rows}


def run_variant(data, variant, scen, cost=MAIN_COST):
    """Série chronologique : [{ti, date, pick, universe, turnover, net, invested, keys}] (dates valides seulement, toutes les 21 séances)."""
    col = ra.column(data, HORIZON, LAG)
    rows, previous = [], {}
    for ti in range(len(data.dates)):
        elig = data.eligible(ti, 0, scen)
        if len(elig) < MIN_POOL:
            previous = {}
            continue
        w = basket(data, ti, variant, scen)
        pool = [col[i] for i in elig if not nan(col[i])]
        if len(pool) < MIN_POOL:
            previous = {}
            continue
        known = {i: x for i, x in w.items() if not nan(col[i])}
        if w and len(known) < 0.5 * len(w):
            previous = {}
            continue
        total = sum(known.values())
        pick = sum(x * col[i] for i, x in known.items()) / total if total else 0.0
        keys = {int(data.c['key'][i]): x / total for i, x in known.items()} if total else {}
        names = set(keys) | set(previous)
        change = sum(abs(keys.get(k, 0.0) - previous.get(k, 0.0)) for k in names)
        previous = keys
        rows.append({'ti': ti, 'date': data.dates[ti], 'pick': pick, 'universe': statistics.fmean(pool), 'turnover': 0.5 * change, 'invested': 1.0 if keys else 0.0,
                     'keys': sorted(keys), 'k': len(keys), 'net': pick - (cost / 100.0) * change})
    return rows


def compound(values):
    v = 1.0
    for x in values:
        v *= 1 + x / 100.0
    return 100 * (v - 1)


def quarterly_pair(data, scen, cost=MAIN_COST):
    """V8 : [(date, rendement du rééquilibrage trimestriel, rendement mensuel composé sur les mêmes 63 séances)], frais inclus pour les deux."""
    monthly = {r['ti']: r for r in run_variant(data, BASELINE, scen, cost)}
    col63 = ra.column(data, 63, LAG)
    out, previous = [], {}
    for ti in range(0, len(data.dates), 3):
        if ti not in monthly or ti + 1 not in monthly or ti + 2 not in monthly:
            previous = {}
            continue
        elig = data.eligible(ti, 0, scen)
        rows = data.order('mom_6_1', ti, 0, scen)[:TOP]
        known = [i for i in rows if not nan(col63[i])]
        if len(rows) < 10 or len(known) < 0.5 * len(rows):
            previous = {}
            continue
        keys = {int(data.c['key'][i]): 1.0 / len(known) for i in known}
        change = sum(abs(keys.get(k, 0.0) - previous.get(k, 0.0)) for k in set(keys) | set(previous))
        previous = keys
        pick = statistics.fmean(col63[i] for i in known)
        out.append({'ti': ti, 'date': data.dates[ti], 'quarterly': pick - (cost / 100.0) * change, 'monthly': compound([monthly[ti + j]['net'] for j in range(3)]),
                    'turnover_q': 0.5 * change, 'turnover_m': statistics.fmean(monthly[ti + j]['turnover'] for j in range(3))})
    return out


def metrics(rows, h=HORIZON):
    net = [r['net'] for r in rows]
    var, cvar = rs.var_cvar(net)
    sd = statistics.pstdev(net)
    return {'periods': len(rows), 'mean_net': statistics.fmean(net), 'median_net': statistics.median(net), 'sd': sd, 'ratio': statistics.fmean(net) / sd if sd else None,
            'max_drawdown': rs.max_drawdown(net), 'var95': var, 'cvar95': cvar, 'worst': min(net), 'turnover': statistics.fmean(r['turnover'] for r in rows),
            'invested': 100.0 * statistics.fmean(r['invested'] for r in rows), 'share_negative': 100.0 * sum(1 for v in net if v < 0) / len(net)}


def verdict(diff, periods, m, base):
    if not diff:
        return 'données insuffisantes'
    positive_periods = sum(1 for v in periods.values() if v is not None and v > 0) >= 2
    better_cvar = m['cvar95'] is not None and base['cvar95'] is not None and m['cvar95'] >= base['cvar95'] * (1 - CVAR_GAIN)
    ratio_ok = m['ratio'] is not None and base['ratio'] is not None and m['ratio'] >= base['ratio']
    if diff['ci_low'] is not None and diff['ci_low'] > 0 and diff['p_block'] is not None and diff['p_block'] < BONFERRONI and positive_periods:
        return 'améliore le rendement'
    if better_cvar and ratio_ok and diff['ci_high'] is not None and diff['ci_high'] >= 0 and positive_periods:
        return 'meilleur compromis rendement/risque'
    if better_cvar and not ratio_ok:
        return 'réduit le risque mais coûte du rendement'
    return 'pas mieux'


def period_means(data, rows, values):
    out = {}
    for name, _, _ in ra.PERIODS:
        vs = [v for r, v in zip(rows, values) if data.date_period(r['ti']) == name]
        out[name] = statistics.fmean(vs) if vs else None
    return out


def analyse(data, scen):
    base_rows = run_variant(data, BASELINE, scen)
    base = metrics(base_rows)
    base_by = {r['ti']: r for r in base_rows}
    out = {'baseline': dict(base, label=LABELS[BASELINE]), 'variants': []}
    for v in VARIANTS:
        if v == 'trimestriel':
            pairs = quarterly_pair(data, scen)
            if len(pairs) < 20:
                continue
            q = [dict(ti=p['ti'], net=p['quarterly'], turnover=p['turnover_q'], invested=1.0) for p in pairs]
            m = metrics(q, 63)
            mm = metrics([dict(ti=p['ti'], net=p['monthly'], turnover=p['turnover_m'], invested=1.0) for p in pairs], 63)
            diff_series = [p['quarterly'] - p['monthly'] for p in pairs]
            diff = rs.summary(diff_series, 63)
            periods = period_means(data, q, diff_series)
            out['variants'].append({'variant': v, 'label': LABELS[v], 'metrics': m, 'reference_same_windows': mm, 'diff': diff, 'periods_diff': periods,
                                    'verdict': verdict(diff, periods, m, mm), 'unit': 'par période de 63 séances'})
            continue
        rows = run_variant(data, v, scen)
        if len(rows) < 20:
            continue
        common = [r for r in rows if r['ti'] in base_by]
        diff_series = [r['net'] - base_by[r['ti']]['net'] for r in common]
        diff = rs.summary(diff_series, HORIZON)
        periods = period_means(data, common, diff_series)
        m = metrics(rows)
        out['variants'].append({'variant': v, 'label': LABELS[v], 'metrics': m, 'diff': diff, 'periods_diff': periods, 'verdict': verdict(diff, periods, m, base),
                                'unit': 'par période de 21 séances', 'common_dates': len(common),
                                'cost_sensitivity': {str(c): statistics.fmean(r['net'] for r in run_variant(data, v, scen, c)) for c in COST_BPS}})
    out['baseline']['cost_sensitivity'] = {str(c): statistics.fmean(r['net'] for r in run_variant(data, BASELINE, scen, c)) for c in COST_BPS}
    return out


def f(x, d=2, signed=True):
    return '—' if x is None else f"{x:{'+' if signed else ''}.{d}f}"


def render(report):
    L = ['# Pistes d\'amélioration du Momentum 6-1', '',
         '*Portefeuille de 20 titres, rééquilibré toutes les 21 séances, entrée à la clôture suivante, frais 30 pb par sens sur les poids échangés, actions négociables. '
         'Univers des titres encore cotés en 2026 (biais de survie) ; périodes déjà consultées : exploratoire. Protocole : research/PROTOCOLE_STRATEGIES.md.*', '']
    for scen, block in report.items():
        b = block['baseline']
        L += [f"## Scénario « {scen} »{' (référence des conclusions)' if scen == PRIMARY else ' (robustesse)'}", '',
              '| Variante | Rendement net moyen | Écart-type | Rendement / écart-type | Baisse max. | CVaR 95 % | Pire période | Rotation | Investi | Écart vs référence [IC95 blocs] | Stabilité (1993-2007 / 2008-2015 / 2017-2026) | Verdict |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|',
              f"| {b['label']} | {f(b['mean_net'])} | {f(b['sd'], 2, False)} | {f(b['ratio'], 3)} | {f(b['max_drawdown'], 0)} | {f(b['cvar95'], 1)} | {f(b['worst'], 0)} | {b['turnover']:.2f} | {b['invested']:.0f} % | — | — | — |"]
        for v in block['variants']:
            m, d = v['metrics'], v['diff']
            per = ' / '.join(f(x) for x in v['periods_diff'].values())
            L.append(f"| {v['label']} | {f(m['mean_net'])} | {f(m['sd'], 2, False)} | {f(m['ratio'], 3)} | {f(m['max_drawdown'], 0)} | {f(m['cvar95'], 1)} | {f(m['worst'], 0)} | {m['turnover']:.2f} | {m['invested']:.0f} % | "
                     f"{(f(d['mean']) + ' [' + f(d['ci_low']) + ' ; ' + f(d['ci_high']) + '] p=' + f(d['p_block'], 3, False)) if d else '—'} | {per} | {v['verdict']} |")
        tri = next((v for v in block['variants'] if v['variant'] == 'trimestriel'), None)
        if tri:
            r = tri['reference_same_windows']
            L += ['', f"V8 se lit par période de 63 séances : référence mensuelle sur les mêmes fenêtres → rendement net {f(r['mean_net'])}, rotation moyenne par mois {r['turnover']:.2f}, CVaR 95 % {f(r['cvar95'], 1)}."]
        L += ['', 'Sensibilité aux frais (rendement net moyen par période, 10 / 30 / 60 pb) : ' + ' ; '.join(
            f"{v['label'].split(' ')[0]} {'/'.join(f(x) for x in v['cost_sensitivity'].values())}" for v in [dict(label='Réf', cost_sensitivity=b['cost_sensitivity'])] + [x for x in block['variants'] if 'cost_sensitivity' in x]), '']
    L += ['## Lecture', '',
          '- **Rendement / écart-type** : rendement moyen par période divisé par sa dispersion (plus haut = meilleur compromis). **CVaR 95 %** : moyenne des 5 % de périodes les plus mauvaises.',
          '- **Verdict** : fixé d\'avance (Bonferroni sur 8 variantes, p < 0,00625 ; CVaR améliorée d\'au moins 10 % ; au moins 2 sous-périodes sur 3 favorables). « pas mieux » ne prouve pas que la variante est mauvaise : l\'échantillon est limité et exploratoire.',
          '- **Limites** : titres encore cotés en 2026 uniquement, pas de change, clôtures seulement, pas de secteur ; un verdict favorable doit être confirmé sur de nouvelles données.']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--panel', required=True)
    ap.add_argument('--out')
    ap.add_argument('--json')
    args = ap.parse_args(argv)
    data = ra.load_data(args.panel, None)
    report = {scen: analyse(data, scen) for scen in SCENARIOS}
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
