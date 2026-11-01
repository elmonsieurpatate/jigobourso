"""Inventaire ÉTENDU (lecture seule, sans réseau, sans entraînement) des historiques exportés : la donnée permet-elle un test d'apprentissage crédible ?

Lit un dossier produit par scripts/export_history.py (universe.csv + history/<clé>.csv.gz : date, close, adjclose, volume) et écrit un rapport Markdown :
  1. couverture par ancienneté (3, 5, 10, 15, 20, 30 ans) et titres exploitables par année, actions et ETF séparés ;
  2. qualité des cours ajustés (distributions, splits, écarts anormaux) et volumes autour des splits ;
  3. reconstitution de la négociabilité à chaque date passée (volumes, valeur échangée) sans aucune donnée actuelle ;
  4. risques de fuite temporelle (niveau de prix ajusté rétroactivement, catégories actuelles) ;
  5. catégories d'ETF : disponibilité et fiabilité ;
  6. origine de l'échantillon et biais de sélection (option --db : lecture seule de la base) ;
  7. scénarios de frais proposés.
Usage : python3 scripts/inventory_extended.py ~/tmp-history-long [--sample 0] [--out rapport.md] [--db]
"""
import argparse
import bisect
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

AGES = (3, 5, 10, 15, 20, 30)
SPLITS = (2, 3, 4, 5, 8, 10, 20)
LIQ_USD = 1_000_000          # valeur échangée médiane par séance (63 séances précédentes), titres cotés en USD seulement : aucun taux de change n'est disponible
WINDOW, NEED = 63, 252


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


def analyze(rows, currency, years_range):
    n = len(rows)
    d = [r[0] for r in rows]
    c = [r[1] for r in rows]
    a = [r[2] for r in rows]
    v = [r[3] for r in rows]
    res = {'n': n, 'first': d[0], 'last': d[-1]}
    t0, t1 = datetime.date.fromisoformat(d[0]), datetime.date.fromisoformat(d[-1])
    res['years'] = (t1 - t0).days / 365.25
    # trous de calendrier
    gap_max, gaps10, prev = 0, 0, t0
    for s in d[1:]:
        t = datetime.date.fromisoformat(s)
        g = (t - prev).days
        gap_max = max(gap_max, g)
        gaps10 += g > 10
        prev = t
    res['gap_max'], res['gaps10'] = gap_max, gaps10
    # cours ajusté : structure du rapport adjclose/close
    ratio = [x / y for x, y in zip(a, c)]
    res['ratio_first'] = ratio[0]
    res['adj_above_close'] = sum(1 for r in ratio if r > 1.001)
    steps_up = steps_down = steps_big = 0
    for i in range(1, n):
        s = ratio[i] / ratio[i - 1] - 1
        if s > 0.0005:
            steps_up += 1
            steps_big += s > 0.3
        elif s < -0.0005:
            steps_down += 1
    res['div_events'], res['ratio_down'], res['ratio_big'] = steps_up, steps_down, steps_big
    if res['years'] >= 1:
        pr, tr = c[-1] / c[0], a[-1] / a[0]
        res['implied_yield'] = ((tr / pr) ** (1 / res['years']) - 1) * 100 if pr > 0 and tr > 0 else None
    else:
        res['implied_yield'] = None
    # sauts extrêmes et ressemblant à un split ; volume autour de ces sauts
    extreme = splitlike = vol_unadj = vol_cont = 0
    for i in range(1, n):
        p = a[i] / a[i - 1]
        if abs(p - 1) >= 0.4:
            extreme += 1
            if any(abs(p - 1 / k) / (1 / k) < 0.04 or abs(p - k) / k < 0.04 for k in SPLITS):
                splitlike += 1
                before = [x for x in v[max(0, i - 10):i] if x]
                after = [x for x in v[i:i + 10] if x]
                if len(before) >= 5 and len(after) >= 5:
                    vq = statistics.median(after) / statistics.median(before)
                    if abs(math.log(vq * p)) < 0.35:
                        vol_unadj += 1                     # le volume a bougé en sens inverse du prix : volume NON ajusté du split
                    elif abs(math.log(vq)) < 0.35:
                        vol_cont += 1                      # volume continu : ajusté
    res['extreme'], res['splitlike'], res['vol_unadj'], res['vol_cont'] = extreme, splitlike, vol_unadj, vol_cont
    # volumes
    vols = [x for x in v if x is not None]
    res['vol_share'] = len(vols) / n
    res['zero_vol'] = sum(1 for x in vols if x == 0) / max(1, len(vols))
    # exploitabilité et négociabilité au 1er janvier de chaque année (uniquement avec les données ANTÉRIEURES)
    by_year = {}
    for y in years_range:
        idx = bisect.bisect_left(d, f'{y}-01-01')
        if idx < NEED or d[-1] < f'{y}-01-01':
            continue
        win = [(c[j], v[j]) for j in range(idx - WINDOW, idx)]
        cover = sum(1 for _, x in win if x) / WINDOW
        values = [px * x for px, x in win if x]
        med = statistics.median(values) if values else 0
        stale = (datetime.date.fromisoformat(f'{y}-01-01') - datetime.date.fromisoformat(d[idx - 1])).days > 10
        by_year[y] = (not stale, cover >= 0.8, cover >= 0.8 and currency == 'USD' and med >= LIQ_USD)
    res['by_year'] = by_year
    return res


def pct(x, tot):
    return f'{100 * x / tot:.0f} %' if tot else '–'


def med(xs):
    return statistics.median(xs) if xs else float('nan')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('directory')
    ap.add_argument('--sample', type=int, default=0, help='nombre de fichiers lus (0 = tous)')
    ap.add_argument('--out', default='')
    ap.add_argument('--db', action='store_true', help='compte aussi, en lecture seule, le catalogue de la base (origine de l\'échantillon)')
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.directory)
    with open(os.path.join(d, 'universe.csv'), encoding='utf-8', newline='') as fh:
        rd = csv.DictReader(fh)
        columns, universe = rd.fieldnames, list(rd)
    present = [u for u in universe if os.path.exists(os.path.join(d, 'history', f"{u['key']}.csv.gz"))]
    pool = present if not args.sample or args.sample >= len(present) else random.Random(1).sample(present, args.sample)
    years_range = range(1994, datetime.date.today().year + 1)
    stats, t0 = [], time.monotonic()
    for i, u in enumerate(pool, 1):
        rows = load(os.path.join(d, 'history', f"{u['key']}.csv.gz"))
        if rows:
            r = analyze(rows, u.get('currency'), years_range)
            r['u'] = u
            stats.append(r)
        if i % 250 == 0:
            print(f'{i}/{len(pool)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    kinds = sorted({s['u']['kind'] for s in stats})
    L = []
    w = L.append
    w('# Inventaire étendu des historiques (lecture seule)\n')
    w(f'*Dossier : {d}. {len(universe)} titres dans universe.csv, {len(present)} fichiers présents, {len(stats)} lus et non vides. Aucun entraînement, aucune écriture, aucune modification de la production.*\n')
    w('## 1. Couverture par ancienneté\n')
    w('Ancienneté = durée entre la première et la dernière séance du titre. Colonnes : nombre de titres ayant AU MOINS cette durée.\n')
    w('| Type | Titres | ' + ' | '.join(f'≥ {x} ans' for x in AGES) + ' | Séances médianes |')
    w('|---|---|' + '---|' * len(AGES) + '---|')
    for k in kinds + ['(tous)']:
        ss = [s for s in stats if k == '(tous)' or s['u']['kind'] == k]
        w(f'| {k} | {len(ss)} | ' + ' | '.join(f"{sum(1 for s in ss if s['years'] >= x)} ({pct(sum(1 for s in ss if s['years'] >= x), len(ss))})" for x in AGES) + f" | {med([s['n'] for s in ss]):.0f} |")
    firsts = Counter(s['first'][:4] for s in stats)
    w('\nTitres dont l\'historique COMMENCE chaque année (extrait) : ' + ', '.join(f'{y} : {firsts[y]}' for y in sorted(firsts) if int(y) % 3 == 0) + '.\n')
    w('## 2. Titres exploitables par année (au 1er janvier, avec les données antérieures seulement)\n')
    w(f'« Exploitable » = au moins {NEED} séances d\'historique avant le 1er janvier et une dernière séance de moins de 10 jours avant cette date. « Négociable (volume) » = de plus, volume renseigné sur au moins 80 % des {WINDOW} séances précédentes. « ≥ 1 M USD » = de plus, valeur échangée médiane (close × volume) d\'au moins 1 M, titres cotés en USD seulement (aucun taux de change).\n')
    for k in kinds:
        w(f'**{k}**\n')
        w('| Année | Exploitables | Négociables (volume) | ≥ 1 M USD (USD seul.) |')
        w('|---|---|---|---|')
        for y in years_range:
            ss = [s['by_year'][y] for s in stats if s['u']['kind'] == k and y in s['by_year']]
            if ss and (y % 3 == 0 or y == years_range[-1]):
                w(f'| {y} | {len(ss)} | {sum(1 for x in ss if x[1])} | {sum(1 for x in ss if x[2])} |')
        w('')
    w('## 3. Qualité des cours ajustés\n')
    w('La clôture (`close`) est ajustée des splits ; `adjclose` l\'est aussi des distributions. Rendement de distribution implicite = (rendement total / rendement hors dividendes) annualisé.\n')
    w('| Type | Titres | Rendement implicite médian (%/an) | Titres sans aucun écart (close = adjclose) | Événements de distribution par titre et par an (médiane) | adjclose > close | Rapport qui baisse | Marche > 30 % |')
    w('|---|---|---|---|---|---|---|---|')
    for k in kinds:
        ss = [s for s in stats if s['u']['kind'] == k]
        yl = [s['implied_yield'] for s in ss if s['implied_yield'] is not None]
        flat = sum(1 for s in ss if s['div_events'] == 0 and abs(s['ratio_first'] - 1) < 0.0005)
        ev = [s['div_events'] / s['years'] for s in ss if s['years'] >= 1]
        w(f"| {k} | {len(ss)} | {med(yl):.2f} | {flat} ({pct(flat, len(ss))}) | {med(ev):.1f} | {sum(1 for s in ss if s['adj_above_close'])} | {sum(1 for s in ss if s['ratio_down'])} | {sum(1 for s in ss if s['ratio_big'])} |")
    w('\nLecture : un ETF distribuant doit montrer un rendement implicite visible et des événements réguliers ; un ETF capitalisant, un écart nul est normal. Un rapport adjclose/close qui BAISSE dans le temps, ou une marche de plus de 30 %, révèle un ajustement douteux.\n')
    w('**Sauts extrêmes (≥ 40 % en une séance, sur adjclose)**\n')
    w('| Type | Titres concernés | Sauts | Dont ressemblant à un split | Volume ajusté du split | Volume NON ajusté du split |')
    w('|---|---|---|---|---|---|')
    for k in kinds:
        ss = [s for s in stats if s['u']['kind'] == k]
        w(f"| {k} | {sum(1 for s in ss if s['extreme'])} | {sum(s['extreme'] for s in ss)} | {sum(s['splitlike'] for s in ss)} | {sum(s['vol_cont'] for s in ss)} | {sum(s['vol_unadj'] for s in ss)} |")
    w('\nUn saut qui ressemble à un split et qui reste dans `adjclose` est un split NON ajusté : il fausse les indicateurs. Un volume non ajusté autour d\'un split fausse la valeur échangée historique.\n')
    w('**Trous de calendrier et volumes**\n')
    w('| Type | Titres avec un trou > 10 jours | Plus grand trou (jours, médiane) | Part de séances avec volume (moyenne) | Part de volumes nuls (moyenne) |')
    w('|---|---|---|---|---|')
    for k in kinds:
        ss = [s for s in stats if s['u']['kind'] == k]
        w(f"| {k} | {sum(1 for s in ss if s['gaps10'])} | {med([s['gap_max'] for s in ss]):.0f} | {100 * sum(s['vol_share'] for s in ss) / len(ss):.0f} % | {100 * sum(s['zero_vol'] for s in ss) / len(ss):.1f} % |")
    w('\n## 4. Fuite temporelle : ce que les ajustements rétroactifs peuvent contaminer\n')
    for k in kinds:
        ss = [s for s in stats if s['u']['kind'] == k]
        low = sum(1 for s in ss if s['ratio_first'] < 0.5)
        mid = sum(1 for s in ss if 0.5 <= s['ratio_first'] < 0.9)
        w(f'- **{k}** : au premier jour de l\'historique, adjclose vaut moins de 50 % de close pour {low} titres ({pct(low, len(ss))}) et 50-90 % pour {mid} ({pct(mid, len(ss))}). Pour ces titres, un seuil de PRIX (par exemple « cours > 5 ») calculé sur adjclose serait faux dans le passé : les niveaux de prix et la valeur échangée doivent venir de `close`, seuls les rendements de `adjclose`.')
    w('- Les rendements calculés sur adjclose sont exacts (le rapport adjclose/close ne change que les niveaux, pas les variations journalières).')
    w('- Le volume est celui de l\'export à la date de téléchargement ; les lignes « volume non ajusté du split » ci-dessus indiquent où il est incohérent.')
    w('- Aucune caractéristique actuelle (secteur, catégorie, pays, statut « sélectionné ») n\'est connue à date : voir §5 et §6 pour ce qui ne devra PAS servir à reconstituer le passé.\n')
    w('## 5. Catégories d\'ETF et secteur\n')
    if 'category' not in columns:
        w('universe.csv ne contient PAS de colonne `category` (python3 scripts/export_history.py --out DOSSIER --update-universe l\'ajoute sans appel Yahoo).\n')
    else:
        for k in kinds:
            uu = [u for u in universe if u['kind'] == k]
            filled = [u for u in uu if (u.get('category') or '').strip()]
            cats = Counter(u['category'].strip() for u in filled)
            w(f'- **{k}** : catégorie renseignée pour {len(filled)} / {len(uu)} ({pct(len(filled), len(uu))}), {len(cats)} valeurs distinctes ; les plus fréquentes : ' + ', '.join(f'{c} ({n})' for c, n in cats.most_common(12)) + '.')
            small = sum(1 for n in cats.values() if n < 15)
            w(f'  {small} catégories ont moins de 15 titres (trop peu pour une médiane de référence fiable).')
        w('\nLa catégorie est celle D\'AUJOURD\'HUI : elle sert à grouper des pairs, pas à reconstituer une information qu\'on aurait eue dans le passé. Si elle sert de groupe de référence, elle doit rester un simple regroupement (jamais un indicateur du modèle).\n')
    w('## 6. Origine de l\'échantillon et biais de sélection\n')
    w('- Les titres exportés viennent de la vue `v_recommendable` : cotations `status = selected` ET principales (`is_primary = 1`), c\'est-à-dire ce que le site recommande AUJOURD\'HUI, après les filtres actuels du catalogue (préfiltres, exclusions, cotation principale). C\'est donc un biais de sélection en plus du biais de survie : un titre est présent parce qu\'il passe les filtres actuels.')
    for field in ('kind', 'country', 'currency', 'mic'):
        if field in columns:
            w(f'- {field} : ' + ', '.join(f'{k or "?"} {v}' for k, v in Counter(u[field] for u in universe).most_common(10)))
    if args.db:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from engine.shared.db import connect
            conn = connect()
            with conn.cursor() as cur:
                cur.execute('SET SESSION TRANSACTION READ ONLY')
                cur.execute('SELECT i.kind, l.status, l.is_primary, COUNT(*) AS n FROM listings l JOIN instruments i ON i.id = l.instrument_id GROUP BY i.kind, l.status, l.is_primary ORDER BY i.kind, l.status')
                rows = cur.fetchall()
                cur.execute("SELECT excluded_reason AS r, COUNT(*) AS n FROM listings WHERE status = 'excluded' GROUP BY excluded_reason ORDER BY n DESC LIMIT 12")
                reasons = cur.fetchall()
            conn.rollback()
            conn.close()
            w('\nCatalogue actuel (lecture seule) :\n')
            w('| Type | Statut | Principale | Cotations |')
            w('|---|---|---|---|')
            for r in rows:
                w(f"| {r['kind']} | {r['status']} | {r['is_primary']} | {r['n']} |")
            w('\nPrincipaux motifs d\'exclusion actuels : ' + '; '.join(f"{r['r']} ({r['n']})" for r in reasons) + '.')
            sel = sum(r['n'] for r in rows if r['status'] == 'selected' and r['is_primary'])
            w(f'\nLe catalogue recommandable compte {sel} cotations ; l\'export en couvre {len(universe)} ({pct(len(universe), sel)}). Si ce rapport est inférieur à 100 %, l\'export est un échantillon aléatoire (graine 1) du catalogue.')
        except Exception as e:                      # le rapport reste utile sans la base
            w(f'\n(Option --db : lecture du catalogue impossible : {e})')
    else:
        w('- Option `--db` non utilisée : relancez avec `--db` (sur l\'hébergement, avec PYTHONPATH=$PWD) pour comparer l\'export au catalogue complet et lister les motifs d\'exclusion.')
    w('')
    w('## 7. Scénarios de frais proposés pour l\'étude (par achat ou vente, avant tout calcul)\n')
    w('| Scénario | Frais + écart de prix | Usage |')
    w('|---|---|---|')
    w('| Favorable | 10 pb | borne haute de ce qu\'un investisseur très liquide peut espérer |')
    w('| Central | 30 pb | scénario de référence des analyses précédentes |')
    w('| Prudent | 60 pb | petits volumes |')
    w('| Défavorable | 100 pb, et 150 pb sous 1 M de valeur échangée quotidienne | spreads élargis, titres peu liquides |')
    w('\nAucun spread historique n\'existe : les coûts sont des hypothèses, jamais des mesures. Le résultat n\'est retenu que s\'il reste positif dans le scénario prudent.')
    text = '\n'.join(L)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
