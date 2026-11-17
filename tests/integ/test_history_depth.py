"""Profondeur permanente de 1 260 séances : rattrapage, reprise, fermetures exceptionnelles, rétention, nouveaux titres. Yahoo simulé : aucun réseau."""

import datetime
import os

import pytest

from engine.market import collect, history_depth
from engine.market.yahoo import RateLimited
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 17, 5, 0, tzinfo=UTC)  # avant la clôture de la séance du jour : la dernière séance réglée est celle de la veille
CAL = history_depth.Calendars(NOW).get('XETR')
DAYS = CAL['dates']  # les 1 260 dernières séances XETR


def ts(day):
    return int(datetime.datetime(day.year, day.month, day.day, 10, tzinfo=UTC).timestamp())


class DeepClient:
    """`series` : {symbole: {date: (clôture, volume)}} ; `first_trade` : date de première cotation déclarée."""

    def __init__(self, series, rate_limit=None, broken=(), first_trade=None):
        self.series, self.rate_limit, self.broken, self.first_trade, self.calls = series, rate_limit, set(broken), first_trade, []

    def chart_dates(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        if symbol == self.rate_limit:
            raise RateLimited(60)
        if symbol in self.broken:
            raise RuntimeError('boom')
        bars = [(ts(d), 1, 1, 1, c, v) for d, (c, v) in sorted(self.series.get(symbol, {}).items()) if start <= d <= end]
        return {'timezone': 'Europe/Berlin', 'bars': bars, 'first_trade': self.first_trade}


def add_title(conn, lid, symbol, days=(), close=10.0, volume=111):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name) VALUES (%s,%s,'equity',%s)", (lid, f'k{lid}', symbol))
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, symbol))
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (%s,%s,%s,%s)', [(lid, d, close, volume) for d in days])
    conn.commit()
    return {'listing_id': lid, 'mic': 'XETR', 'symbol': symbol}


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    yield c
    c.close()


def prices(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT price_date, close_px, volume FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        return cur.fetchall()


def status(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM history_state WHERE listing_id=%s', (lid,))
        return cur.fetchone()


def test_backfill_keeps_existing_closes_fills_volumes_and_classifies_recent_title(conn):
    have = DAYS[-300:]
    row = add_title(conn, 1, 'AAA.DE', have)
    with conn.cursor() as cur:
        cur.execute('UPDATE daily_prices SET volume=NULL WHERE listing_id=1 AND price_date IN (%s,%s,%s)', tuple(have[:3]))
    conn.commit()
    born = DAYS[-700]  # titre coté depuis 700 séances : plus jeune que la profondeur
    client = DeepClient({'AAA.DE': {d: (99.0, 5000) for d in DAYS if d >= born}}, first_trade=born)
    stats = history_depth.run(conn, client, [row], NOW)
    assert stats['recent'] == 1 and stats['added'] == 400
    rows = prices(conn, 1)
    assert len(rows) == 700
    assert {float(r['close_px']) for r in rows if r['price_date'] in set(have)} == {10.0}  # jamais écrasées
    assert all(r['volume'] is not None for r in rows)  # volumes vides complétés
    assert status(conn, 1)['status'] == 'recent'
    # la demande par dates part de la première séance manquante moins une marge, et couvre la fin de la fenêtre
    symbol, start, end = client.calls[0]
    assert start == DAYS[0] - datetime.timedelta(days=history_depth.MARGIN_DAYS) and end >= DAYS[-1]  # première séance manquante de la fenêtre, moins la marge
    # reprise : plus rien à demander, aucun doublon
    again = history_depth.run(conn, client, [row], NOW)
    assert again['candidates'] == 0 and len(client.calls) == 1 and len(prices(conn, 1)) == 700


def test_new_title_without_prices_receives_full_depth_and_title_already_complete_costs_no_call(conn):
    new = add_title(conn, 1, 'NEW.DE')
    full = add_title(conn, 2, 'FULL.DE', DAYS)
    client = DeepClient({'NEW.DE': {d: (50.0, 10) for d in DAYS}})
    stats = history_depth.run(conn, client, [new, full], NOW)
    assert [c[0] for c in client.calls] == ['NEW.DE']  # le titre déjà complet n'a coûté aucun appel
    assert stats['complete'] == 2 and len(prices(conn, 1)) == 1260
    assert status(conn, 2)['detail'] == 'déjà complet'
    cov = history_depth.coverage(conn)
    assert cov['complete'] == 2 and cov['pending'] == 0 and cov['target'] == 1260


def test_exceptional_closure_is_not_a_hole_but_a_real_hole_stays_incomplete(conn):
    closure = DAYS[-500]
    rows = [add_title(conn, i, f'T{i}.DE') for i in range(1, 23)]
    series = {r['symbol']: {d: (10.0, 5) for d in DAYS if d != closure} for r in rows}  # Yahoo n'a aucune barre ce jour-là, pour personne
    series['T22.DE'] = {d: (10.0, 5) for d in DAYS if d not in (closure, DAYS[-200], DAYS[-199])}  # un vrai trou : deux jours omis pour ce seul titre
    client = DeepClient(series)
    history_depth.run(conn, client, rows, NOW, limit=None)
    assert {status(conn, i)['status'] for i in range(1, 22)} == {'incomplete'}  # fermeture encore inconnue : tout paraît incomplet
    changes = history_depth.reclassify(conn, NOW)
    assert changes == {'incomplete -> complete': 21}
    assert status(conn, 1)['status'] == 'complete' and status(conn, 1)['closed_days'] == 1
    assert status(conn, 22)['status'] == 'incomplete' and status(conn, 22)['holes'] == 2
    assert closure in history_depth.closed_days(conn, NOW)['XETR']


def test_errors_are_retried_and_rate_limit_leaves_the_title_unmarked(conn):
    a, b, c = (add_title(conn, i, s) for i, s in ((1, 'A.DE'), (2, 'B.DE'), (3, 'C.DE')))
    series = {s: {d: (10.0, 1) for d in DAYS} for s in ('A.DE', 'B.DE', 'C.DE')}
    history_depth.run(conn, DeepClient(series, broken=['A.DE'], rate_limit='B.DE'), [a, b, c], NOW, limit=None)
    assert status(conn, 1)['status'] == 'error' and status(conn, 2) is None  # 429 : non marqué, repris ensuite
    assert {r['listing_id'] for r in history_depth.candidates(conn, [a, b, c], NOW)} == {2, 3}  # A est en erreur (délai non écoulé), B et C n'ont pas d'état
    # une erreur n'est redemandée qu'après son délai
    assert 1 not in {r['listing_id'] for r in history_depth.candidates(conn, [a], NOW)}
    later = NOW + datetime.timedelta(hours=7)
    assert 1 in {r['listing_id'] for r in history_depth.candidates(conn, [a], later)}
    history_depth.run(conn, DeepClient(series), [a, b, c], later, limit=None)
    assert {status(conn, i)['status'] for i in (1, 2, 3)} == {'complete'}


def test_retention_keeps_five_years_without_any_strategy_and_prunes_beyond(conn):
    today = NOW.date()
    row = add_title(conn, 1, 'OLD.DE', [today - datetime.timedelta(days=d) for d in (1, 1500, 1990)])
    old = today - datetime.timedelta(days=2100)
    with conn.cursor() as cur:
        cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,5)', (old,))
    conn.commit()
    assert collect.prune_daily(conn, NOW) == 1
    assert len(prices(conn, 1)) == 3 and row


def test_daily_plan_never_asks_five_years_and_catchup_stays_short(conn):
    row = add_title(conn, 1, 'SHORT.DE', DAYS[-100:-5])
    plan, _fresh = collect.daily_plan(conn, [row], NOW)
    assert set(plan) <= {'5d', '1mo', '3mo', '6mo', '1y', '2y'}
