"""Répartit les fichiers de tests/integ en n blocs de durée comparable (un fichier appartient à un seul bloc).

Usage : python scripts/integ_shards.py i n   → les fichiers du bloc i (1..n), un par ligne.
Les poids sont des secondes mesurées (pytest --durations, novembre 2026) : ils n'influencent que l'équilibre, jamais la couverture. Un fichier absent de la table reçoit
DEFAULT_WEIGHT : un nouveau test est donc automatiquement dans un bloc, et tests/fast/test_integ_shards.py échoue si un fichier n'était dans aucun bloc ou dans deux.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHT = 3.0
WEIGHTS = {
    'test_portfolio_audit.py': 35,
    'test_momentum_integration.py': 34,
    'test_api.py': 18,
    'test_execution_resilience.py': 17,
    'test_financial_regressions.py': 15,
    'test_incident.py': 15,
    'test_hardening.py': 12,
    'test_catalogue_search.py': 10,
    'test_account.py': 8,
    'test_financial_parity.py': 7,
    'test_legacy_alerts_disabled.py': 5.5,
    'test_ranking_table.py': 5.5,
    'test_tracking_rules.py': 5,
    'test_secondary_filters.py': 4,
    'test_catchup.py': 4,
    'test_compute_incremental.py': 4,
}


def files(root=ROOT):
    return sorted(p.name for p in (root / 'tests/integ').glob('test_*.py'))


def shards(count, root=ROOT):
    """[[fichiers du bloc 1], …] : glouton, les plus lourds d'abord, chacun dans le bloc le moins chargé (ordre déterministe)."""
    loads = [0.0] * count
    out = [[] for _ in range(count)]
    for name in sorted(files(root), key=lambda n: (-WEIGHTS.get(n, DEFAULT_WEIGHT), n)):
        i = loads.index(min(loads))
        out[i].append(name)
        loads[i] += WEIGHTS.get(name, DEFAULT_WEIGHT)
    return [sorted(b) for b in out]


if __name__ == '__main__':
    shard, count = int(sys.argv[1]), int(sys.argv[2])
    for name in shards(count)[shard - 1]:
        print(f'tests/integ/{name}')
