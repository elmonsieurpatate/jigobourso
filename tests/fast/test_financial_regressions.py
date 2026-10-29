"""Audit-only regression expectations, no production access or application changes."""
import datetime as dt
from unittest.mock import patch
from engine.analytics import service as S, strategy as T
from engine.analytics.compute import _compute_one

def test_excluded_search_page_two_must_not_repeat_page_one():
    excluded=[{'id':i,'symbol':f'EX{i}','status':'excluded'} for i in range(1,51)]
    with patch.object(S,'scoped_entries',return_value=([],[],21,{})),patch.object(S,'latest_rates',return_value={}),patch.object(S,'_search_excluded',return_value=excluded),patch.object(S,'_attach_curves'):
        a=S.explore(None,{'view':{'q':'EX','page':1,'page_size':24}})
        b=S.explore(None,{'view':{'q':'EX','page':2,'page_size':24}})
    assert {r['id'] for r in a['rows']}.isdisjoint({r['id'] for r in b['rows']}), 'Page 2 repeats excluded listings from page 1'

def test_owned_only_with_no_holdings_must_return_nothing():
    entry={'id':1,'kind':'equity','mic':'XNYS','country':'US','category':None,'status':'retained','group':'equity','score':50,'rank':1,'fails':[]}
    with patch.object(S,'cached_verdicts',return_value=[entry]):
        _,scoped,_,_=S.scoped_entries(None,T.preset('regular'),{'owned_only':True,'owned_ids':[]},rates={},aux={})
    assert not scoped, 'Owned-only filter returns unowned securities for an empty portfolio'

def test_all_old_prices_must_not_be_marked_current():
    bars=[((dt.date(2026,7,1)+dt.timedelta(days=i)).isoformat(),100*1.002**i,None) for i in range(90)]
    metrics,states=[],[]
    _compute_one(1,'XNAS',bars,(),[21,63],{'XNAS':bars[-1][0]},dt.datetime(2026,10,29),metrics,states)
    assert states[0][-1]=='stale', f'Outdated series marked {states[0][-1]!r} because whole market is equally old'

def test_known_split_without_adjustments_must_not_be_scored_as_real_crash():
    raw=[((dt.date(2026,7,1)+dt.timedelta(days=i)).isoformat(),100*1.002**i/(2 if i>=75 else 1),None) for i in range(90)]
    adjusted=[(d,c,100*1.002**i/2) for i,(d,c,_) in enumerate(raw)]
    cfg=T.preset('regular')
    a=T.evaluate_one(cfg,{'bars':raw,'split_dates':[raw[75][0]]})
    b=T.evaluate_one(cfg,{'bars':adjusted,'split_dates':[raw[75][0]]})
    assert a['status']=='unknown' or a['status']==b['status'], f"Known split is treated as economic loss: raw {a['status']}, adjusted {b['status']}"
