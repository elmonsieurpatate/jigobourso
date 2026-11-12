import copy
import datetime as dt
import pytest
from engine.analytics.series import history
from engine.analytics.portfolio import performance
from engine.analytics.admin.service import criteria_proximity


def trade(i, day, side, qty, price, lid=1, fees=0, fx=1):
    return dict(id=i,trade_at=day+' 12:00:00',date=day,side=side,quantity=qty,unit_price=price,
                listing_id=lid,symbol='A'+str(lid),name=None,currency='EUR',fx_to_eur=fx,fees=fees,fees_eur=fees)


def test_200_euros_plus_five_percent_then_200_purchase_does_not_dilute_performance():
    tx=[trade(1,'2026-01-05','buy',2,100),trade(2,'2026-01-07','buy',2,100,lid=2)]
    before=copy.deepcopy(tx)
    bars={1:[('2026-01-05',100,None),('2026-01-06',105,None),('2026-01-07',105,None)],
          2:[('2026-01-05',100,None),('2026-01-06',100,None),('2026-01-07',100,None)]}
    out=history.build(tx,bars,{}, {1:'EUR',2:'EUR'},{},{},dt.date(2026,1,7))
    assert out['gain']==[0,10,10] and out['value']==[200,210,410]
    assert 100*out['gain'][-1]/out['purchases'][-1]==2.5
    assert out['performance']['index']==pytest.approx([1,1.05,1.05])
    assert out['performance']['estimated']==[True,False,True]
    assert tx==before


def test_daily_flow_estimate_uses_dated_weights_not_a_capital_return():
    r=performance.linked(['2026-01-05','2026-01-06'],[100,220],
        [trade(1,'2026-01-05','buy',1,100),trade(2,'2026-01-06','buy',1,100)])
    assert r['factors'][1]==pytest.approx(1+20/150)
    assert 'estimée' in r['notes'][0]


def test_partial_sale_liquidation_empty_days_and_rebuy_preserve_return():
    trades=[trade(1,'2026-01-05','buy',2,100),trade(2,'2026-01-07','sell',1,105),
            trade(3,'2026-01-08','sell',1,105),trade(4,'2026-01-10','buy',1,100)]
    days=['2026-01-'+str(i).zfill(2) for i in range(5,12)]
    r=performance.linked(days,[200,210,105,0,0,100,110],trades)
    assert r['index']==pytest.approx([1,1.05,1.05,1.05,1.05,1.05,1.155])


def test_fees_remain_losses_and_rounding_does_not_create_gains():
    r=performance.linked(['2026-01-05','2026-01-06'],[100,0],
                         [trade(1,'2026-01-05','buy',1,100,fees=2),trade(2,'2026-01-06','sell',1,100,fees=1)])
    assert r['index'][-1]==pytest.approx(99/102)
    r=performance.linked(['2026-01-05'],[1/3],[trade(1,'2026-01-05','buy',1,1/3)])
    assert r['index']==[1]


def test_missing_values_and_invalid_fx_never_bridge_history():
    tx=[trade(1,'2026-01-05','buy',1,100)]
    r=performance.linked(['2026-01-05','2026-01-06','2026-01-07','2026-01-08'],[100,None,110,121],tx)
    assert r['index']==[1,None,None,None]
    assert r['factors'][-1]==pytest.approx(1.1) # A later selected period can be rebased honestly.
    assert performance.linked(['2026-01-05'],[100],tx,invalid=True)['index']==[None]


def test_converted_flows_and_split_values_do_not_create_performance():
    r=performance.linked(['2026-01-05','2026-01-06'],[90,90],[trade(1,'2026-01-05','buy',1,100,fx=.9)])
    assert r['index']==[1,1] # Split changes shares/prices, never value; FX is already in euros.


def test_near_criteria_is_independent_of_symbol_rank_and_score():
    def reason(value,threshold=10,result='fail'):
        return dict(metric='perf',value=value,threshold=threshold,result=result)
    near=criteria_proximity([reason(9.9)])
    far=criteria_proximity([reason(3)])
    two=criteria_proximity([reason(9.99),reason(9.99)])
    missing=criteria_proximity([reason(9.99),reason(None,result='missing')])
    assert near<far<two<missing
    assert criteria_proximity([reason(-1,0)])[2]==1


def test_history_split_is_neutral_and_old_quote_is_not_redated_for_performance():
    tx=[trade(1,'2026-01-05','buy',1,100)]
    r=history.build(tx,{1:[('2026-01-05',100,None),('2026-01-06',50,None)]},
                    {1:[('2026-01-06',2)]},{1:'EUR'},{},{},dt.date(2026,1,6))
    assert r['value']==[100,100] and r['performance']['index']==[1,1]
    r=history.build(tx,{1:[('2026-01-05',100,None)]},{},{1:'EUR'},{},
                    {1:{'price':100,'price_time':'2026-01-05 18:00:00'}},dt.date(2026,1,20))
    assert r['value'][-1]==100 # Existing valuation convention is preserved.
    assert r['performance']['index'][-1] is None
    assert any('sept jours' in n for n in r['performance']['notes'])


def test_old_fx_is_unavailable_for_neutral_performance_without_rewriting_totals():
    r=history.build([trade(1,'2026-01-05','buy',1,100,fx=.9)],
                    {1:[('2026-01-05',100,None),('2026-01-20',100,None)]},{},{1:'USD'},
                    {'USD':[('2026-01-05',.9)]},{},dt.date(2026,1,20))
    assert r['value'][-1]==90 and r['performance']['index'][-1] is None


def test_legacy_oversale_cannot_produce_a_neutral_performance():
    tx=[trade(1,'2026-01-05','buy',1,100),trade(2,'2026-01-06','sell',2,100)]
    r=history.build(tx,{1:[('2026-01-05',100,None),('2026-01-06',100,None)]},{},{1:'EUR'},{},{},dt.date(2026,1,6))
    assert r['performance']['index']==[None,None]
