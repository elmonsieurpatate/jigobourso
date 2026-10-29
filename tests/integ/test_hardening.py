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


def test_confirmed_split_after_purchase_raises_an_alert_until_free_shares_are_entered(world):
    a = login(world, 'alice', 'alice-secret-1234'); pf = new_portfolio(a)
    assert tx(a, pf, quantity=10, trade_at='2026-10-01')[0] == 200
    c = connect()
    with c.cursor() as q:
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,'2026-10-10',0.5,2,'confirmed',NOW())")
    c.commit(); c.close()
    pos = a.call('portfolio', params=f'&id={pf}')[1]['positions'][0]
    assert pos['split_alerts'] == [{'date': '2026-10-10', 'ratio': 2.0, 'shares_to_add': 10.0}]
    assert tx(a, pf, quantity=10, unit_price=0, trade_at='2026-10-10')[0] == 200        # titres gratuits à la date du split : quantité corrigée, coût inchangé
    pos = a.call('portfolio', params=f'&id={pf}')[1]['positions'][0]
    assert pos['split_alerts'] == [] and pos['qty'] == 20 and abs(pos['cost'] - 1000.0) < 1e-6      # coût d'origine conservé (10 × 100)
