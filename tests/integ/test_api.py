"""API PHP de bout en bout : serveur PHP réel + base jetable. Authentification, cloisonnement, registre, droits, garantie « exclu »."""
import datetime
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

    def call(self, route, body=None, params='', origin=None, headers=None):
        req = urllib.request.Request(f'{self.base}/api.php?r={route}{params}', data=json.dumps(body).encode() if body is not None else None,
                                     method='POST' if body is not None else 'GET', headers={'Content-Type': 'application/json'})
        if origin != '':                                                  # Origin envoyée par défaut, comme un navigateur ; origin='' simule un client sans Origin ni Referer
            req.add_header('Origin', origin or self.base)
        for k, v in (headers or {}).items():
            req.headers.pop(k.capitalize(), None); req.add_header(k, v)
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


def test_saved_filter_preserves_search_visibility_and_status(world):
    a = login(world, 'alice', 'alice-secret-1234')
    config = a.call('strategy/presets')[1]['presets']['regular']
    view = {'q': '  VOO  ', 'tradable': False, 'status': 'all', 'kind': 'large_etf', 'geo_region': 'us', 'sort': 'perf', 'dir': 'desc', 'icon': '⚡', 'description': 'ETF rapides'}
    assert a.call('explorer/library/save', {'kind': 'search', 'name': 'ETF complets', 'payload': {'config': config, 'universe': view}})[0] == 200
    item = next(i for i in a.call('explorer/library')[1]['items'] if i['name'] == 'ETF complets')
    assert item['payload']['universe'] == {'q': 'VOO', 'tradable': False, 'status': 'all', 'kind': 'large_etf', 'geo_region': 'us', 'sort': 'perf', 'dir': 'desc', 'icon': '⚡', 'description': 'ETF rapides'}


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


def test_target_allocation_by_zone(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Prudent'})[1]['id']
    assert a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 10, 'unit_price': 100, 'trade_at': '2026-10-01'})[0] == 200
    alloc = a.call('portfolio', params=f'&id={pf}')[1]['allocation']
    assert alloc['target'] is None and {r['zone']: r['current_pct'] for r in alloc['rows']}['eu'] == 100      # Alpha SE : société allemande
    assert a.call('portfolio/target', {'id': pf, 'target': {'us': 50, 'eu': 25, 'emerging': 30}})[0] == 422
    assert a.call('portfolio/target', {'id': pf, 'target': {'us': 50, 'eu': 25, 'emerging': 25}})[0] == 200
    alloc = a.call('portfolio', params=f'&id={pf}')[1]['allocation']
    rows = {r['zone']: r for r in alloc['rows']}
    assert alloc['target'] == {'us': 50.0, 'eu': 25.0, 'emerging': 25.0} and alloc['rebalance_suggested']
    assert round(rows['us']['gap_eur']) == 600 and round(rows['eu']['gap_eur']) == -900                    # valeur 1 200 € (cours 120)
    bob = login(world, 'bob', 'bob-secret-12345')
    assert bob.call('portfolio/target', {'id': pf, 'target': None})[0] == 404
    assert a.call('portfolio/target', {'id': pf, 'target': None})[0] == 200
    assert a.call('portfolio', params=f'&id={pf}')[1]['allocation']['target'] is None


def test_lot_alerts_follow_each_purchase(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Alertes'})[1]['id']
    add = lambda side, q, p, d: a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': side, 'quantity': q, 'unit_price': p, 'trade_at': d})
    add('buy', 10, 100, '2026-03-02')
    second = add('buy', 5, 140, '2026-06-01')[1]['id']
    sale = add('sell', 12, 130, '2026-07-01')[1]['id']
    conn = connect()
    with conn.cursor() as cur:
        days = [datetime.date(2026, 5, 1) + datetime.timedelta(days=i) for i in range(120)]
        closes = [150.0 if d == datetime.date(2026, 6, 10) else 110.0 if d >= datetime.date(2026, 8, 1) else 130.0 for d in days]
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)', list(zip(days, closes)))
    conn.commit(); conn.close()
    d = a.call('portfolio', params=f'&id={pf}')[1]
    assert [(l['tx_id'], round(l['remaining'], 6)) for l in d['lots']] == [(second, 3.0)]          # FIFO : la vente de 12 solde le 1er achat et entame le 2e
    curve = d['curves']['1']
    assert curve['buys'] == ['2026-06-01'] and curve['points'][0][0] == '2026-06-01' and curve['points'][-1][1] == 110.0 and len(curve['points']) <= 90
    lot = d['lots'][0]['alert']
    assert lot['strategy'] == 'regular' and round(lot['measures']['drop_pct'], 1) == 26.7
    assert lot['risk']['level'] == 'na' and lot['risk']['reason'] == 'history'                         # peu de clôtures : barre non évaluée, jamais une fausse alerte
    kinds = {x['kind'] for x in lot['alerts']}
    assert 'drop' in kinds and ('duration' in kinds) == ((datetime.date.today() - datetime.date(2026, 6, 1)).days >= 182) and lot['level'] == 'watch'
    assert 'momentum' in d['lot_strategies'] and d['lot_strategies']['prudent'].startswith('Prudente')
    assert a.call('lot/settings', {'tx_id': second, 'strategy': 'nope'})[0] == 422
    assert a.call('lot/settings', {'tx_id': second, 'alert_drop_pct': 120})[0] == 422
    assert a.call('lot/settings', {'tx_id': sale, 'strategy': 'momentum'})[0] == 404                 # une vente n'a pas de réglages d'achat
    assert login(world, 'bob', 'bob-secret-12345').call('lot/settings', {'tx_id': second, 'strategy': 'momentum'})[0] == 404
    assert a.call('lot/settings', {'tx_id': second, 'strategy': 'momentum', 'alert_drop_pct': '30', 'alert_days': ''})[0] == 200
    lot = a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]
    assert lot['settings'] == {'strategy': 'momentum', 'alert_days': None, 'alert_drop_pct': 30.0, 'alerts_off': False}
    assert lot['alert']['strategy'] == 'momentum' and lot['alert']['own_strategy'] and 'drop' not in {x['kind'] for x in lot['alert']['alerts']}
    assert a.call('lot/settings', {'tx_id': second, 'alerts_off': True})[0] == 200
    assert a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['alert']['alerts'] == []
    assert a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['alert']['risk'] is None              # alertes désactivées : pas de barre
    assert a.call('lot/settings', {'tx_id': second})[0] == 200                                        # tout vide : retour aux réglages par défaut
    assert a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['settings'] is None


def test_history_and_sales_survive_a_full_sale(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Histo'})[1]['id']
    add = lambda side, q, p, d: a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': side, 'quantity': q, 'unit_price': p, 'trade_at': d, 'fees': 1})
    assert add('buy', 10, 100, '2026-05-04')[0] == 200 and add('sell', 10, 120, '2026-05-06')[0] == 200
    conn = connect()
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (1,%s,%s)', [('2026-05-04', 100), ('2026-05-05', 110), ('2026-05-06', 120), ('2026-05-07', 90)])
    conn.commit(); conn.close()
    h = a.call('portfolio/history', params=f'&id={pf}')[1]
    assert h['dates'][:4] == ['2026-05-04', '2026-05-05', '2026-05-06', '2026-05-07']
    assert h['value'][:4] == [1000.0, 1100.0, 0.0, 0.0] and h['gain'][1] == 1099.0 - 1000 and h['gain'][-1] == 198.0       # 1 199 − 1 001
    d = a.call('portfolio', params=f'&id={pf}')[1]
    assert d['positions'] == [] and [(round(s['gain'], 2), s['quantity']) for s in d['sales']] == [(198.0, 10.0)]
    assert login(world, 'bob', 'bob-secret-12345').call('portfolio/history', params=f'&id={pf}')[0] == 404


def test_week_bars_of_15_minutes(world):
    a = login(world, 'alice', 'alice-secret-1234')
    conn = connect()
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (1,%s,%s,1)',
                        [('2026-10-01 09:00:00', 1), ('2026-10-20 09:00:00', 2), ('2026-10-27 09:00:00', 3), ('2026-10-27 09:15:00', 4)])
    conn.commit(); conn.close()
    assert a.call('bars15', params='&id=1')[1]['bars'] == [['2026-10-20T09:00:00', 2.0], ['2026-10-27T09:00:00', 3.0], ['2026-10-27T09:15:00', 4.0]]
