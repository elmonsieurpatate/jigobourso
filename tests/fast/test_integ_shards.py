"""Le découpage de la CI en blocs d'intégration ne doit jamais perdre ni dupliquer un fichier de test."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import integ_shards  # noqa: E402


@pytest.mark.parametrize('count', [1, 2, 3, 4])
def test_every_integration_file_is_in_exactly_one_shard(count):
    blocks = integ_shards.shards(count)
    flat = [name for block in blocks for name in block]
    assert sorted(flat) == integ_shards.files()  # union = suite complète
    assert len(flat) == len(set(flat))  # aucun fichier en double
    assert all(blocks)  # aucun bloc vide


def test_shards_are_balanced():
    weights = [sum(integ_shards.WEIGHTS.get(n, integ_shards.DEFAULT_WEIGHT) for n in block) for block in integ_shards.shards(2)]
    assert max(weights) <= 1.15 * min(weights)


def test_ci_matrix_matches_the_shard_count():
    workflow = (ROOT / '.github/workflows/tests.yml').read_text()
    assert 'shard: [1, 2]' in workflow and 'test_suite.sh integ ${{ matrix.shard }}/2' in workflow and 'Intégration ${{ matrix.shard }}/2' in workflow
