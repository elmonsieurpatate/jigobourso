"""P0 avec MariaDB jetable et le vrai service Explorer, sans fournisseur réseau."""
import os

import pytest

from engine.analytics import compute, explorer_config as C, service, strategy
from engine.analytics.explorer_metrics import load
from engine.market import collect
from engine.market.calendar import session_dates
from engine.shared.db import connect
from tests.fakes import FakeYahoo
from tests.integ.test_tracking_cache import seed, NOW

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable explicitement requise', allow_module_level=True)


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setattr(service.hours, 'utcnow', lambda: NOW)
    c = connect()
    seed(c)
    yield c
    c.close()


def test_sparse_history_cannot_reuse_an_old_stored_momentum(conn):
    ds = session_dates('XETR', '2026-10-27', 127)
    with conn.cursor() as q:
        q.execute('DELETE FROM daily_prices WHERE listing_id=1')
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)',
                      [(ds[0], 100), (ds[-22], 110), (ds[-1], 111)])
    conn.commit()
    compute.compute_all(conn, NOW)
    with conn.cursor() as q:
        q.execute('SELECT momentum_6m FROM series_state WHERE listing_id=1')
        assert q.fetchone()['momentum_6m'] is None
        # Simulate a stale value from the former endpoint-only implementation.
        q.execute('UPDATE series_state SET momentum_6m=10 WHERE listing_id=1')
    conn.commit()
    cfg = C.editable(strategy.preset('momentum'))
    request = dict(config=cfg, view=dict(tradable=False, status='all'))
    rows = service.explore(conn, request)['rows']
    row = next(r for r in rows if r['id'] == 1)
    assert row['status'] == 'unknown' and row['score'] is None
    assert service.explore(conn, request)['rows'] == rows  # Cache keeps the safe verdict.


def test_historical_configuration_sheet_never_fabricates_ma200(conn):
    # The former historical sheet asked for only 55 dates despite a complete
    # available history. It must now use the same 205-date technical window.
    with conn.cursor() as q:
        q.execute('UPDATE daily_prices SET close_px=100 WHERE listing_id=1')
    conn.commit()
    compute.compute_all(conn, NOW)
    with conn.cursor() as q:
        q.execute('SELECT ma200,ma200_prev FROM series_state WHERE listing_id=1')
        state = q.fetchone()
        assert float(state['ma200']) == 100 and float(state['ma200_prev']) == 100
    sheet = service.instrument_sheet(conn, dict(listing_id=1, config=strategy.preset('momentum_risk'),
                                               fetch_profile=False))
    assert sheet['technical']['ma200'] == 100
    assert sheet['technical']['ma200_prev'] == 100


def test_daily_collection_without_volumes_remains_explicitly_unavailable(conn):
    ds = session_dates('XETR', '2026-10-27', 6)
    with conn.cursor() as q:
        q.execute('DELETE FROM daily_prices WHERE listing_id=1')
    conn.commit()
    import datetime
    client = FakeYahoo(daily={'A.DE': ('Europe/Berlin', [(datetime.date.fromisoformat(d), 100) for d in ds])})
    collect.collect_daily(conn, client, [dict(listing_id=1, mic='XETR', symbol='A.DE')], NOW)
    with conn.cursor() as q:
        q.execute('SELECT volume FROM daily_prices WHERE listing_id=1')
        assert all(r['volume'] is None for r in q.fetchall())
    metric = load(conn, [dict(id=1, mic='XETR', currency='EUR')], [5], lambda c, m: ds[-1])[1][5]
    assert metric['avg_volume'] is None and metric['volume_observations'] == 0
    assert metric['volume_expected'] == 5 and metric['volume_coverage'] == 0
    assert metric['volume_source'] == 'daily_prices.volume'


@pytest.mark.parametrize('currency,base,rate', [('GBp', 'GBP', .5), ('GBX', 'GBP', .5),
                                               ('ZAc', 'ZAR', .05), ('ILA', 'ILS', .25)])
def test_historical_turnover_uses_common_subunit_conversion(conn, currency, base, rate):
    ds = session_dates('XETR', '2026-10-27', 6)
    with conn.cursor() as q:
        q.execute('DELETE FROM daily_prices WHERE listing_id=1')
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (1,%s,100,10)', [(d,) for d in ds])
        q.execute('INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES (%s,%s,%s)', (base, ds[0], rate))
    conn.commit()
    metric = load(conn, [dict(id=1, mic='XETR', currency=currency)], [5], lambda c, m: ds[-1])[1][5]
    assert metric['turnover_eur'] == pytest.approx(100 * 10 * rate / 100)
    assert metric['turnover_coverage'] == 1
