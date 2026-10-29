import datetime
import os
import pytest
from engine.shared.db import connect
from engine.market import collect, hours
from tests.fakes import FakeYahoo
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)       # mardi, Xetra fermée et clôture publiée


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("""INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES
            (1,'isin:DE0001','DE0001','equity','Liquide SE','Germany'),(2,'isin:IE0002','IE0002','etf','DVDG ETF',NULL),(3,'isin:DE0003','DE0003','equity','Trop cher SE','Germany')""")
        cur.execute("""INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES
            (1,1,'XETR','LIQ.DE','EUR','candidate',1),(2,2,'XETR','DVDG.DE','EUR','candidate',1),(3,3,'XETR','PENNY.DE','EUR','candidate',1)""")
    c.commit()
    yield c
    c.close()


def quotes():
    q = lambda p, v: {'price': p, 'price_time': datetime.datetime(2026, 10, 27, 16, 30), 'avg_volume_3m': v, 'currency': 'EUR', 'market_cap': None, 'quote_type': 'EQUITY'}
    return {'LIQ.DE': q(100.0, 50000), 'DVDG.DE': q(42.1, 131), 'PENNY.DE': q(0.5, 9_000_000)}


def rows_of(conn):
    return collect.collection_set(conn)


def test_prefilter_excludes_dvdg_but_held_listing_is_still_collected(conn):
    client = FakeYahoo(quotes=quotes())
    # première passe : tous les candidats reçoivent un Quote
    with conn.cursor() as cur:
        cur.execute('SELECT id AS listing_id, mic, symbol FROM listings')
        everything = cur.fetchall()
    collect.refresh_quotes(conn, client, everything, NOW)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD','2026-10-27',0.9)")
    changed = collect.apply_prefilter(conn, NOW)
    assert changed == {'selected': 1, 'excluded': 2}
    with conn.cursor() as cur:
        cur.execute('SELECT id,status,excluded_reason FROM listings ORDER BY id')
        status = {r['id']: (r['status'], r['excluded_reason']) for r in cur.fetchall()}
    assert status[1][0] == 'selected' and status[2][0] == 'excluded' and 'liquidité' in status[2][1]
    # DVDG.DE n'est plus collecté ...
    assert {r['listing_id'] for r in rows_of(conn)} == {1}
    # ... sauf s'il est détenu
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users(id,username,pass_hash,created_at) VALUES (1,'u','x',NOW())")
        cur.execute("INSERT INTO portfolios(id,user_id,name,created_at,updated_at) VALUES (1,1,'P',NOW(),NOW())")
        cur.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,trade_at,created_at) VALUES (1,2,'DVDG.DE','buy',1,42,NOW(),NOW())")
    conn.commit()
    got = {r['listing_id']: r['held'] for r in rows_of(conn)}
    assert got == {1: 0, 2: 1}
    # une exclusion persiste après un nouvel appel (idempotent)
    assert collect.apply_prefilter(conn, NOW) == {'selected': 0, 'excluded': 0}


def test_daily_skips_unsettled_session(conn):
    rows = [{'listing_id': 1, 'mic': 'XETR', 'symbol': 'LIQ.DE'}]
    early = datetime.datetime(2026, 10, 27, 15, 0, tzinfo=UTC)        # 16h Berlin : séance du jour non publiée
    client = FakeYahoo(daily={'LIQ.DE': ('Europe/Berlin', [(datetime.date(2026, 10, 26), 100.0), (datetime.date(2026, 10, 27), 101.0)])})
    collect.collect_daily(conn, client, rows, early)
    with conn.cursor() as cur:
        cur.execute('SELECT price_date FROM daily_prices')
        assert [r['price_date'] for r in cur.fetchall()] == [datetime.date(2026, 10, 26)]
    collect.collect_daily(conn, client, rows, NOW)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM daily_prices')
        assert cur.fetchone()['n'] == 2


def test_intraday_final_never_overwritten_by_provisional_and_latest_follows(conn):
    rows = [{'listing_id': 1, 'mic': 'XETR', 'symbol': 'LIQ.DE'}]
    slot = datetime.datetime(2026, 10, 27, 9, 0)
    now1 = datetime.datetime(2026, 10, 27, 9, 20, tzinfo=UTC)         # créneau 9h00 terminé
    collect.collect_intraday(conn, FakeYahoo(intraday={'LIQ.DE': ('UTC', [(slot + datetime.timedelta(minutes=14), 100.0)])}), rows, now1)
    now0 = datetime.datetime(2026, 10, 27, 9, 5, tzinfo=UTC)          # relecture « en retard » : créneau encore ouvert
    collect.collect_intraday(conn, FakeYahoo(intraday={'LIQ.DE': ('UTC', [(slot + datetime.timedelta(minutes=2), 77.0)])}), rows, now0)
    with conn.cursor() as cur:
        cur.execute('SELECT close_px,is_final FROM intraday_prices')
        r = cur.fetchone()
        assert float(r['close_px']) == 100.0 and r['is_final'] == 1
        cur.execute('SELECT price,source FROM latest_prices WHERE listing_id=1')
        assert cur.fetchone()['source'] == 'intraday'


def test_gap_detection_ignores_holidays_and_repairs(conn):
    from engine.market import catchup
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='selected' WHERE id=1")
    conn.commit()
    rows = [{'listing_id': 1, 'mic': 'XETR', 'symbol': 'LIQ.DE'}]
    day = datetime.date(2026, 10, 26)                                  # lundi
    full = [(datetime.datetime(2026, 10, 26, 8, 0) + datetime.timedelta(minutes=15 * i), 100.0 + i) for i in range(34)]
    collect.collect_intraday(conn, FakeYahoo(intraday={'LIQ.DE': ('UTC', full[:10])}), rows, NOW, range_='5d')
    assert day in collect.session_gaps(conn, 'XETR', NOW)               # séance incomplète : trou ; les autres jours (sans barre ni clôture) sont fériés, pas des trous
    assert [t['sessions'] for t in catchup.plan_intraday(conn, NOW)] == [[day]]
    catchup.execute(conn, FakeYahoo(intraday={'LIQ.DE': ('UTC', full)}), catchup.plan_intraday(conn, NOW), NOW, lambda *a: None)
    with conn.cursor() as cur:
        cur.execute('SELECT state FROM price_gaps WHERE session_date=%s', (day,))
        assert cur.fetchone()['state'] == 'repaired'
    assert day not in collect.session_gaps(conn, 'XETR', NOW)


def test_stale_quote_is_excluded_only_when_the_filter_is_applied(conn):
    """Les cours figés (titre mort) sont écartés par « Filtrer », jamais en silence ; le motif et le seuil sont exacts."""
    old = datetime.datetime(2021, 9, 30, 9, 27)
    with conn.cursor() as cur:
        cur.execute('SELECT id AS listing_id, mic, symbol FROM listings')
        everything = cur.fetchall()
    collect.refresh_quotes(conn, FakeYahoo(quotes=quotes()), everything, NOW)
    with conn.cursor() as cur:
        cur.execute("UPDATE latest_prices SET price_time=%s WHERE listing_id=1", (old,))
        cur.execute("SELECT status FROM listings WHERE id=1")
        assert cur.fetchone()['status'] == 'candidate'                       # rien n'a changé tant que le filtre n'est pas relancé
    conn.commit()
    collect.apply_prefilter(conn, NOW)
    with conn.cursor() as cur:
        cur.execute("SELECT status, excluded_reason FROM listings WHERE id=1")
        r = cur.fetchone()
    assert r['status'] == 'excluded' and 'dernier cours trop ancien' in r['excluded_reason']
