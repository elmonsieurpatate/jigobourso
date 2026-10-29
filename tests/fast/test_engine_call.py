"""engine_call (PHP) sans base : délai maximal, stderr volumineux, emplacements. Un faux « python » remplace le moteur."""
import json
import os
import shutil
import subprocess
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytestmark = pytest.mark.skipif(not shutil.which('php'), reason='php absent')


def run(tmp_path, script, **env):
    fake = tmp_path / 'python'
    fake.write_text('#!/bin/sh\n' + textwrap.dedent(script))
    fake.chmod(0o755)
    code = ("require " + json.dumps(ROOT + '/app/lib/engine.php') + ";"
            "try { echo json_encode(['ok' => engine_call('presets', ['x' => 1])]); }"
            "catch (ApiError $e) { echo json_encode(['status' => $e->status, 'message' => $e->getMessage()]); }")
    out = subprocess.run(['php', '-r', code], capture_output=True, text=True, timeout=60,
                         env=dict(os.environ, JIGO_PYTHON=str(fake), JIGO_ENGINE_ROOT=ROOT, JIGO_DATA_DIR=str(tmp_path), **env))
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_normal_answer(tmp_path):
    assert run(tmp_path, "cat >/dev/null; echo '{\"a\": 1}'") == {'ok': {'a': 1}}


def test_huge_stderr_does_not_deadlock(tmp_path):
    # 300 Ko sur stderr : avec un tube lu après stdout, PHP et Python se bloquaient mutuellement.
    r = run(tmp_path, "head -c 300000 /dev/zero | tr '\\0' 'e' >&2; echo '{\"a\": 2}'")
    assert r == {'ok': {'a': 2}}


def test_hung_engine_is_stopped_after_the_timeout(tmp_path):
    r = run(tmp_path, "sleep 30", JIGO_ENGINE_TIMEOUT='1')
    assert r['status'] == 503 and 'trop de temps' in r['message']


def test_request_error_is_reported_as_422(tmp_path):
    r = run(tmp_path, "cat >/dev/null; echo '{\"error\": \"Stratégie invalide\"}'; exit 2")
    assert r == {'status': 422, 'message': 'Stratégie invalide'}
