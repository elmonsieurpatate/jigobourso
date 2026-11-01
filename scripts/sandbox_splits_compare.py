"""Compare deux sorties de sandbox_splits_dump.py (ancien code / nouveau code, même base). Seuls les motifs de données manquantes peuvent différer, et uniquement de « calendar » ou « momentum » vers « break »."""
import collections
import json
import sys

a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
changed_core, total = 0, 0
reasons = collections.Counter()
bad = []
for profile in a:
    for key, x in a[profile].items():
        y = b[profile][key]
        total += 1
        if any(x[f] != y[f] for f in ('status', 'rank', 'score', 'quality', 'criteria')):
            changed_core += 1
            bad.append((profile, x['symbol']))
        if len(x['missing']) != len(y['missing']):
            bad.append((profile, x['symbol'], 'nombre de motifs'))
            continue
        for (p1, m1), (p2, m2) in zip(x['missing'], y['missing']):
            if (p1, m1) != (p2, m2):
                reasons[f'{m1} -> {m2}' + ('' if p1 == p2 else ' (période différente)')] += 1
print(f'{total} (titre × profil) comparés')
print(f'statut, rang, score, qualité ou résultat de critère différents : {changed_core}')
print('motifs de données manquantes modifiés : ' + (', '.join(f'{k} : {n}' for k, n in reasons.items()) or 'aucun'))
unexpected = [k for k in reasons if k not in ('calendar -> break', 'momentum -> break')]
print('modifications inattendues :', unexpected or 'aucune', bad[:5])
sys.exit(1 if changed_core or unexpected or bad else 0)
