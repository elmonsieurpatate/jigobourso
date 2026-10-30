"""Architecture d'exécution : connexion rétablie, réglage des threads, maintenance en étapes indépendantes, déploiement sans recalcul."""
import os
import pathlib
import subprocess
import sys

import pymysql
import pytest

from engine.jobs import tasks
from engine.market.yahoo import RateLimited
from engine.shared import db

ROOT = pathlib.Path(__file__).resolve().parents[2]


class Conn:
    """Connexion simulée : `alive` passe à False quand le serveur l'a fermée ; ping lève comme pymysql."""
    def __init__(self, alive=True):
        self.alive, self.reconnects, self.rollbacks = alive, 0, 0

    def ping(self, reconnect=True):
        if not self.alive:
            raise pymysql.err.InterfaceError(0, '')

    def connect(self):
        self.alive, self.reconnects = True, self.reconnects + 1

    def rollback(self):
        self.rollbacks += 1


def test_ensure_reconnects_only_a_closed_connection():
    live = Conn()
    db.ensure(live)
    assert live.reconnects == 0
    dead = Conn(alive=False)
    db.ensure(dead)
    assert dead.alive and dead.reconnects == 1


def test_blas_is_limited_to_one_thread_before_numpy_loads():
    out = subprocess.run([sys.executable, '-c', 'import os, engine; print(os.environ["OPENBLAS_NUM_THREADS"], "numpy" in __import__("sys").modules)'],
                         cwd=ROOT, env={k: v for k, v in os.environ.items() if not k.endswith('_NUM_THREADS')}, capture_output=True, text=True, check=True).stdout.split()
    assert out == ['1', 'False']
    assert subprocess.run([sys.executable, '-c', 'import os, engine; print(os.environ["OPENBLAS_NUM_THREADS"])'], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS='4'),
                          capture_output=True, text=True, check=True).stdout.strip() == '4'          # un réglage explicite reste prioritaire


def test_database_socket_replaces_host_for_isolated_tests(monkeypatch):
    seen = {}
    monkeypatch.setattr(db.pymysql, 'connect', lambda **kw: seen.update(kw) or object())
    monkeypatch.setenv('JIGO_DB_NAME', 'x'); monkeypatch.setenv('JIGO_DB_USER', 'u'); monkeypatch.setenv('JIGO_DB_PASSWORD', 'p')
    monkeypatch.delenv('JIGO_DB_HOST', raising=False)
    monkeypatch.setenv('JIGO_DB_SOCKET', '/tmp/x.sock')
    db.connect()
    assert seen['unix_socket'] == '/tmp/x.sock' and 'host' not in seen
    monkeypatch.delenv('JIGO_DB_SOCKET')
    with pytest.raises(RuntimeError):
        db.connect()


STEPS = ('backup', 'quotes', 'fx', 'fx_history', 'detect', 'verify', 'compute', 'warm', 'etf', 'snapshot', 'outcomes', 'prune', 'housekeeping')


@pytest.fixture
def plan(monkeypatch):
    calls, fail = [], {}
    pending = {}

    def step(name, result=None):
        def run(*a, **k):
            calls.append(name)
            if name in fail:
                raise fail[name]
            return result
        return run
    monkeypatch.setattr(tasks, 'backup_user_data', step('backup', '/x/userdata.sql.gz'))
    monkeypatch.setattr(tasks.collect, 'collection_set', lambda *a, **k: [{'id': 1}])
    monkeypatch.setattr(tasks.collect, 'refresh_quotes', step('quotes', (1, 0)))
    monkeypatch.setattr(tasks.collect, 'refresh_fx', step('fx'))
    monkeypatch.setattr(tasks.collect, 'backfill_fx', step('fx_history', 0))
    monkeypatch.setattr(tasks.splits, 'detect', step('detect', 0))
    monkeypatch.setattr(tasks.splits, 'verify', step('verify', {'confirmed': 0, 'real_move': 0, 'unanswered': 0}))
    monkeypatch.setattr(tasks.compute, 'compute_all', step('compute', (9612, 57672)))
    monkeypatch.setattr(tasks.etf, 'warm_profiles', step('warm', {'wanted': 1, 'to_refresh': 0, 'fetched': 0, 'unavailable': 0, 'limit': 40}))
    monkeypatch.setattr(tasks.etf, 'build', step('etf', {'etfs': 4677, 'with_minimum_history': 4000}))
    monkeypatch.setattr(tasks.tracking, 'record_snapshot', step('snapshot', ('2026-10-30', 9000)))
    monkeypatch.setattr(tasks.tracking, 'update_outcomes', step('outcomes', 12))
    monkeypatch.setattr(tasks.collect, 'prune_daily', step('prune'))
    monkeypatch.setattr(tasks.collect, 'prune_intraday', lambda *a, **k: None)
    monkeypatch.setattr(tasks, 'housekeeping', step('housekeeping', {}))
    monkeypatch.setattr(tasks.settings, 'put', lambda conn, name, value: pending.__setitem__(name, value))
    logs = []
    return calls, fail, pending, logs, lambda lvl, msg: logs.append((lvl, msg))


def test_maintenance_runs_everything_and_the_backup_comes_first(plan):
    calls, fail, pending, logs, log = plan
    ok, errors, summary = tasks.maintenance(Conn(), object(), None, log)
    assert calls[0] == 'backup' and calls == ['backup', 'quotes', 'fx', 'fx_history', 'detect', 'verify', 'compute', 'warm', 'etf', 'snapshot', 'outcomes', 'prune', 'housekeeping']
    assert errors == 0 and pending['maintenance_pending'] is False and 'séries 9612' in summary and 'en échec' not in summary


def test_an_etf_failure_blocks_nothing_else_and_rearms_the_maintenance(plan):
    calls, fail, pending, logs, log = plan
    conn = Conn(alive=False)                                   # l'erreur 2006 : la connexion est fermée au moment de l'échec
    fail['etf'] = pymysql.err.OperationalError(2006, 'MySQL server has gone away')
    ok, errors, summary = tasks.maintenance(conn, object(), None, log)
    assert calls[-4:] == ['snapshot', 'outcomes', 'prune', 'housekeeping'] and 'backup' in calls
    assert errors == 1 and 'Similarité des ETF' in summary and pending['maintenance_pending'] is True      # nouvelle tentative prévue
    assert conn.alive and conn.reconnects == 1 and conn.rollbacks >= 1                                        # connexion rétablie avant de continuer
    assert any(lvl == 'error' and 'Similarité des ETF' in msg for lvl, msg in logs)


def test_a_backup_failure_does_not_stop_the_market_work(plan):
    calls, fail, pending, logs, log = plan
    fail['backup'] = RuntimeError('mariadb-dump introuvable')
    ok, errors, summary = tasks.maintenance(Conn(), object(), None, log)
    assert errors == 1 and 'compute' in calls and 'housekeeping' in calls and 'Sauvegarde des données utilisateur' in summary


def test_failed_indicators_skip_the_ranking_snapshot_but_not_the_rest(plan):
    calls, fail, pending, logs, log = plan
    fail['compute'] = RuntimeError('boom')
    ok, errors, summary = tasks.maintenance(Conn(), object(), None, log)
    assert 'snapshot' not in calls and {'etf', 'outcomes', 'prune', 'housekeeping'} <= set(calls)             # jamais de photographie d'un classement périmé
    assert any('ignoré' in msg for _, msg in logs) and errors == 1


def test_yahoo_rate_limit_is_a_warning_on_that_step_only(plan):
    calls, fail, pending, logs, log = plan
    fail['quotes'] = RateLimited(60)
    ok, errors, summary = tasks.maintenance(Conn(), object(), None, log)
    assert 'compute' in calls and 'housekeeping' in calls and errors == 1
    assert [lvl for lvl, msg in logs if 'Cours de référence' in msg] == ['warning']


def test_a_deployment_requests_the_recalculation_without_delay(monkeypatch):
    monkeypatch.setattr(tasks.settings, 'get', lambda conn, name, default=None: 'deploy')
    monkeypatch.setattr(tasks, '_ran_within', lambda *a: True)                                               # la maintenance vient de tourner
    assert tasks._maintenance_due(None, None) is True
    monkeypatch.setattr(tasks.settings, 'get', lambda conn, name, default=None: True)
    assert tasks._maintenance_due(None, None) is False                                                       # un échec attend 30 minutes


def test_deploy_script_no_longer_recalculates_or_waits():
    text = (ROOT / 'ops/deploy.sh').read_text()
    for forbidden in ('engine.cli metrics', 'deploy-metrics', 'setsid', 'seq 1 120', 'metrics_pid'):
        assert forbidden not in text
    assert "'maintenance_pending', 'deploy'" in text and text.count('ControlMaster=auto') == 1
    assert subprocess.run(['bash', '-n', str(ROOT / 'ops/deploy.sh')]).returncode == 0


def test_explicit_actions_start_now_and_deploy_starts_the_recalculation_detached():
    admin = (ROOT / 'app/routes/admin.php').read_text()
    for job in ("'maintenance'", "'metrics'", "'etf'"):
        assert job in admin
    assert admin.count("engine_spawn('job'") == 1                                  # un seul lanceur, détaché : aucune requête HTTP n'attend le calcul
    assert tasks.COMPUTE == ('maintenance', 'metrics', 'etf')
    assert set(tasks.COMPUTE) <= set(tasks.MANUAL_LABELS)
    deploy = (ROOT / 'ops/deploy.sh').read_text()
    assert '--name maintenance --trigger system' in deploy and deploy.index('.deployed') < deploy.index('--name maintenance')
