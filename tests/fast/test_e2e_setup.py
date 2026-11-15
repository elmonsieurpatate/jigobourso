"""Le runner prépare ses répertoires avant tout accès à la base de recette."""

import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_browser_runner_creates_a_configured_mail_directory_before_seeding(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copy(ROOT / 'scripts/e2e_browser.sh', scripts / 'e2e_browser.sh')
    binaries = tmp_path / '.venv/bin'
    binaries.mkdir(parents=True)
    python = binaries / 'python'
    # Arrêt au premier seed : ni PHP, ni navigateur, ni base ne sont utilisés.
    python.write_text('#!/bin/sh\nexit 23\n')
    python.chmod(0o755)
    mail = tmp_path / 'new mail directory'
    result = subprocess.run(
        ['bash', str(scripts / 'e2e_browser.sh')],
        env={**os.environ, 'JIGO_TEST_MAIL_DIR': str(mail), 'PLAYWRIGHT_MODULE': 'unused', 'JIGO_CHROMIUM': 'unused'},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 23, result.stderr
    assert mail.is_dir() and mail.stat().st_mode & 0o777 == 0o700
