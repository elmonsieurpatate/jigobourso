"""Diagnostic DESCRIPTIF du moteur sur l'historique (lecture seule ; aucune optimisation ; aucun paramètre ni classement modifié ; période finale non lue).

Mêmes dates et même univers que `research_ridge.py valid` / `research_profiles.py` (actions USD, valeur échangée >= 1 M, 2004 -> début 2023 moins 63 séances), moteur de production rejoué
sur les clôtures non ajustées des dividendes ("production"). Deux volets :

A. RUPTURES DE COURS (facteur 1,6). Le moteur déclare « rupture » un saut d'une séance au-delà de x1,6 ou en deçà de /1,6 (baisse de plus de 37,5 %) ; une rupture après le début de la fenêtre
   (J-126 / J-252) rend le momentum non évaluable. Pour chaque titre et chaque date on calcule le momentum du moteur AVEC et SANS cette règle (mêmes clôtures nettoyées par le moteur) :
   nombre de titres exclus, composition du Top 20 du momentum simple, nature des événements (classification v3 : A1 split / A2 erreur isolée / B mouvement réel / C incertain),
   rendements ensuite, et décomposition de l'écart « momentum simple - momentum de production » (règle des ruptures / reste : dividendes, nettoyage du moteur, fenêtre). La règle n'est PAS retirée du moteur.
B. ROTATION des quatre profils filtrants : titres du Top 20 qui sortent parce qu'ils ne respectent plus un critère (rejetés / non évaluables / hors univers) ou parce qu'ils descendent dans le
   classement ; critères qui écartent le plus, ratés de peu (moins de 10 % du seuil), effet des conditions cumulées (taux de passage joint contre produit des taux par période).
C. Sensibilité à la négociabilité : mêmes mesures avec le seuil de 2,2 M$/jour (environ 2 M EUR : le filtre par défaut du site masque les actions sous 2 fois le minimum de 1 M EUR).
Usage : python3 scripts/research_diagnostics.py ~/tmp-history-long --out dossier [--min-titles 150] [--sample 0]
"""
import argparse
import bisect
import datetime
import math
import os
import statistics
import sys
import time
from array import array
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import research_ridge as rr                                                      # noqa: E402
import research_profiles as rp                                                   # noqa: E402
from research_cleaning import load                                               # noqa: E402
from research_cleaning_cases import classify_v3                                  # noqa: E402
from engine.analytics import strategy                                            # noqa: E402
from engine.analytics.series import analyze_series, momentum_6_1, momentum_12_1  # noqa: E402

NAN = float('nan')
fin = rr.fin
FILTERING = ('regular', 'fast', 'recovery', 'low_volatility')
PRIORITY = ('A1', 'A2', 'C', 'B', 'sous seuil 40 %')
LIQ_SITE_DEFAULT = 2.2e6
CRIT = {f: (m, op) for f, m, op in strategy.CRITERIA}


def margin(reason):
    f, v, t = reason['criterion'], reason.get('value'), reason.get('threshold')
    if v is None or t is None or f not in CRIT:
        return None
    op = CRIT[f][1]
    return ((t - v) if op == '>=' else (v - t)) / max(abs(t), 1e-9)


def replay(D, needed, directory):
    """Rejeu du moteur (base production) : momentum avec/sans règle des ruptures, ruptures datées et classées, verdicts des six profils (statut, premier échec, marges)."""
    cfgs = {name: strategy.validate(strategy.preset(name)) for name in strategy.PRESETS}
    windows = sorted({n for c in cfgs.values() for n in strategy.required_sessions(c)})
    N = len(D.c['k'])
    m6, m6n, m12, m12n = (array('d', [NAN]) * N for _ in range(4))
    st = {p: array('b', [-1]) * N for p in strategy.PRESETS}          # 0 retenu, 1 écarté, 2 non évaluable, -1 non rejoué
    why = {p: array('h', [-1]) * N for p in strategy.PRESETS}
    whymap = {}
    records = {p: {} for p in strategy.PRESETS}
    brk = {}                                                           # row -> [(offset, ratio, date, classe)]
    crit_fail, sole, near_only = {p: Counter() for p in FILTERING}, {p: Counter() for p in FILTERING}, {p: 0 for p in FILTERING}
    rejected_n, blocks = {p: 0 for p in FILTERING}, {p: defaultdict(lambda: [0, 0]) for p in FILTERING}
    joint = {p: [0, 0] for p in FILTERING}
    marginal = {p: Counter() for p in FILTERING}
    t0, done = time.monotonic(), 0
    for ti, items in needed.items():
        key = D.titles[ti][2]
        rows = [r for r in load(os.path.join(directory, 'history', f'{key}.csv.gz')) if r[0] >= '1998-01-01']
        dates = [r[0] for r in rows]
        evmap = {}
        a_, c_, v_ = [r[2] for r in rows], [r[1] for r in rows], [r[3] for r in rows]
        for i, cls, p, end in classify_v3(a_, c_, v_):
            evmap[dates[i]] = cls
        for row, kk in items:
            day = datetime.date.fromordinal(D.cal[D.dec[kk]]).isoformat()
            i = bisect.bisect_left(dates, day)
            if i >= len(dates) or dates[i] != day:
                continue
            visible = [(r[0], r[1], None) for r in rows[max(0, i + 1 - rp.BARS):i + 1]]
            vd, closes, basis, breaks, measures, missing, tech = analyze_series(visible, windows, ())
            if not vd:
                continue
            n = len(vd)
            f6, f12 = momentum_6_1(vd, closes, breaks, None), momentum_12_1(vd, closes, breaks, None)
            g6, g12 = momentum_6_1(vd, closes, [], None), momentum_12_1(vd, closes, [], None)
            m6[row], m6n[row], m12[row], m12n[row] = (NAN if x is None else x for x in (f6, g6, f12, g12))
            blist = []
            for b in breaks:
                off = n - 1 - b
                if off <= 251:
                    ratio = closes[b] / closes[b - 1]
                    blist.append((off, ratio, vd[b], evmap.get(vd[b]) or 'sous seuil 40 %'))
            if blist:
                brk[row] = blist
            for name, cfg in cfgs.items():
                mode = cfg['ranking']['mode']
                mom = (f12 if mode == 'momentum12' else f6) if mode in strategy.MOMENTUM_WINDOWS else None
                v = strategy.judge(cfg, measures, tech, missing, vd[-1], None, mom)
                code = {'retained': 0, 'rejected': 1, 'unknown': 2}[v['status']]
                st[name][row] = code
                if v['status'] == 'retained':
                    records[name][row] = ('m', mom) if mode in strategy.MOMENTUM_WINDOWS else ('s', {s: ({k: measures[s].get(k) for k in rp.SLIM} if measures.get(s) else None) for s in rp.cfg_sessions(cfg)})
                else:
                    if v['status'] == 'rejected':
                        first = next(r for r in v['reasons'] if r['result'] == 'fail')
                        label = f"{first['period'] or 'général'}·{first['criterion']}"
                    else:
                        first = next((r for r in v['reasons'] if r['result'] == 'missing'), None)
                        label = f"non évaluable : {(first or {}).get('metric') or 'donnée'}"
                    why[name][row] = whymap.setdefault(label, len(whymap))
                if name in FILTERING:
                    fails = [r for r in v['reasons'] if r['result'] == 'fail']
                    pk = {r['period'] for r in v['reasons'] if r['period'] and r['period'] != 'technical'}
                    if v['status'] != 'unknown':
                        for per in [p['id'] for p in cfg['periods'] if p['enabled']]:
                            ok = not any(r['period'] == per and r['result'] == 'fail' for r in v['reasons'])
                            marginal[name][per] += ok
                        joint[name][0] += v['status'] == 'retained'
                        joint[name][1] += 1
                    if v['status'] == 'rejected':
                        rejected_n[name] += 1
                        keys = {f"{r['period']}·{r['criterion']}" for r in fails}
                        for k in keys:
                            crit_fail[name][k] += 1
                        if len(keys) == 1:
                            sole[name][next(iter(keys))] += 1
                        ms = [margin(r) for r in fails]
                        if ms and all(x is not None and x <= 0.10 for x in ms):
                            near_only[name] += 1
        done += 1
        if done % 100 == 0:
            print(f'rejeu moteur {done}/{len(needed)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    return dict(m6=m6, m6n=m6n, m12=m12, m12n=m12n, st=st, why=why, whymap={v: k for k, v in whymap.items()}, records=records, brk=brk, crit_fail=crit_fail, sole=sole,
                near_only=near_only, rejected_n=rejected_n, joint=joint, marginal=marginal)


def evaluate_scores(cfg, getter, keys, top=20):
    out = {}
    D = cfg.D
    for kk in keys:
        d = cfg.dates.get(kk)
        if d is None:
            continue
        rows, f = d['rows'], d['f']
        ok = [j for j in range(len(rows)) if fin(f[j])]
        if len(ok) < 30:
            continue
        valid = [(getter(rows[j]), j) for j in ok]
        valid = [(s, j) for s, j in valid if s is not None and fin(s)]
        if not valid:
            continue
        valid.sort(key=lambda x: -x[0])
        sel = [j for _, j in valid[:top]]
        uni = statistics.mean(f[j] for j in ok)
        out[kk] = {'ic': NAN, 'top': statistics.mean(f[j] for j in sel), 'uni': uni, 'sel': frozenset(int(D.c['ti'][rows[j]]) for j in sel), 'dec': [NAN] * 10, 'n': len(ok)}
    return out


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
    args = ap.parse_args(argv)
    directory = os.path.expanduser(args.directory)
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)
    D = rr.build(directory, args.min_titles, args.sample)
    cal = D.cal
    final_idx = bisect.bisect_left(cal, rr.FINAL.toordinal())
    lo, hi = bisect.bisect_left(cal, datetime.date(2004, 1, 1).toordinal()), final_idx - 63
    cfgs = {h: rr.Config(D, 'principal', 'none', h) for h in rr.HZ}
    tests = {h: {kk for kk in cfgs[h].keys if lo <= D.dec[kk] < hi} for h in rr.HZ}
    needed, seen = defaultdict(list), set()
    for h in rr.HZ:
        for kk in tests[h]:
            for r in cfgs[h].dates[kk]['rows']:
                if r not in seen:
                    seen.add(r)
                    needed[int(D.c['ti'][r])].append((r, kk))
    print(f'{len(seen)} (titre, date) à rejouer', file=sys.stderr)
    R = replay(D, needed, directory)
    L = []
    w = L.append
    year = lambda kk: datetime.date.fromordinal(cal[D.dec[kk]]).year
    w('# Diagnostic du moteur de production sur l\'historique (descriptif, lecture seule)\n')
    w('*Survivants sélectionnés aujourd\'hui par le catalogue : biais de survie et de sélection NON corrigés. Aucune règle, aucun paramètre ni classement n\'est modifié ; la période finale n\'est pas lue. Ce n\'est pas une preuve de rentabilité.*\n')
    w(f'{len(D.titles)} titres ; dates du {datetime.date.fromordinal(cal[D.dec[min(tests[21])]])} au {datetime.date.fromordinal(cal[D.dec[max(tests[63])]])} ; univers : actions USD, valeur échangée >= 1 M ; moteur rejoué sur {len(seen)} (titre, date), base « production » (clôtures non ajustées des dividendes).\n')
    # ───── A. ruptures de cours
    w('## A. Règle des ruptures de cours (x1,6)\n')
    for h in rr.HZ:
        cfg = cfgs[h]
        keys = sorted(tests[h])
        exc6 = exc12 = uni_n = top_n = top_exc6 = top_exc12 = 0
        per_date = []
        grp = defaultdict(list)                # (classe, fenêtre) -> écarts de rendement (f - moyenne de l'univers à la date)
        grp_top = defaultdict(list)
        events = defaultdict(set)              # classe -> {(titre, date d'événement)}
        timing = Counter()
        for kk in keys:
            d = cfg.dates[kk]
            rows, f, X = d['rows'], d['f'], d['X']
            ok = [j for j in range(len(rows)) if fin(f[j])]
            if not ok:
                continue
            uni = statistics.mean(f[j] for j in ok)
            order = sorted(ok, key=lambda j: -X[j][0])[:rr.TOP]
            topset = set(order)
            e6 = e12 = 0
            for j in ok:
                r = rows[j]
                x6 = fin(R['m6n'][r]) and not fin(R['m6'][r])
                x12 = fin(R['m12n'][r]) and not fin(R['m12'][r])
                e6 += x6
                e12 += x12
                if x6 or x12:
                    window = 125 if x6 else 251
                    bl = [b for b in R['brk'].get(r, []) if b[0] <= window]
                    cls = next((c for c in PRIORITY if any(b[3] == c for b in bl)), 'sous seuil 40 %')
                    where = 'dernier mois (J-20 à J)' if all(b[0] < 21 for b in bl) else 'dans la fenêtre du momentum'
                    key = (cls, 'momentum 6 mois' if x6 else 'momentum 12 mois seul')
                    grp[key].append(100 * (f[j] - uni))
                    if j in topset:
                        grp_top[key].append(100 * (f[j] - uni))
                    for b in bl:
                        events[b[3]].add((int(D.c['ti'][r]), b[2]))
                    timing[(where, j in topset)] += 1
            exc6 += e6
            exc12 += e12
            uni_n += len(ok)
            top_exc6 += sum(1 for j in order if fin(R['m6n'][rows[j]]) and not fin(R['m6'][rows[j]]))
            top_exc12 += sum(1 for j in order if fin(R['m12n'][rows[j]]) and not fin(R['m12'][rows[j]]))
            top_n += len(order)
            per_date.append((e6, len(ok)))
        w(f'### Horizon {h} séances\n')
        w(f'- Titres de l\'univers dont le momentum est rendu non évaluable par la règle, par date (moyenne) : 6 mois {exc6 / max(1, len(per_date)):.1f} ({100 * exc6 / max(1, uni_n):.1f} % de l\'univers) ; 12 mois {exc12 / max(1, len(per_date)):.1f} ({100 * exc12 / max(1, uni_n):.1f} %).')
        w(f'- Parmi les 20 premiers du momentum SIMPLE (cours ajustés), exclus par la règle : 6 mois {top_exc6 / max(1, len(per_date)):.2f} par date ({100 * top_exc6 / max(1, top_n):.1f} %) ; 12 mois {top_exc12 / max(1, len(per_date)):.2f} par date ({100 * top_exc12 / max(1, top_n):.1f} %).\n')
        w('| Nature de l\'événement (classification v3) | Événements distincts (titre, date) | Expositions titre-date (momentum 6 mois) | Écart de rendement moyen à l\'univers sur l\'horizon (pts) | Dont dans le Top 20 simple : expositions, écart moyen |')
        w('|---|---|---|---|---|')
        for cls in PRIORITY:
            xs, xt = grp.get((cls, 'momentum 6 mois'), []), grp_top.get((cls, 'momentum 6 mois'), [])
            w(f"| {cls} | {len(events.get(cls, ()))} | {len(xs)} | {f2(mean_of(xs))} | {len(xt)} ; {f2(mean_of(xt))} |")
        w('\nA1 = split ou regroupement non ajusté (donnée à corriger) ; A2 = erreur de cotation isolée ; B = mouvement de marché plausible ; C = incertain ; « sous seuil 40 % » = baisse de 37,5 à 40 % (rupture du moteur, pas un événement v3). ')
        w('Moment du saut pour les titres exclus (expositions) : ' + ' ; '.join(f"{k[0]}{' (Top 20 simple)' if k[1] else ''} : {n}" for k, n in sorted(timing.items())) + '.\n')
        # décomposition de l'écart
        sc_simple = lambda r: cfg.D.fc[0][r]
        s_simple = rr.summarize(evaluate_scores(cfg, lambda r: D.fc[0][r], keys), h)
        s_nobreak = rr.summarize(evaluate_scores(cfg, lambda r: R['m6n'][r] if fin(R['m6n'][r]) else None, keys), h)
        s_prod = rr.summarize(evaluate_scores(cfg, lambda r: R['m6'][r] if fin(R['m6'][r]) else None, keys), h)
        s12 = rr.summarize(evaluate_scores(cfg, lambda r: D.fc[1][r], keys), h)
        s12n = rr.summarize(evaluate_scores(cfg, lambda r: R['m12n'][r] if fin(R['m12n'][r]) else None, keys), h)
        s12p = rr.summarize(evaluate_scores(cfg, lambda r: R['m12'][r] if fin(R['m12'][r]) else None, keys), h)
        w('Effet de la règle sur le classement : excès brut du Top 20 (pts), même univers, mêmes dates.\n')
        w('| Classement | Excès brut Top 20 [IC95 blocs] | Net 60 pb | Rotation |')
        w('|---|---|---|---|')
        for label, s in (('Momentum 6-1 simple (cours ajustés)', s_simple), ('Moteur, SANS la règle des ruptures (cours non ajustés)', s_nobreak), ('Moteur de production (avec la règle)', s_prod),
                         ('Momentum 12-1 simple (cours ajustés)', s12), ('Moteur 12 mois, SANS la règle', s12n), ('Moteur 12 mois de production', s12p)):
            w(f"| {label} | {f2(s['gross'])} [{f2(s['ci'][0])} ; {f2(s['ci'][1])}] | {f2(s['net'].get(60, NAN))} | {100 * s['turn']:.0f} % |")
        for label, a, b, c in (('6 mois', s_simple, s_nobreak, s_prod), ('12 mois', s12, s12n, s12p)):
            common = sorted(set(a['series']) & set(b['series']) & set(c['series']))
            tot = [a['series'][k] - c['series'][k] for k in common]
            rule = [b['series'][k] - c['series'][k] for k in common]
            rest = [a['series'][k] - b['series'][k] for k in common]
            lo1, hi1, _, _ = rr.boot(rule)
            w(f"- Écart « simple - production » {label} : {f2(mean_of(tot))} pt ; part due à la règle des ruptures : {f2(mean_of(rule))} [{f2(lo1)} ; {f2(hi1)}] ; part due au reste (dividendes, nettoyage du moteur, fenêtre de 420 clôtures) : {f2(mean_of(rest))}.")
        w('')
    # ───── B. rotation
    w('## B. Rotation des quatre profils filtrants\n')
    cfg = cfgs[21]
    keys = sorted(tests[21])
    rowof = {(int(D.c['ti'][r]), kk): r for kk in keys for r in cfg.dates[kk]['rows']}
    cause = {p: Counter() for p in FILTERING}
    stay = {p: [0, 0, 0, 0] for p in FILTERING}      # retenus à k qui restent retenus à k+1, top20 qui restent top20, total retenus, total top20
    pool_small = {p: [0, 0] for p in FILTERING}
    persist = {p: [] for p in FILTERING}
    pool_sizes = {p: [] for p in FILTERING}
    entr = {p: Counter() for p in FILTERING}
    for p in FILTERING:
        scfg = strategy.validate(strategy.preset(p))
        tops, ranked_all = {}, {}
        for kk in keys:
            d = cfg.dates[kk]
            verdicts = [{'key': r, 'group': 'equity', 'symbol': str(r), 'status': 'retained', 'measures': R['records'][p][r][1], 'momentum': None} for r in d['rows'] if r in R['records'][p]]
            if not verdicts:
                continue
            ranked = strategy.rank(scfg, verdicts)
            order = sorted((v for v in ranked if v.get('rank') is not None), key=lambda v: v['rank'])
            ranked_all[kk] = {v['key']: v['score'] for v in order}
            tops[kk] = [v['key'] for v in order[:20]]
            pool_sizes[p].append(len(order))
            pool_small[p][0] += len(order) <= 20
            pool_small[p][1] += 1
        for kk in keys:
            nxt = kk + 1
            if kk not in tops or nxt not in tops:
                continue
            top_now, top_next = tops[kk], set(tops[nxt])
            ti_next = {int(D.c['ti'][r]): r for r in cfg.dates[nxt]['rows']}
            pool_next = ranked_all[nxt]
            stay[p][2] += len(ranked_all[kk])
            stay[p][3] += len(top_now)
            for r in ranked_all[kk]:
                r2 = ti_next.get(int(D.c['ti'][r]))
                if r2 is not None and r2 in pool_next:
                    stay[p][0] += 1
            for r in top_now:
                t = int(D.c['ti'][r])
                r2 = ti_next.get(t)
                if r2 in top_next:
                    stay[p][1] += 1
                    continue
                if r2 is None:
                    cause[p]['sorti de l\'univers (liquidité, couverture ou données)'] += 1
                elif r2 in pool_next:
                    cause[p]['toujours retenu mais descendu sous le 20e rang'] += 1
                else:
                    code = R['st'][p][r2]
                    cause[p][R['whymap'].get(R['why'][p][r2], 'inconnu') if code in (1, 2) else 'inconnu'] += 1
            prev_rows = {int(D.c['ti'][r]): r for r in cfg.dates[kk]['rows']}
            for r2 in tops[nxt]:
                if r2 in set(top_now) or any(int(D.c['ti'][r]) == int(D.c['ti'][r2]) for r in top_now):
                    continue
                r = prev_rows.get(int(D.c['ti'][r2]))
                if r is None:
                    entr[p]['absent de l\'univers à la date précédente'] += 1
                elif r in ranked_all[kk]:
                    entr[p]['déjà retenu, remonté dans le Top 20'] += 1
                else:
                    entr[p]['non retenu à la date précédente (nouvel éligible)'] += 1
            common = [r for r in ranked_all[kk] if (lambda r2: r2 is not None and r2 in pool_next)(ti_next.get(int(D.c['ti'][r])))]
            if len(common) >= 10:
                a1 = [ranked_all[kk][r] for r in common]
                a2 = [pool_next[ti_next[int(D.c['ti'][r])]] for r in common]
                persist[p].append(rr.spearman(a1, a2))
    w('Rotation = part du Top 20 de la date précédente absente du Top 20 de la date suivante (21 séances plus tard). Causes des sorties :\n')
    for p in FILTERING:
        tot = sum(cause[p].values())
        w(f"**{p}** · retenus par date (moyenne) {mean_of(pool_sizes[p]):.0f} (dates où le groupe de retenus compte au plus 20 titres : {100 * pool_small[p][0] / max(1, pool_small[p][1]):.0f} %) · "
          f"{100 * stay[p][0] / max(1, stay[p][2]):.0f} % des titres retenus le restent 21 séances plus tard ; un titre du Top 20 reste dans le Top 20 dans {100 * stay[p][1] / max(1, stay[p][3]):.0f} % des cas · "
          f"corrélation de rang du score entre deux dates (retenus aux deux dates) : {f2(mean_of(persist[p]), 2)}")
        for k, n in cause[p].most_common(8):
            w(f'  - {k} : {n} ({100 * n / max(1, tot):.0f} % des sorties)')
        w('  - entrants du Top 20 : ' + '; '.join(f'{k} {n}' for k, n in entr[p].most_common()))
    w('\n### Critères qui écartent le plus, ratés de peu et conditions cumulées\n')
    for p in FILTERING:
        cf, so = R['crit_fail'][p], R['sole'][p]
        rn = R['rejected_n'][p]
        w(f"**{p}** · titres écartés : {rn} · dont ratés de peu (tous les critères en échec à moins de 10 % du seuil) : {R['near_only'][p]} ({100 * R['near_only'][p] / max(1, rn):.1f} %)")
        w('  - critères en échec (titres écartés qui y échouent ; « seul » = unique critère en échec) : ' + '; '.join(f'{k} {n} (seul : {so[k]})' for k, n in cf.most_common(8)))
        j = R['joint'][p]
        marg = R['marginal'][p]
        total = j[1]
        prod = 1.0
        for per, ok in marg.items():
            prod *= ok / max(1, total)
        w(f"  - taux de passage par période (titres évaluables) : " + ', '.join(f'{per} {100 * ok / max(1, total):.0f} %' for per, ok in marg.items()) + f" ; taux de passage joint {100 * j[0] / max(1, j[1]):.1f} % contre {100 * prod:.1f} % si les périodes étaient indépendantes.")
    # ───── C. négociabilité
    w('\n## C. Sensibilité à la négociabilité (seuil de 2,2 M$/jour ≈ 2 M EUR, filtre par défaut du site)\n')
    w('Le site masque les actions sous 2 fois le minimum du catalogue (2 M EUR/jour) ; un titre dont la liquidité est inconnue ou périmée n\'est jamais masqué (la recherche, elle, exclut les titres couverts à moins de 80 % par des volumes). Mesure du site : moyenne 3 mois du volume × cours du JOUR ; recherche : médiane de la valeur échangée des 63 séances précédentes à chaque date.\n')
    for h in rr.HZ:
        saved = rr.LIQ_MIN
        rr.LIQ_MIN = LIQ_SITE_DEFAULT
        cfg_site = rr.Config(D, 'principal', 'none', h)
        rr.LIQ_MIN = saved
        keys_site = sorted(k for k in tests[h] if k in cfg_site.dates)
        w(f'### Horizon {h} séances : 1 M$ contre 2,2 M$ (univers moyen par date : {mean_of([len(cfgs[h].dates[k]["rows"]) for k in tests[h]]):.0f} contre {mean_of([len(cfg_site.dates[k]["rows"]) for k in keys_site]):.0f} titres)\n')
        w('| Stratégie | Excès brut Top 20, 1 M$ | Net 60 pb, 1 M$ | Excès brut Top 20, 2,2 M$ | Net 60 pb, 2,2 M$ | Rotation 2,2 M$ |')
        w('|---|---|---|---|---|---|')
        rows_out = []
        for name in strategy.PRESETS:
            scfg = strategy.validate(strategy.preset(name))
            res = {}
            for label, cf, ks in (('base', cfgs[h], sorted(tests[h])), ('site', cfg_site, keys_site)):
                r_, _ = rp.evaluate_profile(cf, h, R['records'][name], scfg, set(ks))
                res[label] = rr.summarize(r_, h)
            rows_out.append((rp.LABELS[name], res))
        for label, getter in (('Momentum 6-1 simple (cours ajustés)', lambda r: D.fc[0][r]), ('Momentum 12-1 simple (cours ajustés)', lambda r: D.fc[1][r])):
            res = {'base': rr.summarize(evaluate_scores(cfgs[h], getter, sorted(tests[h])), h), 'site': rr.summarize(evaluate_scores(cfg_site, getter, keys_site), h)}
            rows_out.append((label, res))
        for label, res in rows_out:
            b, s = res['base'], res['site']
            w(f"| {label} | {f2(b['gross'])} | {f2(b['net'].get(60, NAN))} | {f2(s['gross'])} [{f2(s['ci'][0])} ; {f2(s['ci'][1])}] | {f2(s['net'].get(60, NAN))} | {100 * s['turn']:.0f} % |")
        w('')
    usd = [i for i in range(len(D.c['k'])) if D.c['usd'][i]]
    low = [i for i in usd if D.c['cov'][i] < 0.8]
    w(f"Part des (titre, date) en USD dont la couverture volume est inférieure à 80 % (donc écartés de la recherche mais NON masqués par le site) : {100 * len(low) / max(1, len(usd)):.1f} % ({len(low)} sur {len(usd)}).")
    text = '\n'.join(L)
    print(text)
    with open(os.path.join(out_dir, 'diagnostic_moteur.md'), 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
