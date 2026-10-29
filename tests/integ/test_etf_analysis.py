"""Réponses attendues indépendantes : deux mêmes rendements => r=1 ; pondérations en EUR."""
import datetime as dt
import json
import math
import os
import pytest
from engine.analytics import etf, service, strategy
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        for lid in range(1, 5):
            cur.execute("INSERT INTO instruments(id,group_key,kind,name,category) VALUES (%s,%s,'etf',%s,%s)", (lid, 'etf:' + str(lid), 'ETF ' + str(lid), 'Energy' if lid < 4 else 'Commodities'))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, str(lid) + '.DE'))
        day = dt.date(2026, 4, 20)
        i = 0
        while day <= dt.date(2026, 10, 29):
            if day.weekday() < 5:
                for lid in range(1, 5):
                    price = (100 + i + 2 * math.sin(i * .3)) * lid
                    cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', (lid, day, price))
                i += 1
            day += dt.timedelta(days=1)
        profile = {'holdings': [{'name': 'A', 'weight': None}], 'expense_ratio': 0, 'sectors': {'Énergie': 100}, 'stock_position': 100}
        cur.execute("INSERT INTO etf_profiles VALUES (1,'2026-10-29',2,'ok',%s)", (json.dumps(profile),))
    c.commit()
    yield c
    c.close()


def test_coverage_is_read_only_and_complete(conn):
    before = etf.coverage(conn)
    assert before['selected_primary'] == dict(listings=4, instruments=4, cached=1, state_ok=1, holdings=1,
                                            ten_valid_weights=0, some_valid_weights=0, sectors=1, fees=1, legacy_weight_ambiguity=0)
    assert etf.coverage(conn)['selected_primary'] == before['selected_primary']


def test_precomputed_similarity_metadata_and_portfolio(conn, monkeypatch):
    now = dt.datetime(2026, 10, 29, 20)
    monkeypatch.setattr(etf.dt, 'datetime', type('Clock', (dt.datetime,), {'utcnow': classmethod(lambda cls: now)}))
    result = etf.build(conn, now)
    assert result['etfs'] == result['with_minimum_history'] == 4
    p = etf.load(conn, [1, 2])
    assert p[1]['similar'][0]['coefficient'] == 1
    assert p[1]['similar'][0]['sessions'] >= 100
    assert p[1]['profile']['holdings'][0]['weight'] is None
    r = etf.portfolio(conn, [{'listing_id': 1, 'kind': 'etf', 'symbol': 'A', 'value': 100},
                             {'listing_id': 2, 'kind': 'etf', 'symbol': 'B', 'value': 300}])
    assert r['known_eur'] == 100 and r['unknown_eur'] == 300 and r['unknown_percent'] == 75
    assert len(r['similar_pairs']) == 1 and r['similar_pairs'][0]['coefficient'] == 1
    alert = etf.concentration(conn, [1, 2, 3, 4])
    assert alert['alerts'][0]['count'] == 3 and alert['sample'] == 4
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM portfolio_transactions')
        assert cur.fetchone()['n'] == 0


def test_ranking_cache_not_modified(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM strategy_metrics')
        before = cur.fetchone()['n']
    etf.build(conn, dt.datetime(2026, 10, 29, 20))
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM strategy_metrics')
        assert cur.fetchone()['n'] == before
