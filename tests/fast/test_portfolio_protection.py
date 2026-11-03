import datetime as dt
import pytest

from engine.analytics.portfolio import protection, diagnose
from engine.market import hours

DAYS = ['2026-01-01', '2026-01-02', '2026-01-03']
RATES = {d: 1 for d in DAYS}
LOT = {'trade_date': '2026-01-02', 'remaining': 1, 'remaining_cost': 100}


def test_100_108_104_distinguishes_percentage_points_from_price_decline():
    p = protection([LOT], DAYS, [99,100,108], RATES, 104,104,'2026-01-04')
    assert p['peak_gain_pct'] == pytest.approx(8)
    assert p['gain_pct'] == pytest.approx(4)
    assert p['given_back_pp'] == pytest.approx(4)
    assert p['drop_pct'] == pytest.approx(100*(1-104/108))


def test_multiple_buys_do_not_sum_peaks_or_include_a_lot_before_purchase():
    lots=[LOT,dict(LOT,trade_date='2026-01-03',remaining_cost=110)]
    p=protection(lots,DAYS,[99,200,110],RATES,115,115,'2026-01-04',basis_cost=210)
    assert p['start']=='2026-01-03'
    assert p['peak_gain_eur']==20 and p['high']==115 # 200 was before the second lot.
    own=protection([LOT],DAYS,[99,200,110],RATES,115,115,'2026-01-04')
    assert own['peak_gain_eur']==100


def test_partial_sale_and_split_use_remaining_cost_and_adjusted_units():
    # Half of a 100-euro purchase remains after a 2:1 split => one share, cost 50.
    l=dict(LOT,remaining=1,remaining_cost=50)
    p=protection([l],DAYS,[49.5,50,54],RATES,52,52,'2026-01-04')
    assert p['gain_pct']==pytest.approx(4) and p['peak_gain_pct']==pytest.approx(8)
    p=protection([dict(l,remaining=.1)],DAYS,[495,500,540],RATES,520,520,'2026-01-04')
    assert p['gain_pct']==pytest.approx(4)


def test_fees_and_historical_currency_rates_are_personal_not_price_returns():
    rates={d:.8 for d in DAYS}; l=dict(LOT,remaining_cost=91) # paid 100 USD at .9 + 1 EUR fees.
    p=protection([l],DAYS,[99,100,108],rates,104*.85,104,'2026-01-04')
    assert p['gain_eur']==pytest.approx(-2.6)
    assert p['drop_pct']==pytest.approx(100*(1-104/108))
    assert p['gain_pct']!=pytest.approx(4)


@pytest.mark.parametrize('change',[{'remaining_cost':None},{'remaining_cost':0},{'manual_split':True},{'history_incomplete':True}])
def test_unknown_or_non_comparable_basis_never_fabricates_a_peak(change):
    assert not protection([dict(LOT,**change)],DAYS,[99,100,108],RATES,104,104,'2026-01-04')['available']


def test_truncated_or_missing_fx_and_future_data_are_not_used_as_true_peak():
    assert not protection([LOT],DAYS[2:],[108],RATES,104,104,'2026-01-04')['available']
    assert not protection([LOT],DAYS,[99,100,108],{},104,104,'2026-01-04')['available']
    p=protection([LOT],DAYS+['2026-01-10'],[99,100,108,9999],RATES,104,104,'2026-01-04')
    assert p['peak_gain_pct']==pytest.approx(8)


def test_returned_gain_is_not_new_capital_loss():
    p=protection([LOT],DAYS,[99,100,108],RATES,90,90,'2026-01-04')
    assert p['given_back_pp']==pytest.approx(8) # all positive gain returned; the loss is separate.
    assert p['gain_pct']==pytest.approx(-10)


def test_personal_profit_and_unfavorable_market_can_coexist(monkeypatch):
    now=dt.datetime(2026,1,6,10,tzinfo=dt.timezone.utc);monkeypatch.setattr(hours,'utcnow',lambda:now)
    p={'value':104,'price':104,'price_time':'2026-01-06 10:00:00','mic':'XPAR','unrealized':4}
    state={'last_close_date':'2026-01-05','quality':'ok','close':104,'momentum_6m':-10,'ma50':110}
    measures={21:{'slope':-.1,'perf':-6},63:{'perf':15,'volatility':2}}
    d=diagnose(p,[{'strategy':'momentum','alerts':[{'kind':'momentum','message':'Momentum négatif','level':'act','action':'examiner'}]}],state,measures,{},'2026-01-06')
    assert d['status']=='act' and 'bénéficiaire' in d['personal_text'] and d['market']['trend']=='down'
    d=diagnose(dict(p,unrealized=-4),[],state,{21:{'slope':.1,'perf':6}}, {},'2026-01-06')
    assert 'en perte' in d['personal_text'] and d['market']['trend']!='down'


def test_missing_data_is_neutral_and_existing_contradiction_is_preventive(monkeypatch):
    now=dt.datetime(2026,1,6,10,tzinfo=dt.timezone.utc);monkeypatch.setattr(hours,'utcnow',lambda:now)
    p={'value':104,'price':104,'price_time':'2026-01-06 10:00:00','mic':'XPAR','unrealized':4}
    st={'last_close_date':'2026-01-05','quality':'ok','close':104};m={21:{'slope':-.1,'perf':-6},63:{'perf':15}}
    assert diagnose(p,[],st,m,{},'2026-01-06')['status']=='watch'
    assert diagnose(p,[],dict(st,quality='stale'),m,{},'2026-01-06')['status']=='unknown'
    assert diagnose(p,[],st,{}, {},'2026-01-06')['status']=='unknown'


def test_duplicate_reasons_keep_the_highest_severity(monkeypatch):
    monkeypatch.setattr(hours,'utcnow',lambda:dt.datetime(2026,1,6,10,tzinfo=dt.timezone.utc))
    p={'value':104,'price':104,'price_time':'2026-01-06 10:00:00','mic':'XPAR','unrealized':4}
    lots=[{'alerts':[{'kind':'drop','message':'Même recul','level':'act','action':'examiner'}]},
          {'alerts':[{'kind':'drop','message':'Même recul','level':'watch','action':'surveiller'}]}]
    d=diagnose(p,lots,{'last_close_date':'2026-01-05','quality':'ok','close':104},{21:{'slope':.1,'perf':4}}, {},'2026-01-06')
    assert d['status']=='act' and len(d['reasons'])==1


def test_volatility_watch_uses_the_selected_profile_ceiling_not_a_universal_drop(monkeypatch):
    monkeypatch.setattr(hours,'utcnow',lambda:dt.datetime(2026,1,6,10,tzinfo=dt.timezone.utc))
    p={'value':104,'price':104,'price_time':'2026-01-06 10:00:00','mic':'XPAR','unrealized':4}
    st={'last_close_date':'2026-01-05','quality':'ok','close':104}
    m={21:{'slope':.1,'perf':4,'volatility':2},63:{'perf':4,'volatility':2}}
    slow=diagnose(p,[{'strategy':'low_volatility','alerts':[]}],st,m,{},'2026-01-06')
    fast=diagnose(p,[{'strategy':'fast','alerts':[]}],st,m,{},'2026-01-06')
    assert slow['status']=='watch' and any(r['threshold']==1.5 for r in slow['reasons'])
    assert fast['status']=='normal'


def test_duration_reminder_does_not_claim_market_deterioration(monkeypatch):
    monkeypatch.setattr(hours,'utcnow',lambda:dt.datetime(2026,1,6,10,tzinfo=dt.timezone.utc))
    p={'value':104,'price':104,'price_time':'2026-01-06 10:00:00','mic':'XPAR','unrealized':4}
    lot={'alerts':[{'kind':'duration','message':'Rappel 182 jours','level':'watch','action':'réexaminer','threshold':182}]}
    d=diagnose(p,[lot],{'last_close_date':'2026-01-05','quality':'ok','close':104},{21:{'slope':.1,'perf':4}}, {},'2026-01-06')
    assert d['status']=='watch' and 'Rappel périodique' in d['next_step']
    assert 'sans conclure à une dégradation' in d['next_step']
