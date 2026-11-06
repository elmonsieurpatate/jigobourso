"""Volumes quotidiens : un appel Chart par titre ; seul `daily_prices.volume` est écrit (jamais une clôture), uniquement pour des séances réglées déjà en base."""
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
ROWS = [{'listing_id': i, 'symbol': s, 'mic': 'XNAS'} for i, s in ((1, 'AAA'), (2, 'BBB'), (3, 'CCC'))]


def ts(day):
    return int(datetime.datetime(day.year, day.month, day.day, 14, 30, tzinfo=UTC).timestamp())


class ChartClient:
    """Yahoo simulé. `volumes` : volume par séance (None = absent) ; `rate_limit` / `broken` : symboles en 429 / en erreur."""
    def __init__(self, volumes=(1000, 0, 3000, 4000, 5000), rate_limit=None, broken=(), empty=()):
        self.calls, self.volumes, self.rate_limit, self.broken, self.empty = [], volumes, rate_limit, set(broken), set(empty)

    def chart(self, symbol, range_='5d', interval='15m'):
        self.calls.append((symbol, range_, interval))
        if symbol == self.rate_limit:
            raise RateLimited(60)
        if symbol in self.broken:
            self.broken.discard(symbol)                                         # échec isolé : réussit à la reprise
            raise RuntimeError('boom')
        if symbol in self.empty:
            return {'timezone': 'America/New_York', 'bars': []}
        return {'timezone': 'America/New_York', 'bars': [(ts(d), 1, 1, 1, 777 + i, v) for i, (d, v) in enumerate(zip(DAYS, self.volumes))]}


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        for i, sym in ((1, 'AAA'), (2, 'BBB'), (3, 'CCC')):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name) VALUES (%s,%s,'equity',%s)", (i, 'k%d' % i, sym))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XNAS',%s,'USD','selected',1)", (i, i, sym))
            for d in DAYS:
                cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', (i, d, 99))
    c.commit()
    yield c
    c.close()


def state(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT price_date, close_px, volume FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        return {r['price_date']: (float(r['close_px']), None if r['volume'] is None else int(r['volume'])) for r in cur.fetchall()}


def checked(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT volume_checked_at FROM liquidity_state WHERE listing_id=%s', (lid,))
        r = cur.fetchone()
        return r and r['volume_checked_at']


def test_volumes_match_dates_zero_is_kept_and_closes_never_change(conn):
    r = collect.fill_volumes_batch(conn, ChartClient(), ROWS[:1], NOW)
    got = state(conn, 1)
    assert [got[d][1] for d in DAYS] == [1000, 0, 3000, 4000, 5000]            # même jour Yahoo / base ; le volume 0 est une donnée valide
    assert all(got[d][0] == 99.0 for d in DAYS)                                 # les clôtures de Chart (777…) ne sont jamais écrites
    assert r['examined'] == 1 and r['written'] == 5 and checked(conn, 1) is not None


def test_unsettled_session_never_gets_a_volume(conn):
    early = datetime.datetime(2026, 10, 6, 15, 0, tzinfo=UTC)                  # mardi 6 à 11 h à New York : séance en cours
    collect.fill_volumes_batch(conn, ChartClient(), ROWS[:1], early)
    got = state(conn, 1)
    assert got[DAYS[1]][1] is None and got[DAYS[2]][1] is None                  # séance en cours et futures : rien
    assert got[DAYS[0]][1] == 1000


def test_last_two_sessions_are_consolidated_older_volumes_are_kept(conn):
    with conn.cursor() as cur:
        for d, v in ((DAYS[0], 1), (DAYS[3], 5), (DAYS[4], 7)):
            cur.execute('UPDATE daily_prices SET volume=%s WHERE listing_id=1 AND price_date=%s', (v, d))
    conn.commit()
    collect.fill_volumes_batch(conn, ChartClient(), ROWS[:1], NOW)
    got = state(conn, 1)
    assert got[DAYS[0]][1] == 1                                                 # ancienne séance déjà renseignée : conservée telle quelle
    assert got[DAYS[3]][1] == 4000 and got[DAYS[4]][1] == 5000                  # deux dernières séances : volume consolidé relu
    assert got[DAYS[1]][1] == 0 and got[DAYS[2]][1] == 3000                     # vides : remplies


def test_title_without_trades_stays_null_and_is_not_reasked_at_once(conn):
    r = collect.fill_volumes_batch(conn, ChartClient(volumes=(None,) * 5), ROWS[:1], NOW)
    assert all(v[1] is None for v in state(conn, 1).values()) and r['without_volume'] == 1 and r['written'] == 0
    again = ChartClient()
    assert collect.fill_volumes_batch(conn, again, ROWS[:1], NOW)['examined'] == 0 and not again.calls
    empty = collect.fill_volumes_batch(conn, ChartClient(empty={'BBB'}), ROWS[1:2], NOW)
    assert empty['examined'] == 1 and all(v[1] is None for v in state(conn, 2).values())      # réponse sans barre : aucune écriture, titre marqué


def test_rerun_has_no_duplicates_and_no_new_calls(conn):
    collect.fill_volumes_batch(conn, ChartClient(), ROWS, NOW)
    before = [state(conn, i) for i in (1, 2, 3)]
    again = ChartClient()
    r = collect.fill_volumes_batch(conn, again, ROWS, NOW)
    assert r['examined'] == 0 and not again.calls and [state(conn, i) for i in (1, 2, 3)] == before
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM daily_prices')
        assert cur.fetchone()['n'] == 15


def test_rate_limit_stops_and_resume_asks_only_the_remaining_titles(conn):
    r = collect.fill_volumes_batch(conn, ChartClient(rate_limit='BBB'), ROWS, NOW)
    assert r['rate_limited'] and r['examined'] == 1 and checked(conn, 1) and not checked(conn, 2) and not checked(conn, 3)
    retry = ChartClient()
    r2 = collect.fill_volumes_batch(conn, retry, ROWS, NOW)
    assert r2['examined'] == 2 and sorted(c[0] for c in retry.calls) == ['BBB', 'CCC']      # AAA déjà fait : non redemandé


def test_isolated_failure_does_not_stop_others_and_is_retried_at_the_end(conn):
    client = ChartClient(broken={'BBB'})
    r = collect.fill_volumes_batch(conn, client, ROWS, NOW)
    assert r['examined'] == 3 and r['errors'] == 0 and r['retried'] == 1 and [c[0] for c in client.calls].count('BBB') == 2
    assert state(conn, 2)[DAYS[0]][1] == 1000


def test_persistent_failure_is_logged_and_does_not_block_the_batch(conn):
    class Always(ChartClient):
        def chart(self, symbol, range_='5d', interval='15m'):
            if symbol == 'BBB':
                raise RuntimeError('toujours en erreur')
            return super().chart(symbol, range_, interval)
    r = collect.fill_volumes_batch(conn, Always(), ROWS, NOW)
    assert r['examined'] == 2 and r['errors'] == 1 and not checked(conn, 2)
    assert '2' in collect.setting(conn, collect.VOLUME_ERRORS, {})
    assert collect.fill_volumes_batch(conn, ChartClient(), ROWS, NOW)['examined'] == 0     # échec récent : pas d'insistance automatique
    assert collect.fill_volumes_batch(conn, ChartClient(), ROWS, NOW, since=NOW + datetime.timedelta(hours=1))['examined'] == 3   # le rattrapage manuel les reprend tous


def test_four_threads_give_the_same_result(conn):
    r = collect.fill_volumes_batch(conn, ChartClient(), ROWS, NOW, workers=4, client_factory=ChartClient)
    assert r['examined'] == 3 and r['written'] == 15 and all(state(conn, i)[DAYS[1]][1] == 0 for i in (1, 2, 3))


def test_new_session_makes_checked_titles_candidates_again_with_the_short_window(conn):
    collect.fill_volumes_batch(conn, ChartClient(), ROWS[:1], NOW)
    later = NOW + datetime.timedelta(days=3)                                    # lundi suivant réglé
    c = ChartClient()
    r = collect.fill_volumes_batch(conn, c, ROWS[:1], later)
    assert r['examined'] == 1 and c.calls == [('AAA', collect.VOLUME_REFRESH_RANGE, '1d')]
    first = ChartClient()
    collect.fill_volumes_batch(conn, first, ROWS[1:2], NOW)
    assert first.calls == [('BBB', collect.VOLUME_BACKFILL_RANGE, '1d')]         # jamais interrogé : un an


def test_gap_closes_keep_the_volume_received_with_the_close(conn):
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE listing_id=1 AND price_date=%s', (DAYS[1],))
    conn.commit()
    titles, added = collect.fill_daily_gaps(conn, ChartClient(), ROWS[:1], NOW)
    got = state(conn, 1)
    assert added == 1 and got[DAYS[1]] == (778.0, 0)                            # clôture ajoutée avec son volume, y compris un volume nul
    assert got[DAYS[0]] == (99.0, None)                                         # clôtures existantes intactes, volume non touché par ce chemin


def test_candidates_order_never_checked_first(conn):
    collect.fill_volumes_batch(conn, ChartClient(), ROWS[:1], NOW)
    later = NOW + datetime.timedelta(days=3)
    assert [i for i, _ in collect.volume_candidates(conn, ROWS, later)] == [2, 3, 1]


def test_manual_job_collects_everything_then_recomputes_and_closes_stay_identical(conn, monkeypatch):
    from engine.jobs import tasks
    monkeypatch.setattr(tasks.collect, 'collection_set', lambda c: ROWS)
    recomputed = []
    monkeypatch.setattr(tasks.compute, 'compute_all', lambda c, n: recomputed.append(1) or (3, 9))
    closes_before = [{d: v[0] for d, v in state(conn, i).items()} for i in (1, 2, 3)]
    examined, problems, summary = tasks.volumes_all(conn, ChartClient(), NOW, lambda *a, **k: None)
    assert examined == 3 and problems == 0 and recomputed == [1] and '15 volumes écrits' in summary
    assert [{d: v[0] for d, v in state(conn, i).items()} for i in (1, 2, 3)] == closes_before     # clôtures historiques identiques
    assert tasks.volumes_all(conn, ChartClient(), NOW, lambda *a, **k: None)[0] == 0              # relance : rien à refaire
    cov = tasks.history_coverage(conn)
    assert 'volume_checked' in cov and 'volume_errors' in cov
