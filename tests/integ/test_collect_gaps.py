"""Clôtures manquantes : le point d'accès groupé de Yahoo omet certains jours ; « chart » les fournit. Seuls les jours absents sont ajoutés, jamais modifiés."""
import datetime
import os

import pytest

from engine.market import collect
from engine.market.yahoo import RateLimited
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
DAYS = [datetime.date(2026, 10, d) for d in (5, 6, 7, 8, 9)]                 # lundi à vendredi


def ts(day):
    return int(datetime.datetime(day.year, day.month, day.day, 14, 30, tzinfo=UTC).timestamp())


class ChartClient:
    """Yahoo simulé : « chart » renvoie les cinq jours, dont celui que la base n'a pas ; peut simuler une limitation (429)."""
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def chart(self, symbol, range_='5d', interval='15m'):
        self.calls.append((symbol, range_, interval))
        if symbol == self.fail_on:
            raise RateLimited(60)
        return {'timezone': 'America/New_York', 'bars': [(ts(d), 1, 1, 1, 10 + i, 1000) for i, d in enumerate(DAYS)]}


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        for i, sym in ((1, 'AAA'), (2, 'BBB')):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name) VALUES (%s,%s,'equity',%s)", (i, 'k%d' % i, sym))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XNAS',%s,'USD','selected',1)", (i, i, sym))
            for d in DAYS:
                if d != DAYS[1]:                                                    # le mardi 6 manque
                    cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', (i, d, 99))
            cur.execute("INSERT INTO series_state(listing_id,computed_at,closes_count,coverage_252,observed_252,expected_252) VALUES (%s,NOW(),4,0.8,4,5)", (i,))
    c.commit()
    yield c
    c.close()


def closes(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT price_date, close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        return {r['price_date']: float(r['close_px']) for r in cur.fetchall()}


def test_only_the_missing_day_is_added_and_existing_closes_are_never_changed(conn):
    titles, added = collect.fill_daily_gaps(conn, ChartClient(), [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}], NOW)
    got = closes(conn, 1)
    assert (titles, added) == (1, 1) and got[DAYS[1]] == 11.0                         # jour ajouté avec le cours de « chart »
    assert all(got[d] == 99.0 for d in DAYS if d != DAYS[1])                           # les autres clôtures gardent leur valeur
    assert collect.fill_daily_gaps(conn, ChartClient(), [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}], NOW) == (1, 0)    # deuxième passage : rien d'ajouté


def test_unsettled_session_is_never_added(conn):
    early = datetime.datetime(2026, 10, 6, 15, 0, tzinfo=UTC)                          # le mardi 6 n'est pas terminé
    assert collect.fill_daily_gaps(conn, ChartClient(), [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}], early)[1] == 0


def test_batch_marks_titles_and_does_not_ask_again_before_the_delay(conn):
    rows = [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}, {'listing_id': 2, 'symbol': 'BBB', 'mic': 'XNAS'}]
    client = ChartClient()
    first = collect.fill_gaps_batch(conn, client, rows, NOW)
    assert first['examined'] == 2 and first['added'] == 2 and first['remaining'] == 0 and len(client.calls) == 2
    again = ChartClient()
    assert collect.fill_gaps_batch(conn, again, rows, NOW)['examined'] == 0 and not again.calls          # déjà examinés : pas de nouvel appel Yahoo


def test_rate_limit_stops_the_batch_and_leaves_the_current_title_for_later(conn):
    rows = [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}, {'listing_id': 2, 'symbol': 'BBB', 'mic': 'XNAS'}]
    r = collect.fill_gaps_batch(conn, ChartClient(fail_on='BBB'), rows, NOW)
    assert r['rate_limited'] and r['examined'] == 1 and r['remaining'] == 1
    retry = ChartClient()
    assert collect.fill_gaps_batch(conn, retry, rows, NOW)['examined'] == 1 and [c[0] for c in retry.calls] == ['BBB']      # BBB est repris, pas AAA


def test_manual_force_ignores_the_retry_delay_but_automatic_runs_do_not(conn):
    rows = [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}]
    collect.fill_gaps_batch(conn, ChartClient(), rows, NOW)
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE listing_id=1 AND price_date=%s', (DAYS[1],))
    conn.commit()
    later = NOW + datetime.timedelta(days=2)
    assert collect.fill_gaps_batch(conn, ChartClient(), rows, later)['examined'] == 0                     # automatique : délai de 30 jours
    assert collect.fill_gaps_batch(conn, ChartClient(), rows, NOW, force=True)['examined'] == 0           # manuel, même jour : reprend là où il s'est arrêté
    assert collect.fill_gaps_batch(conn, ChartClient(), rows, later, force=True)['examined'] == 1         # manuel, un autre jour : repasse


def test_progress_reports_done_over_total_after_each_title(conn):
    rows = [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}, {'listing_id': 2, 'symbol': 'BBB', 'mic': 'XNAS'}]
    seen = []
    collect.fill_gaps_batch(conn, ChartClient(), rows, NOW, progress=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 2), (2, 2)]


def test_parallel_fetch_gives_the_same_result_and_a_rate_limit_leaves_that_title_for_later(conn):
    rows = [{'listing_id': 1, 'symbol': 'AAA', 'mic': 'XNAS'}, {'listing_id': 2, 'symbol': 'BBB', 'mic': 'XNAS'}]
    r = collect.fill_gaps_batch(conn, ChartClient(), rows, NOW, workers=3, client_factory=ChartClient)
    assert r['examined'] == 2 and r['added'] == 2 and closes(conn, 1)[DAYS[1]] == 11.0 and closes(conn, 2)[DAYS[1]] == 11.0
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE price_date=%s', (DAYS[1],))
        cur.execute("DELETE FROM settings WHERE name='gap_fill_tried'")
    conn.commit()
    limited = collect.fill_gaps_batch(conn, ChartClient(), rows, NOW, workers=3, client_factory=lambda: ChartClient(fail_on='BBB'))
    assert limited['rate_limited'] and limited['examined'] == 1 and closes(conn, 1).get(DAYS[1]) == 11.0 and DAYS[1] not in closes(conn, 2)
