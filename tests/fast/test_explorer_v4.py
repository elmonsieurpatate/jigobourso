"""Financial and configuration contracts for the single Explorer engine."""
import copy
import math
import pytest
from engine.analytics import strategy as S, explorer_config as C, configurable_score as R
from engine.analytics.measures import window_metrics
from engine.analytics.explorer_metrics import path_metrics


def setup_config():
    c=C.empty();p=c['periods'][2];p.update(enabled=True,min_slope=0)
    return c,p


@pytest.mark.parametrize('n',[1,5,21,63,126,252])
@pytest.mark.parametrize('value',[-99,-10,0,5,200])
def test_period_slope_roundtrip(n,value):
    assert C.period_slope(C.session_slope(value,n),n)==pytest.approx(value)


def test_upgrade_preserves_all_historical_thresholds_and_original():
    old=S.preset('fast');before=copy.deepcopy(old);c=C.upgrade(old)
    assert old==before and c['version']==4
    for a,b in zip(old['periods'],c['periods']):
        assert all(b[k]==v for k,v in a.items())
        assert b['require_history']==a['enabled']
    assert C.validate(c)==c
    assert S.validate(old)==old


def test_empty_and_zero_are_distinct():
    c=C.empty();assert not any(p['enabled'] for p in c['periods'])
    c,p=setup_config()
    assert S.judge(c,{21:{'slope':-0.001}},{},{})['status']=='rejected'
    p['min_slope']=None
    assert S.judge(c,{},{},{})['status']=='retained'


def test_last_day_is_close_return_and_unavailable_statistics_rejected():
    m=window_metrics([100,99]);assert m['slope']==pytest.approx(-1) and m['r2'] is None
    c=C.empty();c['periods'][0].update(enabled=True,min_r2=0)
    with pytest.raises(ValueError):C.validate(c)


def test_path_metrics_concentration_continuity_and_missing_liquidity():
    m=path_metrics([100,110,121,120],[10,None,30],[100,200,300])
    assert m['up_days']==2 and m['up_fraction']==pytest.approx(2/3)
    assert m['gain_share']==pytest.approx(50) and m['avg_volume'] is None
    assert m['turnover_eur']==200 and m['current_drawdown']==pytest.approx(100/121)
    assert path_metrics([100,None,110])=={}
    assert path_metrics([100,90,80])['gain_net_share'] is None
    assert path_metrics([100,100])['gain_share']==0


def test_constraints_missing_vs_zero_and_any_keeps_mandatory_freshness():
    c,p=setup_config();p.update(min_r2=.6);c['selection'].update(combine='any',require_fresh=True)
    assert S.judge(c,{21:{'slope':1,'r2':.1}},{},{})['status']=='retained'
    assert S.judge(c,{21:{'slope':1,'r2':.1}},{},{},'2026-10-01','2026-10-02')['status']=='unknown'
    c['selection']['missing']='reject'
    assert S.judge(c,{21:{'slope':1,'r2':.1}},{},{},'2026-10-01','2026-10-02')['status']=='rejected'


def verdict(key,value,kind='equity'):
    return dict(key=key,symbol=str(key),group=kind,status='retained',reasons=[],technical={},measures={21:{'perf':value,'slope':None if value is None else value/100}})


def scored_config():
    c,p=setup_config();p['min_slope']=None
    c['ranking']['components']=[dict(id='return',metric='perf',period='month',enabled=True,kind='all',weight=2,normalization='percentile',direction='higher',transform='identity',min=0,max=100,exponent=1)]
    return C.validate(c)


def test_weighted_percentiles_global_ties_and_exact_contributions():
    c=scored_config();vs=[verdict(1,1),verdict(2,2),verdict(3,3),verdict(4,2)]
    R.rank(c,vs,S._percentiles)
    assert vs[2]['rank']==1 and vs[1]['score']==vs[3]['score']
    assert all(v['score']==pytest.approx(sum(p['contribution'] for p in v['score_parts'])) for v in vs)
    assert [v['score'] for v in vs]==pytest.approx([0,50,100,50])


def test_negative_weights_zero_inactive_period_and_missing_policies():
    c=scored_config();c['ranking']['components'][0].update(weight=-2,normalization='raw')
    vs=[verdict(1,4),verdict(2,None)]
    R.rank(c,vs,S._percentiles)
    assert vs[0]['score']==-4 and vs[1]['status']=='unknown'
    c['ranking']['missing']='renormalize';vs=[verdict(1,None)]
    R.rank(c,vs,S._percentiles);assert vs[0]['score'] is None and vs[0]['score_missing']==1
    c['periods'][2]['enabled']=False
    assert R.active_components(c)==[]


def test_per_asset_overrides_and_score_disabling():
    c=scored_config();c['asset_rules']={'etf':{'periods':{'month':{'min_r2':.6,'enabled':False}}}}
    c=C.validate(c);assert C.effective(c,'equity')['periods'][2]['enabled']
    assert not C.effective(c,'etf')['periods'][2]['enabled']
    vs=[verdict(1,5,'equity'),verdict(2,5,'etf')];R.rank(c,vs,S._percentiles)
    assert vs[0]['score'] is not None and vs[1]['score'] is None


def test_validation_inverted_bounds_and_unknown_metric():
    c,p=setup_config();p.update(min_r2=.8,max_r2=.6)
    with pytest.raises(ValueError):C.validate(c)
    c=scored_config();c['ranking']['components'][0]['metric']='invented'
    with pytest.raises(ValueError):C.validate(c)


@pytest.mark.parametrize('name',S.PRESETS)
def test_migrated_builtin_rank_is_numerically_unchanged(name):
    old=S.preset(name);new=C.upgrade(old)
    def rows():
        return [dict(key=i,symbol=str(i),group='equity',status='retained',reasons=[],technical={},momentum={'6m':i*2,'12m':i*3} if name=='momentum_risk' else i*2,
                     measures={n:dict(slope=i*.1,perf=i*2,r2=.6+i*.05,volatility=4-i*.4,drawdown=10-i) for n in (1,5,21,63,126,252)}) for i in (1,2,3)]
    a=S.rank(old,rows());b=S.rank(new,rows())
    assert [v['score'] for v in b]==pytest.approx([v['score'] for v in a])
    assert [v['rank'] for v in b]==[v['rank'] for v in a]
    for v in b:assert v['score']==pytest.approx(sum(p['contribution'] for p in v['score_parts']))


def test_deselecting_momentum_period_stops_its_missing_data_gate_and_score():
    c=C.upgrade(S.preset('momentum'));c['periods'][4]['enabled']=False
    v=S.judge(c,{},{},{},momentum=None);assert v['status']=='retained'
    v.update(key=1,symbol='S',group='equity')
    assert S.rank(c,[v])[0]['score'] is None


def test_log_regression_exact_period_growth_and_stability():
    for n in [5,21,63,126,252]:
        expected=12.5;b=math.log1p(expected/100)/n
        prices=[100*math.exp(i*b) for i in range(n+1)]
        m=window_metrics(prices)
        assert C.period_slope(m['slope'],n)==pytest.approx(expected)
        assert m['r2']==pytest.approx(1) and m['perf']==pytest.approx(expected)
        assert m['volatility']==pytest.approx(0,abs=1e-10) and m['drawdown']==0


@pytest.mark.parametrize('field,value',[('technical',[]),('selection','false'),('liquidity',3),('ranking',[]),('asset_rules',False),('presentation','global')])
def test_malformed_sections_are_validation_errors(field,value):
    c=C.empty();c[field]=value
    with pytest.raises(ValueError):C.validate(c)


def test_string_false_is_never_a_boolean_and_null_weight_is_not_numeric():
    c=C.empty();c['technical']['above_ma50']='false'
    with pytest.raises(ValueError):C.validate(c)
    c=C.upgrade(S.preset('regular'));c['ranking']['weights']['month']=None
    with pytest.raises(ValueError):C.validate(c)


@pytest.mark.parametrize('name',S.PRESETS)
def test_editable_presets_use_generic_components_and_keep_legacy_scores(name):
    old=C.upgrade(S.preset(name));new=C.editable(S.preset(name));assert new['ranking']['mode']=='weighted'
    def rows():
        return [dict(key=i,symbol=str(i),group='equity',status='retained',reasons=[],technical={},momentum={'6m':i*2,'12m':i*3} if name=='momentum_risk' else {'6m':i*2,'12m':i*3},measures={n:dict(slope=i*.1,perf=i*2,r2=.6+i*.05,volatility=4-i*.4,drawdown=10-i) for n in (1,5,21,63,126,252)}) for i in (1,2,3)]
    legacy=rows()
    if name in ('momentum','momentum12'):
        for v in legacy:v['momentum']=v['momentum']['12m' if name=='momentum12' else '6m']
    a=S.rank(old,legacy);b=S.rank(new,rows())
    assert [v['score'] for v in a]==pytest.approx([v['score'] for v in b])


def test_php_legacy_empty_weight_array_is_normalized_by_original_validator():
    c=S.preset('fast');c['ranking']['weights']=[]
    assert C.upgrade(c)['ranking']['weights']['month']==1
    assert c['ranking']['weights']==[]
