"""Vérifie que l'environnement Python respecte requirements.txt (versions comprises) et que le moteur s'importe.

Usage : .venv/bin/python scripts/check_env.py   (code 0 = conforme, 1 = écart listé, 2 = fichier illisible)
Sert à valider un venv neuf (README, « Démarrage depuis zéro ») et à contrôler la reproductibilité (tests/fast/test_environment.py).
"""

import importlib
import importlib.metadata as md
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORTS = {'PyMySQL': 'pymysql', 'numpy': 'numpy', 'pandas': 'pandas', 'exchange_calendars': 'exchange_calendars'}


def parse(text):
    """[(paquet, [(opérateur, version)])] depuis un requirements.txt (commentaires et lignes vides ignorés)."""
    out = []
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+)\s*(.*)$', line)
        specs = [(op, v) for op, v in re.findall(r'(==|>=|<=|<|>|!=)\s*([0-9][0-9A-Za-z.]*)', m.group(2))]
        out.append((m.group(1), specs))
    return out


def key(version):
    return tuple(int(x) for x in re.findall(r'\d+', version)[:4])


def satisfies(version, specs):
    cur = key(version)
    for op, v in specs:
        want = key(v)
        width = max(len(cur), len(want))
        a, b = cur + (0,) * (width - len(cur)), want + (0,) * (width - len(want))
        ok = {'==': a == b, '>=': a >= b, '<=': a <= b, '<': a < b, '>': a > b, '!=': a != b}[op]
        if not ok:
            return False
    return True


def problems(requirements_text):
    found = []
    for name, specs in parse(requirements_text):
        try:
            version = md.version(name)
        except md.PackageNotFoundError:
            found.append(f'{name} : non installé')
            continue
        if not satisfies(version, specs):
            found.append(f'{name} {version} : hors des bornes {", ".join(op + v for op, v in specs)}')
        module = IMPORTS.get(name, name.replace('-', '_'))
        try:
            importlib.import_module(module)
        except Exception as exc:  # un paquet présent mais inutilisable (binaire incompatible) est un écart
            found.append(f'{name} : import impossible ({exc})')
    return found


def main():
    try:
        text = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    except OSError as exc:
        print(f'requirements.txt illisible : {exc}', file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT))
    # engine.__init__ borne BLAS avant le premier import de numpy/pandas.
    # Sur l'hébergement mutualisé, inverser cet ordre peut interrompre Python
    # (130) sans aucun problème de version des paquets.
    found = []
    try:
        importlib.import_module('engine.cli')
    except Exception as exc:
        found.append(f'engine.cli : import impossible ({exc})')
    found.extend(problems(text))
    for line in found:
        print('ÉCART', line)
    if not found:
        print('Environnement conforme à requirements.txt ;', len(parse(text)), 'dépendances vérifiées ; moteur importable')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
