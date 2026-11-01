"""Compare deux sorties de sandbox_splits_dump.py (ancien code / nouveau code, même base). Seuls les motifs de données manquantes peuvent différer, et uniquement de « calendar » vers « break »."""
import collections
import json
import sys

a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
changed_core, changed_reason, total = 0, collections.Counter(), 0
bad = []
for profile in a:
    for key, x in a[profile].items():
        y = b[profile][key]
        total += 1
        if any(x[f] != y[f] for f in ('status', 'rank', 'score', 'quality', 'criteria')):
            changed_core += 1
            bad.append((profile, x['symbol']))
        if x['missing'] != y['missing']:
            for (p1, m1), (p2, m2) in zip(x['missing'], y['missing']) if len(x['missing']) == len(y['missing']) else []:
                changed_reason[f'{m1} -> {m2}'] += 1
            if len(x['missing']) != len(y['missing']):
                bad.append((profile, x['symbol'], 'nombre de motifs'))
print(f'{total} (titre × profil) comparés')
print(f'statut, rang, score, qualité ou résultat de critère différents : {changed_core}')
print('motifs de données manquantes modifiés : ' + (', '.join(f'{k} : {n}' for k, n in changed_reason.items()) or 'aucun'))
unexpected = [k for k in changed_reason if k not in ('calendar -> break', 'momentum -> break')]
print('modifications inattendues :', unexpected or 'aucune', bad[:5])
sys.exit(1 if changed_core or unexpected or any(len(x) == 3 for x in bad) else 0)
