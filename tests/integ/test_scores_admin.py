"""Administration des scores sur une vraie base : simulation, suivi et profils, avec des séries enregistrées (aucune donnée d'exemple dans le produit)."""
import datetime
import os

import pytest

from engine.analytics import compute, scores_admin as A
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


def seed(conn):
    import exchange_calendars as xc
    calendar = xc.get_calendar('XETR', start='2026-01-05', end='2027-01-31')
    days = [d.date() for d in calendar.sessions if d.date() >= datetime.date(2026, 1, 5)][:260]
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:UP.DE','equity','Monte SE','Germany'),(2,'sym:XETR:ZIG.DE','equity','Zigzag AG','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','UP.DE','EUR','selected',1),(2,2,'XETR','ZIG.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                        [(1, d, round(100 * 1.004 ** i, 6)) for i, d in enumerate(days)] + [(2, d, round(100 * 1.0015 ** i * (1.04 if i % 3 == 0 else 0.97), 6)) for i, d in enumerate(days)])
        cur.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (%s,%s,%s,'daily','EUR',%s)", [(1, 250.0, NOW, 300000), (2, 120.0, NOW, 50000)])
    conn.commit()
    compute.compute_all(conn, NOW)


def test_simulation_monitor_and_profiles_use_real_data_and_stay_independent_of_conformity():
    conn = connect()
    reset_data(conn)
    empty = A.simulate(conn, {'strategy': 'growth_v1'})
    assert empty['empty'] and 'Aucun titre noté' in empty['reason']                    # sans données : jamais d'exemple fictif
    assert A.monitor(conn)['rated'] == 0
    seed(conn)
    mon = A.monitor(conn)
    assert mon['rated'] == 2 and mon['liquidity']['universe'] == 2 and mon['freshness']['last_close'] is not None
    sim = A.simulate(conn, {'strategy': 'growth_v1', 'q': 'UP.DE'})
    assert sim['title']['symbol'] == 'UP.DE' and [p['id'] for p in sim['periods']] == ['week', 'month']
    simple, complex_ = sim['result']['simple'], sim['result']['complex']
    assert simple['score'] is not None and 0 < simple['score'] <= 100 and complex_['score'] is not None
    assert sum(sim['result']['weights'].values()) == pytest.approx(1)
    assert A.simulate(conn, {'strategy': 'growth_v1', 'q': 'introuvable'}).get('not_found')
    # régulier mieux noté que le titre en dents de scie (score simple)
    zig = A.simulate(conn, {'strategy': 'growth_v1', 'q': 'ZIG.DE'})['result']['simple']['score']
    assert zig is None or zig < simple['score']
    # les seuils de conformité ne changent aucune note
    p = A.profile_of(A.base_config('growth_v1'))
    for x in p['periods'].values():
        x.pop('sessions')
    p['periods']['week']['min_slope'] = 0.9
    p['periods']['month']['min_r2'] = 0.95
    A.save(conn, {'profile': dict(p, name='growth_v1')})
    again = A.simulate(conn, {'strategy': 'growth_v1', 'q': 'UP.DE'})['result']
    assert again['simple']['score'] == simple['score'] and again['complex']['score'] == complex_['score']
    # une granularité de plus change les notes ; le brouillon non enregistré permet de simuler sans enregistrer
    p['periods']['quarter']['enabled'] = True
    draft = A.simulate(conn, {'strategy': 'growth_v1', 'q': 'UP.DE', 'draft': {'profile': dict(p, name='growth_v1')}})
    assert [x['id'] for x in draft['periods']] == ['week', 'month', 'quarter']
    assert [x['id'] for x in A.simulate(conn, {'strategy': 'growth_v1', 'q': 'UP.DE'})['periods']] == ['week', 'month']
    A.save(conn, {'reset': 'all'})
    assert not [s for s in A.state(conn)['strategies'] if s['name'] == 'growth_v1'][0]['customised']
