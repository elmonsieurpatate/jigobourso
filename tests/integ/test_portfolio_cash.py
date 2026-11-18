"""Liquidités, conversion, archivage, réinitialisation et suppression des portefeuilles (phase 1). Base jetable uniquement, vraie API PHP."""

import os

import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('disposable DB only', allow_module_level=True)

from engine.shared.db import connect
from tests.integ.test_api import login, server, world  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def alice(world):
    return login(world, 'alice', 'alice-secret-1234')


def create(c, name='Simu', kind='virtual', capital=1000, **extra):
    extra.setdefault('start_date', '2026-05-01')  # le capital précède les opérations de test (dates de mai)
    status, data = c.call('portfolio/create', dict(name=name, kind=kind, initial_capital=capital, **extra))
    assert status == 200, data
    return data['id']


def buy(c, pf, qty, price, date='2026-05-04', side='buy', **extra):
    return c.call('tx/add', dict(portfolio_id=pf, listing_id=extra.pop('listing_id', 1), side=side, quantity=qty, unit_price=price, trade_at=date, **extra))


def cash(c, pf):
    status, data = c.call('portfolio/cash', params=f'&id={pf}')
    assert status == 200, data
    return data


def balance(c, pf):
    return cash(c, pf)['cash']['balance']


def rows(sql, args=()):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(sql, args)
        out = cur.fetchall()
    conn.close()
    return out


# ───────── création ─────────
def test_virtual_portfolio_gets_its_capital_as_an_external_contribution_not_a_gain(alice):
    pf = create(alice, capital=1000, icon='🚀', description='Test long terme')
    data = cash(alice, pf)
    assert data['cash']['balance'] == 1000 and data['cash']['kind'] == 'virtual'
    assert [m['kind'] for m in data['movements']] == ['initial_capital']
    listed = {p['id']: p for p in alice.call('portfolios')[1]['portfolios']}[pf]
    assert listed['icon'] == '🚀' and listed['description'] == 'Test long terme' and listed['kind'] == 'virtual'
    detail = alice.call('portfolio', params=f'&id={pf}')[1]
    assert detail['totals']['total_gain'] == 0 and detail['cash']['balance'] == 1000  # le capital n'est jamais un gain


def test_creation_validation(alice):
    assert alice.call('portfolio/create', {'name': 'V0', 'kind': 'virtual', 'initial_capital': 0})[0] == 422  # virtuel : capital obligatoire
    assert alice.call('portfolio/create', {'name': 'V1', 'kind': 'virtual'})[0] == 400
    assert alice.call('portfolio/create', {'name': 'Bad', 'kind': 'virtual', 'initial_capital': 10, 'icon': 'x'})[0] == 422
    assert alice.call('portfolio/create', {'name': 'Bad', 'kind': 'other', 'initial_capital': 10})[0] == 422
    assert alice.call('portfolio/create', {'name': 'D', 'kind': 'virtual', 'initial_capital': 10, 'description': 'x' * 281})[0] == 400
    real = alice.call('portfolio/create', {'name': 'Réel vide', 'kind': 'real'})
    assert real[0] == 200 and cash(alice, real[1]['id'])['cash']['balance'] == 0  # réel : capital facultatif
    assert alice.call('portfolio/create', {'name': 'Réel vide', 'kind': 'real'})[0] == 409  # nom unique
    legacy = alice.call('portfolio/create', {'name': 'Ancien modèle'})[1]['id']  # appel sans kind : comportement d'avant, aucune liquidité
    assert cash(alice, legacy)['cash'] is None


# ───────── achats, ventes, dépôts, retraits ─────────
def test_buy_debits_sell_credits_and_virtual_buys_cannot_exceed_cash(alice):
    pf = create(alice, capital=1000)
    assert buy(alice, pf, 5, 100)[0] == 200 and balance(alice, pf) == 500
    status, data = buy(alice, pf, 6, 100)
    assert status == 422 and 'Liquidités insuffisantes' in data['error'] and balance(alice, pf) == 500  # refusé, rien d'écrit
    assert len(rows('SELECT id FROM portfolio_transactions WHERE portfolio_id=%s', (pf,))) == 1
    assert buy(alice, pf, 2, 110, date='2026-05-05', side='sell')[0] == 200 and balance(alice, pf) == 720  # la vente crédite
    assert buy(alice, pf, 1, 100, date='2026-05-06', fees=2.5)[0] == 200 and balance(alice, pf) == 617.5  # frais compris dans le débit


def test_foreign_currency_and_fees_are_converted_once(alice):
    pf = create(alice, capital=1000)
    assert buy(alice, pf, 4, 100, currency='USD', fx_to_eur=0.9, fees=3)[0] == 200
    assert balance(alice, pf) == 1000 - (4 * 100 * 0.9 + 3)  # 636,99 : le prix est converti, les frais sont déjà en euros
    assert buy(alice, pf, 4, 100, date='2026-05-05', side='sell', currency='USD', fx_to_eur=1.1, fees=2)[0] == 200
    assert balance(alice, pf) == round(1000 - 363 + (4 * 100 * 1.1 - 2), 2)


def test_deposit_withdrawal_dividend_fee_are_distinct_and_never_gains(alice):
    pf = create(alice, capital=1000)
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 500, 'occurred_at': '2026-05-04'})[0] == 200
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'withdrawal', 'amount': 200, 'occurred_at': '2026-05-05'})[0] == 200
    assert (
        alice.call(
            'cash/add',
            {'portfolio_id': pf, 'kind': 'dividend', 'amount': 10, 'currency': 'USD', 'fx_to_eur': 0.9, 'gross_amount': 14, 'withholding_tax': 4, 'listing_id': 1, 'occurred_at': '2026-05-06'},
        )[0]
        == 200
    )
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'fee', 'amount': 1.5, 'occurred_at': '2026-05-07'})[0] == 200
    assert balance(alice, pf) == 1000 + 500 - 200 + 9 - 1.5
    div = [m for m in cash(alice, pf)['movements'] if m['kind'] == 'dividend'][0]
    assert float(div['gross_amount']) == 14 and float(div['withholding_tax']) == 4 and div['currency'] == 'USD'  # structure brut / retenue / devise conservée
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 5, 'currency': 'USD', 'occurred_at': '2026-05-04'})[0] == 422  # dépôts en euros
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'bonus', 'amount': 5, 'occurred_at': '2026-05-04'})[0] == 422
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'withdrawal', 'amount': 99999, 'occurred_at': '2026-05-08'})[0] == 422  # on ne retire pas plus que le disponible


def test_same_day_operations_follow_a_deterministic_order(alice):
    pf = create(alice, capital=100)
    assert buy(alice, pf, 1, 100, date='2026-05-04 12:00')[0] == 200 and balance(alice, pf) == 0
    # à la même seconde, la vente est traitée avant l'achat : son produit finance l'achat, quel que soit l'ordre de saisie
    sell = buy(alice, pf, 1, 100, date='2026-05-04 12:00', side='sell')
    assert sell[0] == 200 and balance(alice, pf) == 100
    assert buy(alice, pf, 1, 100, date='2026-05-04 12:00')[0] == 200 and balance(alice, pf) == 0
    assert alice.call('tx/delete', {'id': sell[1]['id']})[0] == 422  # sans cette vente, le second achat n'est plus financé : suppression refusée
    # un dépôt sans heure vaut début de journée : il finance un achat de 08:00 le même jour ; un retrait sans heure vaut fin de journée
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 300, 'occurred_at': '2026-05-04'})[0] == 200
    assert buy(alice, pf, 3, 100, date='2026-05-04 08:00')[0] == 200 and balance(alice, pf) == 0
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'withdrawal', 'amount': 50, 'occurred_at': '2026-05-04'})[0] == 422  # solde nul
    assert buy(alice, pf, 1, 50, date='2026-05-04 13:00', side='sell')[0] == 200
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'withdrawal', 'amount': 50, 'occurred_at': '2026-05-04'})[0] == 200  # fin de journée : après la vente de 13:00
    assert balance(alice, pf) == 0


def test_backdated_operation_is_checked_against_the_whole_timeline(alice):
    pf = create(alice, capital=1000, start_date='2026-05-10')
    assert buy(alice, pf, 1, 100, date='2026-05-05')[0] == 422  # avant le capital initial : pas de liquidités à cette date
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 150, 'occurred_at': '2026-05-02'})[0] == 200
    assert buy(alice, pf, 1, 100, date='2026-05-05')[0] == 200
    assert buy(alice, pf, 1, 100, date='2026-05-06')[0] == 422  # il ne reste que 50 € à cette date
    assert balance(alice, pf) == 1050


def test_real_portfolio_tolerates_a_negative_balance_but_not_a_withdrawal_from_it(alice):
    pf = create(alice, name='Réel', kind='real', capital=100)
    assert buy(alice, pf, 2, 100)[0] == 200  # dépôt manquant ? toléré en réel
    c = cash(alice, pf)['cash']
    assert c['balance'] == -100 and c['negative'] is True
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'withdrawal', 'amount': 1, 'occurred_at': '2026-05-08'})[0] == 422


# ───────── corrections ─────────
def test_correction_recomputes_history_and_refuses_what_would_break_it(alice):
    pf = create(alice, capital=1000)
    assert buy(alice, pf, 8, 100)[0] == 200  # solde 200
    capital = cash(alice, pf)['movements'][0]
    before = rows('SELECT amount_net FROM portfolio_cash_movements WHERE id=%s', (capital['id'],))[0]['amount_net']
    assert alice.call('cash/update', {'id': capital['id'], 'amount': 700, 'occurred_at': str(capital['occurred_at'])[:10]})[0] == 422  # 700 < 800 déjà dépensés
    assert rows('SELECT amount_net FROM portfolio_cash_movements WHERE id=%s', (capital['id'],))[0]['amount_net'] == before  # rien n'a bougé
    assert alice.call('cash/delete', {'id': capital['id']})[0] == 422
    assert alice.call('cash/update', {'id': capital['id'], 'amount': 1200, 'occurred_at': str(capital['occurred_at'])[:10], 'note': 'erreur de saisie corrigée'})[0] == 200
    data = cash(alice, pf)
    assert data['cash']['balance'] == 400 and [a['action'] for a in data['audit']] == ['edit']  # solde recalculé, correction tracée
    assert alice.call('cash/delete', {'id': capital['id']})[0] == 422
    dep = alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 50, 'occurred_at': '2026-05-09'})[1]['id']
    assert alice.call('cash/delete', {'id': dep})[0] == 200 and cash(alice, pf)['audit'][0]['action'] == 'remove'


def test_a_transaction_correction_is_revalidated_against_cash(alice):
    pf = create(alice, capital=1000)
    tx = buy(alice, pf, 5, 100)[1]['id']
    assert alice.call('tx/update', {'id': tx, 'side': 'buy', 'quantity': 11, 'unit_price': 100, 'trade_at': '2026-05-04', 'currency': 'EUR'})[0] == 422
    assert alice.call('tx/update', {'id': tx, 'side': 'buy', 'quantity': 9, 'unit_price': 100, 'trade_at': '2026-05-04', 'currency': 'EUR'})[0] == 200
    assert balance(alice, pf) == 100
    assert alice.call('tx/delete', {'id': tx})[0] == 200 and balance(alice, pf) == 1000


# ───────── conversion explicite ─────────
def legacy_with_history(c, name='Ancien'):
    pf = c.call('portfolio/create', {'name': name})[1]['id']
    assert buy(c, pf, 10, 100, date='2026-05-04')[0] == 200
    assert buy(c, pf, 5, 110, date='2026-05-06')[0] == 200
    assert buy(c, pf, 5, 120, date='2026-05-08', side='sell')[0] == 200
    return pf


def test_conversion_preview_writes_nothing_and_apply_needs_the_matching_preview(alice):
    pf = legacy_with_history(alice)
    snapshot = rows('SELECT cash_model, kind, cash_from FROM portfolios WHERE id=%s', (pf,))[0]
    status, prev = alice.call('portfolio/convert-preview', {'id': pf, 'kind': 'real', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 1500}]})
    assert status == 200 and prev['ok'] and prev['balance'] == 1500 - 1000 - 550 + 600 and prev['operations_in_model'] == 3
    assert rows('SELECT cash_model, kind, cash_from FROM portfolios WHERE id=%s', (pf,))[0] == snapshot  # aperçu : aucune écriture
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_movements WHERE portfolio_id=%s', (pf,))[0]['n'] == 0
    body = {'id': pf, 'kind': 'real', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 1500}], 'confirm': True}
    assert alice.call('portfolio/convert', dict(body, plan_hash='0' * 40))[0] == 409  # aperçu non correspondant
    assert alice.call('portfolio/convert', {k: v for k, v in body.items() if k != 'confirm'} | {'plan_hash': prev['plan_hash']})[0] == 422  # confirmation obligatoire
    assert alice.call('portfolio/convert', dict(body, plan_hash=prev['plan_hash']))[0] == 200
    assert cash(alice, pf)['cash']['balance'] == 550
    assert len(rows('SELECT id FROM portfolio_transactions WHERE portfolio_id=%s', (pf,))) == 3  # transactions jamais modifiées
    assert alice.call('portfolio/convert-preview', {'id': pf, 'kind': 'real', 'mode': 'full'})[0] == 409  # déjà converti


def test_virtual_conversion_with_a_missing_deposit_is_refused_and_leaves_the_portfolio_untouched(alice):
    pf = legacy_with_history(alice)
    status, prev = alice.call('portfolio/convert-preview', {'id': pf, 'kind': 'virtual', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 900}]})
    assert status == 200 and prev['ok'] is False and prev['needed_opening'] == 650 and prev['negatives']
    status, data = alice.call('portfolio/convert', {'id': pf, 'kind': 'virtual', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 900}], 'confirm': True, 'plan_hash': prev['plan_hash']})
    assert status == 422
    assert rows('SELECT cash_model, kind FROM portfolios WHERE id=%s', (pf,))[0] == {'cash_model': 'legacy', 'kind': None}
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_movements WHERE portfolio_id=%s', (pf,))[0]['n'] == 0  # retour arrière complet


def test_conversion_from_a_date_keeps_older_operations_in_the_legacy_period(alice):
    pf = legacy_with_history(alice)
    status, prev = alice.call('portfolio/convert-preview', {'id': pf, 'kind': 'real', 'mode': 'from_date', 'date': '2026-05-07', 'opening_balance': 0})
    assert status == 200 and prev['legacy_operations'] == 2 and prev['operations_in_model'] == 1  # la vente du 08/05 seule agit sur les liquidités
    assert any('non renseigné' in w for w in prev['warnings'])
    assert alice.call('portfolio/convert', {'id': pf, 'kind': 'real', 'mode': 'from_date', 'date': '2026-05-07', 'opening_balance': 0, 'confirm': True, 'plan_hash': prev['plan_hash']})[0] == 200
    assert cash(alice, pf)['cash']['balance'] == 600


def test_conversion_flags_a_probable_duplicate_without_deleting_anything(alice):
    pf = legacy_with_history(alice)
    assert buy(alice, pf, 3, 23.7, date='2026-05-09')[0] == 200 and buy(alice, pf, 3, 23.7, date='2026-05-09')[0] == 200
    prev = alice.call('portfolio/convert-preview', {'id': pf, 'kind': 'real', 'mode': 'full'})[1]
    assert len(prev['duplicates']) == 1 and any('Doublon' in w for w in prev['warnings'])
    assert len(rows('SELECT id FROM portfolio_transactions WHERE portfolio_id=%s', (pf,))) == 5


def test_undo_conversion_is_refused_when_later_operations_depend_on_it(alice):
    pf = legacy_with_history(alice)
    body = {'id': pf, 'kind': 'real', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 2000}]}
    prev = alice.call('portfolio/convert-preview', body)[1]
    assert alice.call('portfolio/convert', dict(body, confirm=True, plan_hash=prev['plan_hash']))[0] == 200
    pre = alice.call('portfolio/convert-undo-preview', params=f'&id={pf}')[1]
    assert pre['possible'] is True
    assert buy(alice, pf, 1, 100, date='2026-05-10')[0] == 200  # nouvelle opération saisie sous le modèle liquidités
    pre = alice.call('portfolio/convert-undo-preview', params=f'&id={pf}')[1]
    assert pre['possible'] is False and pre['blockers'][0]['type'] == 'transaction'
    status, data = alice.call('portfolio/convert-undo', {'id': pf, 'confirm': True})
    assert status == 409 and 'dépendent' in data['error']
    assert rows('SELECT cash_model FROM portfolios WHERE id=%s', (pf,))[0]['cash_model'] == 'cash'
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_movements WHERE portfolio_id=%s', (pf,))[0]['n'] == 1  # mouvements conservés


def test_undo_conversion_when_nothing_depends_on_it_restores_the_legacy_model(alice):
    pf = legacy_with_history(alice)
    body = {'id': pf, 'kind': 'real', 'mode': 'full', 'deposits': [{'date': '2026-05-04', 'amount': 2000}]}
    prev = alice.call('portfolio/convert-preview', body)[1]
    alice.call('portfolio/convert', dict(body, confirm=True, plan_hash=prev['plan_hash']))
    assert alice.call('portfolio/convert-undo', {'id': pf, 'confirm': True})[0] == 200
    assert rows('SELECT cash_model, kind, cash_from, cash_converted_at FROM portfolios WHERE id=%s', (pf,))[0] == {'cash_model': 'legacy', 'kind': None, 'cash_from': None, 'cash_converted_at': None}
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_movements WHERE portfolio_id=%s', (pf,))[0]['n'] == 0
    assert len(rows('SELECT id FROM portfolio_transactions WHERE portfolio_id=%s', (pf,))) == 3
    # un dépôt manuel saisi après conversion bloque aussi l'annulation
    prev = alice.call('portfolio/convert-preview', body)[1]
    alice.call('portfolio/convert', dict(body, confirm=True, plan_hash=prev['plan_hash']))
    alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 10, 'occurred_at': '2026-05-09'})
    assert alice.call('portfolio/convert-undo', {'id': pf, 'confirm': True})[0] == 409


def test_legacy_portfolio_has_no_cash_features_until_converted(alice):
    pf = legacy_with_history(alice)
    assert alice.call('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 5, 'occurred_at': '2026-05-09'})[0] == 409
    detail = alice.call('portfolio', params=f'&id={pf}')[1]
    assert detail['cash'] is None and detail['portfolio']['cash_model'] == 'legacy'


# ───────── archivage ─────────
def test_archive_reassigns_the_default_and_makes_the_portfolio_read_only(alice):
    a = create(alice, name='A')
    b = create(alice, name='B')
    assert {p['id']: p['is_default'] for p in alice.call('portfolios')[1]['portfolios']}[a] is True
    status, data = alice.call('portfolio/archive', {'id': a})
    assert status == 200 and data['new_default']['id'] == b
    listed = {p['id']: p for p in alice.call('portfolios')[1]['portfolios']}
    assert listed[a]['archived'] is True and listed[a]['is_default'] is False and listed[b]['is_default'] is True
    assert buy(alice, a, 1, 100)[0] == 409 and alice.call('cash/add', {'portfolio_id': a, 'kind': 'deposit', 'amount': 1, 'occurred_at': '2026-05-04'})[0] == 409
    assert alice.call('portfolio/default', {'id': a})[0] == 409
    assert alice.call('portfolio', params=f'&id={a}')[0] == 200  # consultable
    assert [p['id'] for p in alice.call('bilan')[1]['portfolios']] == [b]
    assert {p['id'] for p in alice.call('bilan', params='&include_archived=1')[1]['portfolios']} == {a, b}
    assert alice.call('portfolio/unarchive', {'id': a})[0] == 200 and buy(alice, a, 1, 100)[0] == 200


def test_archiving_the_only_active_default_needs_an_explicit_choice(alice):
    a = create(alice, name='Seul')
    status, data = alice.call('portfolio/archive', {'id': a})
    assert status == 409 and 'seul portefeuille actif' in data['error']
    assert alice.call('portfolio/archive', {'id': a, 'no_default': True})[0] == 200
    assert not any(p['is_default'] for p in alice.call('portfolios')[1]['portfolios'])


# ───────── réinitialisation ─────────
def populate_owned_data(pf, tx_id):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO lot_origin(transaction_id, strategy_key, status, snapshot, set_by, created_at) VALUES (%s,'regular','official','{}','purchase',NOW())", (tx_id,))
        cur.execute("INSERT INTO lot_settings(transaction_id, strategy, updated_at) VALUES (%s,'fast',NOW())", (tx_id,))
        cur.execute("INSERT INTO position_levels(portfolio_id, listing_id, stop_px, updated_at) VALUES (%s,1,90,NOW())", (pf,))
        cur.execute("INSERT INTO portfolio_targets(portfolio_id, us_pct, eu_pct, emerging_pct, updated_at) VALUES (%s,40,50,10,NOW())", (pf,))
        cur.execute("INSERT INTO alert_rules(user_id, portfolio_id, listing_id, kind, created_at, updated_at) SELECT user_id, id, 1, 'stop', NOW(), NOW() FROM portfolios WHERE id=%s", (pf,))
        cur.execute("INSERT INTO position_watch(portfolio_id, listing_id, strategy_key, updated_at) VALUES (%s,1,'regular',NOW())", (pf,))
        cur.execute("INSERT INTO position_watch_log(portfolio_id, listing_id, to_key, summary, at) VALUES (%s,1,'regular','test',NOW())", (pf,))
        cur.execute("INSERT INTO position_plan_rules(portfolio_id, listing_id, rule_key, updated_at) VALUES (%s,1,'stop',NOW())", (pf,))
    conn.commit()
    conn.close()


def test_reset_keeps_identity_and_removes_every_owned_row(alice):
    pf = create(alice, name='À vider', icon='🌍', description='desc', capital=1000)
    other = create(alice, name='Autre', capital=500)
    tx = buy(alice, pf, 2, 100)[1]['id']
    other_tx = buy(alice, other, 1, 100)[1]['id']
    populate_owned_data(pf, tx)
    populate_owned_data(other, other_tx)
    cfg = {'name': 'Ma stratégie'}
    rows('SELECT 1')
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("UPDATE portfolios SET strategy_config=%s WHERE id=%s", ('{"name":"Ma stratégie"}', pf))
    conn.commit()
    conn.close()
    status, prev = alice.call('portfolio/reset-preview', params=f'&id={pf}')
    assert status == 200 and prev['counts']['transactions'] == 1 and prev['counts']['lot_origins'] == 1 and prev['counts']['alert_rules'] == 1
    assert alice.call('portfolio/reset', {'id': pf})[0] == 422 and alice.call('portfolio/reset', {'id': pf, 'confirm': 'mauvais'})[0] == 422  # confirmation par le nom
    assert alice.call('portfolio/reset', {'id': pf, 'confirm': 'À vider', 'initial_capital': 250})[0] == 200
    kept = rows('SELECT name, icon, description, kind, cash_model, is_default, strategy_config IS NOT NULL strat FROM portfolios WHERE id=%s', (pf,))[0]
    assert kept == {'name': 'À vider', 'icon': '🌍', 'description': 'desc', 'kind': 'virtual', 'cash_model': 'cash', 'is_default': 1, 'strat': 1}
    data = cash(alice, pf)
    assert data['cash']['balance'] == 250 and [m['kind'] for m in data['movements']] == ['initial_capital']  # nouveau capital proposé et enregistré
    counts = alice.call('portfolio/reset-preview', params=f'&id={pf}')[1]['counts']
    assert counts['transactions'] == 0 and counts['lot_origins'] == 0 and counts['lot_settings'] == 0 and counts['levels'] == 0 and counts['targets'] == 0
    assert counts['alert_rules'] == 0 and counts['watch'] == 0 and counts['watch_log'] == 0 and counts['plan_rules'] == 0 and counts['cash_movements'] == 1
    untouched = alice.call('portfolio/reset-preview', params=f'&id={other}')[1]['counts']
    assert untouched['transactions'] == 1 and untouched['lot_origins'] == 1 and untouched['alert_rules'] == 1  # l'autre portefeuille est intact
    assert cfg


# ───────── suppression ─────────
def test_delete_is_atomic_complete_and_never_touches_shared_or_other_data(alice, world):
    pf = create(alice, name='À supprimer', capital=1000)
    keep = create(alice, name='À garder', capital=500)
    tx = buy(alice, pf, 2, 100)[1]['id']
    keep_tx = buy(alice, keep, 1, 100)[1]['id']
    populate_owned_data(pf, tx)
    populate_owned_data(keep, keep_tx)
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO explorer_saved(user_id, kind, name, payload, created_at, updated_at) SELECT user_id,'strategy','Stratégie sauvegardée','{}',NOW(),NOW() FROM portfolios WHERE id=%s", (pf,)
        )
    conn.commit()
    conn.close()
    shared_before = {t: rows(f'SELECT COUNT(*) n FROM {t}')[0]['n'] for t in ('listings', 'instruments', 'latest_prices', 'explorer_saved')}
    status, prev = alice.call('portfolio/delete-preview', params=f'&id={pf}')
    assert status == 200 and prev['has_data'] and prev['counts']['cash_movements'] == 1 and prev['new_default']['id'] == keep
    assert alice.call('portfolio/delete', {'id': pf})[0] == 422  # des données : confirmation par le nom obligatoire
    assert alice.call('portfolio/delete', {'id': pf, 'confirm': 'autre nom'})[0] == 422
    assert rows('SELECT id FROM portfolios WHERE id=%s', (pf,))
    status, data = alice.call('portfolio/delete', {'id': pf, 'confirm': 'À supprimer'})
    assert status == 200 and data['new_default']['id'] == keep and data['deleted']['transactions'] == 1
    # aucune ligne résiduelle dans AUCUNE table portant portfolio_id (liste lue dans le schéma, donc valable pour les tables futures)
    for t in [r['table_name'] for r in rows("SELECT DISTINCT table_name FROM information_schema.columns WHERE table_schema=DATABASE() AND column_name='portfolio_id'")]:
        assert rows(f'SELECT COUNT(*) n FROM `{t}` WHERE portfolio_id=%s', (pf,))[0]['n'] == 0, t
    assert rows('SELECT COUNT(*) n FROM lot_origin o LEFT JOIN portfolio_transactions t ON t.id=o.transaction_id WHERE t.id IS NULL')[0]['n'] == 0
    assert rows('SELECT COUNT(*) n FROM lot_settings o LEFT JOIN portfolio_transactions t ON t.id=o.transaction_id WHERE t.id IS NULL')[0]['n'] == 0
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_audit WHERE portfolio_id=%s', (pf,))[0]['n'] == 0
    assert {t: rows(f'SELECT COUNT(*) n FROM {t}')[0]['n'] for t in shared_before} == shared_before  # données partagées et stratégies sauvegardées intactes
    assert alice.call('portfolio/reset-preview', params=f'&id={keep}')[1]['counts']['transactions'] == 1  # l'autre portefeuille n'a rien perdu
    assert {p['id']: p['is_default'] for p in alice.call('portfolios')[1]['portfolios']}[keep] is True


def test_deleting_a_saved_strategy_never_touches_a_portfolio(alice):
    pf = create(alice, name='Avec stratégie')
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("UPDATE portfolios SET strategy_config=%s WHERE id=%s", ('{"name":"Ma stratégie"}', pf))
        cur.execute("INSERT INTO explorer_saved(user_id, kind, name, payload, created_at, updated_at) SELECT user_id,'strategy','Ma stratégie','{}',NOW(),NOW() FROM portfolios WHERE id=%s", (pf,))
        sid = cur.lastrowid
    conn.commit()
    conn.close()
    assert alice.call('explorer/library/delete', {'id': sid})[0] == 200
    assert rows('SELECT strategy_config IS NOT NULL s FROM portfolios WHERE id=%s', (pf,))[0]['s'] == 1
    assert rows('SELECT COUNT(*) n FROM portfolios WHERE id=%s', (pf,))[0]['n'] == 1


def test_update_renames_without_losing_anything_and_ownership_is_enforced(alice, world):
    pf = create(alice, name='Ancien nom')
    tx = buy(alice, pf, 1, 100)[1]['id']
    assert alice.call('portfolio/update', {'id': pf, 'name': 'Nouveau nom', 'icon': '🎯', 'description': 'ok'})[0] == 200
    assert alice.call('portfolio/update', {'id': pf, 'icon': 'x'})[0] == 422 and alice.call('portfolio/update', {'id': pf})[0] == 422
    assert rows('SELECT name, icon, description FROM portfolios WHERE id=%s', (pf,))[0] == {'name': 'Nouveau nom', 'icon': '🎯', 'description': 'ok'}
    assert rows('SELECT id FROM portfolio_transactions WHERE id=%s', (tx,)) and balance(alice, pf) == 900
    other = create(alice, name='Doublon')
    assert alice.call('portfolio/update', {'id': other, 'name': 'Nouveau nom'})[0] == 409
    bob = login(world, 'bob', 'bob-secret-12345')
    mov = cash(alice, pf)['movements'][0]['id']
    for route, body in (
        ('portfolio/update', {'id': pf, 'name': 'Vol'}),
        ('portfolio/archive', {'id': pf}),
        ('portfolio/reset', {'id': pf, 'confirm': 'Nouveau nom'}),
        ('portfolio/delete', {'id': pf, 'confirm': 'Nouveau nom'}),
        ('cash/delete', {'id': mov}),
        ('cash/add', {'portfolio_id': pf, 'kind': 'deposit', 'amount': 1, 'occurred_at': '2026-05-04'}),
    ):
        assert bob.call(route, body)[0] == 404, route


# ───────── scénario de référence et non-régression legacy ─────────
def test_reference_scenario_1000_buy_200_sell_250(alice):
    """1 000 € virtuels, achat à 200 €, vente à 250 € : liquidités 1 000 → 800 → 1 050 €, gain réalisé 50 € conservé."""
    pf = create(alice, capital=1000, start_date='2026-05-01')
    assert balance(alice, pf) == 1000
    assert buy(alice, pf, 1, 200, date='2026-05-04')[0] == 200 and balance(alice, pf) == 800
    assert buy(alice, pf, 1, 250, date='2026-05-06', side='sell')[0] == 200 and balance(alice, pf) == 1050
    detail = alice.call('portfolio', params=f'&id={pf}')[1]
    assert detail['totals']['realized'] == 50 and detail['totals']['total_gain'] == 50 and detail['totals']['unrealized'] == 0
    assert detail['positions'] == [] and len(detail['closed']) == 1 and detail['closed'][0]['realized'] == 50  # clôturée, gain conservé
    assert [m['balance_after'] for m in cash(alice, pf)['movements']] == [1000]
    # le capital n'est jamais un gain : valeur titres 0, gain 50, liquidités 1 050
    assert detail['cash']['balance'] == 1050 and detail['totals']['value'] == 0


def test_legacy_portfolio_is_strictly_unchanged_by_the_new_model(alice):
    """Un portefeuille créé à l'ancienne garde exactement les valeurs d'avant : aucun mouvement, aucune liquidité, mêmes totaux au centime."""
    pf = alice.call('portfolio/create', {'name': 'Ancien'})[1]['id']
    assert buy(alice, pf, 10, 100, date='2026-05-04')[0] == 200  # achat sans aucune liquidité : toujours accepté
    assert buy(alice, pf, 5, 110, date='2026-05-06')[0] == 200
    assert buy(alice, pf, 5, 120, date='2026-05-08', side='sell')[0] == 200
    d = alice.call('portfolio', params=f'&id={pf}')[1]
    t = d['totals']
    assert d['cash'] is None and d['portfolio']['cash_model'] == 'legacy' and d['portfolio']['kind'] is None
    assert round(t['realized'], 2) == 83.33 and round(t['cost'], 2) == 1033.33 and round(t['value'], 2) == 1200 and round(t['unrealized'], 2) == 166.67
    assert round(t['total_gain'], 2) == 250.0
    assert rows('SELECT COUNT(*) n FROM portfolio_cash_movements WHERE portfolio_id=%s', (pf,))[0]['n'] == 0
    row = rows('SELECT cash_model, kind, cash_from, cash_converted_at, archived_at FROM portfolios WHERE id=%s', (pf,))[0]
    assert row == {'cash_model': 'legacy', 'kind': None, 'cash_from': None, 'cash_converted_at': None, 'archived_at': None}
    assert alice.call('portfolio/history', params=f'&id={pf}')[0] == 200  # l'historique et la performance existants fonctionnent
    listed = {p['id']: p for p in alice.call('portfolios')[1]['portfolios']}[pf]
    assert listed['cash'] is None and listed['cash_model'] == 'legacy' and round(listed['totals']['total_gain'], 2) == 250.0
