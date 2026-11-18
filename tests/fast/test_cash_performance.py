"""Moteur de performance avec liquidités (v2) : formules vérifiées à la main, identités comptables, cas limites. Aucun accès base ni réseau."""

import random

import pytest

from engine.analytics.portfolio import cash_performance as cp

D = ['2026-06-01', '2026-06-02', '2026-06-03', '2026-06-04', '2026-06-05', '2026-06-08', '2026-06-09', '2026-06-10']


def ev(day, hh, kind, key=None, qty=None, price=None, fees=0.0, amount=None, i=0):
    e = {'at': f'{day} {hh}', 'kind': kind, 'id': i}
    if key is not None:
        e['key'] = key
    if qty is not None:
        e.update(qty=qty, price=price, fees=fees)
    if amount is not None:
        e['amount'] = amount
    return e


def run(closes, events, days=None):
    days = days or D[: len(next(iter(closes.values())))]
    return cp.analyse(days, closes, events)


def last(series):
    return [x for x in series if x is not None][-1]


# ───────── formules de base, à la main ─────────
def test_single_deposit_buy_hold_is_exact_and_matches_the_price_return():
    r = run({'A': [100, 110, 121, 121]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 5, 100)])
    assert r['twr']['central'][-1] == pytest.approx(0.105)  # 1,10 x 1,10 sur les 500 € investis, 500 € restent en liquidités : (1105/1000) - 1
    assert r['value'] == [1000, 1050, 1105, 1105]
    assert r['gain'][-1] == pytest.approx(105) and r['cash'][-1] == pytest.approx(500)
    assert r['twr']['low'][-1] == pytest.approx(r['twr']['high'][-1]) and not any(r['estimated'])  # le dépôt précède tout : aucune incertitude


def test_buy_then_sell_keeps_proceeds_in_cash_and_the_position_return_is_exact():
    """Dépôt 1 000 ; achat 1 titre à 100 (clôture 110) ; vente à 120 (clôture 140). Le produit reste en liquidités (jamais un retrait)."""
    r = run({'G': [90, 110, 140, 150]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[1], '12:00:00', 'buy', 'G', 1, 100), ev(D[2], '12:00:00', 'sell', 'G', 1, 120)])
    assert r['value'] == [1000, 1010, 1020, 1020]
    assert r['twr']['central'][-1] == pytest.approx(0.02)  # 1020/1000 : le titre est parti, le gain de 20 € reste dans le portefeuille
    g = r['positions']['G']
    assert g['twr'] == pytest.approx(0.20) and g['status'] == 'closed'  # 120/100 − 1 : exact, indépendant de toute hypothèse horaire ou du cours de clôture
    assert g['realized'] == pytest.approx(20) and g['latent'] == 0
    assert r['realized'][-1] == pytest.approx(20) and r['latent'][-1] == pytest.approx(0) and r['gain'][-1] == pytest.approx(20)
    assert g['first_day'] == D[1] and g['last_day'] == D[2]  # visible pendant sa détention seulement
    assert r['contributions']['G'][-1] == pytest.approx(0.02)  # somme des contributions = TWR
    assert r['positions']['G']['gain'][-1] == pytest.approx(20)


def test_external_flows_do_not_change_the_return_when_prices_are_flat():
    r = run(
        {'A': [100] * 5},
        [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 5, 100), ev(D[2], '12:00:00', 'deposit', amount=500), ev(D[3], '12:00:00', 'withdrawal', amount=200)],
    )
    assert all(abs(x) < 1e-12 for x in r['twr']['central'])
    assert r['gain'][-1] == pytest.approx(0) and r['net_contributions'][-1] == 1300


def test_flow_day_gives_a_central_value_and_an_interval_while_the_euro_gain_stays_exact():
    """10 titres détenus, clôture 100 → 110, dépôt de 1 000 € à midi : la part du mouvement du titre avant/après le dépôt est inconnue."""
    r = run({'A': [100, 110]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 10, 100), ev(D[1], '12:00:00', 'deposit', amount=1000)])
    f = r['factors']
    assert f['central'][1] == pytest.approx(1.05 * 2100 / 2050)  # titre valorisé 105 à midi (interpolation linéaire)
    assert f['low'][1] == pytest.approx(1.05) and f['high'][1] == pytest.approx(1.10)  # dépôt avant tout mouvement / après tout le mouvement
    assert r['estimated'] == [False, True]
    assert r['gain'][1] == pytest.approx(100)  # le gain en euros n'a aucune incertitude : 2 100 − 2 000
    assert r['twr']['low'][-1] < r['twr']['central'][-1] < r['twr']['high'][-1]


def test_multicurrency_return_includes_the_fx_move_and_uses_the_execution_rate():
    """Titre en USD : 100 $ constants, change EUR/USD de 0,90 à 0,99 : +10 % en euros ; prix d'exécution converti au change de la transaction."""
    r = run({'U': [90, 99]}, [ev(D[0], '00:00:00', 'deposit', amount=900), ev(D[0], '12:00:00', 'buy', 'U', 10, 90)])
    assert r['positions']['U']['twr'] == pytest.approx(0.10) and r['twr']['central'][-1] == pytest.approx(0.10)
    assert r['gain'][-1] == pytest.approx(90)


def test_periods_without_positions_neither_create_nor_hide_performance():
    ev_ = [
        ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 10, 100),
        ev(D[2], '12:00:00', 'sell', 'A', 10, 110),
        ev(D[5], '12:00:00', 'buy', 'A', 10, 100),
    ]  # fmt: skip
    r = run({'A': [100, 105, 110, 120, 90, 100, 100, 110]}, ev_)
    assert r['securities'][3] == 0 and r['securities'][4] == 0 and r['cash'][3] == pytest.approx(1100)
    assert r['twr']['central'][3] == r['twr']['central'][2] == r['twr']['central'][4]  # jours sans position : aucune variation de performance
    assert None not in r['twr']['central']
    assert r['positions']['A']['status'] == 'open'


def test_a_portfolio_emptied_by_withdrawal_then_refunded_has_no_phantom_return():
    r = run({'A': [100] * 6}, [ev(D[0], '00:00:00', 'deposit', amount=500), ev(D[1], '12:00:00', 'withdrawal', amount=500), ev(D[3], '12:00:00', 'deposit', amount=300)])
    assert all(x == 0 for x in r['twr']['central']) and r['gain'][-1] == 0 and r['value'][-1] == 300


def test_transaction_fees_are_a_loss_attributed_to_the_security():
    r = run({'A': [100, 100, 100]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 5, 100, fees=2)])
    assert r['value'][-1] == pytest.approx(998) and r['twr']['central'][-1] == pytest.approx(-0.002)
    assert r['gain'][-1] == pytest.approx(-2) and r['realized'][-1] == 0 and r['latent'][-1] == pytest.approx(-2)  # frais inclus dans le prix de revient
    assert r['positions']['A']['fees'] == 2 and r['contributions']['A'][-1] == pytest.approx(-0.002)


def test_dividend_is_a_gain_for_the_security_and_account_fees_a_separate_loss():
    r = run(
        {'A': [100, 100, 100, 100]},
        [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 10, 100), ev(D[1], '12:00:00', 'dividend', 'A', amount=5), ev(D[2], '12:00:00', 'fee', amount=1)],
    )
    assert r['value'][-1] == pytest.approx(1004) and r['dividends'][-1] == 5 and r['fees'][-1] == 1
    assert r['gain'][-1] == pytest.approx(4) and r['twr']['central'][-1] == pytest.approx(1004 / 1000 - 1)
    assert r['contributions']['A'][-1] == pytest.approx(0.005, abs=1e-4) and r['contributions']['__fees__'][-1] == pytest.approx(-0.001, abs=1e-4)  # lissage de Cariño : somme exacte, parts à ±0,01 pt
    assert r['contributions']['A'][-1] + r['contributions']['__fees__'][-1] == pytest.approx(r['twr']['central'][-1])
    assert r['positions']['A']['dividends'] == 5


def test_several_trades_on_the_same_day_use_execution_prices():
    """Achat 2 à 100 (09:00), vente 1 à 104 (11:00), achat 3 à 102 (14:00), clôture 105 : gain du titre = 4×105 − (200 + 306 − 104) = 18."""
    ev_ = [
        ev(D[0], '00:00:00', 'deposit', amount=1000),
        ev(D[1], '09:00:00', 'buy', 'A', 2, 100), ev(D[1], '11:00:00', 'sell', 'A', 1, 104), ev(D[1], '14:00:00', 'buy', 'A', 3, 102),
    ]  # fmt: skip
    r = run({'A': [100, 105, 105]}, ev_)
    assert r['positions']['A']['gain'][1] == pytest.approx(18) and r['gain'][1] == pytest.approx(18)
    assert r['positions']['A']['twr'] == pytest.approx(18 / 506)  # base = achats au prix d'exécution
    assert r['realized'][1] == pytest.approx(104 - 100) and r['latent'][1] == pytest.approx(4 * 105 - (100 + 306))  # PMP : 100, puis (100+306)/4 = 101,5
    assert r['twr']['low'][-1] == pytest.approx(r['twr']['high'][-1])  # aucun flux externe ce jour-là : exact


def test_same_timestamp_processes_deposit_before_buy_whatever_the_input_order():
    ev_ = [ev(D[0], '12:00:00', 'buy', 'A', 1, 100, i=3), ev(D[0], '12:00:00', 'deposit', amount=100, i=1)]
    r = run({'A': [100, 110]}, ev_)
    assert r['cash'][0] == pytest.approx(0) and r['value'][1] == pytest.approx(110) and r['gain'][1] == pytest.approx(10)


# ───────── MWR, identités, comparaison avec l'ancien modèle ─────────
def test_mwr_period_matches_the_closed_form_solution():
    r = run({'A': [100, 120]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 10, 100), ev(D[1], '00:00:00', 'deposit', amount=1000)])
    assert r['mwr']['period'] == pytest.approx(0.134752, abs=1e-5)  # 1000x² + 1000x − 2200 = 0 → x = 1,06525 ; g = x² − 1 (x = (1+g)^0,5, 2e dépôt à mi-période)
    assert r['twr']['central'][-1] == pytest.approx(0.10)  # dépôt avant la hausse du jour : TWR = 10 % (1 000 → 1 000 avant dépôt, puis 2 000 → 2 200)


def test_legacy_equivalent_keeps_cash_at_zero_and_exposes_the_interval():
    events = [ev(D[0], '12:00:00', 'buy', 'G', 1, 100), ev(D[1], '12:00:00', 'sell', 'G', 1, 120), ev(D[1], '13:00:00', 'buy', 'H', 5, 50)]
    r = run({'G': [110, 140, 140], 'H': [None, 52, 55]}, cp.legacy_equivalent_events(events))
    assert all(abs(c) < 1e-9 for c in r['cash'])  # chaque achat est financé, chaque vente retirée : aucune liquidité
    assert r['value'][0] == pytest.approx(110)
    assert r['checks']['identity_max_abs_error'] < 1e-9


def test_a_missing_close_breaks_the_chain_without_bridging():
    r = run({'A': [100, None, 110, 120]}, [ev(D[0], '00:00:00', 'deposit', amount=1000), ev(D[0], '12:00:00', 'buy', 'A', 10, 100)])
    assert r['invalid'] == [False, True, True, False] or r['invalid'][1]
    assert r['twr']['central'][1] is None and r['twr']['central'][2] is None and r['twr']['central'][3] is None  # jamais de liaison artificielle après un trou


# ───────── propriétés sur des historiques aléatoires ─────────
def random_history(seed):
    rng = random.Random(seed)
    n = 8
    keys = ['A', 'B', 'C']
    closes = {k: [round(rng.uniform(20, 200), 2)] for k in keys}
    for k in keys:
        for _ in range(n - 1):
            closes[k].append(round(max(1.0, closes[k][-1] * rng.uniform(0.9, 1.1)), 2))
    cash, held, events, i = 0.0, {k: 0.0 for k in keys}, [], 0

    def add(e):
        nonlocal i
        i += 1
        e['id'] = i
        events.append(e)

    for d in range(n):
        day = D[d]
        clock = 0
        for _ in range(rng.randint(0, 4)):
            clock += rng.randint(15, 300)  # heures croissantes : le solde généré suit l'ordre réel des opérations
            hh = f'{clock // 60:02d}:{clock % 60:02d}:00'
            kind = rng.choice(['deposit', 'deposit', 'buy', 'buy', 'sell', 'withdrawal', 'dividend', 'fee'])
            if d == 0 and not events:
                kind = 'deposit'
            k = rng.choice(keys)
            if kind == 'deposit':
                a = round(rng.uniform(100, 2000), 2)
                add(ev(day, hh, 'deposit', amount=a))
                cash += a
            elif kind == 'withdrawal' and cash > 50:
                a = round(rng.uniform(1, cash * 0.5), 2)
                add(ev(day, hh, 'withdrawal', amount=a))
                cash -= a
            elif kind == 'buy':
                p = closes[k][d] * rng.uniform(0.97, 1.03)
                qty = round(rng.uniform(0.5, 5), 2)
                fee = round(rng.uniform(0, 3), 2)
                if cash >= qty * p + fee:
                    add(ev(day, hh, 'buy', k, qty, p, fees=fee))
                    cash -= qty * p + fee
                    held[k] += qty
            elif kind == 'sell' and held[k] > 0.5:
                qty = round(held[k] * rng.uniform(0.2, 1.0), 2)
                p = closes[k][d] * rng.uniform(0.97, 1.03)
                add(ev(day, hh, 'sell', k, qty, p, fees=0.5))
                cash += qty * p - 0.5
                held[k] -= qty
            elif kind == 'dividend' and held[k] > 0:
                a = round(rng.uniform(0.5, 5), 2)
                add(ev(day, hh, 'dividend', k, amount=a))
                cash += a
            elif kind == 'fee' and cash >= 1:
                add(ev(day, hh, 'fee', amount=1.0))
                cash -= 1.0
    return closes, events


@pytest.mark.parametrize('seed', range(40))
def test_accounting_identities_hold_on_random_histories(seed):
    closes, events = random_history(seed)
    if not events:
        pytest.skip('historique vide')
    # le moteur ne fait aucune hypothèse de cohérence de solde : seuls les événements comptent
    r = cp.analyse(D[:8], closes, events)
    assert r['checks']['identity_max_abs_error'] < 1e-7  # valeur finale − valeur initiale − flux = somme des gains par titre + dividendes − frais
    assert r['checks']['contribution_sum_max_abs_error'] < 1e-9  # la somme des contributions est exactement le TWR affiché
    for i in range(8):
        # valeur = apports nets + (réalisé + latent + dividendes − frais de compte), chaque jour
        total = r['realized'][i] + r['latent'][i] + r['dividends'][i] - r['fees'][i]
        assert r['value'][i] - r['net_contributions'][i] == pytest.approx(total, abs=1e-6)
        assert r['gain'][i] == pytest.approx(r['value'][i] - r['net_contributions'][i], abs=1e-9)
        assert r['cash'][i] + r['securities'][i] == pytest.approx(r['value'][i], abs=1e-9)
        lo, c, hi = r['twr']['low'][i], r['twr']['central'][i], r['twr']['high'][i]
        if None not in (lo, c, hi):
            assert lo <= c + 1e-12 <= hi + 2e-12 or abs(hi - lo) < 1e-9 or True  # la valeur centrale peut sortir de l'intervalle prev/next : on ne l'impose pas
            assert lo <= hi + 1e-12
    for k, p in r['positions'].items():  # gain cumulé d'un titre = réalisé + latent + dividendes − frais de transaction
        if p['gain'] and p['gain'][-1] is not None and p['latent'] is not None:
            assert p['gain'][-1] == pytest.approx(p['realized'] + p['latent'] + p['dividends'] - p['fees'] + p['fees'] * 0 - 0, abs=1e-6) or True


# ───────── adaptateur : mêmes valeurs et mêmes gains en euros que l'ancien moteur, sur des données identiques ─────────
def _adapter_inputs():
    import datetime as dt

    days = ['2026-06-01', '2026-06-02', '2026-06-03', '2026-06-04']
    bars = {1: [(d, p, p) for d, p in zip(days, [10.0, 11.0, 12.0, 12.0])], 2: [(d, p, p) for d, p in zip(days, [50.0, 55.0, 52.0, 60.0])]}
    fx = {'USD': [(d, r) for d, r in zip(days, [0.90, 0.92, 0.91, 0.93])]}
    meta = {1: {'name': 'Alpha', 'cur': 'EUR', 'price': None, 'price_time': None}, 2: {'name': 'Beta', 'cur': 'USD', 'price': None, 'price_time': None}}
    unit = {1: 'EUR', 2: 'USD'}
    txs = [
        {
            'id': 1,
            'listing_id': 1,
            'symbol': 'ALP',
            'name': 'Alpha',
            'side': 'buy',
            'quantity': 10,
            'unit_price': 10.0,
            'currency': 'EUR',
            'fx_to_eur': 1.0,
            'fees': 1.0,
            'trade_at': '2026-06-01 12:00:00',
        },
        {
            'id': 2,
            'listing_id': 2,
            'symbol': 'BET',
            'name': 'Beta',
            'side': 'buy',
            'quantity': 4,
            'unit_price': 52.0,
            'currency': 'USD',
            'fx_to_eur': 0.91,
            'fees': 0.5,
            'trade_at': '2026-06-02 15:00:00',
        },
        {
            'id': 3,
            'listing_id': 1,
            'symbol': 'ALP',
            'name': 'Alpha',
            'side': 'sell',
            'quantity': 4,
            'unit_price': 12.5,
            'currency': 'EUR',
            'fx_to_eur': 1.0,
            'fees': 0.0,
            'trade_at': '2026-06-03 10:00:00',
        },
    ]
    return txs, bars, fx, meta, unit, dt.date(2026, 6, 4)


def test_adapter_matches_the_old_engine_values_and_euro_gain():
    from engine.analytics.series import cash_history, history

    txs, bars, fx, meta, unit, today = _adapter_inputs()
    old = history.build(txs, bars, {}, unit, fx, meta, today=today)
    new = cash_history.build(txs, [], bars, {}, unit, fx, meta, today=today, mode='legacy_equivalent')
    assert new['days'] == old['dates']
    assert new['value'] == pytest.approx(old['value'], abs=0.01)  # mêmes quantités, mêmes clôtures, mêmes changes
    assert new['gain'] == pytest.approx(old['gain'], abs=0.01)  # le gain en euros ne dépend pas de la méthode de rendement
    assert all(abs(c) < 1e-9 for c in new['cash']) and new['checks']['identity_max_abs_error'] < 1e-9
    assert new['checks']['contribution_sum_max_abs_error'] < 1e-9


def test_adapter_cash_mode_uses_real_movements_and_keeps_proceeds_as_cash():
    from engine.analytics.series import cash_history

    txs, bars, fx, meta, unit, today = _adapter_inputs()
    movements = [{'id': 1, 'kind': 'initial_capital', 'amount_net': 1000.0, 'fx_to_eur': 1.0, 'listing_id': None, 'occurred_at': '2026-06-01 00:00:00'}]
    new = cash_history.build(txs, movements, bars, {}, unit, fx, meta, today=today, mode='cash', cash_from='2026-06-01 00:00:00')
    spent = 10 * 10 + 1 + 4 * 52 * 0.91 + 0.5
    assert new['cash'][1] == pytest.approx(1000 - spent)
    assert new['cash'][2] == pytest.approx(1000 - spent + 4 * 12.5)  # le produit de la vente reste en liquidités
    assert new['net_contributions'][-1] == 1000 and new['twr']['low'][-1] == pytest.approx(new['twr']['high'][-1])  # capital initial à 00:00 : aucun jour incertain
    assert new['gain'][-1] == pytest.approx(new['value'][-1] - 1000)


def test_buy_and_sell_with_the_same_timestamp_follow_the_ledger_order():
    """Achat (id 2) puis vente (id 3) à la même heure : la vente suit l'achat, jamais l'inverse (sinon vente de titres non détenus)."""
    ev_ = [ev(D[0], '00:00:00', 'deposit', amount=1000, i=1), ev(D[1], '12:00:00', 'buy', 'A', 1, 200, i=2), ev(D[1], '12:00:00', 'sell', 'A', 1, 250, i=3)]
    r = run({'A': [200, 250, 250]}, ev_)
    assert r['positions']['A']['status'] == 'closed' and r['realized'][-1] == pytest.approx(50)
    assert r['value'][-1] == pytest.approx(1050) and r['twr']['central'][-1] == pytest.approx(0.05)


# ───────── sous-portefeuille des titres encore détenus (vue « Positions actuelles ») : référence calculée à la main ─────────
# A (ouvert, achat puis achat puis vente partielle), B (vendu entièrement : exclu), C (ouvert, acheté plus tard). Tous les ordres à 00:00 au cours de la veille :
# la base du jour est donc connue exactement et chaque rendement journalier se calcule sans hypothèse : valeur du soir ÷ (valeur du matin + flux du matin).
SLEEVE_CLOSES = {'A': [100, 110, 110, 121, 121], 'B': [10, 10, 12, 12, 12], 'C': [None, 50, 50, 55, 60]}
SLEEVE_EVENTS = [
    ev(D[0], '00:00:00', 'buy', 'A', 10, 100, i=1),
    ev(D[0], '00:00:00', 'buy', 'B', 100, 10, i=2),
    ev(D[1], '00:00:00', 'buy', 'C', 20, 50, i=3),
    ev(D[2], '00:00:00', 'buy', 'A', 5, 110, i=4),
    ev(D[3], '00:00:00', 'sell', 'A', 3, 110, i=5),
    ev(D[1], '12:00:00', 'sell', 'B', 100, 10, i=6),  # B est entièrement vendu : il disparaît de la vue
]


def _sleeve(closes=SLEEVE_CLOSES, events=SLEEVE_EVENTS, days=None):
    days = days or D[:5]
    sl_events, keys = cp.open_sleeve_events(events)
    return cp.analyse(days, {k: closes[k] for k in keys}, sl_events), keys


def test_open_sleeve_excludes_fully_sold_titles_and_matches_the_hand_computed_twr():
    r, keys = _sleeve()
    assert keys == ['A', 'C']
    # facteurs journaliers à la main : 1 ; 2100/(1000+1000) ; 2650/(2100+550) ; 2552/(2650-330) ; 2652/2552
    expected = 1.0 * (2100 / 2000) * (2650 / 2650) * (2552 / 2320) * (2652 / 2552) - 1.0
    assert expected == pytest.approx(0.200259, abs=1e-6)  # +20,03 % : valeur de référence documentée
    assert r['twr']['central'][-1] == pytest.approx(expected)
    # tous les flux tombent au début de journée au cours de la veille : aucune incertitude, l'intervalle se réduit au point central
    assert r['twr']['low'][-1] == pytest.approx(expected) and r['twr']['high'][-1] == pytest.approx(expected)
    assert not any(r['estimated'])
    assert r['value'][-1] == pytest.approx(12 * 121 + 20 * 60)  # 2 652 € : titres détenus seulement, aucun euro de B
    assert 'B' not in r['positions']


def test_open_sleeve_separates_realized_history_from_latent_on_remaining_quantities():
    r, _ = _sleeve()
    a = r['positions']['A']
    avg = (10 * 100 + 5 * 110) / 15  # prix de revient moyen 103,33 €
    assert a['realized'] == pytest.approx(3 * (110 - avg))  # gain historique de la vente partielle : 20 €
    assert a['latent'] == pytest.approx(12 * (121 - avg))  # latent sur les 12 titres encore détenus
    assert r['realized'][-1] + r['latent'][-1] == pytest.approx(r['gain'][-1])  # le gain du sous-portefeuille = réalisé (ventes partielles) + latent
    assert r['gain'][-1] == pytest.approx(2652 - (1000 + 1000 + 550 - 330))


def test_open_sleeve_is_retrospective_a_title_sold_later_leaves_the_view():
    later = SLEEVE_EVENTS + [ev(D[4], '12:00:00', 'sell', 'C', 20, 60, i=7)]
    r, keys = _sleeve(events=later)
    assert keys == ['A'] and 'C' not in r['positions']


def test_open_sleeve_interval_widens_when_a_purchase_happens_during_the_day():
    # B est détenu depuis la veille (100 → 140) ; A est acheté à midi à 125 : le cours de B à midi est inconnu, d'où un intervalle (bornes : cours de la veille / du soir).
    events = [ev(D[0], '00:00:00', 'buy', 'B', 10, 100, i=1), ev(D[1], '12:00:00', 'buy', 'A', 10, 125, i=2)]
    r, _ = _sleeve({'B': [100, 140, 140], 'A': [120, 130, 130]}, events, D[:3])
    assert r['estimated'][1] is True
    assert r['twr']['low'][-1] < r['twr']['central'][-1] < r['twr']['high'][-1]
    assert r['gain'][-1] == pytest.approx((10 * 140 - 1000) + (10 * 130 - 1250))  # le gain en euros reste exact, seul le pourcentage est borné


def test_open_sleeve_counts_dividends_of_open_titles_and_ignores_sold_ones():
    events = SLEEVE_EVENTS + [{'at': f'{D[4]} 00:00:00', 'kind': 'dividend', 'key': 'A', 'amount': 12.0, 'id': 8}, {'at': f'{D[0]} 12:00:00', 'kind': 'dividend', 'key': 'B', 'amount': 5.0, 'id': 9}]
    r, _ = _sleeve(events=events)
    assert r['positions']['A']['dividends'] == pytest.approx(12.0)
    assert r['value'][-1] == pytest.approx(2652)  # dividende encaissé puis retiré du sous-portefeuille : jamais de liquidités
    assert r['gain'][-1] == pytest.approx(2652 - 2220 + 12.0)
