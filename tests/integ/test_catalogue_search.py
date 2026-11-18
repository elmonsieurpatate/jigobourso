"""Résolution des cotations par l'identité produit, sans changer leur admission ni leurs notes."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from engine.analytics.admin import adminsvc
from engine.analytics.explorer import funnel
from engine.shared.db import connect
from tests.integ.test_api import login, server as server, world as world

pytestmark = pytest.mark.integration


@pytest.fixture
def catalogue(world):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO instruments(id,group_key,isin,kind,name) VALUES (3,'isin:LU1812092168','LU1812092168','etf','Produit de test'),(4,'isin:LU0000000001','LU0000000001','etf','Produit de test')"
        )
        cur.execute(
            "INSERT INTO listings(id,instrument_id,mic,symbol,status,is_primary,excluded_reason) VALUES (3,3,'XPAR','TEST.PA','selected',1,NULL),(4,3,'XETR','TEST.DE','excluded',0,'préfiltre : liquidité'),(5,4,'XLON','OTHER.L','selected',1,NULL)"
        )
        for mic, symbol, step in [('XPAR', 'TEST.PA', None), ('XETR', 'TEST.DE', None), ('XLON', 'TEST.L', 'markets')]:
            cur.execute(
                'INSERT INTO catalogue_raw(kind,mic,symbol,isin,name,group_key,removed_step) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                ('etf', mic, symbol, 'LU1812092168', 'Produit de test', 'isin:LU1812092168', step),
            )
    conn.commit()
    yield conn, login(world, 'alice', 'alice-secret-1234')
    conn.close()


@pytest.mark.parametrize('term', ['LU1812092168', 'TEST.DE', 'TEST.L', 'test.de'])
def test_secondary_and_raw_alias_find_retained_product(catalogue, term):
    conn, client = catalogue
    status, data = client.call('listings/search', params='&q=' + term)
    assert status == 200, data
    assert {r['id'] for r in data['results']} <= {3, 4}  # aucun rapprochement par ressemblance de nom
    assert data['results']
    for row in data['results']:
        assert row['primary']['id'] == 3 and row['primary']['symbol'] == 'TEST.PA'
        assert row['primary']['in_catalogue'] is True
        assert row['in_catalogue'] is (row['id'] == 3)
    with conn.cursor() as cur:
        cur.execute('SELECT status,is_primary FROM listings WHERE id=4')
        assert cur.fetchone() == {'status': 'excluded', 'is_primary': 0}  # la recherche ne réadmet rien


def test_admin_distinguishes_admitted_listing_and_retained_product(catalogue):
    conn, _ = catalogue
    rows = {r['symbol']: r for r in adminsvc.titles(conn, {'q': 'LU1812092168'})['rows']}
    assert rows['TEST.PA']['in_final'] is True
    assert rows['TEST.DE']['fdb_state'] == 'kept' and rows['TEST.DE']['in_final'] is False
    assert rows['TEST.DE']['primary']['id'] == 3
    assert rows['TEST.L']['fdb_state'] == 'removed' and rows['TEST.L']['primary']['id'] == 3


def test_held_excluded_listing_is_followed_but_not_in_final_catalogue(catalogue):
    conn, _ = catalogue
    with conn.cursor() as cur:
        cur.execute("INSERT INTO portfolios(user_id,name,created_at,updated_at) SELECT id,'Test',NOW(),NOW() FROM users WHERE username='alice'")
        pid = cur.lastrowid
        cur.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,trade_at,created_at) VALUES (%s,4,'TEST.DE','buy',1,100,NOW(),NOW())", (pid,))
    conn.commit()
    row = adminsvc.titles(conn, {'q': 'TEST.DE'})['rows'][0]
    assert row['held'] is True and row['in_final'] is False
    assert row['primary']['in_catalogue'] is True
    assert row['d_state'] == 'absent'


def test_read_only_inspection_reports_raw_and_imported_alternatives(catalogue):
    import base64

    conn, _ = catalogue
    script = Path(__file__).resolve().parents[2] / 'scripts/release/inspect_catalogue.php'
    result = subprocess.run(['php', str(script)], capture_output=True, text=True, check=True, env={**os.environ, 'JIGO_CATALOGUE_QUERY_B64': base64.b64encode(b'LU1812092168').decode()})
    rows = json.loads(result.stdout)['rows']
    assert {r['symbol'] for r in rows} == {'TEST.PA', 'TEST.DE', 'TEST.L'}
    assert all(r['primary_symbol'] == 'TEST.PA' for r in rows)
    assert next(r for r in rows if r['symbol'] == 'TEST.L')['id'] is None


def test_explain_links_secondary_raw_listing_to_primary(catalogue):
    conn, _ = catalogue
    report = funnel.explain(conn, 'TEST.L')
    row = report['results'][0]
    assert row['raw']['symbol'] == 'TEST.L'
    assert row['primary'] == {'id': 3, 'symbol': 'TEST.PA', 'mic': 'XPAR', 'in_catalogue': True}


@pytest.mark.parametrize('term', ['TEST.DE', 'TEST.L'])
def test_admin_catalogue_primary_filter_resolves_alias(catalogue, term):
    _, client = catalogue
    status, data = client.call('admin/catalogue', params='&primary=1&q=' + term)
    assert status == 200, data
    assert [r['symbol'] for r in data['rows']] == ['TEST.PA']


def test_secondary_lookup_still_resolves_without_raw_source(catalogue):
    conn, client = catalogue
    with conn.cursor() as cur:
        cur.execute('DELETE FROM catalogue_raw')
    conn.commit()
    status, data = client.call('listings/search', params='&q=TEST.DE')
    assert status == 200
    assert {r['id'] for r in data['results']} == {3, 4}
    assert all(r['primary']['id'] == 3 for r in data['results'])


def test_lu1812092168_secondary_candidates_and_filtered_venues(catalogue):
    """États réels observés le 17/11/2026, reproduits sans prix ni données de compte réelles."""
    conn, client = catalogue
    alternatives = [
        ('SELD.DE', 'XETR', None),
        ('SEL.PA', 'XPAR', None),
        ('SEL.MI', 'XMIL', None),
        ('LYSEL.SW', 'XSWX', None),
        ('SELD.BE', 'XBER', 'markets'),
        ('SELD.DU', 'XDUS', 'markets'),
        ('SELD.F', 'XFRA', 'markets'),
        ('SELD.MU', 'XMUN', 'markets'),
    ]
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET symbol='SELD.DE',mic='XETR' WHERE id=3")
        cur.execute("UPDATE listings SET symbol='SEL.PA',mic='XPAR',status='candidate',excluded_reason=NULL WHERE id=4")
        cur.execute('DELETE FROM catalogue_raw')
        for symbol, mic, step in alternatives:
            cur.execute(
                'INSERT INTO catalogue_raw(kind,mic,symbol,isin,name,group_key,removed_step) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                ('etf', mic, symbol, 'LU1812092168', 'Produit de test', 'isin:LU1812092168', step),
            )
    conn.commit()
    for term in ['LU1812092168', *(s for s, _, _ in alternatives)]:
        status, data = client.call('listings/search', params='&q=' + term)
        assert status == 200, data
        assert data['results'], term
        assert all(r['primary']['symbol'] == 'SELD.DE' and r['primary']['in_catalogue'] for r in data['results']), term
        assert next(r for r in data['results'] if r['id'] == 3)['in_catalogue'] is True
    row = adminsvc.titles(conn, {'q': 'SEL.PA'})['rows'][0]
    assert row['fdb_state'] == 'kept' and row['y_state'] == 'secondary'
    assert row['in_final'] is False and row['primary']['in_catalogue'] is True


def test_actions_etf_http_search_does_not_keep_unrelated_rows(catalogue):
    _, client = catalogue
    status, data = client.call('admin/titles', params='&q=LU1812092168')
    assert status == 200, data
    assert data['total'] == 3
    assert {r['symbol'] for r in data['rows']} == {'TEST.PA', 'TEST.DE', 'TEST.L'}
    assert all(r['isin'] == 'LU1812092168' for r in data['rows'])
    status, data = client.call('admin/titles', params='&q=LU9999999999')
    assert status == 200, data
    assert data['total'] == 0 and data['rows'] == []


def test_actions_etf_can_return_partial_intraday_without_hiding_the_title(catalogue):
    from engine.market import hours, intraday

    conn, client = catalogue
    day = hours.session_date('XPAR', hours.utcnow())
    start, _ = intraday.session_window('XPAR', day)
    with conn.cursor() as cur:
        cur.execute('INSERT INTO intraday_prices(listing_id,slot_start,close_px) VALUES (3,%s,100)', (start,))
    conn.commit()
    status, data = client.call('admin/titles', params='&q=LU1812092168')
    assert status == 200, data
    primary = next(r for r in data['rows'] if r['lid'] == 3)
    assert primary['in_final'] is True and primary['intraday_state'] == 'partial'


def test_financedatabase_and_yahoo_rows_link_to_the_retained_product(catalogue):
    conn, _ = catalogue
    rows = {r['symbol']: r for r in funnel.items(conn, 'catalogue', 'raw', q='LU1812092168')['rows']}
    assert rows['TEST.PA']['id'] == 3 and rows['TEST.PA']['sheet_id'] == 3
    assert rows['TEST.DE']['id'] == 4 and rows['TEST.DE']['sheet_id'] == 3
    assert rows['TEST.L']['id'] is None and rows['TEST.L']['sheet_id'] == 3
    assert rows['TEST.L']['sheet_redirected'] and rows['TEST.DE']['sheet_redirected']
    assert all(r['sheet_symbol'] == 'TEST.PA' for r in rows.values())
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='candidate',excluded_reason=NULL WHERE id=4")
    conn.commit()
    secondary = funnel.items(conn, 'yahoo', 'secondary', q='TEST.DE')['rows']
    assert secondary[0]['id'] == 4 and secondary[0]['sheet_id'] == 3


def test_sheet_exposes_five_years_and_keeps_volumes_aligned(catalogue, monkeypatch):
    from engine.analytics.admin import title_sheet
    from engine.market.calendar import session_dates

    conn, _ = catalogue
    days = session_dates('XPAR', '2026-11-17', 1261)
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (3,%s,%s,%s)', [(d, 100 + i / 100, 1000 + i) for i, d in enumerate(days)])
    conn.commit()
    monkeypatch.setattr(title_sheet, 'expected_close', lambda *_: '2026-11-17')
    sheet = title_sheet.instrument_sheet(conn, {'listing_id': 3, 'config': 'regular'})
    assert len(sheet['daily']) == len(sheet['daily_raw']) == len(sheet['daily_volume']) == 1261
    assert sheet['daily'][0][0] == days[0] and sheet['daily_volume'][0] == 1000
    assert sheet['daily_volume'][-1] == 2260
    assert sheet['measures']['756']['perf'] is not None and sheet['measures']['1260']['perf'] is not None
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE listing_id=3 AND price_date<%s', (days[-696],))
    conn.commit()
    short = title_sheet.instrument_sheet(conn, {'listing_id': 3, 'config': 'regular'})
    assert len(short['daily']) == 696  # aucune nouvelle troncature à 400
    assert short['measures']['756'] is None or short['measures']['756'].get('perf') is None
    assert short['window_coverage']['756']['observations'] == 696
