"""Extension du diagnostic des ruptures de cours (lecture seule, descriptive ; aucune règle modifiée ; période finale non lue pour les rendements).

Même univers et mêmes dates que `research_diagnostics.py`. Questions :
 1. Hausses ou baisses : quelle direction explique les exclusions, l'écart au momentum simple et le risque (CVaR 95 %) ? On calcule le momentum du moteur (clôtures non ajustées) avec :
    la règle complète ; sans la règle ; la règle seulement pour les BAISSES (ratio < 1/1,6) ; la règle seulement pour les HAUSSES (ratio > 1,6).
 2. Toutes les ruptures du moteur sur 1998-2026 pour les 1 553 actions (hors univers de rendement) classées par nature (A1 split/regroupement confirmé par le volume, A2 erreur isolée, B mouvement
    plausible, C incertain, « sous seuil 40 % ») et par direction : combien sont des anomalies de données qu'une protection doit garder, combien sont de vrais mouvements à signaler seulement.
 3. Liste « mouvement extrême à vérifier » (jamais réintroduite dans un classement) : rendements et risque des titres signalés, hausses et baisses séparées.
 4. Part des titres retenus par chaque profil et par année (2004-2022) : le profil « Hausse calme » (low_volatility) est-il rare dans tous les régimes ?
Usage : python3 scripts/research_diagnostics2.py ~/tmp-history-long --out dossier [--min-titles 150] [--sample 0]
"""
import argparse
import bisect
import datetime
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
import research_diagnostics as rd                                                # noqa: E402
from research_cleaning import load                                               # noqa: E402
from research_cleaning_cases import classify_v3                                  # noqa: E402
from engine.analytics import strategy                                            # noqa: E402
from engine.analytics.series import analyze_series, momentum_6_1, momentum_12_1, prepare_series   # noqa: E402

NAN = float('nan')
fin = rr.fin
BREAK = 1.6
VARIANTS = ('full', 'none', 'down', 'up')          # règle complète / sans règle / règle seulement pour les baisses / seulement pour les hausses
PRIORITY = ('A1', 'A2', 'C', 'B', 'sous seuil 40 %')


def replay(D, needed, directory):
    cfgs = {name: strategy.validate(strategy.preset(name)) for name in strategy.PRESETS}
    windows = sorted({n for c in cfgs.values() for n in strategy.required_sessions(c)})
    N = len(D.c['k'])
    mom = {(w, v): array('d', [NAN]) * N for w in (6, 12) for v in VARIANTS}
    st = {p: array('b', [-1]) * N for p in strategy.PRESETS}
    brk = {}
    t0, done = time.monotonic(), 0
    for ti, items in needed.items():
        key = D.titles[ti][2]
        rows = [r for r in load(os.path.join(directory, 'history', f'{key}.csv.gz')) if r[0] >= '1998-01-01']
        dates = [r[0] for r in rows]
        evmap = {dates[i]: cls for i, cls, p, end in classify_v3([r[2] for r in rows], [r[1] for r in rows], [r[3] for r in rows])}
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
            sets = {'full': breaks, 'none': [], 'down': [b for b in breaks if closes[b] < closes[b - 1]], 'up': [b for b in breaks if closes[b] > closes[b - 1]]}
            for v, bl in sets.items():
                for w, fn in ((6, momentum_6_1), (12, momentum_12_1)):
                    x = fn(vd, closes, bl, None)
                    mom[(w, v)][row] = NAN if x is None else x
            blist = [(n - 1 - b, closes[b] / closes[b - 1], vd[b], evmap.get(vd[b]) or 'sous seuil 40 %') for b in breaks if n - 1 - b <= 251]
            if blist:
                brk[row] = blist
            for name, cfg in cfgs.items():
                m = None
                if cfg['ranking']['mode'] in strategy.MOMENTUM_WINDOWS:
                    m = (momentum_12_1 if cfg['ranking']['mode'] == 'momentum12' else momentum_6_1)(vd, closes, breaks, None)
                st[name][row] = {'retained': 0, 'rejected': 1, 'unknown': 2}[strategy.judge(cfg, measures, tech, missing, vd[-1], None, m)['status']]
        done += 1
        if done % 100 == 0:
            print(f'rejeu moteur {done}/{len(needed)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    return mom, st, brk


def all_breaks(directory, universe_rows):
    """Toutes les ruptures du moteur sur 1998-2026 pour toutes les actions : {(classe, direction): nombre d'événements distincts}."""
    counts, examples = Counter(), defaultdict(list)
    for u in universe_rows:
        rows = [r for r in load(os.path.join(directory, 'history', f"{u['key']}.csv.gz")) if r[0] >= '1998-01-01']
        if len(rows) < 100:
            continue
        evmap = {rows[i][0]: cls for i, cls, p, end in classify_v3([r[2] for r in rows], [r[1] for r in rows], [r[3] for r in rows])}
        dates, closes, basis, breaks = prepare_series([(r[0], r[1], None) for r in rows])
        for b in breaks:
            ratio = closes[b] / closes[b - 1]
            cls = evmap.get(dates[b]) or 'sous seuil 40 %'
            direction = 'hausse' if ratio > 1 else 'baisse'
            counts[(cls, direction)] += 1
            if len(examples[(cls, direction)]) < 4:
                examples[(cls, direction)].append(f"{u['symbol']} {dates[b]} ×{ratio:.3g}")
    return counts, examples


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
    mom, st, brk = replay(D, needed, directory)
    L = []
    w = L.append
    year = lambda kk: datetime.date.fromordinal(cal[D.dec[kk]]).year
    w('# Extension du diagnostic des ruptures de cours (descriptif, lecture seule)\n')
    w('*Survivants sélectionnés aujourd\'hui par le catalogue : biais de survie et de sélection NON corrigés. Aucune règle modifiée. Rendements : dates de décision de 2004 à 2022 uniquement.*\n')
    # ───── 1. direction
    w('## 1. Hausses et baisses : effet sur les exclusions, l\'écart au momentum simple et le risque\n')
    for h in rr.HZ:
        cfg = cfgs[h]
        keys = sorted(tests[h])
        w(f'### Horizon {h} séances\n')
        # exclusions par direction (momentum 6 mois)
        exc = Counter()
        ret_dir = defaultdict(list)
        ret_top = defaultdict(list)
        uni_sizes = []
        for kk in keys:
            d = cfg.dates[kk]
            rows, f, X = d['rows'], d['f'], d['X']
            ok = [j for j in range(len(rows)) if fin(f[j])]
            if not ok:
                continue
            uni = statistics.mean(f[j] for j in ok)
            top20 = set(sorted(ok, key=lambda j: -X[j][0])[:rr.TOP])
            uni_sizes.append(len(ok))
            for j in ok:
                r = rows[j]
                if fin(mom[(6, 'none')][r]) and not fin(mom[(6, 'full')][r]):
                    bl = [b for b in brk.get(r, []) if b[0] <= 125]
                    ups, downs = any(b[1] > 1 for b in bl), any(b[1] < 1 for b in bl)
                    direction = 'hausse seule' if ups and not downs else 'baisse seule' if downs and not ups else 'hausse et baisse'
                    exc[direction] += 1
                    ret_dir[direction].append(100 * (f[j] - uni))
                    if j in top20:
                        ret_top[direction].append(100 * (f[j] - uni))
        w('Titres rendus non évaluables par la règle (momentum 6 mois), par direction du saut dans la fenêtre : ' + ' ; '.join(f'{k} {n} expositions' for k, n in exc.most_common()) + f' (univers moyen {mean_of(uni_sizes):.0f} titres par date).\n')
        w('| Direction | Expositions | Écart moyen de rendement à l\'univers (pts) | Dans le Top 20 simple : expositions, écart moyen | 10 % pires écarts (pts) |')
        w('|---|---|---|---|---|')
        for k in ('hausse seule', 'baisse seule', 'hausse et baisse'):
            xs = sorted(ret_dir.get(k, []))
            tail = mean_of(xs[:max(1, len(xs) // 10)]) if xs else NAN
            w(f"| {k} | {exc.get(k, 0)} | {f2(mean_of(xs))} | {len(ret_top.get(k, []))} ; {f2(mean_of(ret_top.get(k, [])))} | {f2(tail)} |")
        w('\nMomentum du moteur selon la façon d\'appliquer la règle (excès brut du Top 20, net 60 pb, CVaR 95 % du portefeuille net 60 pb) :\n')
        w('| Fenêtre | Règle appliquée | Excès brut [IC95 blocs] | Net 60 pb | CVaR95 | Rotation |')
        w('|---|---|---|---|---|---|')
        results = {}
        for wnd in (6, 12):
            for v, label in (('none', 'aucune (momentum du moteur sans la règle)'), ('down', 'baisses seulement'), ('up', 'hausses seulement'), ('full', 'règle complète (production)')):
                s = rr.summarize(rd.evaluate_scores(cfg, (lambda arr: lambda r: arr[r] if fin(arr[r]) else None)(mom[(wnd, v)]), keys), h)
                results[(wnd, v)] = s
                w(f"| {wnd} mois | {label} | {f2(s['gross'])} [{f2(s['ci'][0])} ; {f2(s['ci'][1])}] | {f2(s['net'].get(60, NAN))} | {f2(s['cvar'])} | {100 * s['turn']:.0f} % |")
        for wnd in (6, 12):
            common = sorted(set(results[(wnd, 'none')]['series']) & set(results[(wnd, 'full')]['series']))
            diff = [results[(wnd, 'none')]['series'][k] - results[(wnd, 'full')]['series'][k] for k in common]
            lo1, hi1, _, _ = rr.boot(diff)
            w(f"- Momentum {wnd} mois : effet de la règle complète sur l'excès brut (sans moins avec) : {f2(mean_of(diff))} [{f2(lo1)} ; {f2(hi1)}] ; variation de la CVaR95 : {f2(results[(wnd, 'full')]['cvar'] - results[(wnd, 'none')]['cvar'])} pt.")
        w('')
    # ───── 2. toutes les ruptures
    w('## 2. Nature des ruptures du moteur sur 1998-2026 (1 553 actions, hors filtre d\'univers)\n')
    with open(os.path.join(directory, 'universe.csv'), encoding='utf-8', newline='') as fh:
        import csv
        universe_rows = [u for u in csv.DictReader(fh) if u['kind'] == 'equity' and os.path.exists(os.path.join(directory, 'history', f"{u['key']}.csv.gz"))]
    if args.sample and args.sample < len(universe_rows):
        import random
        universe_rows = random.Random(1).sample(universe_rows, args.sample)
    counts, examples = all_breaks(directory, universe_rows)
    total = sum(counts.values())
    w(f'{total} ruptures (événements distincts titre × date). A1 = split ou regroupement confirmé par le volume (à garder exclu) ; A2 = erreur de cotation isolée (à garder exclue) ; B = mouvement plausible ; C = incertain ; « sous seuil 40 % » = baisse de 37,5 à 40 %.\n')
    w('| Nature | Hausses | Baisses | Total | Exemples |')
    w('|---|---|---|---|---|')
    for cls in PRIORITY:
        up, down = counts.get((cls, 'hausse'), 0), counts.get((cls, 'baisse'), 0)
        ex = '; '.join(examples.get((cls, 'hausse'), [])[:2] + examples.get((cls, 'baisse'), [])[:2])
        w(f'| {cls} | {up} | {down} | {up + down} | {ex} |')
    prot = counts.get(('A1', 'hausse'), 0) + counts.get(('A1', 'baisse'), 0) + counts.get(('A2', 'hausse'), 0) + counts.get(('A2', 'baisse'), 0)
    w(f'\nRuptures reconnaissables comme anomalies de données (A1 + A2) : {prot} sur {total} ({100 * prot / max(1, total):.1f} %). Les {total - prot} autres seraient des mouvements à signaler seulement. '
      'Réserve : la classification regarde les 10 séances suivantes (un saut récent ne peut donc pas être classé et resterait « à vérifier »). Les données d\'export sont ajustées des splits par Yahoo : le nombre de splits non ajustés '
      'est ici SOUS-estimé par rapport à la production (cours Spark non ajustés), dont l\'audit donne la répartition réelle.\n')
    # ───── 3. liste à vérifier
    w('## 3. Liste « mouvement extrême à vérifier » (jamais réintroduite dans un classement)\n')
    w('Titres exclus du momentum 6 mois par la règle ET situés dans le meilleur cinquième du momentum simple à la date. Rendements ensuite (écart à la moyenne de l\'univers, pts) ; hausses et baisses séparées.\n')
    for h in rr.HZ:
        cfg = cfgs[h]
        rowsout = defaultdict(list)
        for kk in sorted(tests[h]):
            d = cfg.dates[kk]
            rows, f, X = d['rows'], d['f'], d['X']
            ok = [j for j in range(len(rows)) if fin(f[j])]
            if not ok:
                continue
            uni = statistics.mean(f[j] for j in ok)
            for j in ok:
                r = rows[j]
                if X[j][0] >= 0.3 and fin(mom[(6, 'none')][r]) and not fin(mom[(6, 'full')][r]):
                    bl = [b for b in brk.get(r, []) if b[0] <= 125]
                    ups, downs = any(b[1] > 1 for b in bl), any(b[1] < 1 for b in bl)
                    key = 'hausse seule' if ups and not downs else 'baisse seule' if downs and not ups else 'hausse et baisse'
                    rowsout[key].append((100 * (f[j] - uni), 100 * f[j]))
                    rowsout['tous'].append((100 * (f[j] - uni), 100 * f[j]))
        base = []
        for kk in sorted(tests[h]):
            d = cfg.dates[kk]
            rows, f, X = d['rows'], d['f'], d['X']
            ok = [j for j in range(len(rows)) if fin(f[j])]
            if not ok:
                continue
            uni = statistics.mean(f[j] for j in ok)
            for j in ok:
                r = rows[j]
                if X[j][0] >= 0.3 and fin(mom[(6, 'full')][r]):
                    base.append((100 * (f[j] - uni), 100 * f[j]))
        w(f'**Horizon {h} séances** — meilleur cinquième du momentum simple, titres NON exclus : {len(base)} expositions, écart moyen {f2(mean_of([x for x, _ in base]))}, rendement inférieur à -30 % dans {100 * sum(1 for _, y in base if y < -30) / max(1, len(base)):.1f} % des cas.\n')
        w('| Signalés | Expositions | Écart moyen (pts) | Médiane (pts) | Rendement < -30 % | Rendement > +50 % |')
        w('|---|---|---|---|---|---|')
        for k in ('tous', 'hausse seule', 'baisse seule', 'hausse et baisse'):
            xs = rowsout.get(k, [])
            w(f"| {k} | {len(xs)} | {f2(mean_of([x for x, _ in xs]))} | {f2(statistics.median([x for x, _ in xs]) if xs else NAN)} | {100 * sum(1 for _, y in xs if y < -30) / max(1, len(xs)):.1f} % | {100 * sum(1 for _, y in xs if y > 50) / max(1, len(xs)):.1f} % |")
        w('')
    # ───── 4. part retenue par année
    w('## 4. Part des titres retenus par chaque profil et par année (univers de recherche)\n')
    w('| Année | ' + ' | '.join(rp.LABELS[p] for p in strategy.PRESETS) + ' |')
    w('|---|' + '---|' * len(strategy.PRESETS))
    by_year = defaultdict(lambda: {p: [0, 0] for p in strategy.PRESETS})
    for r in seen:
        kk = int(D.c['k'][r])
        for p in strategy.PRESETS:
            code = st[p][r]
            if code >= 0:
                by_year[year(kk)][p][1] += 1
                by_year[year(kk)][p][0] += code == 0
    for y in sorted(by_year):
        w(f'| {y} | ' + ' | '.join(f"{100 * by_year[y][p][0] / max(1, by_year[y][p][1]):.1f} %" for p in strategy.PRESETS) + ' |')
    allp = {p: sum(by_year[y][p][0] for y in by_year) / max(1, sum(by_year[y][p][1] for y in by_year)) for p in strategy.PRESETS}
    w('\nMoyenne 2004-2022 : ' + ' ; '.join(f'{rp.LABELS[p]} {100 * allp[p]:.1f} %' for p in strategy.PRESETS) + '.')
    text = '\n'.join(L)
    print(text)
    with open(os.path.join(out_dir, 'diagnostic_ruptures.md'), 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
