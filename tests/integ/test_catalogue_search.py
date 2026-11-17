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
