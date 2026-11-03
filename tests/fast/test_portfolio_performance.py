"""Exercise the actual JavaScript performance function with independent cash-flow examples."""
import json
from pathlib import Path
import subprocess

import pytest


def perf(gain, values, purchases, start, end):
    source = (Path(__file__).resolve().parents[2] / 'app/public/assets/portefeuilles.js').read_text()
    function = source[source.index('  function perf('):source.index('  const PER_LABEL')]
    code = function + '\nconsole.log(JSON.stringify(perf(...JSON.parse(process.argv[1]))));'
    out = subprocess.run(['node', '-e', code, json.dumps([gain, values, purchases, start, end])],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_total_percentage_uses_purchases_not_net_cash_after_full_sale():
    assert perf([0, 20], [100, 0], [100, 100], 0, 1) == {'eur': 20, 'pct': 20}
    result = perf([0, 233.4], [100, 2900.4], [100, 3942], 0, 1)
    assert result['pct'] == pytest.approx(100 * 233.4 / 3942)


def test_period_includes_new_purchases_but_does_not_subtract_sales():
    # Start value 1000, purchase 500, net sale 300, final value 1300 => gain 100.
    assert perf([0, 0, 100], [0, 1000, 1300], [0, 1000, 1500], 1, 2) == {'eur': 100, 'pct': 100 / 15}


def test_unknown_value_is_not_zero_and_small_capital_has_a_percentage():
    assert perf([None, None], [None, None], [10, 10], 0, 1) == {'eur': None, 'pct': None}
    assert perf([0, .1], [.1, .2], [.1, .1], 0, 1) == {'eur': .1, 'pct': 100}


def test_period_reference_is_calendar_based_and_clamps_month_end():
    source = (Path(__file__).resolve().parents[2] / 'app/public/assets/portefeuilles.js').read_text()
    function = source[source.index('  function periodStart('):source.index('  /* Gain /')]
    code = "const EVO={per:process.argv[1]};\n" + function + '\nconsole.log(periodStart({dates:JSON.parse(process.argv[2])}));'
    for period,dates,expected in [('1m',['2026-02-27','2026-02-28','2026-03-01','2026-03-31'],1),
                                  ('1w',['2026-10-26','2026-10-27','2026-10-28','2026-11-03'],1),
                                  ('all',['2026-01-01','2026-11-03'],0)]:
        out=subprocess.run(['node','-e',code,period,json.dumps(dates)],capture_output=True,text=True,check=True)
        assert int(out.stdout)==expected


def test_purchase_markers_never_clamp_outside_window_and_keep_recorded_time():
    source=(Path(__file__).resolve().parents[2]/'app/public/assets/portefeuilles.js').read_text()
    functions=source[source.index('  const tradePrice ='):source.index('  function focusAnalysis(')]
    trades=[dict(key='1',side='buy',date='2026-01-01',trade_at='2026-01-01 12:00:00',symbol='A'),
            dict(key='1',side='buy',date='2026-01-07',trade_at='2026-01-07 09:15:00',symbol='A',quantity=2,unit_price=50,currency='USD',fees_eur=1,fx_to_eur=.9,first_buy=False),
            dict(key='2',side='buy',date='2026-01-07',trade_at='2026-01-07 12:00:00',symbol='B'),
            dict(key='1',side='buy',date='2026-02-01',trade_at='2026-02-01 12:00:00',symbol='A')]
    prelude='const J={num:String,eur:String};const ANALYSIS={markers:true,focus:"1"};const H={trades:JSON.parse(process.argv[1])};'
    code=prelude+functions+'''\nconst daily=purchaseMarkers(['2026-01-05','2026-01-09']);
    const intraday=purchaseMarkers(['2026-01-07T09:00:00','2026-01-07T09:30:00'],true);
    ANALYSIS.markers=false;
    console.log(JSON.stringify([daily,intraday,purchaseMarkers(['2026-01-05','2026-01-09'])]));'''
    out=subprocess.run(['node','-e',code,json.dumps(trades)],capture_output=True,text=True,check=True)
    daily,intraday,hidden=json.loads(out.stdout)
    assert [m['x'] for m in daily]==['2026-01-07']
    assert [m['x'] for m in intraday]==['2026-01-07T09:15:00']
    assert 'complémentaire A' in daily[0]['label']
    assert 'USD' in daily[0]['detail'] and 'frais 1' in daily[0]['detail']
    assert hidden==[]
