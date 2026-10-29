"""Splits : un saut ressemblant à un split est vérifié auprès du fournisseur ; l'historique ajusté remplace le nôtre, un vrai mouvement n'est jamais « corrigé »."""
import datetime
import os

import pytest

from engine.jobs import tasks
from engine.market import collect, splits
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)
SESSIONS = [datetime.date(2026, 9, 28) + datetime.timedelta(days=i) for i in range(29) if (datetime.date(2026, 9, 28) + datetime.timedelta(days=i)).weekday() < 5]
JUMP = datetime.date(2026, 10, 13)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (1,'isin:DE0001','DE0001','equity','Split SE','Germany'),(2,'isin:DE0002','DE0002','equity','Chute SE','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','SPL.DE','EUR','selected',1),(2,2,'XETR','MOVE.DE','EUR','selected',1)")
        for lid in (1, 2):
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, d, 100.0 if d < JUMP else 50.0) for d in SESSIONS])
            cur.execute("INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,quality,break_dates) VALUES (%s,%s,%s,%s,'break',%s)",
                        (lid, NOW.replace(tzinfo=None), SESSIONS[-1], len(SESSIONS), JUMP.isoformat()))
    c.commit()
    yield c
    c.close()


def yahoo(split_adjusted):
    """Yahoo ajuste l'historique du titre 1 (split) ; pour le titre 2 la chute est réelle et reste dans les données."""
    old = 50.0 if split_adjusted else 100.0
    days = SESSIONS + [datetime.date(2026, 10, 27)]
    return FakeYahoo(daily={'SPL.DE': ('Europe/Berlin', [(d, old if d < JUMP else 50.0) for d in days]),
                            'MOVE.DE': ('Europe/Berlin', [(d, 100.0 if d < JUMP else 50.0) for d in days])})


def test_a_split_like_jump_is_logged_and_scheduled_once(conn):
    assert splits.detect(conn, NOW) == 2
    assert splits.detect(conn, NOW) == 0                      # déjà noté : pas de nouvelle redemande
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status, ratio FROM split_log ORDER BY listing_id')
        rows = cur.fetchall()
        cur.execute('SELECT id, next_daily_check FROM listings ORDER BY id')
        due = cur.fetchall()
    assert [(r['listing_id'], r['status'], float(r['ratio'])) for r in rows] == [(1, 'detected', 2.0), (2, 'detected', 2.0)]
    assert all(r['next_daily_check'] == NOW.date() for r in due)


def test_the_provider_decides_split_or_real_move(conn):
    splits.detect(conn, NOW)
    rows = collect.collection_set(conn)
    out = tasks.fetch_daily(conn, yahoo(split_adjusted=True), rows, NOW)
    assert out['splits_confirmed'] == 1 and out['splits_real_move'] == 1
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status FROM split_log ORDER BY listing_id')
        assert [(r['listing_id'], r['status']) for r in cur.fetchall()] == [(1, 'confirmed'), (2, 'real_move')]
        cur.execute("SELECT close_px FROM daily_prices WHERE listing_id=1 AND price_date='2026-10-09'")
        assert float(cur.fetchone()['close_px']) == 50.0       # historique du titre 1 réécrit à l'échelle actuelle
        cur.execute("SELECT close_px FROM daily_prices WHERE listing_id=2 AND price_date='2026-10-09'")
        assert float(cur.fetchone()['close_px']) == 100.0      # la chute réelle du titre 2 n'est pas touchée
        cur.execute('SELECT COUNT(*) n FROM listings WHERE next_daily_check IS NOT NULL')
        assert cur.fetchone()['n'] == 0


def test_no_conclusion_when_the_provider_does_not_answer(conn):
    splits.detect(conn, NOW)
    out = tasks.fetch_daily(conn, FakeYahoo(), collect.collection_set(conn), NOW)
    assert out['splits_confirmed'] == 0 and out['splits_real_move'] == 0
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM split_log WHERE status='detected'")
        assert cur.fetchone()['n'] == 2
        cur.execute('SELECT DISTINCT next_daily_check d FROM listings')
        assert cur.fetchone()['d'] == NOW.date() + datetime.timedelta(days=1)    # nouvel essai demain
