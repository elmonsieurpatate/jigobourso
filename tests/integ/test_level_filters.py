"""Filtres Régularité / Volatilité / Négociabilité et résumé du profil, sur une vraie base jetable : masquage seul, rang et score du catalogue inchangés."""
import datetime
import math
import os

import pytest

from engine.analytics import compute, service
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


@pytest.fixture(autouse=True)
def fixed_market_clock(monkeypatch):
    monkeypatch.setattr(service.hours, 'utcnow', lambda: NOW)


def seed(conn):
    """Six actions qui montent à des rythmes différents ; les pairs sont lisses (régulières), les impairs en dents de scie (irrégulières)."""
    reset_data(conn)
    days, d = [], datetime.date(2026, 10, 27)
    while len(days) < 300:
        if d.weekday() < 5:
            days.append(d)
        d -= datetime.timedelta(days=1)
    days.reverse()
    with conn.cursor() as cur:
        for lid in range(1, 7):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'Germany')", (lid, f'sym:XETR:S{lid}.DE', f'Titre {lid}'))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, f'S{lid}.DE'))
            rate = 1.002 + 0.0004 * lid
            noise = 0.0 if lid % 2 == 0 else 0.06
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                            [(lid, day, round(100 * rate ** i * (1 + noise * math.sin(i * 1.7)), 6)) for i, day in enumerate(days)])
            volume = 100000 if lid <= 4 else 10                              # les deux derniers : négociabilité limitée
            cur.execute('INSERT INTO latest_prices(listing_id,price,currency,avg_volume_3m,quote_at) VALUES (%s,100,%s,%s,%s)', (lid, 'EUR', volume, NOW.replace(tzinfo=None)))
    conn.commit()
    compute.compute_all(conn, NOW)


def explore(conn, **view):
    return service.explore(conn, {'preset': 'fast', 'view': dict({'status': 'all', 'tradable': False, 'page_size': 50}, **view)})


def test_level_filters_hide_without_changing_rank_score_or_relative_order():
    conn = connect()
    seed(conn)
    base = explore(conn)
    levels = {r['symbol']: {s['key']: s['level'] for s in r['signals']} for r in base['rows']}
    assert {l['regularity'] for l in levels.values()} >= {'ok', 'bad'} or len({l['regularity'] for l in levels.values()}) > 1     # le jeu de test contient bien des niveaux différents
    for key, level in (('regularity', 'ok'), ('liquidity', 'ok'), ('risk', 'ok')):
        filtered = explore(conn, **{key: level})
        kept = {r['symbol'] for r in base['rows'] if levels[r['symbol']][key] == level}
        assert {r['symbol'] for r in filtered['rows']} == kept
        by = {r['symbol']: (r['rank'], r['score']) for r in base['rows']}
        assert all(by[r['symbol']] == (r['rank'], r['score']) for r in filtered['rows'])                         # rang et score du catalogue inchangés
        order = [r['symbol'] for r in base['rows'] if r['symbol'] in kept]
        assert [r['symbol'] for r in filtered['rows']] == order                                                  # même ordre relatif
        assert filtered['level_filters']['masked'] == len(base['rows']) - len(kept)
    assert explore(conn, regularity='ok|warn|bad|unknown')['rows'] == base['rows']                               # tout coché = rien de masqué


def test_level_filters_cumulate_and_report_the_counts_of_each_level():
    conn = connect()
    seed(conn)
    base = explore(conn)
    both = explore(conn, regularity='ok', liquidity='ok')
    levels = {r['symbol']: {s['key']: s['level'] for s in r['signals']} for r in base['rows']}
    assert {r['symbol'] for r in both['rows']} == {s for s, l in levels.items() if l['regularity'] == 'ok' and l['liquidity'] == 'ok'}
    counts = base['level_filters']['counts']
    assert sum(counts['regularity'].values()) == len(base['rows']) and counts['liquidity'].get('bad') == 2
    assert explore(conn, q='S5.DE', liquidity='ok')['rows'][0]['symbol'] == 'S5.DE'                              # titre retrouvé par son symbole exact : jamais masqué


def test_the_sheet_carries_the_assessment_and_pills_with_their_period():
    conn = connect()
    seed(conn)
    sheet = service.instrument_sheet(conn, {'listing_id': 2, 'config': 'fast', 'view': {}, 'fetch_profile': False})
    a = sheet['assessment']
    assert a['label'] in ('Très favorable', 'Favorable', 'Mitigé', 'Défavorable', 'Indéterminé') and a['period'] == '1 mois' and a['closing']
    periods = {s['key']: s.get('period') for s in sheet['signals']}
    assert periods['regularity'] == '1 mois' and periods['risk'] == '1 mois' and periods['liquidity'] == '3 mois'
