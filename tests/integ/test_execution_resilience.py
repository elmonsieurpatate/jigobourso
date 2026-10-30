"""Connexion fermée par MariaDB (wait_timeout) : le statut du traitement s'écrit quand même ; l'ETF est indépendant des indicateurs."""
import datetime as dt
import os
import time

import pytest

from engine.analytics import compute, etf
from engine.jobs.runner import run_job
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
    c.close()


def status_of(conn, job_id):
    with conn.cursor() as cur:
        cur.execute('SELECT status, summary FROM jobs WHERE id=%s', (job_id,))
        return cur.fetchone()


def short_timeout(conn, seconds=1):
    with conn.cursor() as cur:
        cur.execute(f'SET SESSION wait_timeout={seconds}')


def test_failed_job_is_recorded_as_failed_even_if_the_error_closed_the_connection(conn):
    def work(log):
        short_timeout(conn)
        time.sleep(2.5)                                         # le serveur ferme la connexion pendant que le calcul tourne
        raise RuntimeError('calcul interrompu')
    job = run_job(conn, 'essai-resilience', work)
    row = status_of(conn, job)
    assert row['status'] == 'failed' and 'calcul interrompu' in row['summary']          # avant : restait « running » puis « interrompu (processus arrêté) »


def test_successful_job_is_recorded_after_a_long_silent_computation(conn):
    def work(log):
        short_timeout(conn)
        log.step('calcul long', lambda: time.sleep(2.5), None)
        return 5, 0, 'terminé'
    job = run_job(conn, 'essai-resilience', work)
    assert status_of(conn, job)['status'] == 'completed'
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM job_steps WHERE job_id=%s', (job,))
        assert cur.fetchone()['n'] == 1


def seed_etfs(conn, count=4):
    with conn.cursor() as cur:
        for lid in range(1, count + 1):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name,category) VALUES (%s,%s,'etf',%s,'Energy')", (lid, 'etf:%d' % lid, 'ETF %d' % lid))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, '%d.DE' % lid))
        day, i = dt.date(2025, 10, 6), 0
        while day <= dt.date(2026, 10, 29):
            if day.weekday() < 5:
                for lid in range(1, count + 1):
                    cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', (lid, day, (100 + i) * lid))
                i += 1
            day += dt.timedelta(days=1)
    conn.commit()


def test_indicators_do_not_build_the_etf_analysis_and_vice_versa(conn):
    seed_etfs(conn)
    now = dt.datetime(2026, 10, 29, 20, tzinfo=dt.timezone.utc)
    compute.compute_all(conn, now)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM etf_analysis')
        assert cur.fetchone()['n'] == 0
        cur.execute('SELECT COUNT(*) n FROM series_state')
        assert cur.fetchone()['n'] == 4
    etf.build(conn, now)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM etf_analysis')
        assert cur.fetchone()['n'] == 4


def test_etf_publication_survives_a_connection_closed_during_the_computation(conn):
    seed_etfs(conn)
    short_timeout(conn)
    real_correlate = etf.correlate

    def slow(a, b):
        time.sleep(0.4)
        return real_correlate(a, b)
    etf.correlate = slow
    try:
        result = etf.build(conn, dt.datetime(2026, 10, 29, 20))          # plus d'une seconde sans requête avant l'écriture
    finally:
        etf.correlate = real_correlate
    assert result['etfs'] == 4
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM etf_analysis')
        assert cur.fetchone()['n'] == 4


def test_compute_jobs_share_one_lock_and_a_failed_one_can_be_relaunched(conn):
    from engine.jobs import tasks
    started = []
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at) VALUES ('etf','admin','running',UTC_TIMESTAMP())")
    conn.commit()
    assert run_job(conn, 'maintenance', lambda log: started.append(1) or (0, 0, 'x')) is None           # un calcul en cours bloque les autres calculs dérivés
    assert not started
    with pytest.raises(ValueError, match='déjà en cours'):
        tasks.precheck(conn, 'metrics')
    with conn.cursor() as cur:
        cur.execute("UPDATE jobs SET status='failed' WHERE job_type='etf'")
    conn.commit()
    tasks.precheck(conn, 'etf')                                                                           # un échec n'empêche pas la relance
    def boom(log):
        raise RuntimeError('cause visible')
    failed = run_job(conn, 'etf', boom, trigger='admin')
    assert status_of(conn, failed)['status'] == 'failed' and 'cause visible' in status_of(conn, failed)['summary']
    ok = run_job(conn, 'etf', lambda log: (1, 0, 'relancé'), trigger='admin')
    assert status_of(conn, ok)['status'] == 'completed'
