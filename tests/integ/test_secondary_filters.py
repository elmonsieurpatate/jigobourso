"""Real PHP/MariaDB regression coverage for secondary settings, no market engine."""
import os
import json
from pathlib import Path
import subprocess

import pytest

from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if os.environ.get('JIGO_TEST_DATABASE') != '1':
    pytest.skip('disposable database required', allow_module_level=True)


def test_secondary_filters_persistence_and_preservation():
    assert os.environ['JIGO_DB_NAME'] in ('jigobourso_it', 'jigobourso_filters_it')
    conn = connect()
    try:
        reset_data(conn)
    finally:
        conn.close()
    root = Path(__file__).resolve().parents[2]
    script = root / 'tests/e2e/secondary-persistence.php'
    result = subprocess.run(['php', str(script), 'seed'], cwd=root, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    # Reproduce concurrent initial creation before either settings document exists.
    code = 'require ' + json.dumps(str(root / 'app/services/secondary_filters.php')) + '; $s=secondary_read(); echo count($s["definitions"]["filters"]);'
    workers = [subprocess.Popen(['php', '-r', code], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    for process in workers:
        out, err = process.communicate(timeout=30)
        assert process.returncode == 0 and out == '13', out + err
    result = subprocess.run(['php', str(script)], cwd=root, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout
