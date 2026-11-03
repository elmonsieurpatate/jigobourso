import pytest
from engine.analytics import session

T=['2026-11-02T09:00:00','2026-11-02T09:15:00','2026-11-02T09:30:00']
B={1:list(zip(T,[100,101,102])),2:list(zip(T,[100,99,98]))}

def test_constant_holdings_euros_and_percentages_reconcile():
 r=session.build({1:2,2:1},B,{1:'EUR',2:'USD'},{'USD':[('2026-11-02',.8)]},[])
 assert r['value']==[280,281.2,282.4]
 assert r['gain'][-1]==pytest.approx(2.4)
 assert sum(l['gain'][-1] for l in r['lines'])==pytest.approx(r['gain'][-1])
 assert sum(100*l['gain'][-1]/r['base'] for l in r['lines'])==pytest.approx(r['pct'][-1])
 assert r['lines'][0]['pct'][-1]==2
 assert r['lines'][1]['pct'][-1]==pytest.approx(-2)


def test_intraday_trade_invalidates_that_line_and_global_not_other_titles():
 tx=[dict(listing_id=1,symbol='A',trade_at='2026-11-02 09:15:00')]
 r=session.build({1:2,2:1},B,{1:'EUR',2:'EUR'},{},tx)
 assert r['base'] is None and all(g is None for g in r['gain'])
 assert all(g is None for g in r['lines'][0]['gain'])
 assert r['lines'][1]['gain'][-1]==-2
 assert 'Transaction' in r['lines'][0]['reason']


def test_later_purchase_or_split_does_not_replay_current_quantities_in_old_session():
 r=session.build({1:20},B,{1:'EUR'},{},[dict(listing_id=1,symbol='A',trade_at='2026-11-03 12:00:00')])
 assert r['gain'][-1] is None
 r=session.build({1:20},B,{1:'EUR'},{},[],{1:[('2026-11-03',2)]})
 assert r['gain'][-1] is None and 'Split' in r['lines'][0]['reason']


def test_missing_bars_and_missing_first_price_stay_explicit():
 r=session.build({1:2,2:1},{1:B[1],2:B[2][1:]},{1:'EUR',2:'EUR'},{},[])
 assert r['lines'][0]['gain'][-1]==4
 assert r['gain'][-1] is None
 assert 'début' in r['lines'][1]['reason']
 assert session.build({1:2},{},{1:'EUR'},{},[])['dates']==[]


def test_no_fill_from_daily_close_when_a_fifteen_minute_bar_is_absent():
 r=session.build({1:2,2:1},{1:[B[1][0],B[1][2]],2:B[2]},{1:'EUR',2:'EUR'},{},[])
 assert r['lines'][0]['gain'][1] is None and r['gain'][1] is None
 assert r['gain'][-1]==2


@pytest.mark.parametrize('currency,fx,expected', [('GBp',{'GBP':[('2026-11-02',1.2)]},.012),('USD',{'USD':[('2026-10-20',.8)]},None),('USD',{},None)])
def test_fx_age_and_pence(currency,fx,expected):
 assert session.euro_rate(currency,'2026-11-02',fx)==expected


def test_last_stored_session_is_used_with_its_real_date():
 bars={1:[('2026-10-30T09:00:00',90)]+B[1]}
 r=session.build({1:2},bars,{1:'EUR'},{},[])
 assert r['day']=='2026-11-02' and r['dates']==T
