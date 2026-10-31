"""Inventaire (lecture seule, sans réseau) d'un dossier d'historiques exporté par scripts/export_history.py : ce que les analyses de recherche peuvent réellement utiliser.

Affiche : nombre de titres par type (action / ETF), devise, pays ; titres sans historique ; profondeur (première et dernière date) ; nombre de titres suivis par année (le biais de survie
se voit ici : peu de titres dans les années 1990) ; part de volumes renseignés ; colonnes disponibles dans universe.csv (secteur ou non).
Usage : python3 scripts/inventory_history.py ~/tmp-history-long [--sample 400]
"""
import argparse
import csv
import gzip
import os
import random
import sys
from collections import Counter


def read_dates(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('directory')
    ap.add_argument('--sample', type=int, default=400, help='nombre de fichiers lus pour la profondeur et les volumes (0 = tous)')
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.directory)
    with open(os.path.join(d, 'universe.csv'), encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        columns, universe = reader.fieldnames, list(reader)
    print(f'universe.csv : {len(universe)} titres · colonnes : {", ".join(columns)}')
    print('  secteur (category) :', 'OUI' if 'category' in columns else 'NON (python3 scripts/export_history.py --out DOSSIER --update-universe)')
    for field in ('kind', 'currency', 'country', 'mic'):
        if field in columns:
            print(f'  {field} : ' + ', '.join(f'{k or "?"} {v}' for k, v in Counter(u[field] for u in universe).most_common(8)))
    present = [u for u in universe if os.path.exists(os.path.join(d, 'history', f"{u['key']}.csv.gz"))]
    print(f'fichiers d\'historique : {len(present)} / {len(universe)}')
    pool = present if not args.sample or args.sample >= len(present) else random.Random(1).sample(present, args.sample)
    per_year, firsts, lasts, vol_share, empty, lengths = Counter(), [], [], [], 0, []
    for u in pool:
        rows = read_dates(os.path.join(d, 'history', f"{u['key']}.csv.gz"))
        if not rows:
            empty += 1
            continue
        firsts.append(rows[0]['date'])
        lasts.append(rows[-1]['date'])
        lengths.append(len(rows))
        vol_share.append(sum(1 for r in rows if r['volume'] not in ('', None)) / len(rows))
        for y in {r['date'][:4] for r in rows}:
            per_year[y] += 1
    n = len(pool) - empty
    print(f'échantillon lu : {len(pool)} fichiers dont {empty} vides')
    if n:
        print(f'  première date : {min(firsts)} · dernière : {max(lasts)} · séances par titre (médiane) : {sorted(lengths)[len(lengths) // 2]}')
        print(f'  part de séances avec volume (moyenne) : {100 * sum(vol_share) / n:.0f} %')
        print('  titres de l\'échantillon présents, par année (extrait) :')
        for y in sorted(per_year):
            if int(y) % 3 == 0 or y == max(per_year):
                print(f'    {y} : {per_year[y]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
