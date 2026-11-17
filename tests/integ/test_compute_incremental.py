"""Calcul incrémental : seuls les titres dont les données d'entrée ont changé sont recalculés, résultat identique à un calcul complet ; recalcul complet si la méthode change."""

import datetime
import hashlib
import json
import math
import os
import random

import pytest

from engine.analytics.series import compute
from engine.market import collect
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 20, 0, tzinfo=datetime.timezone.utc)
TABLES = {
    'strategy_metrics': 'SELECT * FROM strategy_metrics ORDER BY listing_id, sessions',
    'score_inputs': 'SELECT * FROM score_inputs ORDER BY listing_id, sessions',
    'series_state': 'SELECT * FROM series_state ORDER BY listing_id',
    'liquidity_state': 'SELECT listing_id, turnover_eur, days, source FROM liquidity_state ORDER BY listing_id',
}


def sessions(mic, count=330):
    import exchange_calendars as xc

    calendar = xc.get_calendar(mic, start='2025-01-02', end='2026-12-31')
    return [d.date() for d in calendar.sessions if d.date() <= datetime.date(2026, 10, 27)][-count:]


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    rng = random.Random(3)
    with c.cursor() as cur:
        for lid, (mic, symbol) in enumerate([('XETR', 'AAA.DE'), ('XETR', 'BBB.DE'), ('XETR', 'CCC.DE'), ('XPAR', 'DDD.PA')], start=1):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name) VALUES (%s,%s,'equity',%s)", (lid, f'k{lid}', symbol))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,%s,%s,'EUR','selected',1)", (lid, lid, mic, symbol))
            price, rows = 100.0, []
            for d in sessions(mic):
                price *= math.exp(rng.gauss(0.0004, 0.012))
                rows.append((lid, d, round(price, 6), 1000 + lid))
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (%s,%s,%s,%s)', rows)
    c.commit()
    yield c
    c.close()


def snap(conn):
    out = {}
    with conn.cursor() as cur:
        for name, query in TABLES.items():
            cur.execute(query)
            rows = cur.fetchall()
            for r in rows:
                r.pop('computed_at', None)
            out[name] = hashlib.md5(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest()
    return out


def full_after(conn, state):
    """Résultat d'un calcul complet du même état de la base."""
    compute.compute_all(conn, NOW, full=True)
    assert compute.LAST['mode'] == 'full' and compute.LAST['recomputed'] == compute.LAST['total']
    return snap(conn)


def test_nothing_new_recomputes_nothing_and_changes_nothing(conn):
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'full' and compute.LAST['reason']  # premier passage : aucune empreinte, tout est calculé
    first = snap(conn)
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'unchanged' and compute.LAST['recomputed'] == 0
    assert snap(conn) == first


def test_one_new_close_recomputes_only_that_title_and_matches_the_full_result(conn):
    compute.compute_all(conn, NOW)
    last = sessions('XETR')[-1]
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE listing_id=2 AND price_date=%s', (last,))  # BBB perd sa dernière clôture : état « avant »
    conn.commit()
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'incremental' and compute.LAST['recomputed'] == 1
    incremental = snap(conn)
    assert incremental == full_after(conn, 'BBB sans sa dernière clôture')
    with conn.cursor() as cur:
        cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (2,%s,150,9)', (last,))  # la clôture arrive
    conn.commit()
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'incremental' and compute.LAST['recomputed'] == 1
    assert snap(conn) == full_after(conn, 'BBB complet')


def test_several_modified_titles_match_the_full_result_and_others_are_untouched(conn):
    compute.compute_all(conn, NOW)
    with conn.cursor() as cur:
        cur.execute('SELECT computed_at, close_px FROM series_state WHERE listing_id=3')
        untouched = cur.fetchone()['close_px']
        for lid in (1, 4):
            cur.execute(
                'UPDATE daily_prices SET close_px=close_px*1.02 WHERE listing_id=%s AND price_date=(SELECT m FROM (SELECT MAX(price_date) m FROM daily_prices WHERE listing_id=%s) t)', (lid, lid)
            )
    conn.commit()
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'incremental' and compute.LAST['recomputed'] == 2
    incremental = snap(conn)
    assert incremental == full_after(conn, 'deux titres corrigés')
    with conn.cursor() as cur:
        cur.execute('SELECT close_px FROM series_state WHERE listing_id=3')
        assert cur.fetchone()['close_px'] == untouched


def test_a_new_session_on_a_market_recomputes_its_titles_only(conn):
    compute.compute_all(conn, NOW)
    # la place XETR a une nouvelle séance (pour tous ses titres) ; XPAR n'a rien de neuf
    import exchange_calendars as xc

    day = [d.date() for d in xc.get_calendar('XETR', start='2026-10-27', end='2026-11-10').sessions if d.date() > datetime.date(2026, 10, 27)][0]
    later = datetime.datetime(day.year, day.month, day.day, 20, 0, tzinfo=datetime.timezone.utc)
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (%s,%s,101,5)', [(lid, day) for lid in (1, 2, 3)])
    conn.commit()
    compute.compute_all(conn, later)
    assert compute.LAST['mode'] == 'incremental' and 3 <= compute.LAST['recomputed'] < 4  # les trois titres XETR, pas celui de XPAR
    incremental = snap(conn)
    compute.compute_all(conn, later, full=True)
    assert snap(conn) == incremental


def test_a_method_change_forces_a_full_recompute_then_goes_back_to_incremental(conn, monkeypatch):
    compute.compute_all(conn, NOW)
    original = compute.wanted_windows
    monkeypatch.setattr(compute, 'wanted_windows', lambda c: sorted(set(original(c)) | {400}))  # une stratégie demande une période de plus
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'full' and 'méthode' in compute.LAST['reason']
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'unchanged'
    monkeypatch.setattr(compute, 'wanted_windows', original)
    compute.compute_all(conn, NOW)
    assert compute.LAST['mode'] == 'full'  # période retirée : les anciennes fenêtres reviennent, tout est recalculé


def test_a_title_leaving_the_collection_is_cleaned_and_a_new_title_is_computed(conn):
    compute.compute_all(conn, NOW)
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='candidate' WHERE id=4")
        cur.execute("INSERT INTO instruments(id,group_key,kind,name) VALUES (9,'k9','equity','NEW')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (9,9,'XETR','NEW.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (9,%s,%s,10)', [(d, 50 + i * 0.1) for i, d in enumerate(sessions('XETR'))])
    conn.commit()
    compute.compute_all(conn, NOW)
    assert compute.LAST['recomputed'] == 1 and compute.LAST['removed'] == 1
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id FROM series_state ORDER BY listing_id')
        assert [r['listing_id'] for r in cur.fetchall()] == [1, 2, 3, 9]
        cur.execute('SELECT COUNT(*) n FROM strategy_metrics WHERE listing_id=4')
        assert cur.fetchone()['n'] == 0
    incremental = snap(conn)
    assert incremental == full_after(conn, 'sélection modifiée')


def test_daily_collection_never_stores_bars_older_than_the_retention_so_nothing_is_added_then_purged(conn):
    """Cause des « 25 clôtures ajoutées » répétées : une clôture plus ancienne que la rétention était insérée à chaque collecte puis supprimée par la purge."""
    old = NOW.date() - datetime.timedelta(days=collect.DAILY_KEEP_DAYS + 30)
    recent = sessions('XETR')[-1]

    class Spark:
        def spark(self, symbols, range_, interval):
            ts = lambda d: int(datetime.datetime(d.year, d.month, d.day, 12, tzinfo=datetime.timezone.utc).timestamp())
            return {s: {'timezone': 'Europe/Berlin', 'bars': [(ts(old), 9.0), (ts(recent), 10.0)]} for s in symbols}

    rows = [{'listing_id': 1, 'symbol': 'AAA.DE', 'mic': 'XETR'}]
    for _ in range(3):
        collect.collect_daily(conn, Spark(), rows, NOW, range_='5y')
        collect.prune_daily(conn, NOW)
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) n FROM daily_prices WHERE listing_id=1 AND price_date < %s', (NOW.date() - datetime.timedelta(days=collect.DAILY_KEEP_DAYS),))
            assert cur.fetchone()['n'] == 0  # jamais insérée


def test_etf_similarity_is_rebuilt_only_when_its_inputs_change(conn):
    from engine.analytics.market_views import etf

    with conn.cursor() as cur:
        cur.execute("UPDATE instruments SET kind='etf' WHERE id IN (1,2,3)")
    conn.commit()
    first = etf.build(conn, NOW)
    assert not first.get('skipped')
    again = etf.build(conn, NOW)
    assert again.get('skipped') and again['etfs'] == first['etfs'] == 3  # aucune donnée d'entrée n'a changé
    with conn.cursor() as cur:
        cur.execute('SELECT built_at FROM etf_analysis WHERE listing_id=1')
        built = cur.fetchone()['built_at']
    with conn.cursor() as cur:
        cur.execute('UPDATE daily_prices SET close_px=close_px*1.01 WHERE listing_id=2 AND price_date=%s', (sessions('XETR')[-1],))
    conn.commit()
    changed = etf.build(conn, NOW)
    assert not changed.get('skipped')  # une clôture a changé : reconstruction
    assert etf.build(conn, NOW + datetime.timedelta(days=1)).get('skipped') is not True  # le lendemain : la fenêtre glisse, reconstruction
    assert etf.build(conn, NOW, force=True).get('skipped') is None  # demande explicite : toujours reconstruit
    assert built is not None


def test_an_unavailable_etf_profile_is_not_requested_again_at_every_maintenance(conn):
    """Un profil resté indisponible (ancien profil conservé) était redemandé à chaque passage : 84 appels Yahoo inutiles par maintenance."""
    from engine.analytics.market_views import etf

    with conn.cursor() as cur:
        cur.execute("UPDATE instruments SET kind='etf' WHERE id=1")
        cur.execute(
            "INSERT INTO etf_profiles(listing_id,fetched_at,version,state,data_json) VALUES (1,%s,%s,'ok','{}')", (NOW.replace(tzinfo=None) - datetime.timedelta(days=40), etf.etf_profile.VERSION)
        )
    conn.commit()

    class Client:
        calls = 0
        transport = None

    calls = []
    original = etf.fetch_profile
    etf.fetch_profile = lambda transport, symbol: calls.append(symbol)  # Yahoo ne répond plus rien d'exploitable
    try:
        first = etf.warm_profiles(conn, Client(), NOW)
        second = etf.warm_profiles(conn, Client(), NOW + datetime.timedelta(hours=1))
        third = etf.warm_profiles(conn, Client(), NOW + datetime.timedelta(days=2))
    finally:
        etf.fetch_profile = original
    assert first['unavailable'] == 1 and second['to_refresh'] == 0 and len(calls) == 1 + (third['unavailable'])  # redemandé le surlendemain seulement
