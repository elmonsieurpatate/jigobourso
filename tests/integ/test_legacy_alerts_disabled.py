"""Ancien moteur d'alertes (« Surveillance ») : désactivé. Les règles restent stockées, intactes ; plus aucune évaluation, aucun événement, aucune notification,
par aucun point d'entrée réel (tick planifié, CLI, API, e-mails du cron). Le Plan de suivi reste lisible. Exécuter avec PHP 8.3 (voir Makefile : integ)."""
import json
import os
import re
import subprocess

import pytest

from engine.analytics import watch
from engine.shared.db import connect
from tests.integ.test_api import ROOT, login, server, world  # noqa: F401  (fixtures)

pytestmark = pytest.mark.integration


def snapshot(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM alert_rules ORDER BY id')
        rules = cur.fetchall()
        cur.execute('SELECT COUNT(*) n FROM alert_events')
        return rules, cur.fetchone()['n']


def scenario(world):
    """Une position, une règle qui serait déclenchée (cours > 0,0001), une règle déjà « déclenchée » en attente de notification, un e-mail valide."""
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Ancien'})[1]['id']
    assert a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 10, 'unit_price': 100, 'trade_at': '2026-10-01'})[0] == 200
    rid = a.call('alerts/rule-save', {'portfolio_id': pf, 'listing_id': 1, 'kind': 'price_above', 'threshold': 0.0001, 'severity': 'vigilance'})[1]['id']
    rid2 = a.call('alerts/rule-save', {'portfolio_id': pf, 'listing_id': 1, 'kind': 'price_below', 'threshold': 1e6, 'severity': 'vigilance'})[1]['id']
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET email='alice@example.test' WHERE username='alice'")
        cur.execute("UPDATE alert_rules SET state='triggered', triggered_at=NOW(), acked_at=NULL, notified_at=NULL, enabled=1 WHERE id=%s", (rid2,))
    conn.commit()
    return a, pf, rid, rid2, conn


def test_legacy_engine_run_all_is_a_noop_and_rules_stay_intact(world):
    a, pf, rid, rid2, conn = scenario(world)
    before = snapshot(conn)
    assert len(before[0]) >= 2
    for kw in ({}, {'force': True}, {'user_id': 1, 'force': True}):
        assert watch.run_all(conn, **kw) == {'disabled': True, 'rules': 0, 'triggered': 0}
    conn.commit()
    assert snapshot(conn) == before                         # aucune règle modifiée (état, dernière évaluation), aucun événement créé


def test_every_real_entry_point_is_closed(world):
    a, pf, rid, rid2, conn = scenario(world)
    before = snapshot(conn)
    # API : l'actualisation manuelle ne lance plus rien
    st, res = a.call('alerts/refresh', {})
    assert st == 200 and res['disabled'] is True and res['triggered'] == 0
    # CLI : commande watch-run
    r = subprocess.run([os.environ.get('JIGO_PYTHON') or 'python', '-m', 'engine.cli', 'watch-run'], input=json.dumps({'user_id': 1}), cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1]).get('disabled') is True, r.stdout + r.stderr
    # tick planifié et cron : plus d'appel au moteur ni aux e-mails
    tasks = open(os.path.join(ROOT, 'engine/jobs/tasks.py'), encoding='utf-8').read()
    assert not re.search(r'^[^#\n]*watch\.run_all|from \.\.analytics import watch', tasks, re.M)
    assert snapshot(conn) == before


def test_new_tracking_plan_still_works_and_old_rules_remain_readable(world):
    a, pf, rid, rid2, conn = scenario(world)
    st, state = a.call('tracking/state', params=f'&portfolio={pf}')
    assert st == 200 and state['positions'] and 'strategies' in state
    st, old = a.call('alerts/state', params=f'&portfolio={pf}')              # lecture seule des anciennes règles : toujours possible (données conservées)
    assert st == 200 and {r['id'] for r in old['rules']} >= {rid, rid2}
    assert a.call('tracking/state', params=f'&portfolio={pf}')[0] == 200


def test_lot_setting_alerts_off_is_kept_when_dialog_no_longer_sends_it(world):
    a = login(world, 'alice', 'alice-secret-1234')
    pf = a.call('portfolio/create', {'name': 'Lots'})[1]['id']
    a.call('tx/add', {'portfolio_id': pf, 'listing_id': 1, 'side': 'buy', 'quantity': 5, 'unit_price': 100, 'trade_at': '2026-10-01'})
    tx = a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['tx_id']
    assert a.call('lot/settings', {'tx_id': tx, 'strategy': 'momentum', 'alerts_off': True})[0] == 200
    # nouveau dialogue : ne transmet plus alerts_off ; les autres réglages restent modifiables et la valeur stockée est conservée
    assert a.call('lot/settings', {'tx_id': tx, 'strategy': 'regular', 'alert_days': '30', 'alert_drop_pct': '12'})[0] == 200
    s = a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['settings']
    assert s == {'strategy': 'regular', 'alert_days': 30, 'alert_drop_pct': 12.0, 'alerts_off': True}
    # tous les champs vides sans alerts_off : retour aux réglages par défaut (aussi pour une ancienne case cochée)
    assert a.call('lot/settings', {'tx_id': tx})[0] == 200
    assert a.call('portfolio', params=f'&id={pf}')[1]['lots'][0]['settings'] is None
