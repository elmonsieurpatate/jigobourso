"""Justification du nettoyage : montre, sur les vraies données, CE QUE la règle fait (lecture seule, actions uniquement, aucun entraînement).

Pour une règle v1 (celle du diagnostic déjà publié) et une règle v2 plus STRICTE (proposée), liste les cas A1 (tous), A2 (échantillon tiré avec une graine fixe) et B (échantillon), avec les
preuves utilisées (précision du rapport de prix, évolution du volume, séance du saut) et les cours AVANT / APRÈS correction autour de l'événement. Une matrice de transition v1 -> v2 montre combien
d'événements changent de classe. Rien ne regarde un rendement futur d'exemple d'apprentissage.

RÈGLE v2 (stricte ; ce qui n'est pas certain devient C = conservé et signalé, jamais corrigé) :
  A1 : saut = 1/k ou k à 1,5 % près ; niveau persistant (médiane des 10 séances suivantes à 15 % du niveau du saut) ; volume médian des 10 séances suivantes en sens inverse du prix à 50 % près ;
       ET volume de la séance du saut à l'échelle du split (produit volume × prix à 2 près), pas un pic démesuré. Rapport entre 1,5 % et 3 % de 1/k ou k, ou volume qui ne confirme pas : C.
  A2 : retour du cours en 1 ou 2 séances à moins de 5 % de son niveau d'avant, sens opposé au saut, ET volume des séances du saut <= 3 fois la médiane des 20 séances précédentes. Retour avec gros
       volume : B (vraie envolée). Retour sans volume exploitable, ou en 3 séances, ou à 5-10 % : C.
  B  : tout le reste ; C : incertain.
Disponibilité (aucun avenir pour un exemple daté t) : A1 n'est connu qu'à l'événement + 10 séances, A2 qu'à + 2 séances ; avant cela l'événement est traité comme C pour tout exemple daté dans ce délai.
Usage : python3 scripts/research_cleaning_cases.py ~/tmp-history-long [--seed 7] [--out rapport.md]
"""
import argparse
import csv
import math
import os
import random
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from research_cleaning import KS, THRESH, classify, clean_series, load, med, title_flag   # noqa: E402


def split_err(p):
    return min(min(abs(p - 1 / k) / (1 / k), abs(p - k) / k) for k in KS)


def classify_v2(a, c, v):
    n, events, i = len(a), [], 1
    while i < n:
        p = a[i] / a[i - 1]
        if abs(p - 1) < THRESH:
            i += 1
            continue
        back = next((j for j in range(i + 1, min(n, i + 4)) if abs(a[j] / a[i - 1] - 1) < 0.10 and (p - 1) * (a[j] / a[i] - 1) < 0), None)
        if back is not None:
            tight = back <= i + 2 and abs(a[back] / a[i - 1] - 1) < 0.05
            base = [x for x in v[max(0, i - 20):i] if x]
            spike = v[i:back]
            if tight and len(base) >= 10 and all(x is not None for x in spike):
                cls = 'A2' if max(spike) <= 3 * med(base) else 'B'
            else:
                cls = 'C'
            events.append((i, cls, p, back - 1))
            i = back + 1
            continue
        err = split_err(p)
        after = a[i:i + 10]
        persists = len(after) >= 5 and abs(med(after) / a[i] - 1) < 0.15
        cls = 'B'
        if err < 0.03 and persists:
            bv = [x for x in v[max(0, i - 10):i] if x]
            av = [x for x in v[i:i + 10] if x]
            if len(bv) >= 5 and len(av) >= 5 and v[i]:
                vq, vd = med(av) / med(bv), v[i] / med(bv)
                ok = err < 0.015 and abs(math.log(vq * p)) < math.log(1.5) and abs(math.log(vd * p)) < math.log(2)
                cls = 'A1' if ok else ('C' if abs(math.log(vq)) < 0.4 or err >= 0.015 else 'B')
            else:
                cls = 'C'
        events.append((i, cls, p, i))
        i += 1
    return events


def evidence(a, c, v, i, p):
    bv = [x for x in v[max(0, i - 10):i] if x]
    av = [x for x in v[i:i + 10] if x]
    vq = med(av) / med(bv) if len(bv) >= 5 and len(av) >= 5 else None
    vd = v[i] / med(bv) if bv and v[i] else None
    return f'précision du rapport : {100 * split_err(p):.2f} % · volume 10 s après / avant : {vq:.2f}' if vq else 'volume insuffisant', (f'· volume du jour / médiane avant : {vd:.2f}' if vd else '')


def fmt(rows, vals, i, w=3):
    lo, hi = max(0, i - w), min(len(vals), i + w + 1)
    return ' '.join(f'{vals[j]:.4g}' if j != i else f'[{vals[j]:.4g}]' for j in range(lo, hi))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('directory')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', default='')
    ap.add_argument('--a2', type=int, default=10)
    ap.add_argument('--b', type=int, default=4)
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.directory)
    with open(os.path.join(d, 'universe.csv'), encoding='utf-8', newline='') as fh:
        universe = [u for u in csv.DictReader(fh) if u['kind'] == 'equity']
    rnd = random.Random(args.seed)
    trans, cases = Counter(), {'A1': [], 'A2': [], 'B': []}
    for u in universe:
        path = os.path.join(d, 'history', f"{u['key']}.csv.gz")
        if not os.path.exists(path):
            continue
        rows = load(path)
        if len(rows) < 322:
            continue
        dates, c, a, v = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]
        if title_flag(a, c):
            continue
        e1, e2 = classify(a, c, v), {i: cls for i, cls, _, _ in classify_v2(a, c, v)}
        for i, cls, p, end in e1:
            trans[(cls, e2.get(i, 'absent'))] += 1
            if cls in cases:
                cases[cls].append((u['symbol'], dates, c, a, v, i, p, end, e2.get(i, 'absent'), e1))
    L, w = [], None
    w = L.append
    w('# Justification du nettoyage : règle v1 (publiée) et v2 (stricte proposée)\n')
    w('## 1. Matrice de transition v1 -> v2 (nombre d\'événements)\n')
    names = ('A1', 'A2', 'B', 'C', 'absent')
    w('| v1 \\ v2 | ' + ' | '.join(names) + ' |')
    w('|---|' + '---|' * len(names))
    for r in ('A1', 'A2', 'B', 'C'):
        w(f'| {r} | ' + ' | '.join(str(trans[(r, x)]) for x in names) + ' |')
    w('\n« absent » : l\'événement a été absorbé par un autre dans la règle v2 (séquences de sauts rapprochés).\n')
    picks = [('A1', cases['A1']), ('A2', rnd.sample(cases['A2'], min(args.a2, len(cases['A2'])))), ('B', rnd.sample(cases['B'], min(args.b, len(cases['B']))))]
    w('## 2. Cas (cours AVANT -> APRÈS correction v1, 3 séances de chaque côté ; [crochets] = séance du saut)\n')
    w('| Classe v1 | Classe v2 | Titre | Date | Saut | Preuves |')
    w('|---|---|---|---|---|---|')
    for cls, lst in picks:
        for sym, dates, c, a, v, i, p, end, v2, e1 in lst:
            ev = evidence(a, c, v, i, p)
            w(f'| {cls} | {v2} | {sym} | {dates[i]} | ×{p:.3g} | {ev[0]} {ev[1]} |')
    w('\n## 3. Détail avant / après\n')
    for cls, lst in picks:
        for sym, dates, c, a, v, i, p, end, v2, e1 in lst:
            one = clean_series(a, [(i, cls, p, end)]) if cls in ('A1', 'A2') else a
            w(f'**{cls} (v2 : {v2}) · {sym} · {dates[i]} · ×{p:.3g}**')
            w(f'- clôture ajustée avant correction : {fmt(None, a, i)}')
            w(f'- clôture ajustée après correction  : {fmt(None, one, i)}')
            w(f'- volume brut                        : {fmt(None, [x or 0 for x in v], i)}')
            w('')
    w('## 4. Lecture\n')
    w('- A1 : après correction, le rendement de la séance du saut est fixé à 0 (le rendement réel de cette séance est inconnu), et tous les cours d\'avant sont multipliés par le rapport du saut. Un vrai krach classé A1 par erreur verrait sa perte effacée : c\'est le risque que la règle v2 réduit.')
    w('- A2 : les barres du saut sont remplacées par le dernier cours valide. Un aller-retour réel (envolée sans volume anormal) serait masqué : le critère de volume et le retour sous 5 % en 2 séances limitent ce risque ; le reste passe en C.')
    text = '\n'.join(L)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
