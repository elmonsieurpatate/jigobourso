"""Correctifs de l'audit du 29/10/2026 : bornes des montants, limites de connexion et d'inscription, export CSV, mode strict, verrou de traitement, purge."""
import datetime as dt
import os
import subprocess

import pytest

from engine.jobs import tasks
from engine.jobs.runner import run_job
from engine.shared.db import connect
from tests.integ.test_api import Client, ROOT, login, server, world  # noqa: F401

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


def new_portfolio(c):
    return c.call('portfolio/create', {'name': 'Audit'})[1]['id']


def tx(c, pf, **over):
    body = {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 1, 'unit_price': 100, 'trade_at': '2026-10-01'}
    return c.call('tx/add', dict(body, **over))


def test_amounts_are_bounded_before_reaching_the_database(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    for field in ("quantity", "unit_price", "fees"):
        status, data = tx(a, pf, **{field: 1e15})
        assert status == 400 and 'trop grand' in data['error'], field
    assert tx(a, pf)[0] == 200


def test_currency_must_be_text(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, currency=['EUR'])[0] == 422


def test_login_lockout_hits_the_failing_ip_not_every_user(world):
    anon = Client(world)
    for _ in range(5):
        assert anon.call('auth/login', {'username': 'alice', 'password': 'faux'})[0] == 401
    assert anon.call('auth/login', {'username': 'alice', 'password': 'alice-secret-1234'})[0] == 429
    assert Client(world).call('auth/login', {'username': 'bob', 'password': 'bob-secret-12345'})[0] == 200     # un autre compte n'est pas touché


def test_registration_code_attempts_are_limited_with_a_short_key(world):
    a = login(world, 'alice', 'alice-secret-1234')
    assert a.call('admin/settings', {'name': 'invite_code', 'value': 'bonjour1'})[0] == 200
    anon = Client(world)
    for _ in range(5):
        assert anon.call('auth/register', {'username': 'carol', 'password': 'carol-secret-1234', 'code': 'faux'})[0] == 403
    assert anon.call('auth/register', {'username': 'carol', 'password': 'carol-secret-1234', 'code': 'bonjour1'})[0] == 429
    c = connect()
    with c.cursor() as q:
        q.execute("SELECT MAX(CHAR_LENGTH(username)) n FROM login_attempts")
        assert q.fetchone()['n'] <= 30
    c.close()


def test_csv_export_neutralises_spreadsheet_formulas(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, note='=HYPERLINK("http://evil.example")')[0] == 200
    with a.opener.open(f'{world}/api.php?r=export&id={pf}', timeout=30) as r:
        body = r.read().decode()
    assert "'=HYPERLINK" in body and '\n=HYPERLINK' not in body and ',=HYPERLINK' not in body


def test_pdo_session_is_strict(world):
    code = "require " + repr(ROOT + '/app/lib/db.php') + "; echo q('SELECT @@sql_mode')->fetchColumn();"
    out = subprocess.run(['php', '-r', code], capture_output=True, text=True, env=os.environ)
    assert 'STRICT_TRANS_TABLES' in out.stdout, out.stderr


def test_admin_flags_are_parsed_as_booleans(world):
    a = login(world, 'alice', 'alice-secret-1234')
    bob = a.call('admin/users')[1]['users']; bob = next(u for u in bob if u['username'] == 'bob')
    assert a.call('admin/user/update', {'id': bob['id'], 'is_admin': 'false'})[0] == 200
    assert next(u for u in a.call('admin/users')[1]['users'] if u['username'] == 'bob')['is_admin'] == 0
    assert a.call('admin/user/update', {'id': bob['id'], 'is_admin': 'peut-être'})[0] == 422


def test_a_job_type_cannot_start_twice_at_the_same_time(world):
    holder, c = connect(), connect()
    try:
        with holder.cursor() as q:
            q.execute("SELECT GET_LOCK('jigo:job:audit', 0)")
        called = []
        assert run_job(c, 'audit', lambda log: called.append(1) or (0, 0, 'x')) is None and not called    # un autre processus est en train de démarrer ce type
        with holder.cursor() as q:
            q.execute("SELECT RELEASE_LOCK('jigo:job:audit')")
        assert run_job(c, 'audit', lambda log: called.append(1) or (0, 0, 'x')) is not None and called
    finally:
        holder.close(); c.close()


def test_housekeeping_purges_only_what_is_old_or_expired(world):
    c = connect(); now = dt.datetime(2026, 10, 29, 12, 0)
    old, fresh = now - dt.timedelta(days=3), now - dt.timedelta(minutes=5)
    with c.cursor() as q:
        q.execute("INSERT INTO login_attempts(username,ip,at) VALUES ('x','1',%s),('y','1',%s)", (old, fresh))
        q.execute("INSERT INTO account_attempts(scope_hash,at) VALUES (REPEAT('a',64),%s),(REPEAT('b',64),%s)", (old, fresh))
        q.execute("SELECT id FROM users LIMIT 1"); uid = q.fetchone()['id']
        q.execute("INSERT INTO sessions(token_hash,user_id,created_at,last_seen,expires_at) VALUES (REPEAT('1',64),%s,%s,%s,%s),(REPEAT('2',64),%s,%s,%s,%s)",
                  (uid, old, old, now - dt.timedelta(days=1), uid, fresh, fresh, now + dt.timedelta(days=1)))
        q.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at) VALUES ('t','cron','completed',%s),('t','cron','completed',%s),('t','cron','running',%s)",
                  (now - dt.timedelta(days=200), fresh, now - dt.timedelta(days=200)))
    c.commit()
    done = tasks.housekeeping(c, now)
    assert done['login_attempts'] == 1 and done['account_attempts'] == 1 and done['sessions'] == 1 and done['jobs'] == 1
    with c.cursor() as q:
        q.execute("SELECT COUNT(*) n FROM jobs WHERE status='running'"); assert q.fetchone()['n'] == 1       # un traitement en cours n'est jamais purgé
    c.close()


def confirmed_split(c, listing, day, ratio):
    with c.cursor() as q:
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (%s,%s,%s,%s,'confirmed',NOW())", (listing, day, 1 / ratio, ratio))
    c.commit()


def position(a, pf):
    return a.call('portfolio', params=f'&id={pf}')[1]['positions'][0]


def test_confirmed_split_is_applied_automatically_and_keeps_the_total_cost(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=10, trade_at='2026-10-01')[0] == 200
    c = connect(); confirmed_split(c, 1, '2026-10-10', 2.0); c.close()
    pos = position(a, pf)
    assert pos['qty'] == 20 and abs(pos['cost'] - 1000.0) < 1e-6 and abs(pos['avg_cost'] - 50.0) < 1e-6
    assert pos['splits_applied'][0]['ratio'] == 2.0
    assert tx(a, pf, side='sell', quantity=20, trade_at='2026-10-20')[0] == 200        # vendre toute la quantité d'après-split est permis


def test_reverse_split_reduces_the_quantity_and_blocks_selling_more_than_held(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=100, unit_price=1, trade_at='2026-10-01')[0] == 200
    c = connect(); confirmed_split(c, 1, '2026-10-10', 0.1); c.close()
    pos = position(a, pf)
    assert abs(pos['qty'] - 10) < 1e-9 and abs(pos['cost'] - 100.0) < 1e-6
    status, data = tx(a, pf, side='sell', quantity=50, trade_at='2026-10-20')
    assert status == 422 and 'supérieure' in data['error']


def test_manual_correction_made_before_automation_is_not_counted_twice(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=10, trade_at='2026-10-01')[0] == 200
    assert tx(a, pf, quantity=10, unit_price=0, trade_at='2026-10-10')[0] == 200        # titres gratuits saisis à la main à la date du split
    c = connect(); confirmed_split(c, 1, '2026-10-10', 2.0); c.close()
    assert position(a, pf)['qty'] == 20


def test_held_flag_follows_split_adjusted_quantity(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=10, trade_at='2026-10-01')[0] == 200
    c = connect(); confirmed_split(c, 1, '2026-10-10', 2.0); c.close()
    assert tx(a, pf, side='sell', quantity=19, trade_at='2026-10-20')[0] == 200
    held = a.call('explore', {'preset': 'regular', 'view': {'owned_only': True, 'status': 'all'}})[1]
    assert [r['id'] for r in held['rows']] == [1]                                       # 1 titre restant après la vente de 19 sur 20


def legacy_usd_transaction_without_rate(pf):
    c = connect()
    with c.cursor() as q:
        q.execute("INSERT INTO portfolio_transactions(portfolio_id,symbol,side,quantity,unit_price,currency,trade_at,created_at) VALUES (%s,'OLD','buy',1,100,'USD','2026-10-01',NOW())", (pf,))
    c.commit(); c.close()


def test_an_incomplete_transaction_only_excludes_its_own_position(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=2, unit_price=100, trade_at='2026-10-01')[0] == 200      # titre complet : coût 200 €
    legacy_usd_transaction_without_rate(pf)
    v = a.call('portfolio', params=f'&id={pf}')[1]
    t = v['totals']
    assert not v['integrity']['ok'] and t['partial'] and t['excluded'] == ['OLD']
    assert abs(t['cost'] - 200.0) < 1e-6 and t['invested_total'] == 200.0               # le titre complet reste calculé
    assert next(p for p in v['positions'] if p['symbol'] == 'OLD')['cost'] is None


def test_bilan_keeps_other_portfolios_results_when_one_transaction_is_incomplete(world):
    a = login(world, 'alice', 'alice-secret-1234'); good = new_portfolio(a)
    bad = a.call('portfolio/create', {'name': 'Ancien'})[1]['id']
    assert tx(a, good, quantity=1, unit_price=100, trade_at='2026-10-01')[0] == 200
    assert tx(a, good, side='sell', quantity=1, unit_price=150, trade_at='2026-10-05')[0] == 200      # +50 € réalisés
    legacy_usd_transaction_without_rate(bad)
    b = a.call('bilan')[1]
    assert not b['integrity']['ok'] and b['totals']['partial'] and len(b['totals']['excluded']) == 1
    assert abs(b['totals']['realized'] - 50.0) < 1e-6 and b['realized_by_year'] == {'2026': 50.0}
