"""Résumé lisible (texte) des résultats JSON de scripts/research_analyses.py, pour les lire sans télécharger les fichiers. Lecture seule.
Usage : python3 scripts/research_digest.py DOSSIER_RESULTATS risk|horizons|candidates|rank|ic|deciles
"""
import json
import os
import sys

SL = {'regular': 'Régulière', 'fast': 'Rapide', 'recovery': 'Rebond', 'low_volatility': 'Faible vol.', 'mom_6_1': 'Momentum 6-1'}


def f(x, d=2, s=True):
    return '—' if x is None else f"{x:{'+' if s else ''}.{d}f}"


def ci(b):
    return '—' if not b else f"{f(b['mean'])} [{f(b['ci_low'])};{f(b['ci_high'])}] p={f(b['p_block'], 3, False)} n={b['dates']}"


def risk(d):
    print('PORTEFEUILLES (Top 20, rééquilibrés toutes les 21 séances, frais 30 pb sur le turnover réel)')
    for r in d['portfolios']:
        print(f"{SL.get(r['strategy'], r['strategy']):13} {r['scenario']:12} lag{r['lag']} n={r['periods']:3} moy={f(r['mean_net'])} univ={f(r['universe_mean'])} écart={ci(r['excess_net'])} "
              f"sd={f(r['sd'], 1, False)} MDD={f(r['max_drawdown'], 0)}(univ {f(r['universe_max_drawdown'], 0)}) VaR95={f(r['var95'], 1)} CVaR95={f(r['cvar95'], 1)} "
              f"pire={f(r['worst'], 0)} %neg={r['share_negative']:.0f} turnover={r['turnover_mean']:.2f} série+longue={r['longest_loss_streak'].get('length')}")
    for scen, e in d['momentum_episodes'].items():
        print(f'\nPIRES ÉPISODES Momentum 6-1 · {scen}')
        for x in e['episodes']:
            print(f"  {x['date']} portefeuille {f(x['portfolio'], 1)} univers {f(x['universe'], 1)} · {', '.join(f'{s} {f(v, 0)}' for s, v in x['movers'])} · marché: mom médian {f(x['market_median_momentum_6_1'], 0)}%, vol jour {f(x['market_median_volatility_daily'], 1, False)}%")
        print('  concentration :', {k: f"{v['top_share_mean']:.0f}% (max {v['top_share_max']:.0f}%)" for k, v in e['concentration'].items()})


def horizons(d):
    print('SÉLECTION CONSERVÉE N SÉANCES (Top 20, usd_1M) : rendement par 21 séances équivalentes, net 30 pb')
    for r in d['held']:
        print(f"{SL.get(r['strategy'], r['strategy']):13} h={r['horizon']:3} n={r['dates']:3} sél={f(r['pick_mean'])} univ={f(r['universe_mean'])} excès brut {ci(r['excess_gross'])} net30 {f(r['net30']['mean'])} (≈{f(r['net_per_21_sessions'])}/21s)")
    print('\nREBALANCÉ')
    for r in d['rebalanced']:
        print(f"{SL.get(r['strategy'], r['strategy']):13} tous les {r['rebalance_sessions']:3} séances turnover={r['turnover_mean']:.2f} excès brut={f(r['gross_excess'])} net {ci(r['net_excess'])}")
    print('\nPERSISTANCE', [(SL.get(p['strategy'], p['strategy']), p['gap_sessions'], round(p['common_share_mean'], 2)) for p in d['persistence']])


def candidates(d):
    print(f"CANDIDATES (Bonferroni {d['bonferroni_tests']} tests, seuil p<{d['threshold']:.4f}) ; Momentum 6-1 CVaR95 mensuelle = {f(d['base_risk']['cvar95'], 1) if d['base_risk'] else '—'}")
    for c in d['candidates']:
        print(f"\n{c['label']} → {c['verdict']} · critères {c['criteria']}")
        for h, b in c['horizons'].items():
            cd, base, cl = b['candidate'], b['mom_6_1'], b['closest']
            print(f"  h={h}: cand net30 excès={f(cd['excess_net']['30']) if cd else '—'} | mom6-1={f(base['excess_net']['30']) if base else '—'} | {c['closest_existing']}={f(cl['excess_net']['30']) if cl else '—'} | diff vs mom6-1 {ci(b['difference_vs_mom_6_1'])} périodes {b['difference_periods']}")
        if c['risk']:
            print(f"  risque: CVaR95={f(c['risk']['cvar95'], 1)} MDD={f(c['risk']['max_drawdown'], 0)} turnover={c['risk']['turnover_mean']:.2f}")


def rank(d):
    for r in d:
        if r['scenario'] != 'usd_1M' or r['group'] != 'equity' or r['lag'] != 0:
            continue
        g = r['excess_gross']
        print(f"{SL.get(r['strategy'], r['strategy']):13} {r['slice']:11} h={r['horizon']:2} n={r['dates']:3} sél={f(r['pick_mean'])} méd={f(r['pick_median'])} univ={f(r['universe_mean'])} excès brut {f(g['mean'])} [{f(g['ci_low'])};{f(g['ci_high'])}] net30={f(r['excess_net']['30'])} %+={r['share_positive_net30']:.0f} p_hasard={f(r['p_random'], 3, False)}")


def ic(d):
    for r in d['ic']:
        if r['scenario'] != 'usd_1M' or r['group'] != 'equity':
            continue
        p = r['partial_ic']
        print(f"{r['signal']:7} h={r['horizon']:2} IC moy={f(r['ic']['mean'], 3)} méd={f(r['ic']['median'], 3)} [{f(r['ic']['ci_low'], 3)};{f(r['ic']['ci_high'], 3)}] %+={r['ic']['share_positive']:.0f} t={f(r['ic']['t_indep'], 1)} n={r['ic']['dates']} | partiel {f(p['mean'], 3) if p else '—'} [{f(p['ci_low'], 3) if p else '—'};{f(p['ci_high'], 3) if p else '—'}]")
    print('\nREDONDANCE (|corr rang| > 0,5)')
    for r in d['redundancy']:
        if abs(r['mean_rank_correlation']) > 0.5:
            print(f"  {r['a']}~{r['b']}: {r['mean_rank_correlation']:.2f}")


def deciles(d):
    for r in d:
        if r['scenario'] != 'usd_1M' or r['group'] != 'equity':
            continue
        s = r['spread_d10_d1']
        print(f"{r['signal']:14} h={r['horizon']:2} D1={f(r['decile_mean'][0], 1)} D5={f(r['decile_mean'][4], 1)} D10={f(r['decile_mean'][9], 1)} D10-D1 {f(s['mean'])} [{f(s['ci_low'])};{f(s['ci_high'])}] %dates D10>D1={r['share_dates_d10_above_d1']:.0f} monotonie={f(r['monotonicity'], 2)}")


if __name__ == '__main__':
    base, name = sys.argv[1], sys.argv[2]
    with open(os.path.join(os.path.expanduser(base), f'{name}.json'), encoding='utf-8') as fh:
        globals()[name](json.load(fh))
