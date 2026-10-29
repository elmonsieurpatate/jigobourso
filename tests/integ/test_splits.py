"""Splits : un saut ressemblant à un split n'est corrigé que si Yahoo déclare ce split ; une vraie chute n'est jamais « corrigée »."""
import datetime
import os

import pytest

from engine.analytics import compute
from engine.market import splits
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)
START = datetime.date(2026, 8, 3)
SESSIONS = [START + datetime.timedelta(days=i) for i in range(100) if (START + datetime.timedelta(days=i)).weekday() < 5 and START + datetime.timedelta(days=i) <= datetime.date(2026, 10, 27)]
JUMP = datetime.date(2026, 10, 13)


def price(d):
    return 100.0 if d < JUMP else 10.0           # cours divisé par 10 : split 10 pour 1 (ou chute de 90 %)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (1,'isin:DE0001','DE0001','equity','Split SE','Germany'),(2,'isin:DE0002','DE0002','equity','Chute SE','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','SPL.DE','EUR','selected',1),(2,2,'XETR','MOVE.DE','EUR','selected',1)")
        for lid in (1, 2):
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, d, price(d)) for d in SESSIONS])
    c.commit()
    compute.compute_all(c, NOW)                   # remplit series_state (break_dates) comme la maintenance
    yield c
    c.close()


def quality(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT quality FROM series_state WHERE listing_id=%s', (lid,))
        return cur.fetchone()['quality']


def test_both_series_start_as_breaks_and_both_jumps_look_like_splits(conn):
    assert quality(conn, 1) == 'break' and quality(conn, 2) == 'break'
    assert splits.detect(conn, NOW) == 2
    assert splits.detect(conn, NOW) == 0                      # déjà noté
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status, ratio FROM split_log ORDER BY listing_id')
        assert [(r['listing_id'], r['status'], float(r['ratio'])) for r in cur.fetchall()] == [(1, 'detected', 10.0), (2, 'detected', 10.0)]


def test_only_the_split_declared_by_yahoo_is_corrected(conn):
    splits.detect(conn, NOW)
    client = FakeYahoo(declared_splits={'SPL.DE': [('2026-10-13', 10.0, 1.0)]})              # Yahoo ne déclare rien pour MOVE.DE
    out = splits.verify(conn, client, NOW)
    assert out == {'confirmed': 1, 'real_move': 1, 'unanswered': 0}
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status FROM split_log ORDER BY listing_id')
        assert [(r['listing_id'], r['status']) for r in cur.fetchall()] == [(1, 'confirmed'), (2, 'real_move')]
        cur.execute('SELECT listing_id, kind, ratio FROM corporate_events')
        assert [(r['listing_id'], r['kind'], float(r['ratio'])) for r in cur.fetchall()] == [(1, 'split', 10.0)]
    compute.compute_all(conn, NOW)
    assert quality(conn, 1) == 'ok'                           # le split est corrigé, sans rupture inexpliquée
    with conn.cursor() as cur:
        cur.execute('SELECT coverage_252, expected_252 FROM series_state WHERE listing_id=1')
        coverage = cur.fetchone()
        assert coverage['coverage_252'] < 1 and coverage['expected_252'] > 100  # couverture annuelle incomplète, affichée à la lecture
    assert quality(conn, 2) == 'break'                        # la chute du titre 2 reste une rupture, non corrigée


def test_declared_split_that_does_not_explain_the_jump_is_ignored(conn):
    splits.detect(conn, NOW)
    client = FakeYahoo(declared_splits={'MOVE.DE': [('2026-10-13', 3.0, 1.0)], 'SPL.DE': [('2026-06-01', 10.0, 1.0)]})     # ratio ou date sans rapport avec le saut
    assert splits.verify(conn, client, NOW) == {'confirmed': 0, 'real_move': 2, 'unanswered': 0}
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM corporate_events')
        assert cur.fetchone()['n'] == 0


def test_no_conclusion_when_yahoo_does_not_answer(conn):
    splits.detect(conn, NOW)

    class Broken(FakeYahoo):
        def splits(self, symbol, range_='2y'):
            raise RuntimeError('réseau')
    assert splits.verify(conn, Broken(), NOW) == {'confirmed': 0, 'real_move': 0, 'unanswered': 2}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM split_log WHERE status='detected'")
        assert cur.fetchone()['n'] == 2                       # rien n'est conclu : nouvel essai au prochain passage
