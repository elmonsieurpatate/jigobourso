"""Six scénarios de validation du modèle à liquidités (voir tests/seeds/cash_scenarios.py). Les valeurs attendues sont calculées à la main dans les commentaires."""

import pytest

from tests.seeds import cash_scenarios as sc


def test_s1_buy_200_sell_250_gives_1050_gain_50_and_5_percent():
    r = sc.row(sc.s1)
    assert (r['cash'], r['securities'], r['value'], r['gain'], r['realized'], r['latent']) == pytest.approx((1050, 0, 1050, 50, 50, 0))
    assert r['open'] == {} and r['net_contributions'] == 1000
    assert r['twr']['central'] == pytest.approx(0.05) and r['twr']['low'] == pytest.approx(0.05) and r['twr']['high'] == pytest.approx(0.05)
    assert r['estimated_days'] == 0  # aucun flux externe après le capital initial : rendement exact


def test_s2_deposit_and_withdrawal_create_no_gain_or_loss():
    r = sc.row(sc.s2)
    # 1 050 + 500 − 100 = 1 450 ; apports nets 1 000 + 500 − 100 = 1 400 ; gain 1 450 − 1 400 = 50 (inchangé)
    assert (r['cash'], r['value'], r['net_contributions'], r['gain']) == pytest.approx((1450, 1450, 1400, 50))
    assert r['twr']['central'] == pytest.approx(0.05)  # même rendement que le scénario 1
    assert r['estimated_days'] == 0  # dépôt et retrait sans titre détenu : aucune incertitude
    one, two = sc.row(sc.s1), r
    assert one['gain'] == two['gain'] and one['twr']['central'] == pytest.approx(two['twr']['central'])


def test_s3_successive_trades_with_reinvestment():
    r = sc.row(sc.s3)
    # cash : 1000 − 500 + 550 − 500 − 420 + 560 = 690 ; A : 4 × 110 = 440 ; valeur 1 130
    assert (r['cash'], r['securities'], r['value']) == pytest.approx((690, 440, 1130))
    # réalisé : A 550 − 500 = 50 ; B 560 − 500 = 60 ; latent : A 440 − 420 = 20 ; total 130
    assert (r['realized'], r['latent'], r['gain']) == pytest.approx((110, 20, 130))
    assert r['open'] == {'A': 4} and r['twr']['central'] == pytest.approx(0.13) and r['estimated_days'] == 0
    assert sum(r['contributions'].values()) == pytest.approx(0.13)


def test_s4_realized_gain_is_kept_after_full_sale_whatever_the_price_does_next():
    s, res = sc.run(sc.s4)
    assert res['positions']['A']['status'] == 'closed' and res['positions']['A']['quantity'] == 0
    assert res['realized'][-1] == pytest.approx(300) and res['latent'][-1] == pytest.approx(0)
    assert res['value'] == pytest.approx([1000, 1000, 1300, 1300, 1300, 1300])  # A tombe à 80 après la vente : aucun effet
    assert res['positions']['A']['twr'] == pytest.approx(0.30) and res['twr']['central'][-1] == pytest.approx(0.30)
    assert res['positions']['A']['last_day'] == sc.DAYS[2]  # visible pendant sa détention seulement


def test_s5_contributions_per_security_sum_to_the_portfolio_return():
    r = sc.row(sc.s5)
    # A 4 × (121 − 100) = +84 ; B 4 × (45 − 50) = −20 ; C 10 × (22 − 20) = +20 ; liquidités 200 € sans rendement
    assert (r['cash'], r['securities'], r['value'], r['gain']) == pytest.approx((200, 884, 1084, 84))
    assert r['twr']['central'] == pytest.approx(0.084)
    c = r['contributions']
    assert sum(c.values()) == pytest.approx(0.084, abs=1e-12)
    assert c['A'] == pytest.approx(0.084, abs=0.003) and c['B'] == pytest.approx(-0.020, abs=0.003) and c['C'] == pytest.approx(0.020, abs=0.003)
    assert c['__fees__'] == 0 and r['checks']['contribution_sum_max_abs_error'] < 1e-12


def test_s6_foreign_currency_gain_splits_into_price_and_exchange_effects():
    s, res = sc.run(sc.s6)
    # prix : 10 × (110 − 100) $ × 0,90 = 90 € ; change : 10 × 110 $ × (0,95 − 0,90) = 55 € ; total 145 €
    price_effect = 10 * (110 - 100) * 0.90
    fx_effect = 10 * 110 * (0.95 - 0.90)
    assert price_effect == pytest.approx(90) and fx_effect == pytest.approx(55)
    assert res['gain'][-1] == pytest.approx(price_effect + fx_effect) and res['realized'][-1] == pytest.approx(145)
    assert res['value'][-1] == pytest.approx(1145) and res['twr']['central'][-1] == pytest.approx(0.145)
    assert res['positions']['U']['twr'] == pytest.approx(1045 / 900 - 1)  # rendement du titre en euros
    assert res['value'][2] == pytest.approx(100 + 10 * 110 * 0.95)  # valorisation au change du jour (1 145)
    assert res['checks']['identity_max_abs_error'] < 1e-9


@pytest.mark.parametrize('build', sc.SCENARIOS)
def test_every_scenario_respects_the_accounting_identities(build):
    s, r = sc.run(build)
    assert r['checks']['identity_max_abs_error'] < 1e-9 and r['checks']['contribution_sum_max_abs_error'] < 1e-12
    for i in range(len(sc.DAYS)):
        assert r['cash'][i] + r['securities'][i] == pytest.approx(r['value'][i])
        assert r['value'][i] - r['net_contributions'][i] == pytest.approx(r['realized'][i] + r['latent'][i] + r['dividends'][i] - r['fees'][i])
