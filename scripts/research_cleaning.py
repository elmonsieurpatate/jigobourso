"""Diagnostic du nettoyage des mouvements extrêmes (lecture seule, actions uniquement, AUCUN entraînement).

RÈGLE FIGÉE AVANT TOUT RÉSULTAT. Elle ne regarde jamais le rendement futur d'un exemple d'apprentissage : elle qualifie des ÉVÉNEMENTS dans la série de cours d'un titre, avec une signature
technique, puis corrige ou masque l'événement dans la série (donc pour tous les exemples qui le contiennent, qu'il soit dans la fenêtre d'indicateurs ou dans l'horizon de la cible).

Événement = variation de adjclose d'au moins 40 % en une séance (hausse ou baisse). Classes :
  A1  split non ajusté, CONFIRMÉ : le saut vaut 1/k (ou k) à 3 % près pour k dans {2,3,4,5,6,8,10,15,20,25,50,100}, le niveau persiste (médiane des 10 séances suivantes à 15 % du niveau du saut) ET le
      volume médian des 10 séances suivantes change en sens inverse du prix (produit volume × prix constant à 40 % près) : c'est la signature d'un volume et d'un prix non ajustés. CORRIGÉ (cours et volume
      d'avant l'événement ramenés à l'échelle d'après).
  A2  erreur de cotation isolée : le cours revient à moins de 10 % de son niveau d'avant en 1 à 3 séances, dans le sens opposé au saut. MASQUÉ (barres remplacées par le dernier cours valide).
  A3  incohérence de titre : adjclose supérieur à close de plus de 0,1 % ou rapport adjclose/close qui baisse. TITRE ÉCARTÉ (critère technique, indépendant de la performance).
  C   incertain : ressemble à un split mais le volume ne le confirme pas (volume continu ou absent), ou marche de plus de 30 % dans le rapport adjclose/close (dividende exceptionnel ou erreur).
      CONSERVÉ dans le résultat principal, ISOLÉ ici, et mesuré en sensibilité.
  B   mouvement réel plausible : tout le reste (écart de résultats, faillite, rachat, biotech...). CONSERVÉ toujours.
Ce script écrit un rapport Markdown : comptes par classe, exemples, part des exemples (titre × date de décision toutes les 21 séances) touchés, et ce que changerait un retrait (pour montrer le danger
de la sélection sur le résultat). Usage : python3 scripts/research_cleaning.py ~/tmp-history-long [--sample 0] [--out rapport.md]
"""
import argparse
import csv
import datetime
import gzip
import math
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict

KS = (2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 50, 100)
THRESH, STEP, HORIZONS, WARM = 0.4, 21, (21, 63), 252
CLASSES = ('A1', 'A2', 'B', 'C')


def load(path):
    out = []
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        rd = csv.reader(fh)
        head = next(rd, None)
        if not head:
            return out
        ix = {h: i for i, h in enumerate(head)}
        for r in rd:
            try:
                v = r[ix['volume']]
                out.append((r[ix['date']], float(r[ix['close']]), float(r[ix['adjclose']]), float(v) if v not in ('', None) else None))
            except (ValueError, KeyError, IndexError):
                continue
    return out


def med(xs):
    return statistics.median(xs) if xs else None


def is_split_ratio(p):
    return any(abs(p - 1 / k) / (1 / k) < 0.03 or abs(p - k) / k < 0.03 for k in KS)


def classify(a, c, v):
    """-> liste d'événements (indice, classe, p, fin) ; fin = dernière barre à masquer pour A2."""
    n, events, i = len(a), [], 1
    while i < n:
        p = a[i] / a[i - 1]
        if abs(p - 1) < THRESH:
            i += 1
            continue
        # A2 : retour du cours dans les 3 séances suivantes
        back = next((j for j in range(i + 1, min(n, i + 4)) if abs(a[j] / a[i - 1] - 1) < 0.10 and (p - 1) * (a[j] / a[i] - 1) < 0), None)
        if back is not None:
            events.append((i, 'A2', p, back - 1))
            i = back + 1
            continue
        after = [x for x in a[i:i + 10]]
        persists = len(after) >= 5 and abs(med(after) / a[i] - 1) < 0.15
        cls = 'B'
        if is_split_ratio(p) and persists:
            before_v = [x for x in v[max(0, i - 10):i] if x]
            after_v = [x for x in v[i:i + 10] if x]
            if len(before_v) >= 5 and len(after_v) >= 5:
                vq = med(after_v) / med(before_v)
                cls = 'A1' if abs(math.log(vq * p)) < 0.4 else ('C' if abs(math.log(vq)) < 0.4 else 'B')
            else:
                cls = 'C'
        events.append((i, cls, p, i))
        i += 1
    return events


def clean_series(a, events):
    """adjclose nettoyé : A1 corrigé (échelle d'après), A2 masqué. B et C inchangés."""
    a2 = list(a)
    for i, cls, p, end in events:
        if cls == 'A1':
            for j in range(i):
                a2[j] *= p
        elif cls == 'A2':
            for j in range(i, end + 1):
                a2[j] = a2[i - 1]
    return a2


def title_flag(a, c):
    ratio = [x / y for x, y in zip(a, c)]
    if any(r > 1.001 for r in ratio):
        return 'adj>close'
    down = sum(1 for i in range(1, len(ratio)) if ratio[i] / ratio[i - 1] - 1 < -0.0005)
    if down:
        return 'ratio'
    return None


def ratio_steps(a, c):
    ratio = [x / y for x, y in zip(a, c)]
    return sum(1 for i in range(1, len(ratio)) if ratio[i] / ratio[i - 1] - 1 > 0.3)


def pct(x, tot):
    return f'{100 * x / tot:.1f} %' if tot else '–'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('directory')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--out', default='')
    ap.add_argument('--kind', default='equity')
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.directory)
    with open(os.path.join(d, 'universe.csv'), encoding='utf-8', newline='') as fh:
        universe = [u for u in csv.DictReader(fh) if u['kind'] == args.kind]
    universe = [u for u in universe if os.path.exists(os.path.join(d, 'history', f"{u['key']}.csv.gz"))]
    pool = universe if not args.sample or args.sample >= len(universe) else random.Random(1).sample(universe, args.sample)
    ev_count, ev_titles, examples = Counter(), defaultdict(set), defaultdict(list)
    by_decade = defaultdict(Counter)
    flagged = Counter()
    c_steps_titles = 0
    # exemples d'apprentissage : (titre, date de décision toutes les 21 séances)
    groups = defaultdict(lambda: {h: {'raw': [], 'clean': []} for h in HORIZONS})
    total_obs, hit = 0, Counter()
    t0 = time.monotonic()
    for k, u in enumerate(pool, 1):
        rows = load(os.path.join(d, 'history', f"{u['key']}.csv.gz"))
        if len(rows) < WARM + 70:
            continue
        dates, c, a, v = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]
        tf = title_flag(a, c)
        if tf:
            flagged[tf] += 1
            continue
        steps = ratio_steps(a, c)
        evs = classify(a, c, v)
        if steps:
            c_steps_titles += 1
        for i, cls, p, end in evs:
            ev_count[cls] += 1
            ev_titles[cls].add(u['key'])
            by_decade[dates[i][:3] + '0'][cls] += 1
            if len(examples[cls]) < 6:
                examples[cls].append(f"{u['symbol']} {dates[i]} ×{p:.3g}")
        clean = clean_series(a, evs)
        ev_idx = [(i, cls, end) for i, cls, p, end in evs]
        for t in range(WARM, len(a) - max(HORIZONS), STEP):
            total_obs += 1
            lo, hi = t - WARM, t + max(HORIZONS)
            classes = {cls for i, cls, end in ev_idx if lo < i <= hi}
            if steps:
                classes.add('C')
            key = 'aucun' if not classes else '+'.join(sorted(classes))
            for cls in classes:
                hit[cls] += 1
            for h in HORIZONS:
                groups[key][h]['raw'].append(100 * (a[t + h] / a[t] - 1))
                groups[key][h]['clean'].append(100 * (clean[t + h] / clean[t] - 1))
        if k % 250 == 0:
            print(f'{k}/{len(pool)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    L = []
    w = L.append
    w('# Diagnostic du nettoyage des mouvements extrêmes (actions, lecture seule)\n')
    w(f'*{len(pool)} titres lus, {sum(flagged.values())} écartés pour incohérence technique (A3), {total_obs} exemples (titre × date de décision toutes les {STEP} séances, historique d\'au moins {WARM} séances et {max(HORIZONS)} séances futures). Aucun rendement futur n\'est utilisé pour classer un événement.*\n')
    w('## 1. Événements d\'au moins 40 % en une séance\n')
    w('| Classe | Événements | Titres concernés | Traitement |')
    w('|---|---|---|---|')
    names = {'A1': 'split non ajusté confirmé (prix ET volume)', 'A2': 'erreur de cotation isolée (retour en 1 à 3 séances)', 'B': 'mouvement réel plausible', 'C': 'incertain'}
    treat = {'A1': 'corrigé', 'A2': 'masqué', 'B': 'conservé', 'C': 'conservé, isolé, sensibilité'}
    for cls in CLASSES:
        w(f'| {cls} · {names[cls]} | {ev_count[cls]} | {len(ev_titles[cls])} | {treat[cls]} |')
    w(f'| A3 · incohérence de titre (adjclose > close ou rapport qui baisse) | {sum(flagged.values())} titres ({", ".join(f"{k} {n}" for k, n in flagged.items()) or "aucun"}) | – | titre écarté |')
    w(f'| C · marche > 30 % dans adjclose/close (titres) | {c_steps_titles} titres | – | classés C : exemples touchés comptés en C |')
    w('\nExemples : ' + ' ; '.join(f'**{cls}** : ' + (', '.join(examples[cls]) or 'aucun') for cls in CLASSES) + '.\n')
    w('Par décennie (événements) : ' + ' ; '.join(f'{dec} : ' + ', '.join(f'{cls} {by_decade[dec][cls]}' for cls in CLASSES) for dec in sorted(by_decade)) + '.\n')
    w('## 2. Part des exemples touchés\n')
    w('Un exemple est « touché » par une classe si un événement de cette classe tombe dans sa fenêtre d\'indicateurs (252 séances avant la date) ou dans son horizon (63 séances après).\n')
    w('| Classe | Exemples touchés | Part |')
    w('|---|---|---|')
    for cls in CLASSES:
        w(f'| {cls} | {hit[cls]} | {pct(hit[cls], total_obs)} |')
    w('\n## 3. Ce que changerait un retrait (rendement des exemples, en %, adjclose)\n')
    w('Pour chaque groupe d\'exemples : nombre, rendement moyen et médian à 21 et 63 séances, tel quel (« brut ») et après correction A1/A2 (« nettoyé »). Un groupe dont le rendement moyen est très inférieur aux autres montre ce que gagnerait artificiellement un retrait systématique.\n')
    w('| Groupe d\'événements dans la fenêtre ou l\'horizon | Exemples | Part | 21 s brut moy. | 21 s nettoyé moy. | 63 s brut moy. (méd.) | 63 s nettoyé moy. (méd.) |')
    w('|---|---|---|---|---|---|---|')
    allraw63 = [x for g in groups.values() for x in g[63]['raw']]
    for key in sorted(groups, key=lambda s: (s != 'aucun', s)):
        g = groups[key]
        m = lambda xs: f'{statistics.mean(xs):+.2f}' if xs else '–'
        md = lambda xs: f'{statistics.median(xs):+.2f}' if xs else '–'
        n = len(g[63]['raw'])
        w(f"| {key} | {n} | {pct(n, total_obs)} | {m(g[21]['raw'])} | {m(g[21]['clean'])} | {m(g[63]['raw'])} ({md(g[63]['raw'])}) | {m(g[63]['clean'])} ({md(g[63]['clean'])}) |")
    ex = [x for k2, g in groups.items() if k2 != 'aucun' for x in g[63]['raw']]
    base = groups['aucun'][63]['raw']
    if ex and base:
        w(f'\nRetirer d\'un coup tous les exemples touchés par au moins un événement ôterait {pct(len(ex), total_obs)} des exemples ; leur rendement moyen à 63 séances est {statistics.mean(ex):+.2f} % contre {statistics.mean(base):+.2f} % pour les exemples sans événement.')
    w('\n## 4. Plan de sensibilité (défini avant l\'entraînement)\n')
    w('1. **Principal** : séries corrigées (A1) et masquées (A2), titres A3 écartés, B et C conservés.')
    w('2. **S1** : principal + exemples touchés par C exclus (mesure le poids de l\'incertain).')
    w('3. **S2** : principal + cible aplatie à ±3 écarts-types de la médiane de la date (limite l\'influence d\'un point sans le supprimer).')
    w('4. **S3 (borne agressive)** : tous les exemples touchés par un événement de 40 % retirés. Sert UNIQUEMENT à montrer de combien un nettoyage trop agressif améliorerait artificiellement les résultats ; jamais retenu comme résultat.')
    w('5. Le modèle est jugé sur le principal ; un résultat qui n\'existe que dans S3 ou S1 est déclaré fragile.')
    text = '\n'.join(L)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
