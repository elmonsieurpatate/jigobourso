import datetime
import os
import pytest
from engine.shared.db import connect
from engine.analytics import compute, strategy
from engine.analytics.repository import recommendable_candidates
from engine.jobs import tasks
from engine.jobs.runner import run_job
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


def test_manual_selection_then_maintenance_with_fake_yahoo():
    conn = connect()
    reset_data(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:UP.DE','equity','Monte SE','Germany'),(2,'sym:XETR:ILLIQ.DE','etf','Illiquide ETF',NULL)")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','UP.DE','EUR','candidate',1),(2,2,'XETR','ILLIQ.DE','EUR','candidate',1)")
        start = datetime.date(2026, 1, 5)
        days = [start + datetime.timedelta(days=i) for i in range(400) if (start + datetime.timedelta(days=i)).weekday() < 5][:260]
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(1, d, round(100 * 1.003 ** i, 6)) for i, d in enumerate(days)])
    conn.commit()
    q = lambda p, v: {'price': p, 'price_time': datetime.datetime(2026, 10, 27, 16, 30), 'avg_volume_3m': v, 'currency': 'EUR', 'market_cap': None, 'quote_type': 'EQUITY'}
    client = FakeYahoo(quotes={'UP.DE': q(230.0, 100000), 'ILLIQ.DE': q(40.0, 100)})
    run_job(conn, 'yahoo_info', lambda log: tasks.yahoo_info(conn, client, NOW, log))
    run_job(conn, 'yahoo_filter', lambda log: tasks.yahoo_filter(conn, log, NOW))
    job = run_job(conn, 'maintenance', lambda log: tasks.maintenance(conn, client, NOW, log))
    with conn.cursor() as cur:
        cur.execute('SELECT status, summary FROM jobs WHERE id=%s', (job,))
        row = cur.fetchone()
        assert row['status'] in ('completed', 'completed_with_errors'), row
        cur.execute('SELECT status FROM listings ORDER BY id')
        assert [r['status'] for r in cur.fetchall()] == ['selected', 'excluded']
        cur.execute('SELECT sessions, slope, r2 FROM strategy_metrics WHERE listing_id=1 ORDER BY sessions')
        metrics = {r['sessions']: r for r in cur.fetchall()}
        assert set(metrics) == {1, 5, 21, 63, 126, 252}
        assert abs(float(metrics[21]['slope']) - 0.3) < 0.01 and float(metrics[21]['r2']) > 0.999
        cur.execute('SELECT quality, closes_count FROM series_state WHERE listing_id=1')
        assert cur.fetchone()['closes_count'] == 260
    result = strategy.evaluate(strategy.preset('regular'), recommendable_candidates(conn))
    assert [v['key'] for v in result] == [1] and result[0]['status'] == 'retained'
    # un deuxième lancement simultané est refusé
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,status,started_at) VALUES ('maintenance','running',%s)", (datetime.datetime.utcnow(),))
    conn.commit()
    assert run_job(conn, 'maintenance', lambda log: (0, 0, 'x')) is None
