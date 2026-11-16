"""Supprime les fiches `*.dist-info` obsolètes laissées par `pip install --target`.

`pip --target --upgrade` remplace le dossier du paquet mais pas la fiche de l'ancienne version (`pymysql-1.2.3.dist-info` reste à côté
de `pymysql-1.2.4.dist-info`). Le contrôle d'environnement lit alors la mauvaise version et refuse un venv pourtant à jour.

Règle prudente : un nom n'est touché que s'il a plusieurs fiches ET qu'une seule correspond à la version figée dans requirements.txt ;
les fiches des autres versions sont supprimées. Sans correspondance exacte, rien n'est supprimé.

Usage : python3 prune_stale_metadata.py <site-packages> <requirements.txt>
"""

import re
import shutil
import sys
from pathlib import Path


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def pinned(requirements_text):
    """{nom normalisé: version} pour les lignes `nom==version`."""
    found = {}
    for line in requirements_text.splitlines():
        match = re.match(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s#;]+)', line)
        if match:
            found[normalize(match.group(1))] = match.group(2)
    return found


def prune(site, requirements_text):
    """Renvoie la liste des fiches supprimées."""
    wanted = pinned(requirements_text)
    by_name = {}
    for entry in Path(site).glob('*.dist-info'):
        name, _, version = entry.name[: -len('.dist-info')].rpartition('-')
        if name:
            by_name.setdefault(normalize(name), []).append((version, entry))
    removed = []
    for name, entries in by_name.items():
        if len(entries) < 2 or name not in wanted:
            continue
        keep = [e for v, e in entries if v == wanted[name]]
        if len(keep) != 1:
            continue
        for version, entry in entries:
            if entry != keep[0]:
                shutil.rmtree(entry)
                removed.append(entry.name)
    return sorted(removed)


if __name__ == '__main__':
    site, requirements = sys.argv[1], sys.argv[2]
    for name in prune(site, Path(requirements).read_text()):
        print('fiche obsolète supprimée :', name)
