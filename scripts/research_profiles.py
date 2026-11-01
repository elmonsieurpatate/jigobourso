"""Rejeu DESCRIPTIF des six profils de Jigobourso sur les mêmes dates et le même univers que l'expérience Ridge (lecture seule ; aucune optimisation, aucun réentraînement).

Ce qui est RÉELLEMENT utilisé : les fonctions et paramètres de production (`engine.analytics.strategy` : presets, `judge`, `rank` ; `engine.analytics.series.analyze_series` ; `momentum_6_1` et
`momentum_12_1`). Pour chaque (titre, date de décision) de l'univers Ridge, le moteur reçoit les 420 dernières clôtures visibles à cette date. Dates : mêmes dates de décision que `research_ridge.py valid`
(2004 à début 2023 moins 63 séances ; la période finale n'est PAS lue). Univers : exactement les exemples éligibles de Ridge (actions en USD, valeur échangée médiane >= 1 M, volume >= 80 %,
A1/A3 écartés). Cibles : mêmes rendements réels à 21 et 63 séances (série nettoyée v3) ; Top 20 équipondéré ; mêmes frais, même rotation, même CVaR.

Deux bases de prix pour les indicateurs du moteur : « production » (clôtures non ajustées des dividendes, comme l'application, dont la colonne de cours ajustés est vide) et « ajustée » (cours
ajustés des dividendes de l'export). Les rendements évalués sont toujours les mêmes (ajustés).
DIFFÉRENCES NON REPRODUCTIBLES (rappelées dans le rapport) : calendrier de séances attendues (formule datée du moteur) absent -> formule par index ; classement par percentiles au sein de l'univers
Ridge et non de tous les titres retenus du site ; pas de filtre de négociabilité du site ; pas de cours d'origine Spark ; univers de survivants ; splits déclarés absents.
Usage : python3 scripts/research_profiles.py ~/tmp-history-long --out dossier [--min-titles 150] [--sample 0] [--bases production,ajustee]
"""
import argparse
import bisect
import datetime
import os
import statistics
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import research_ridge as rr                                                     # noqa: E402
from research_cleaning import load                                              # noqa: E402
from engine.analytics import strategy                                           # noqa: E402
from engine.analytics.series import analyze_series, momentum_6_1, momentum_12_1  # noqa: E402

NAN = float('nan')
fin = rr.fin
BARS = 420
SLIM = ('slope', 'perf', 'r2', 'volatility')
PROFILES = strategy.PRESETS
LABELS = {'regular': 'Régulière', 'fast': 'Rapide', 'recovery': 'Rebond', 'low_volatility': 'Faible volatilité', 'momentum': 'Momentum 6 mois (essai)', 'momentum12': 'Momentum 12 mois (essai)'}


def replay(D, needed, bases, directory):
    """needed : {ti: [(row, kk)]} -> records[(base, preset)][row] = ('m', valeur) | ('s', mesures allégées) pour les seuls titres RETENUS par le moteur."""
    cfgs = {name: strategy.validate(strategy.preset(name)) for name in PROFILES}
    windows = sorted({n for c in cfgs.values() for n in strategy.required_sessions(c)})
    records = {(b, p): {} for b in bases for p in PROFILES}
    t0, done = time.monotonic(), 0
    for ti, items in needed.items():
        key = D.titles[ti][2]
        rows = [r for r in load(os.path.join(directory, 'history', f'{key}.csv.gz')) if r[0] >= '1998-01-01']
        dates = [r[0] for r in rows]
        for row, kk in items:
            day = datetime.date.fromordinal(D.cal[D.dec[kk]]).isoformat()
            i = bisect.bisect_left(dates, day)
            if i >= len(dates) or dates[i] != day:
                continue
            for b in bases:
                visible = [(r[0], r[1], r[2] if b == 'ajustee' else None) for r in rows[max(0, i + 1 - BARS):i + 1]]
                vd, closes, basis, breaks, measures, missing, tech = analyze_series(visible, windows, ())
                if not vd:
                    continue
                for name, cfg in cfgs.items():
                    mode = cfg['ranking']['mode']
                    mom = None
                    if mode in strategy.MOMENTUM_WINDOWS:
                        mom = (momentum_12_1 if mode == 'momentum12' else momentum_6_1)(vd, closes, breaks, None)
                    v = strategy.judge(cfg, measures, tech, missing, vd[-1], None, mom)
                    if v['status'] != 'retained':
                        continue
                    if mode in strategy.MOMENTUM_WINDOWS:
                        records[(b, name)][row] = ('m', mom)
                    else:
                        records[(b, name)][row] = ('s', {n: ({k: measures[n].get(k) for k in SLIM} if measures.get(n) else None) for n in cfg_sessions(cfg)})
        done += 1
        if done % 100 == 0:
            print(f'rejeu moteur {done}/{len(needed)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    return records, cfgs


_SESS = {}


def cfg_sessions(cfg):
    k = id(cfg)
    if k not in _SESS:
        _SESS[k] = [p['sessions'] for p in cfg['periods'] if p['enabled']]
    return _SESS[k]


def quintiles(order, ret):
    n = len(order)
    if n < 25:
        return [NAN] * 5
    return [statistics.mean(ret[j] for j in order[q * n // 5:(q + 1) * n // 5]) for q in range(5)]


def evaluate_profile(cfg_ridge, h, recs, cfg, test_keys, top=rr.TOP):
    """Même résultat que rr.evaluate, pour un profil du moteur : sélection = les `top` premiers titres RETENUS dans l'ordre de classement de production."""
    out, extra = {}, {}
    D = cfg_ridge.D
    for kk in sorted(test_keys):
        d = cfg_ridge.dates.get(kk)
        if d is None:
            continue
        verdicts = []
        for j, r in enumerate(d['rows']):
            rec = recs.get(r)
            if rec is None or not fin(d['f'][j]):
                continue
            if rec[0] == 'm':
                verdicts.append({'key': j, 'group': 'equity', 'symbol': str(j), 'status': 'retained', 'measures': {}, 'momentum': rec[1]})
            else:
                verdicts.append({'key': j, 'group': 'equity', 'symbol': str(j), 'status': 'retained', 'measures': rec[1], 'momentum': None})
        if not verdicts:
            continue
        ranked = strategy.rank(cfg, verdicts)
        ordered = sorted((v for v in ranked if v.get('rank') is not None), key=lambda v: v['rank'])
        if not ordered:
            continue
        ok = [j for j in range(len(d['rows'])) if fin(d['f'][j])]
        if len(ok) < 30:
            continue
        ret = d['f']
        uni = statistics.mean(ret[j] for j in ok)
        sel = [v['key'] for v in ordered[:top]]
        score = {v['key']: v['score'] for v in ordered}
        ic_ret = rr.spearman([score[v['key']] for v in ordered], [ret[v['key']] for v in ordered])
        ic_all = rr.spearman([score.get(j, -1.0) for j in ok], [ret[j] for j in ok])
        order_ret = [v['key'] for v in ordered]
        out[kk] = {'ic': ic_all, 'top': statistics.mean(ret[j] for j in sel), 'uni': uni, 'sel': frozenset(int(D.c['ti'][d['rows'][j]]) for j in sel),
                   'dec': [NAN] * 10, 'n': len(ok)}
        extra[kk] = {'ic_ret': ic_ret, 'retained': len(ordered), 'selected': len(sel), 'ret_excess': 100 * (statistics.mean(ret[j] for j in order_ret) - uni), 'q5': quintiles(order_ret, ret),
                     'universe': len(ok), 'sel_titles': frozenset(int(D.c['ti'][d['rows'][j]]) for j in sel)}
    return out, extra


def f2(x, d=2):
    return '–' if not fin(x) else f'{x:+.{d}f}'


def mean_of(xs):
    xs = [x for x in xs if fin(x)]
    return statistics.mean(xs) if xs else NAN


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('directory')
    ap.add_argument('--out', required=True)
    ap.add_argument('--min-titles', type=int, default=150)
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--bases', default='production,ajustee')
    args = ap.parse_args(argv)
    directory = os.path.expanduser(args.directory)
    bases = [b for b in args.bases.split(',') if b]
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)
    D = rr.build(directory, args.min_titles, args.sample)
    cal = D.cal
    final_idx = bisect.bisect_left(cal, rr.FINAL.toordinal())
    lo, hi = bisect.bisect_left(cal, datetime.date(2004, 1, 1).toordinal()), final_idx - 63
    cfgs = {h: rr.Config(D, 'principal', 'none', h) for h in rr.HZ}
    tests = {h: {kk for kk in cfgs[h].keys if lo <= D.dec[kk] < hi} for h in rr.HZ}
    needed = defaultdict(list)
    seen = set()
    for h in rr.HZ:
        for kk in tests[h]:
            for r in cfgs[h].dates[kk]['rows']:
                if r not in seen:
                    seen.add(r)
                    needed[int(D.c['ti'][r])].append((r, kk))
    print(f'{sum(len(v) for v in needed.values())} (titre, date) à rejouer dans le moteur', file=sys.stderr)
    records, cfg_eng = replay(D, needed, bases, directory)
    periods = ((2004, 2010), (2011, 2016), (2017, 2022))
    L = []
    w = L.append
    w('# Rejeu descriptif des six profils de Jigobourso (mêmes dates et même univers que l\'expérience Ridge)\n')
    w('*Étude exploratoire sur des survivants sélectionnés aujourd\'hui par le catalogue : biais de survie et de sélection NON corrigés. Ce n\'est PAS une preuve de rentabilité réelle. Analyse descriptive : aucun paramètre optimisé, Ridge non réentraîné, période finale non lue, application inchangée.*\n')
    w(f'{len(D.titles)} titres, dates de décision du {datetime.date.fromordinal(cal[D.dec[min(tests[21])]])} au {datetime.date.fromordinal(cal[D.dec[max(tests[63])]])} (toutes les {rr.STEP} séances), univers : actions USD, valeur échangée >= 1 M, mêmes exemples éligibles que Ridge. Moteur de production rejoué sur {len(seen)} (titre, date).\n')
    w('**Ce qui est reproduit à l\'identique** : fonctions du moteur (`judge`, `rank`, `analyze_series`, `momentum_6_1`, `momentum_12_1`), réglages des profils (seuils par période, mode de classement), 420 clôtures visibles, détection des ruptures de cours, Top 20 équipondéré, rendements évalués, frais et rotation.\n')
    w('**Différences non reproductibles ou non reproduites** :')
    w('- Les profils classent en percentiles au sein des titres retenus du groupe. Ici le groupe est l\'univers Ridge (actions USD liquides), pas tout le catalogue (toutes devises, sans filtre de liquidité). Pour les deux Momentum, un seul score : l\'ordre est identique ; pour les quatre autres profils il peut différer.')
    w('- Pas de calendrier de séances attendues : formules par index de séances (la production utilise la formule datée du moteur pour le momentum).')
    w('- Base « production » : clôtures non ajustées des dividendes (comme l\'application, dont la colonne de cours ajustés est vide) ; base « ajustée » : cours ajustés de l\'export. Les cours de l\'export viennent de Yahoo et non du fournisseur de production (Spark).')
    w('- Splits déclarés (table d\'événements de production) absents ; aucun filtre de négociabilité du site ; univers de survivants.\n')
    for h in rr.HZ:
        cfg = cfgs[h]
        base_keys = sorted(tests[h])
        w(f'\n## Horizon {h} séances\n')
        refs = {'Momentum 6-1 simple (cours ajustés)': 0, 'Momentum 12-1 simple (cours ajustés)': 1}
        results = {}
        for b in bases:
            for name in PROFILES:
                res, extra = evaluate_profile(cfg, h, records[(b, name)], cfg_eng[name], tests[h])
                results[(b, name)] = (rr.summarize(res, h), extra)
        for label, q in refs.items():
            res = rr.evaluate(cfg, h, (lambda q: lambda kk, d: [x[q] for x in d['X']] if d is not None and kk in tests[h] else None)(q), base_keys)
            results[('ref', label)] = (rr.summarize(res, h), None)
        for b in bases + ['ref']:
            keys = [(b, n) for n in (PROFILES if b != 'ref' else refs)] if b != 'ref' else [('ref', n) for n in refs]
            title = {'production': 'Base « production » (clôtures non ajustées des dividendes, comme l\'application)', 'ajustee': 'Base « ajustée » (cours ajustés des dividendes, comme les références Ridge)', 'ref': 'Références simples de l\'expérience Ridge (mêmes calculs)'}[b]
            w(f'\n### {title}\n')
            w('| Stratégie | Dates | Retenus (moy.) | Sélectionnés | IC (univers) | IC (retenus) | Excès brut des retenus | Excès brut Top 20 [IC95 blocs] | Net 10 pb | Net 30 pb | Net 60 pb | Net 100 pb | Rotation | CVaR95 (net 60) |')
            w('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
            for key in keys:
                s, extra = results[key]
                label = LABELS.get(key[1], key[1])
                if extra:
                    ret = mean_of([e['retained'] for e in extra.values()])
                    sel = mean_of([e['selected'] for e in extra.values()])
                    ic_ret = mean_of([e['ic_ret'] for e in extra.values()])
                    rex = mean_of([e['ret_excess'] for e in extra.values()])
                else:
                    ret = sel = ic_ret = rex = NAN
                w(f"| {label} | {s['dates']} | {'–' if not fin(ret) else f'{ret:.0f}'} | {'–' if not fin(sel) else f'{sel:.1f}'} | {f2(s['ic'], 3)} | {f2(ic_ret, 3)} | {f2(rex)} | {f2(s['gross'])} [{f2(s['ci'][0])} ; {f2(s['ci'][1])}] | "
                  + ' | '.join(f2(s['net'].get(c, NAN)) for c in rr.COSTS) + f" | {100 * s['turn']:.0f} % | {f2(s['cvar'])} |")
        w('\n#### Qualité du classement : rendement moyen réel (en %) par cinquième des titres retenus (du moins bien au mieux classé)\n')
        for b in bases:
            for name in PROFILES:
                extra = results[(b, name)][1]
                qs = [mean_of([e['q5'][q] for e in extra.values()]) * 100 for q in range(5)] if extra else [NAN] * 5
                w(f"- {LABELS[name]} ({b}) : " + ', '.join(f2(x, 1) for x in qs))
        w('\n#### Sous-périodes : excès brut du Top 20 (net 60 pb), en points\n')
        w('| Stratégie (base) | ' + ' | '.join(f'{a}-{c}' for a, c in periods) + ' |')
        w('|---|' + '---|' * len(periods))
        series_rows = [(f'{LABELS[n]} ({b})', results[(b, n)][0]) for b in bases for n in PROFILES] + [(n, results[('ref', n)][0]) for n in refs]
        for label, s in series_rows:
            cells = []
            for a, c in periods:
                sub = [(v, s['netseries60'].get(k)) for k, v in s['series'].items() if a <= datetime.date.fromordinal(cal[D.dec[k]]).year <= c]
                cells.append(f"{f2(mean_of([x for x, _ in sub]))} ({f2(mean_of([y for _, y in sub]))})" if sub else '–')
            w(f'| {label} | ' + ' | '.join(cells) + ' |')
        # recouvrement avec les références simples
        w('\n#### Les Momentum de production ressemblent-ils aux références simples ? (recouvrement moyen du Top 20, par date)\n')
        for name, q in (('momentum', 0), ('momentum12', 1)):
            for b in bases:
                extra = results[(b, name)][1]
                ov = []
                for kk, e in extra.items():
                    d = cfg.dates[kk]
                    sc = [x[q] for x in d['X']]
                    order = sorted(range(len(sc)), key=lambda j: -sc[j])[:rr.TOP]
                    simple = frozenset(int(D.c['ti'][d['rows'][j]]) for j in order)
                    ov.append(len(simple & e['sel_titles']) / rr.TOP)
                w(f"- {LABELS[name]} ({b}) contre {'6-1' if q == 0 else '12-1'} simple : {100 * mean_of(ov):.0f} % de titres communs")
    w('\n## Lecture prudente\n')
    w('- Un excès brut positif dont l\'intervalle contient zéro n\'est pas établi. Les frais sont des hypothèses (aucun spread historique). Les périodes ont déjà été consultées.')
    w('- Cette comparaison est descriptive : rien n\'a été optimisé, aucune décision de réglage n\'en découle. Elle ne dit rien sur les résultats futurs.')
    text = '\n'.join(L)
    print(text)
    with open(os.path.join(out_dir, 'profils_valid.md'), 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
