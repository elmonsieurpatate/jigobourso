import copy
import math
import pytest
from engine.analytics import growth as G, strategy as S, explorer_config as C
from scripts.preview_growth_v4 import fixtures
from tests.fast.test_explorer_v4_readiness import dates


def evaluate(name, config=None, kind='equity', missing=None):
    config=config or G.preset();ds=dates(64);prices=fixtures()[name]
    bars=[(d,v,None) for i,(d,v) in enumerate(zip(ds,prices)) if i!=missing]
    v=S.evaluate_one(config,dict(bars=bars,session_windows={n:ds[-(n+1):] for n in (1,5,21,63)}))
    v.update(key=name,symbol=name,group=kind);S.rank(config,[v]);return v


def test_initial_periods_and_exact_primary_controls():
    c=G.preset();assert [p['id'] for p in c['periods'] if p['enabled']]==['week','month']
    for p in c['periods']:
        if p['enabled']:
            assert p['min_slope']==.08
            assert p['min_return'] is None and p['max_gain_share'] is None
    assert evaluate('stable')['status']=='retained'
    for field,value in [('min_slope',0),('min_slope',None),('min_r2',None)]:
        bad=copy.deepcopy(c);bad['periods'][1][field]=value
        with pytest.raises(ValueError):C.validate(bad)


def test_recent_dynamics_and_plateau_admission():
    a,b,c=[evaluate(n) for n in ('acceleration','stable','ralentissement')]
    assert a['score']>b['score']>c['score']
    assert b['scores']['parts']['simple'][2]['normalized']==pytest.approx(50)
    for name in ('plateau','plat','pic_unique'):
        v=evaluate(name);assert v['status']=='rejected' and v['score'] is None
    cfg=G.preset();cfg['periods'][1]['enabled']=False
    assert evaluate('plateau',cfg)['status']=='retained'
    assert evaluate('stable',cfg)['scores']['not_applicable']


def test_advanced_or_never_compensates_a_primary_failure():
    cfg=G.preset();cfg['selection']['combine']='any';cfg['periods'][2]['min_return']=0
    assert evaluate('plateau',cfg)['status']=='rejected'
    cfg['periods'][2]['min_return']=99;cfg['selection']['combine']='all'
    v=evaluate('stable',cfg);assert v['status']=='rejected'
    assert any(r['criterion']=='min_return' and r['result']=='fail' for r in v['reasons'])


@pytest.mark.parametrize('missing',[0,40,62,63])
def test_missing_active_window_is_unknown_not_zero(missing):
    v=evaluate('stable',missing=missing)
    # A point before both active windows doesn't affect admission.
    if missing==0:assert v['status']=='retained'
    elif missing==40:assert v['status']=='retained'  # Month begins at index 42.
    else:assert v['status']=='unknown' and v['scores']['simple'] is None


def test_same_math_for_equity_and_etf_and_complete_decomposition():
    a=evaluate('acceleration');b=evaluate('acceleration',kind='etf')
    assert a['scores']==b['scores']
    for name in ('simple','complex'):
        parts=a['scores']['parts'][name]
        assert sum(p['effective_weight'] for p in parts)==pytest.approx(1)
        assert sum(p['contribution'] for p in parts)==pytest.approx(a['scores'][name])
        assert 0<=a['scores'][name]<=100


def test_missing_risk_does_not_improve_complex_or_remove_admission():
    cfg=G.preset();v=evaluate('stable');v['measures'][21]['volatility']=None
    got=G.score(cfg,v)
    assert got['simple'] is not None and got['complex'] is None
    assert v['status']=='retained'


def test_classification_bounds_unknown_and_validation():
    d=G.defaults();cat=d['categories']['volatility']
    assert G.classify(1.5,cat)['id']=='c0'
    assert G.classify(1.50001,cat)['id']=='c1'
    assert G.classify(999,cat)['id']=='c3'
    for value in (None,math.nan,math.inf):assert G.classify(value,cat)['id']=='unknown'
    assert G.classify(0,cat)['value']==0
    for mutation in ('weights','bounds','color','unit'):
        bad=copy.deepcopy(d)
        if mutation=='weights':bad['weights']['simple']['force']=90
        if mutation=='bounds':bad['categories']['volatility']['bounds']=[3,1,5]
        if mutation=='color':bad['categories']['volatility']['colors'][0]='red;bad'
        if mutation=='unit':bad['categories']['volatility']['unit']='annualisé'
        with pytest.raises(ValueError):G.validate_settings(bad)


def test_all_categories_including_unknown_initially_included_and_no_intrinsic_change():
    d=G.defaults();v=evaluate('stable');scores=copy.deepcopy(v['scores'])
    for key,cat in d['categories'].items():
        assert len(d['filters'][key])==len(cat['labels'])+1 and 'unknown' in d['filters'][key]
    d['categories']['volatility']['bounds']=[.000001,.000002,.000003]
    G.validate_settings(d)
    assert G.score(G.preset(),v)==scores


def test_admin_cannot_hide_an_extra_primary_filter_in_defaults():
    d=G.defaults();d['periods']['week']['min_return']=10
    with pytest.raises(ValueError):G.validate_settings(d)
