"""Règles de calcul du Portefeuille (pf-math.js, exécuté sous Node) avec des exemples de flux indépendants."""
import json, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node absent')


def js(expr, data):
    code = "const PFM=require(process.argv[1]);const D=JSON.parse(process.argv[2]);console.log(JSON.stringify(" + expr + "));"
    out = subprocess.run(['node', '-e', code, str(ROOT / 'app/public/assets/pf-math.js'), json.dumps(data)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def hist(dates, gain, value, purchases, net_in=None, factors=None):
    line = dict(key='1', symbol='A', name='A', values=value, gain=gain, purchases=purchases, net_in=net_in or purchases, quantities=[1] * len(dates))
    return dict(dates=dates, gain=gain, value=value, purchases=purchases, net_in=net_in or purchases, lines=[line], trades=[], performance=dict(factors=factors or [None] * len(dates)), market=None)


def test_total_percentage_uses_purchases_not_net_cash_after_full_sale():
    h = hist(['2026-01-01', '2026-01-02'], [0, 20], [100, 0], [100, 100])
    r = js("PFM.position(D,D.lines[0],PFM.resolveWindow(D,'all'))", h)
    assert r['result'] == 20 and r['pct'] == pytest.approx(20)


def test_period_includes_new_purchases_but_does_not_subtract_sales():
    # valeur de départ 1000, achat 500, vente nette 300, valeur finale 1300 => gain 100, base 1500
    h = hist(['2026-01-01', '2026-01-02'], [0, 100], [1000, 1300], [1000, 1500])
    r = js("PFM.position(D,D.lines[0],{i0:0,i1:1})", h)
    assert r['result'] == 100 and r['base'] == 1500 and r['pct'] == pytest.approx(100 * 100 / 1500)


def test_unknown_value_is_not_zero():
    h = hist(['2026-01-01', '2026-01-02', '2026-01-03'], [0, None, 10], [100, None, 110], [100, 100, 100])
    r = js("PFM.position(D,D.lines[0],{i0:1,i1:2})", h)
    assert r['result'] is None and r['reason']                                          # départ non valorisable : pas de zéro inventé
    assert js("PFM.position(D,D.lines[0],PFM.resolveWindow(D,'all'))", h)['result'] == 10


def test_period_reference_is_calendar_based_and_clamps_month_end():
    dates = ['2026-01-28', '2026-02-27', '2026-02-28', '2026-03-31']
    h = hist(dates, [0, 1, 2, 3], [1, 2, 3, 4], [1, 1, 1, 1])
    w = js("PFM.resolveWindow(D,'1m')", h)
    assert w['from'] == '2026-02-28' and w['i0'] == 2                                  # 31 mars − 1 mois = 28 février
    assert js("PFM.resolveWindow(D,'1w')", h)['from'] == '2026-03-24'


def test_period_before_history_is_flagged_not_extrapolated():
    h = hist(['2026-03-01', '2026-03-02'], [0, 5], [10, 15], [10, 10])
    w = js("PFM.resolveWindow(D,'1y')", h)
    assert w['clipped'] is True and w['i0'] == -1


def test_contribution_uses_portfolio_capital_not_stock_return():
    h = hist(['2026-01-01', '2026-01-02'], [0, 10], [100, 110], [100, 100])
    c = js("PFM.contribution(PFM.position(D,D.lines[0],{i0:-1,i1:1}),PFM.portfolio(D,{i0:-1,i1:1}))", h)
    assert c == pytest.approx(10)                                                      # 10 € sur 100 € engagés


def test_personal_peak_and_drop():
    h = hist(['a', 'b', 'c'], [0, 30, 10], [1, 1, 1], [1, 1, 1])
    r = js("PFM.personalPeak(D.lines[0])", h)
    assert r['peak'] == 30 and r['drop'] == -20
