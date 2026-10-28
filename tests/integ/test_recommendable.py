"""Garantie : un titre exclu (liquidité insuffisante) n'apparaît dans aucun classement, quelle que soit la période.
Cas de référence : DVDG.DE, ETF exclu, tendance parfaite."""
import datetime
import os
import pytest
from engine.shared.db import connect
from tests.dbutil import reset_data
from engine.analytics import strategy as S
from engine.analytics.repository import recommendable_candidates

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


def seed(conn):
    reset_data(conn)
    with conn.cursor() as cur:
        pass
        cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name) VALUES (1,'isin:DE000A000001','DE000A000001','equity','Bon SA'),(2,'isin:DE000A000002','DE000A000002','etf','DVDG ETF'),(3,'isin:DE000A000003','DE000A000003','equity','Multi SA')")
        cur.execute("""INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,excluded_reason,is_primary) VALUES
            (10,1,'XETR','GOOD.DE','EUR','selected',NULL,1),
            (20,2,'XETR','DVDG.DE','EUR','excluded','liquidité insuffisante',1),
            (30,3,'XETR','MULTI.DE','EUR','selected',NULL,1),
            (31,3,'XNYS','MULTI','USD','selected',NULL,0)""")
        start = datetime.date(2025, 1, 1)
        rows = []
        for lid, rate in ((10, 1.004), (20, 1.006), (30, 1.004), (31, 1.004)):
            p = 100.0
            for i in range(300):
                rows.append((lid, start + datetime.timedelta(days=i), round(p, 6)))
                p *= rate
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', rows)
        cur.execute("INSERT INTO users(id,username,pass_hash,created_at) VALUES (1,'t','x',NOW())")
        cur.execute("INSERT INTO portfolios(id,user_id,name,created_at,updated_at) VALUES (1,1,'P',NOW(),NOW())")
        cur.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,trade_at,created_at) VALUES (1,20,'DVDG.DE','buy',10,100,NOW(),NOW())")
    conn.commit()


def test_excluded_never_recommended_even_when_held():
    conn = connect()
    seed(conn)
    candidates = recommendable_candidates(conn)
    assert {c['key'] for c in candidates} == {10, 30}      # ni 20 (exclu), ni 31 (non principale)
    for name in S.PRESETS:
        cfg = S.preset(name)
        for period in cfg['periods']:                      # chaque période seule : jour, semaine, mois, trimestre, semestre, année
            for p in cfg['periods']:
                p['enabled'] = p is period
            period.update(min_slope=0.0)
            if period['id'] == 'day':
                period['sessions'] = 1
            res = S.evaluate(cfg, candidates)
            assert 20 not in {v['key'] for v in res}
    with conn.cursor() as cur:
        cur.execute("SELECT listing_id FROM v_collect_set WHERE held=1")
        assert {r['listing_id'] for r in cur.fetchall()} == {20}
        cur.execute("SELECT COUNT(*) n FROM v_collect_set WHERE listing_id=20")
        assert cur.fetchone()['n'] == 1                    # collectée une seule fois
