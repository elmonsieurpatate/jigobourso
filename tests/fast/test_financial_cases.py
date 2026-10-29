"""Numerical oracles: hand-computable returns, splits and independent clock freshness."""
import datetime as dt
import math
import pytest
from engine.analytics.series import analyze_series
from engine.market import hours
from engine.market.collect import to_eur_factor

@pytest.mark.parametrize('unit,factor',[('GBP',1.2),('GBp',.012),('GBX',.012),('EUR',1)])
def test_price_units(unit,factor):
    assert to_eur_factor(unit,{'GBP':1.2})==pytest.approx(factor)

@pytest.mark.parametrize('ratio',[2.0, .1, 1.25])
def test_split_ratio_is_not_economic_return(ratio):
    # A 2:1 split turns 100 into 50; a 1:10 reverse split turns 100 into 1000.
    bars=[('2026-10-01',100,None),('2026-10-02',100/ratio,None),('2026-10-05',110/ratio,None)]
    _,closes,_,breaks,metrics,_,_=analyze_series(bars,[1,2],[('2026-10-02',ratio)])
    assert not breaks
    assert metrics[2]['perf']==pytest.approx(10)
    assert metrics[1]['perf']==pytest.approx(10)
    assert closes[0]==pytest.approx(100/ratio)

def test_unknown_small_split_is_not_treated_as_return():
    bars=[('2026-10-01',100,None),('2026-10-02',80,None),('2026-10-05',84,None)]
    _,_,_,_,metrics,missing,_=analyze_series(bars,[1,2],['2026-10-02'])
    assert metrics[2] is None and missing[2]=='break'
    assert metrics[1]['perf']==pytest.approx(5)

def test_vendor_adjustments_take_priority_over_split_ratio():
    bars=[('2026-10-01',100,50),('2026-10-02',50,50),('2026-10-05',55,55)]
    *_,metrics,missing,tech=analyze_series(bars,[2],[('2026-10-02',2)])
    assert metrics[2]['perf']==pytest.approx(10)  # never apply the split twice

def test_log_slope_compounding_known_case():
    bars=[(str(i),100*1.01**i,None) for i in range(22)]
    *_,metrics,missing,tech=analyze_series(bars,[21])
    m=metrics[21]
    assert m['slope']==pytest.approx(1)
    assert m['r2']==pytest.approx(1)
    assert m['perf']==pytest.approx(100*(1.01**21-1))
    assert m['drawdown']==pytest.approx(0)

@pytest.mark.parametrize('mic,stamp,expected',[
 ('XETR','2026-10-26T07:00:00+00:00','2026-10-23'),
 ('XETR','2026-10-26T16:45:00+00:00','2026-10-23'),
 ('XETR','2026-10-26T17:00:00+00:00','2026-10-26'),
 ('XNYS','2026-10-29T20:29:00+00:00','2026-10-28'),
 ('XNYS','2026-10-29T20:30:00+00:00','2026-10-29'),
 ('XNYS','2026-11-02T21:30:00+00:00','2026-11-02'),
 ('XETR','2026-10-25T18:00:00+00:00','2026-10-23')])
def test_independent_freshness_clock(mic,stamp,expected):
    assert hours.expected_last_close(mic,dt.datetime.fromisoformat(stamp))==expected
