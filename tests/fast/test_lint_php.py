"""scripts/lint_php.sh : une erreur de syntaxe fait échouer le contrôle (F05), un contrôle vide aussi."""

import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'scripts', 'lint_php.sh')
pytestmark = pytest.mark.skipif(not shutil.which('php'), reason='php absent')


def lint(*args, **env):
    return subprocess.run(['bash', SCRIPT, *args], capture_output=True, text=True, env=dict(os.environ, **env))


def test_valid_file_passes(tmp_path):
    f = tmp_path / 'ok.php'
    f.write_text('<?php echo 1;')
    assert lint(str(f)).returncode == 0


def test_parse_error_fails_even_after_a_valid_file(tmp_path):
    good, bad = tmp_path / 'ok.php', tmp_path / 'bad.php'
    good.write_text('<?php echo 1;')
    bad.write_text('<?php function broken( {')
    r = lint(str(bad), str(good))
    assert r.returncode == 1 and 'bad.php' in r.stderr and 'OK' not in r.stdout


def test_missing_php_is_an_error_not_a_success(tmp_path):
    assert lint(str(tmp_path / 'x.php'), PHP='/nonexistent/php').returncode == 2
