"""Fixed metadata groups: pure classification, no database, network or financial engine."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from engine.catalogue.rules import MARKET_NAMES

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / 'app/config/secondary_metadata_groups.json').read_text())


def test_fixed_domains_and_all_known_repository_mics():
    assert {k: len(v) for k, v in CONFIG['groups'].items()} == {'country': 5, 'market': 5, 'sector': 12, 'asset': 2}
    assert set(MARKET_NAMES) <= set(CONFIG['mic_groups'])
    assert len(CONFIG['country_aliases']) > 500
    for values in CONFIG['groups'].values():
        assert len({v['id'] for v in values}) == len(values)
    assert [v['id'] for v in CONFIG['groups']['asset']] == ['asset:equity', 'asset:etf']


CASES = [
    ('country', 'United States', None, 'country:us'),
    ('country', 'États-Unis', None, 'country:us'),
    ('country', 'US', None, 'country:us'),
    ('country', 'France', None, 'country:europe'),
    ('country', 'Czech Republic', None, 'country:europe'),
    ('country', 'PL', None, 'country:europe'),
    ('country', 'China', None, 'country:emerging'),
    ('country', 'South Korea', None, 'country:emerging'),
    ('country', 'Canada', None, 'country:other'),
    ('country', 'NA', None, 'country:other'),
    ('country', 'Pays non répertorié', None, 'country:other'),
    ('country', None, None, 'unknown'),
    ('country', ' Unknown ', None, 'unknown'),
    ('market', 'XNAS', None, 'market:us'),
    ('market', 'xpar', None, 'market:europe'),
    ('market', 'XHKG', None, 'market:other'),
    ('market', 'XSHG', None, 'market:emerging'),
    ('market', 'XTKS', None, 'market:other'),
    ('market', 'XXXX', None, 'unknown'),
    ('sector', 'Technology', 'equity', 'sector:technology'),
    ('sector', 'Financial Services', 'equity', 'sector:finance'),
    ('sector', 'Consumer Cyclical', 'equity', 'sector:consumption'),
    ('sector', 'Consumer Defensive', 'equity', 'sector:consumption'),
    ('sector', 'Equity', 'etf', 'sector:other'),
    ('sector', 'Sector Equity Technology', 'etf', 'sector:technology'),
    ('sector', 'Property', 'etf', 'sector:other'),
    ('sector', 'Information Technology', 'etf', 'sector:other'),
    ('sector', None, 'etf', 'unknown'),
    ('sector', 'Nouveau secteur', 'equity', 'sector:other'),
    ('asset', 'equity', None, 'asset:equity'),
    ('asset', 'etf', None, 'asset:etf'),
    ('asset', 'mutualfund', None, None),
]


@pytest.mark.skipif(not shutil.which('php'), reason='PHP required')
def test_php_actual_classification_and_js_local_migration_agree():
    # Exercise every shipped ISO alias plus all explicit edge cases in both implementations.
    alias_cases = [('country', key, None, group) for key, group in CONFIG['country_aliases'].items()]
    cases = [list(c[:3]) for c in CASES + alias_cases]
    result = subprocess.run(['php', 'tests/php/secondary-metadata.php'], cwd=ROOT,
                            input=json.dumps(cases), text=True, capture_output=True, check=True)
    output = json.loads(result.stdout)
    assert [r['id'] for r in output] == [c[3] for c in CASES + alias_cases]
    assert output[next(i for i, c in enumerate(CASES) if c[1] == 'Pays non répertorié')]['reason'] == 'unmapped-country'
    assert output[next(i for i, c in enumerate(CASES) if c[1] == 'XXXX')]['reason'] == 'unmapped-mic'
    js = subprocess.run(['node', 'tests/e2e/secondary-metadata.cjs'], cwd=ROOT,
                        input=json.dumps(cases), text=True, capture_output=True, check=True)
    assert json.loads(js.stdout) == [c[3] for c in CASES + alias_cases]
