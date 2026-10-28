import datetime as dt
import os
import pytest
from engine.shared.db import connect
from engine.market import intraday
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC)


class FakeChart:
    def __init__(self, bars):
        self.bars, self.calls = bars, 0

    def chart(self, symbol, range_='5d', interval='15m'):
        self.calls += 1
        return {'currency': 'EUR', 'timezone': 'Europe/Paris', 'bars': self.bars, 'periods': []}


def ts(slot):
    return int(slot.replace(tzinfo=UTC).timestamp())


def make_bars(days):
    out = []
    for d in days:
        for i, s in enumerate(intraday.expected_slot_starts('XPAR', d)):
            out.append((ts(s), 10 + i * .01, 10.2 + i * .01, 9.9 + i * .01, 10.1 + i * .01, 1000 + i))
    return out


def seed(conn):
    reset_data(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XPAR:AA.PA','equity','Alpha','France')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XPAR','AA.PA','EUR','selected',1)")
    conn.commit()


def test_view_fetches_two_sessions_without_duplicates_and_respects_cooldown():
    conn = connect()
    seed(conn)
    client = FakeChart(make_bars([dt.date(2026, 10, 26), dt.date(2026, 10, 27)]))
    v = intraday.view(conn, 1, now=NOW, client=client)
    assert [s['date'] for s in v['sessions']] == ['2026-10-26', '2026-10-27'] and all(s['complete'] for s in v['sessions'])
    assert v['sessions'][0]['summary']['volume_complete'] and v['source'].startswith('Yahoo')
    # deuxième consultation : aucun nouvel appel (délai de grâce) et aucun doublon en base
    again = intraday.view(conn, 1, now=NOW, client=client)
    assert client.calls == 1 and again['sessions'] == v['sessions']
    intraday.store_chart(conn, 1, client.bars, NOW)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n, COUNT(DISTINCT slot_start) d FROM intraday_prices WHERE listing_id=1')
        r = cur.fetchone()
    assert r['n'] == r['d'] == 68


def test_provisional_bar_never_overwrites_a_final_one_but_gets_completed():
    conn = connect()
    seed(conn)
    slot = intraday.expected_slot_starts('XPAR', dt.date(2026, 10, 27))[0]
    with conn.cursor() as cur:
        cur.execute('INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (1,%s,50,1)', (slot,))
    conn.commit()
    early = dt.datetime.combine(dt.date(2026, 10, 27), dt.time(7, 5), UTC)         # créneau pas terminé : barre provisoire
    intraday.store_chart(conn, 1, [(ts(slot), 1, 2, 0.5, 99, 7)], early)
    with conn.cursor() as cur:
        cur.execute('SELECT close_px, is_final, volume FROM intraday_prices WHERE listing_id=1')
        r = cur.fetchone()
    assert float(r['close_px']) == 50 and r['is_final'] == 1 and r['volume'] == 7


def test_yahoo_failure_falls_back_to_stored_data_with_a_note():
    conn = connect()
    seed(conn)

    class Broken:
        def chart(self, *a, **k):
            raise RuntimeError('HTTP 429')
    v = intraday.view(conn, 1, now=NOW, client=Broken())
    assert v['supported'] and v['sessions'] == [] and any('indisponible' in n for n in v['notes'])
