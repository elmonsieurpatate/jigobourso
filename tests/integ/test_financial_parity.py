"""Étape 6 : un seul règle de quantités (splits compris) pour validation, valorisation et contrôle de release ; lecture des splits explicite."""
import json
import os
import subprocess

import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('disposable DB only', allow_module_level=True)

from engine.shared.db import connect
from tests.integ.test_api import login, server, world  # noqa: F401
from tests.integ.test_portfolio_audit import account, add, portfolio

pytestmark = pytest.mark.integration
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def splits(*rows):
    conn = connect()
    with conn.cursor() as q:
        q.execute('DELETE FROM split_log WHERE listing_id=1')
        for day, ratio in rows:
            q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,%s,%s,%s,'confirmed',NOW())", (day, 1 / ratio, ratio))
    conn.commit(); conn.close()


def release_issues():
    out = subprocess.run(['php', os.path.join(ROOT, 'scripts/release/check_financial_integrity.php')], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)['issues']


def sell(client, pf, qty, date):
    return client.call('tx/add', dict(portfolio_id=pf, listing_id=1, side='sell', quantity=qty, unit_price=100, trade_at=date))


def test_sell_after_valid_split_is_accepted_and_not_flagged_by_the_release_check(world):
    a, pf = account(world); add(a, pf, qty=10, date='2026-05-01')
    splits(('2026-06-01', 2))
    st, d = sell(a, pf, 20, '2026-07-01')
    assert st == 200, d
    assert [i for i in release_issues() if i['code'] == 'oversold_at_trade_date'] == []     # ancien faux diagnostic : 20 vendus pour 10 achetés


def test_several_splits_and_same_day_operations(world):
    a, pf = account(world); add(a, pf, qty=10, date='2026-05-01')
    splits(('2026-06-01', 2), ('2026-06-15', 3))
    assert sell(a, pf, 21, '2026-06-01')[0] == 422                  # le jour du split, le ratio est déjà compté : 10 x 2 = 20
    assert sell(a, pf, 10, '2026-06-01')[0] == 200                  # reste 10
    assert sell(a, pf, 31, '2026-06-20')[0] == 422                  # 10 x 3 = 30 après le second split
    assert sell(a, pf, 30, '2026-06-20')[0] == 200


def test_reverse_split_then_manual_zero_price_buy_follows_the_documented_rule(world):
    """Règle documentée (FINANCIAL_INTEGRITY.md, « Corrections manuelles ») : un achat à prix zéro daté à partir du split vaut correction manuelle,
    le split n'est alors plus appliqué automatiquement pour ce titre ; le recensement de release le signale pour confirmation."""
    a, pf = account(world); add(a, pf, qty=100, date='2026-05-01')
    splits(('2026-06-01', 0.1))
    assert sell(a, pf, 11, '2026-06-02')[0] == 422                  # regroupement 1 pour 10 : 10 parts
    add(a, pf, qty=5, price=0, date='2026-06-05')
    assert portfolio(a, pf)['positions'][0]['qty'] == pytest.approx(105)   # pas de second ajustement : l'utilisateur est réputé avoir corrigé lui-même


def test_release_check_lists_zero_price_buys_without_changing_anything(world):
    a, pf = account(world); add(a, pf, qty=10, date='2026-05-01')
    splits(('2026-06-01', 2))
    zero = add(a, pf, qty=10, price=0, date='2026-06-02')
    before = portfolio(a, pf)
    codes = {(i.get('id'), i['code']) for i in release_issues()}
    assert (zero, 'zero_price_buy_manual_split_or_gift') in codes
    assert portfolio(a, pf) == before                                # contrôle en lecture seule


def test_unreadable_split_table_is_503_not_silently_empty(world):
    a, pf = account(world); add(a, pf, qty=10, date='2026-05-01')
    conn = connect()
    with conn.cursor() as q: q.execute('RENAME TABLE split_log TO split_log_off')
    conn.commit()
    try:
        st, d = a.call('portfolio', params=f'&id={pf}')
        assert st == 503 and 'split' in d['error'].lower()
        assert sell(a, pf, 1, '2026-07-01')[0] == 503                  # une écriture n'est pas validée sur des quantités inconnues
    finally:
        with conn.cursor() as q: q.execute('RENAME TABLE split_log_off TO split_log')
        conn.commit(); conn.close()
    assert portfolio(a, pf)['positions'][0]['qty'] == pytest.approx(10)


def test_release_check_reports_confirmed_split_missing_from_the_engine_table(world):
    splits(('2026-06-01', 2))                                         # écrit dans split_log seulement : le moteur (corporate_events) l'ignorerait
    assert any(i['code'] == 'confirmed_split_without_corporate_event' and i.get('listing_id') == 1 for i in release_issues())
    conn = connect()
    with conn.cursor() as q: q.execute("INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (1,'2026-06-01','split',2)")
    conn.commit(); conn.close()
    assert not any(i['code'] == 'confirmed_split_without_corporate_event' for i in release_issues())
    conn = connect()
    with conn.cursor() as q: q.execute("DELETE FROM corporate_events WHERE listing_id=1 AND event_date='2026-06-01'")
    conn.commit(); conn.close()


def test_detected_price_jump_is_never_applied_as_a_split(world):
    a, pf = account(world); add(a, pf, qty=10, date='2026-05-01')
    conn = connect()
    with conn.cursor() as q:
        q.execute('DELETE FROM split_log WHERE listing_id=1')
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,'2026-06-01',.5,2,'detected',NOW())")
    conn.commit(); conn.close()
    assert portfolio(a, pf)['positions'][0]['qty'] == pytest.approx(10)      # simple saut de cours détecté : aucune quantité modifiée
    assert sell(a, pf, 11, '2026-07-01')[0] == 422
