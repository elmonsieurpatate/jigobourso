import csv
import datetime
import os
import pytest
from engine.shared.db import connect
from engine.shared import settings
from engine.catalogue import loader
from engine.analytics import funnel, adminsvc
from engine.jobs import schedule, tasks
from engine.jobs.runner import run_job
from engine.market import collect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=datetime.timezone.utc)
FIELDS = ('symbol', 'name', 'mic', 'isin', 'currency', 'delisted', 'sector', 'country')
EQUITIES = [
    ('LIQ.DE', 'Liquide SE', 'XETR', 'DE0000000001', 'EUR', 'False', 'Tech', 'Germany'),
    ('OLD.DE', 'Vieille SE', 'XETR', 'DE0000000002', 'EUR', 'True', 'Tech', 'Germany'),
    ('WRT.DE', 'Machin Warrants', 'XETR', 'DE0000000003', 'EUR', 'False', 'Tech', 'Germany'),
    ('FAR.T', 'Loin KK', 'XTKS', 'JP0000000004', 'JPY', 'False', 'Tech', 'Japan'),
    ('SPC.DE', 'Foo Acquisition Corp', 'XETR', 'DE0000000005', 'EUR', 'False', 'Fin', 'Germany'),
]


@pytest.fixture
def conn(tmp_path):
    c = connect()
    reset_data(c)
    (tmp_path / 'database' / 'equities').mkdir(parents=True)
    (tmp_path / 'database' / 'etfs').mkdir(parents=True)
    with (tmp_path / 'database' / 'equities' / 'a.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        w.writerows(EQUITIES)
        w.writerow(('LIQ.DE', 'Liquide SE', 'XETR', 'DE0000000001', 'EUR', 'False', 'Tech', 'Germany'))      # doublon
    with (tmp_path / 'database' / 'etfs' / 'a.csv').open('w', newline='') as fh:
        csv.writer(fh).writerows([('symbol', 'name', 'mic', 'isin', 'currency', 'delisted', 'category_group'), ('ETF.DE', 'Bon ETF', 'XETR', 'IE0000000006', 'EUR', 'False', 'Equity')])
    c.root = str(tmp_path)
    yield c
    c.close()


def stats(steps):
    return {s['key']: (s['before'], s['removed'], s['kept']) for s in steps}


def test_filter_change_applies_without_redownload(conn):
    assert loader.store_raw(conn, conn.root) == 7
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    first = stats(funnel.catalogue_funnel(conn))
    assert first['raw'][2] == 7
    assert first['duplicates'][1] == 1 and first['delisted'][1] == 1 and first['warrants'][1] == 1 and first['spac'][1] == 1 and first['markets'][1] == 1
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM listings WHERE symbol='OLD.DE' AND status='excluded'")
        assert cur.fetchone()['n'] == 1
    # le titre radié est réadmis en désactivant la règle : aucun fichier relu
    cfg = settings.catalogue_rules(conn)
    cfg['delisted']['enabled'] = False
    adminsvc.rules_save(conn, 'catalogue', cfg)
    assert adminsvc._level(conn, 'catalogue')['pending'] is True
    os.remove(os.path.join(conn.root, 'database', 'equities', 'a.csv'))
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    second = stats(funnel.catalogue_funnel(conn))
    assert second['delisted'][1] == 0
    assert second['to_yahoo'][2] == first['to_yahoo'][2] + 1
    assert adminsvc._level(conn, 'catalogue')['pending'] is False
    items = funnel.items(conn, 'catalogue', 'warrants')
    assert [r['symbol'] for r in items['rows']] == ['WRT.DE']
    why = funnel.explain(conn, 'FAR.T')
    assert 'markets' in str(why)


def test_held_listing_never_deleted_and_invalid_rule_rejected(conn):
    loader.store_raw(conn, conn.root)
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM listings WHERE symbol='LIQ.DE'")
        lid = cur.fetchone()['id']
        cur.execute("INSERT INTO users(id,username,pass_hash,is_admin,active,created_at) VALUES (1,'u','x',0,1,NOW())")
        cur.execute("INSERT INTO portfolios(id,user_id,name,created_at,updated_at) VALUES (1,1,'p',NOW(),NOW())")
        cur.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,trade_at,created_at) VALUES (1,%s,'LIQ.DE','buy',1,10,'2026-10-01 10:00:00',NOW())", (lid,))
    conn.commit()
    cfg = settings.catalogue_rules(conn)
    cfg['markets']['values'] = ['XPAR']
    adminsvc.rules_save(conn, 'catalogue', cfg)
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM listings WHERE id=%s', (lid,))
        assert cur.fetchone()['status'] == 'excluded'
    with pytest.raises(ValueError):
        adminsvc.rules_save(conn, 'catalogue', {'markets': {'values': ['bad mic!']}})
    with pytest.raises(ValueError):
        adminsvc.rules_save(conn, 'prefilter', {'price': {'min_eur': -1}})


def test_prefilter_change_updates_funnel_and_items(conn):
    loader.store_raw(conn, conn.root)
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='candidate', is_primary=1 WHERE symbol IN ('LIQ.DE','ETF.DE')")
        cur.execute("INSERT INTO latest_prices(listing_id,source,price,currency,avg_volume_3m,quote_at,price_time) SELECT id,'quote',50,'EUR',IF(symbol='LIQ.DE',100,1000000),NOW(),NOW() FROM listings WHERE symbol IN ('LIQ.DE','ETF.DE')")
    conn.commit()
    collect.apply_prefilter(conn)
    before = stats(funnel.yahoo_funnel(conn))
    assert before['liquidity'][1] == 1                      # LIQ.DE : 50 × 100 = 5 000 €/jour
    cfg = settings.prefilter_rules(conn)
    cfg['liquidity_equity']['min_eur'] = 1000.0
    adminsvc.rules_save(conn, 'prefilter', cfg)
    job = run_job(conn, 'yahoo_filter', lambda log: tasks.yahoo_filter(conn, log), trigger='admin')
    after = stats(funnel.yahoo_funnel(conn))
    assert after['liquidity'][1] == 0
    detail = adminsvc.job_detail(conn, job)
    assert detail['steps'] and detail['funnels']['yahoo']
    assert funnel.last_run(conn, 'yahoo')['run']['job_id'] == job


def test_catalogue_filter_requires_raw_and_schedule_is_honest(conn):
    with pytest.raises(RuntimeError):
        tasks.fdb_filter(conn, lambda *a: None)
    state = schedule.state(conn, NOW.replace(tzinfo=None))
    assert state['cron']['state'] == 'never'
    assert all(t['state'] != 'ok' for t in state['tasks'])
    assert state['cron']['observed'] is False and state['diagnosis']
    schedule.beat(conn, NOW, 'admin')                       # un test manuel ne prouve pas que le cron tourne
    assert schedule.state(conn, NOW.replace(tzinfo=None))['cron']['observed'] is False
    schedule.beat(conn, NOW, 'cron')
    assert schedule.state(conn, NOW.replace(tzinfo=None))['cron']['observed'] is True
    settings.put(conn, 'schedule', schedule.normalize({'daily': {'enabled': False}}))
    assert next(t for t in schedule.state(conn, NOW.replace(tzinfo=None))['tasks'] if t['id'] == 'daily')['state'] == 'inactive'


def test_yahoo_items_listing_with_and_without_filter(conn):
    loader.store_raw(conn, conn.root)
    loader.apply_rules(conn)
    loader.sync_listings(conn)
    for step in ('asked', 'price', 'liquidity', 'final'):
        assert funnel.items(conn, 'yahoo', step)['total'] >= 0
        assert funnel.items(conn, 'yahoo', step, q='etf', kind='etf')['total'] >= 0
