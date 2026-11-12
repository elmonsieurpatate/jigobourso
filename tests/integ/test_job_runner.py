"""Journal des traitements (engine/jobs/runner.py) : traitement périmé, verrou concurrent, démarrage en double, reprise d'une demande, échec."""
import datetime
import os
import pytest
from engine.jobs import runner
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    yield c
    reset_data(c)
    c.close()


def add_job(conn, job_type, status, minutes_ago):
    with conn.cursor() as cur:
        cur.execute('INSERT INTO jobs(job_type,trigger_by,status,started_at) VALUES (%s,%s,%s,%s)',
                    (job_type, 'cron', status, runner._now() - datetime.timedelta(minutes=minutes_ago)))
        jid = cur.lastrowid
    conn.commit()
    return jid


def status_of(conn, jid):
    with conn.cursor() as cur:
        cur.execute('SELECT status, finished_at, summary FROM jobs WHERE id=%s', (jid,))
        return cur.fetchone()


def never_called(log):
    raise AssertionError('le traitement ne devait pas démarrer')


def test_stale_thresholds_by_type():
    assert runner.stale_minutes('catchup') == 8 and runner.stale_minutes('metrics') == 45
    assert runner.stale_minutes('intraday:XPAR') == 20 and runner.stale_minutes('daily:XPAR') == 45
    assert runner.stale_minutes('import') == runner.STALE_DEFAULT


def test_stale_running_job_is_interrupted_and_recent_one_is_kept(conn):
    old = add_job(conn, 'catchup', 'running', runner.stale_minutes('catchup') + 2)
    recent = add_job(conn, 'catchup', 'running', 1)
    runner.recover_interrupted(conn)
    s = status_of(conn, old)
    assert s['status'] == 'interrupted' and s['finished_at'] is not None and s['summary'].startswith('interrompu')
    assert status_of(conn, recent)['status'] == 'running'


def test_stale_job_frees_the_slot_for_a_new_run(conn):
    old = add_job(conn, 'catchup', 'running', 30)
    jid = runner.run_job(conn, 'catchup', lambda log: (1, 0, 'ok'))
    assert jid and jid != old
    assert status_of(conn, old)['status'] == 'interrupted' and status_of(conn, jid)['status'] == 'completed'


def test_running_job_of_same_type_blocks_a_duplicate_start(conn):
    add_job(conn, 'catchup', 'running', 1)
    assert runner.run_job(conn, 'catchup', never_called) is None
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM jobs WHERE job_type='catchup'")
        assert cur.fetchone()['n'] == 1


def test_compute_group_never_runs_two_at_once(conn):
    add_job(conn, 'metrics', 'running', 1)
    for other in ('maintenance', 'etf', 'metrics'):
        assert runner.run_job(conn, other, never_called) is None
    jid = runner.run_job(conn, 'catchup', lambda log: (0, 0, 'ok'))      # hors groupe : indépendant
    assert jid and status_of(conn, jid)['status'] == 'completed'


def test_named_lock_held_by_another_connection_blocks_start(conn):
    other = connect()
    try:
        with other.cursor() as cur:
            cur.execute("SELECT GET_LOCK('jigo:job:catchup', 0) got")
            assert cur.fetchone()['got'] == 1
        assert runner.run_job(conn, 'catchup', never_called) is None
        with other.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK('jigo:job:catchup')")
        jid = runner.run_job(conn, 'catchup', lambda log: (1, 0, 'ok'))
        assert jid and status_of(conn, jid)['status'] == 'completed'
    finally:
        other.close()


def test_compute_lock_is_shared_by_the_group(conn):
    other = connect()
    try:
        with other.cursor() as cur:
            cur.execute("SELECT GET_LOCK('jigo:job:compute', 0) got")
        assert runner.run_job(conn, 'etf', never_called) is None
    finally:
        other.close()


def test_lock_is_released_after_start_so_next_run_is_possible(conn):
    first = runner.run_job(conn, 'catchup', lambda log: (1, 0, 'ok'))
    second = runner.run_job(conn, 'catchup', lambda log: (1, 0, 'ok'))
    assert first and second and first != second


def test_queued_request_is_resumed_not_duplicated(conn):
    queued = add_job(conn, 'metrics', 'queued', 0)
    assert runner.run_job(conn, 'metrics', lambda log: (3, 0, 'fini'), trigger='admin') == queued
    s = status_of(conn, queued)
    assert s['status'] == 'completed' and s['summary'] == 'fini'
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM jobs WHERE job_type='metrics'")
        assert cur.fetchone()['n'] == 1


def test_errors_and_failure_are_recorded(conn):
    jid = runner.run_job(conn, 'catchup', lambda log: (1, 2, 'partiel'))
    assert status_of(conn, jid)['status'] == 'completed_with_errors'

    def boom(log):
        raise ValueError('cassé')
    jid = runner.run_job(conn, 'catchup', boom)
    s = status_of(conn, jid)
    assert s['status'] == 'failed' and 'ValueError: cassé' in s['summary']
    with conn.cursor() as cur:
        cur.execute("SELECT level, message FROM job_logs WHERE job_id=%s", (jid,))
        rows = cur.fetchall()
    assert rows and rows[0]['level'] == 'error' and len(rows[0]['message']) <= 400
