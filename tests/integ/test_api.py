"""API PHP de bout en bout : serveur PHP réel + base jetable. Authentification, cloisonnement, registre, droits, garantie « exclu »."""
import http.cookiejar
import json
import os
import socket
import sys
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, route, body=None, params='', origin=None):
        req = urllib.request.Request(f'{self.base}/api.php?r={route}{params}', data=json.dumps(body).encode() if body is not None else None,
                                     method='POST' if body is not None else 'GET', headers={'Content-Type': 'application/json'})
        if origin:
            req.add_header('Origin', origin)
        try:
            with self.opener.open(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode() or 'null')
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or 'null')


@pytest.fixture(scope='module')
def server():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', os.path.join(ROOT, 'app/public')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=dict(os.environ, JIGO_ENGINE_ROOT=ROOT, JIGO_PYTHON=sys.executable))
    for _ in range(50):
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.2).close(); break
        except OSError:
            time.sleep(0.1)
    yield f'http://127.0.0.1:{port}'
    proc.terminate()


@pytest.fixture
def world(server):
    conn = connect()
    reset_data(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:A.DE','equity','Alpha SE','Germany'),(2,'sym:XETR:DVDG.DE','etf','DVDG ETF',NULL)")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,excluded_reason,is_primary) VALUES (1,1,'XETR','A.DE','EUR','selected',NULL,1),(2,2,'XETR','DVDG.DE','EUR','excluded','préfiltre : liquidité',1)")
        cur.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (1,120,NOW(),'intraday','EUR'),(2,42,NOW(),'quote','EUR')")
    conn.commit()
    php = lambda *a: subprocess.run(['php', os.path.join(ROOT, 'scripts/create_user.php'), *a], capture_output=True, text=True, env=os.environ)
    assert php('alice', 'alice-secret-1234', '--admin').returncode == 0
    assert php('bob', 'bob-secret-12345').returncode == 0
    yield server
    conn.close()


def login(base, user, pw):
    c = Client(base)
    status, data = c.call('auth/login', {'username': user, 'password': pw})
    assert status == 200, data
    return c


def test_auth_required_and_login_lockout(world):
    anon = Client(world)
    assert anon.call('portfolios')[0] == 401
    assert anon.call('admin/users')[0] == 401
    for _ in range(5):
        assert anon.call('auth/login', {'username': 'alice', 'password': 'faux'})[0] == 401
    status, data = anon.call('auth/login', {'username': 'alice', 'password': 'alice-secret-1234'})
    assert status == 429                                    # verrouillé après 5 échecs, même avec le bon mot de passe


def test_admin_routes_forbidden_for_regular_user(world):
    bob = login(world, 'bob', 'bob-secret-12345')
    assert bob.call('admin/users')[0] == 403
    assert bob.call('admin/system')[0] == 403
    assert bob.call('admin/settings', {'name': 'invite_code', 'value': 'abcd'})[0] == 403


def test_origin_check_blocks_cross_site_write(world):
    alice = login(world, 'alice', 'alice-secret-1234')
    assert alice.call('portfolio/create', {'name': 'X'}, origin='https://evil.example')[0] == 403


def test_portfolios_are_isolated_between_users(world):
    alice, bob = login(world, 'alice', 'alice-secret-1234'), login(world, 'bob', 'bob-secret-12345')
    pf = alice.call('portfolio/create', {'name': 'Alice'})[1]['id']
    assert bob.call('portfolio', params=f'&id={pf}')[0] == 404
    assert bob.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 1, 'unit_price': 1, 'trade_at': '2026-10-01'})[0] == 404
    assert bob.call('portfolio/delete', {'id': pf})[0] == 404


def test_ledger_average_cost_partial_sale_and_oversell(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'P'})[1]['id']
    add = lambda side, q, p, fees=0, d='2026-10-01': a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': side, 'quantity': q, 'unit_price': p, 'fees': fees, 'trade_at': d})
    assert add('buy', 10, 100, 5)[0] == 200                 # coût 1005
    assert add('buy', 10, 110, 0, '2026-10-02')[0] == 200   # coût +1100 = 2105 pour 20
    status, data = add('sell', 25, 130)
    assert status == 422 and 'supérieure' in data['error']
    assert add('sell', 5, 130, 2, '2026-10-03')[0] == 200   # coût moyen 105,25 ; produit net 650-2 = 648 ; coût sorti 526,25
    v = a.call('portfolio', params=f'&id={pf}')[1]
    pos = v['positions'][0]
    assert abs(pos['qty'] - 15) < 1e-9 and abs(pos['avg_cost'] - 105.25) < 1e-6
    assert abs(v['totals']['realized'] - (648 - 526.25)) < 1e-6
    assert abs(pos['value'] - 15 * 120) < 1e-6 and abs(pos['unrealized'] - (1800 - 15 * 105.25)) < 1e-6
    assert abs(v['totals']['fees'] - 7) < 1e-9
    bilan = a.call('bilan')[1]['totals']
    assert abs(bilan['total_gain'] - (v['totals']['realized'] + v['totals']['unrealized'])) < 1e-6


def test_held_excluded_listing_stays_visible_but_is_never_ranked(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'P'})[1]['id']
    assert a.call('tx/add', {'portfolio_id': pf, 'listing_id': 2, 'side': 'buy', 'quantity': 1, 'unit_price': 42, 'trade_at': '2026-10-01'})[0] == 200
    pos = a.call('portfolio', params=f'&id={pf}')[1]['positions'][0]
    assert pos['catalogue_status'] == 'excluded' and pos['value'] == 42      # visible, valorisé, étiqueté « hors sélection »
    res = a.call('explore', {'preset': 'fast', 'view': {'q': 'DVDG', 'status': 'all'}})[1]
    row = res['rows'][0]
    assert row['status'] == 'excluded' and row['rank'] is None and row['held'] is True
    allrows = a.call('explore', {'preset': 'regular', 'view': {'status': 'all', 'page_size': 100}})[1]['rows']
    assert all(r['id'] != 2 for r in allrows)                                # absent de tout classement sans recherche explicite


def test_delete_portfolio_needs_confirmation(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Gros'})[1]['id']
    a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 1, 'unit_price': 1, 'trade_at': '2026-10-01'})
    assert a.call('portfolio/delete', {'id': pf})[0] == 422
    assert a.call('portfolio/delete', {'id': pf, 'confirm': 'Gros'})[0] == 200


def test_invalid_strategy_config_is_rejected(world):
    a = login(world, 'alice', 'alice-secret-1234')
    cfg = a.call('strategy/presets')[1]['presets']['regular']
    cfg['periods'][2]['sessions'] = 999
    assert a.call('strategy/validate', cfg)[0] == 422
