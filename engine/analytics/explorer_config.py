"""Versioned Explorer configuration; V3 values keep their original internal units."""
import copy
import math

VERSION = 4
PERIODS = ('day','week','month','quarter','half','year')
SESSIONS = dict(zip(PERIODS,(1,5,21,63,126,252)))
BOUNDS = {
 'min_slope':(-100,100),'max_slope':(-100,100),'min_r2':(0,1),'max_r2':(0,1),
 'min_er':(-1,1),'max_er':(-1,1),'min_return':(-100,10000),'max_return':(-100,10000),
 'min_volatility':(0,100),'max_volatility':(0,100),'max_drawdown':(0,100),
 'max_current_drawdown':(0,100),'min_up_fraction':(0,1),'min_up_days':(0,252),
 'max_gain_share':(0,100),'max_gain_net_share':(0,100000),'min_worst_day':(-100,10000),
 'min_volume':(0,1e15),'min_turnover_eur':(0,1e18),'max_spike_share':(0,1)}
CRITERIA = (
 ('min_slope','slope','>='),('max_slope','slope','<='),('min_r2','r2','>='),('max_r2','r2','<='),
 ('min_er','er','>='),('max_er','er','<='),('min_return','perf','>='),('max_return','perf','<='),
 ('min_volatility','volatility','>='),('max_volatility','volatility','<='),('max_drawdown','drawdown','<='),
 ('max_current_drawdown','current_drawdown','<='),('min_up_fraction','up_fraction','>='),
 ('min_up_days','up_days','>='),('max_gain_share','gain_share','<='),('max_gain_net_share','gain_net_share','<='),
 ('min_worst_day','worst_day','>='),('min_volume','avg_volume','>='),('min_turnover_eur','turnover_eur','>='),('max_spike_share','spike_share','<='))
EXTRA = {'current_drawdown','up_fraction','up_days','gain_share','gain_net_share','worst_day','avg_volume','turnover_eur','largest_day','spike_share'}
METRICS = {'perf','slope','r2','er','volatility','drawdown'} | EXTRA | {'momentum6','momentum12','quoted_avg_volume','daily_change','gap_to_ma20','ma50_trend','above_ma50','above_ma200'}
TECHNICAL = {'momentum6','momentum12','quoted_avg_volume','daily_change','gap_to_ma20','ma50_trend','above_ma50','above_ma200'}
SCORES_MODE = 'scores'      # classement par les scores V4 (simple / complexe), calculés hors filtres
LEGACY_MODES = ('trend','performance','regularity','stability','momentum','momentum12','momentum_risk')


def number(v,lo,hi,label):
    if v is None:return None
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
        raise ValueError(f'{label} : nombre attendu entre {lo} et {hi}')
    return float(v)


def boolean(v,label):
    if not isinstance(v,bool):raise ValueError(label+' : booléen attendu')
    return v


def object_field(c,key):
    value=c.get(key,{})
    if not isinstance(value,dict):raise ValueError(key+' : objet attendu')
    return value


def period_slope(slope,sessions):
    if slope is None:return None
    if slope<=-100:return -100.0
    return 100*math.expm1(sessions*math.log1p(slope/100))


def session_slope(value,sessions):
    if value is None:return None
    if value<=-100:raise ValueError('La pente sur période doit être supérieure à −100 %')
    return 100*math.expm1(math.log1p(value/100)/sessions)


def upgrade(config):
    c=copy.deepcopy(config)
    if c.get('version')==4:return validate(c)
    if c.get('version')!=3:raise ValueError('Version de stratégie inconnue : conversion explicite nécessaire')
    from .strategy import validate as validate_legacy
    c=validate_legacy(c)
    c.pop('_upgrade',None)
    c['version']=4;c['slope_unit']='percent_per_session'
    for p in c['periods']:
        # V3 required coverage on every selected period, even without thresholds.
        p['require_history']=bool(p['enabled'])
        for field in BOUNDS:p.setdefault(field,None)
    c['ranking']['weights']={p['id']:c['ranking'].get('weights',{}).get(p['id'],1 if p['enabled'] else 0) for p in c['periods']}
    c['selection']={'combine':'all','missing':'unknown','require_fresh':True}
    c['liquidity']={'min_quoted_volume':None}
    c['asset_rules']={}
    c['presentation']={'configuration':'period'}
    return validate(c)


def empty():
    return validate({'version':4,'name':'custom','slope_unit':'percent_per_session',
      'periods':[dict(id=p,sessions=n,enabled=False,require_history=False,**{f:None for f in BOUNDS}) for p,n in SESSIONS.items()],
      'technical':{},'selection':{'combine':'all','missing':'unknown','require_fresh':False},
      'ranking':{'mode':'weighted','components':[],'missing':'unknown','aggregation':'mean','grouping':'asset_kind'},
      'liquidity':{},'asset_rules':{},'presentation':{'configuration':'period'}})


def validate(raw):
    c=copy.deepcopy(raw)
    if not isinstance(c,dict) or c.get('version')!=4:raise ValueError('Configuration Explorer V4 attendue')
    if c.get('slope_unit','percent_per_session')!='percent_per_session':raise ValueError('Unité interne de pente incorrecte')
    c['slope_unit']='percent_per_session'
    ps=c.get('periods')
    if not isinstance(ps,list) or [p.get('id') for p in ps if isinstance(p,dict)]!=list(PERIODS):raise ValueError('Les six granularités doivent être présentes dans leur ordre canonique')
    for p in ps:
        n=p.get('sessions');pid=p['id']
        if not isinstance(p.get('enabled'),bool) or type(n) is not int or not 1<=n<=252 or (pid=='day' and n!=1) or (pid!='day' and n<2):raise ValueError('Activation ou nombre de séances invalide')
        if not isinstance(p.get('require_history',False),bool):raise ValueError('Exigence d’historique invalide')
        p['require_history']=p.get('require_history',False)
        for f,(lo,hi) in BOUNDS.items():p[f]=number(p.get(f),lo,hi,f)
        for lo,hi in [('min_slope','max_slope'),('min_r2','max_r2'),('min_er','max_er'),('min_return','max_return'),('min_volatility','max_volatility')]:
            if p[lo] is not None and p[hi] is not None and p[lo]>p[hi]:raise ValueError(f'{pid} : minimum supérieur au maximum ({lo})')
        if n<3 and any(p[k] is not None for k in ('min_r2','max_r2','min_er','max_er','min_volatility','max_volatility')):raise ValueError(f'{pid} : R², ER et volatilité non applicables sur moins de trois séances')
    t=object_field(c,'technical')
    if not isinstance(t,dict):raise ValueError('Filtres techniques invalides')
    c['technical']={k:boolean(t.get(k,False),k) for k in ('above_ma50','ma50_rising','above_ma200','ma200_rising')}
    for f in ('max_daily_change','max_gap_ma20'):c['technical'][f]=number(t.get(f),0,1000,f)
    selection=object_field(c,'selection')
    if selection.get('combine','all') not in ('all','any') or selection.get('missing','unknown') not in ('unknown','reject'):raise ValueError('Combinaison ou traitement des données absentes invalide')
    c['selection']={'combine':selection.get('combine','all'),'missing':selection.get('missing','unknown'),'require_fresh':boolean(selection.get('require_fresh',True),'Clôtures récentes')}
    li=object_field(c,'liquidity')
    c['liquidity']={'min_quoted_volume':number(li.get('min_quoted_volume'),0,1e15,'Volume moyen 3 mois'),
                    'min_turnover_eur':number(li.get('min_turnover_eur'),0,1e15,'Valeur échangée minimale par jour'),
                    'min_turnover_eur_us':number(li.get('min_turnover_eur_us'),0,1e15,'Valeur échangée minimale par jour (places américaines)')}
    r=object_field(c,'ranking');mode=r.get('mode','weighted')
    if mode not in LEGACY_MODES+('weighted',SCORES_MODE):raise ValueError('Méthode de score inconnue')
    if mode=='weighted':
        components=r.get('components',[])
        if not isinstance(components,list) or len(components)>48:raise ValueError('48 contributions au score au maximum')
        out=[]
        for i,part in enumerate(components):
            if not isinstance(part,dict) or part.get('metric') not in METRICS:raise ValueError('Indicateur de score inconnu ou indisponible')
            p=part.get('period','month');metric=part['metric']
            if p not in PERIODS:raise ValueError('Période de score invalide')
            if metric in ('r2','er','volatility') and next(x for x in ps if x['id']==p)['sessions']<3:raise ValueError('Contribution non applicable à cette période')
            norm=part.get('normalization','percentile');direction=part.get('direction','higher');transform=part.get('transform','identity')
            if norm not in ('percentile','linear','raw') or direction not in ('higher','lower') or transform not in ('identity','log1p','sqrt','power'):raise ValueError('Transformation du score invalide')
            low=number(part.get('min',0),-1e18,1e18,'Borne basse');high=number(part.get('max',100),-1e18,1e18,'Borne haute')
            if norm=='linear' and (low is None or high is None or high<=low):raise ValueError('La borne haute du score doit dépasser la borne basse')
            kind=part.get('kind','all')
            if kind not in ('all','equity','etf'):raise ValueError('Type de contribution invalide')
            if not isinstance(part.get('enabled',True),bool):raise ValueError('Activation de contribution invalide')
            out.append({'id':str(part.get('id','component-'+str(i)))[:60],'metric':metric,'period':p,'kind':kind,
                        'enabled':part.get('enabled',True),'required':boolean(part.get('required',False),'Mesure de score obligatoire'),'weight':number(part.get('weight',1),-1000,1000,'Poids') or 0,
                        'direction':direction,'normalization':norm,'min':low,'max':high,'transform':transform,
                        'exponent':number(part.get('exponent',1),.1,10,'Exposant') or 1})
        if len({p['id'] for p in out})!=len(out):raise ValueError('Identifiants de contributions dupliqués')
        missing=r.get('missing','unknown');aggregation=r.get('aggregation','mean');grouping=r.get('grouping','asset_kind')
        if missing not in ('unknown','renormalize') or aggregation not in ('mean','sum') or grouping not in ('asset_kind','combined'):raise ValueError('Options de score invalides')
        c['ranking']={'mode':mode,'components':out,'missing':missing,'aggregation':aggregation,'grouping':grouping,'weights':{}}
    elif mode==SCORES_MODE:
        sort=r.get('sort','simple')
        if sort not in ('simple','complex'):raise ValueError('Tri par score inconnu')
        c['ranking']={'mode':mode,'weights':{},'sort':sort}
    else:
        weights=r.get('weights') or {}
        if not isinstance(weights,dict) or any(k not in PERIODS or v is None for k,v in weights.items()):raise ValueError('Poids de période invalides')
        c['ranking']={'mode':mode,'weights':{k:number(v,0,100,'Poids') for k,v in weights.items()}}
    c['scoring']=validate_scoring(c.get('scoring'),ps)
    asset=object_field(c,'asset_rules')
    if not isinstance(asset,dict) or any(k not in ('equity','etf') for k in asset):raise ValueError('Règles Actions/ETF invalides')
    clean={}
    for kind,rule in asset.items():
        if not isinstance(rule,dict) or any(k not in ('periods','liquidity','technical','selection') for k in rule):raise ValueError('Règle par type invalide')
        override={}
        for field in ('periods','liquidity','technical','selection'):
            if field in rule and not isinstance(rule[field],dict):raise ValueError('Surcharge '+field+' : objet attendu')
        for pid,fields in (rule.get('periods') or {}).items():
            if pid not in PERIODS or not isinstance(fields,dict) or any(f not in BOUNDS and f not in ('enabled','require_history') for f in fields):raise ValueError('Surcharge de période invalide')
            override[pid]=fields
        merged=copy.deepcopy(c);merged['asset_rules']={}
        for p in merged['periods']:p.update(override.get(p['id'],{}))
        for field in ('liquidity','technical','selection'):
            if rule.get(field) is not None:merged[field].update(rule[field])
        # Validate through the same schema, never a second selection engine.
        validated=validate(merged)
        clean[kind]={'periods':override}
        for field in ('liquidity','technical','selection'):
            if rule.get(field) is not None:clean[kind][field]={k:validated[field][k] for k in rule[field] if k in validated[field]}
    c['asset_rules']=clean
    config_mode=object_field(c,'presentation').get('configuration','period')
    if config_mode not in ('global','period'):raise ValueError('Mode de configuration invalide')
    c['presentation']={'configuration':config_mode}
    return c


def validate_scoring(raw,periods):
    """Paramètres des scores V4 : κ des poids automatiques, poids de granularité personnalisés (optionnels), poids du score complexe, seuil de couverture.
    Ils ne contiennent aucun critère de conformité : changer un filtre ne change jamais une note."""
    from . import scores as SC
    raw=raw if isinstance(raw,dict) else {}
    kappa=number(raw.get('kappa',SC.KAPPA),0,0.95,'κ');kappa=SC.KAPPA if kappa is None else kappa
    ids=[p['id'] for p in periods]
    weights=raw.get('weights') or {}
    if not isinstance(weights,dict) or any(k not in ids for k in weights):raise ValueError('Poids de granularité invalides')
    weights={k:number(v,0,1000,'Poids de granularité') for k,v in weights.items() if v is not None}
    complex_weights=raw.get('complex_weights') or {}
    if not isinstance(complex_weights,dict) or any(k not in SC.COMPLEX_WEIGHTS for k in complex_weights):raise ValueError('Poids du score complexe invalides')
    complex_weights={k:number(v,0,1000,'Poids du score complexe') for k,v in complex_weights.items() if v is not None}
    if complex_weights and sum(complex_weights.get(k,SC.COMPLEX_WEIGHTS[k]) for k in SC.COMPLEX_WEIGHTS)<=0:raise ValueError('Le score complexe doit garder au moins un poids positif')
    threshold=number(raw.get('threshold',SC.COVERAGE_THRESHOLD),0.1,1,'Seuil de couverture');threshold=SC.COVERAGE_THRESHOLD if threshold is None else threshold
    anchor=number(raw.get('anchor',SC.ANCHOR_LAMBDA),0,1,'Ancrage récent');anchor=SC.ANCHOR_LAMBDA if anchor is None else anchor
    return {'kappa':kappa,'weights':weights,'complex_weights':complex_weights,'threshold':threshold,'anchor':anchor}


def growth_v1():
    """« Croissance rapide » — référence V1 : seuils historiques de scan.py, tous configurables (aucun n'est une règle interne).
    Conformité : jour ≥ 0 (désactivable), semaine ≥ +3 %, mois ≥ +8 % avec R² ≥ 0,60, concentration V1 ≤ 0,45, volatilité ≤ 7 %/séance,
    valeur échangée ≥ 5 M€ (places américaines) / 2 M€ (autres), clôtures récentes. Les scores, eux, ne dépendent d'aucun de ces seuils."""
    c=empty();c['name']='growth_v1'
    by={p['id']:p for p in c['periods']}
    by['day'].update(enabled=True,min_return=0.0)
    by['week'].update(enabled=True,require_history=True,min_return=3.0)
    by['month'].update(enabled=True,require_history=True,min_return=8.0,min_r2=0.60,max_spike_share=0.45,max_volatility=7.0)
    c['selection']={'combine':'all','missing':'unknown','require_fresh':True}
    c['liquidity']={'min_quoted_volume':None,'min_turnover_eur':2e6,'min_turnover_eur_us':5e6}
    c['ranking']={'mode':SCORES_MODE,'sort':'simple'}
    c['scoring']={'kappa':0.7,'weights':{},'complex_weights':{},'threshold':0.75}
    return validate(c)


def effective(c,kind):
    rule=(c.get('asset_rules') or {}).get(kind,{})
    if not rule:return c
    out=copy.deepcopy(c)
    for p in out['periods']:p.update((rule.get('periods') or {}).get(p['id'],{}))
    for field in ('liquidity','technical','selection'):
        if field in rule:out[field].update(rule[field])
    return out


def needs_extended(c):
    for kind in ('equity','etf'):
        ec=effective(c,kind)
        if any(p['enabled'] and any(p.get(f) is not None for f,m,_ in CRITERIA if m in EXTRA) for p in ec['periods']):return True
    return any(p.get('enabled',True) and p.get('weight',0)!=0 and p['metric'] in EXTRA and any(x['id']==p['period'] and x['enabled'] for kind in ('equity','etf') for x in effective(c,kind)['periods']) for p in c['ranking'].get('components',[]))


def editable(raw):
    """Expose legacy formulas as generic components without changing their math."""
    c=upgrade(raw);c.pop('_editable',None);r=c['ranking'];mode=r['mode']
    if mode in ('weighted',SCORES_MODE):return c
    if mode=='momentum_risk':
        specs=[('momentum6','half',.35,'higher',True),('momentum12','year',.45,'higher',True),('volatility','year',.10,'lower',False),('drawdown','year',.10,'lower',False)]
    elif mode in ('momentum','momentum12'):
        specs=[('momentum12' if mode=='momentum12' else 'momentum6','year' if mode=='momentum12' else 'half',1,'higher',True)]
    else:
        metric={'trend':'slope','performance':'perf','regularity':'r2','stability':'volatility'}[mode]
        specs=[(metric,p['id'],r['weights'].get(p['id'],0),'lower' if mode=='stability' else 'higher',False) for p in c['periods'] if p['sessions']>=3 or metric not in ('r2','volatility','er')]
    c['ranking']={'mode':'weighted','missing':'renormalize','aggregation':'mean','grouping':'asset_kind','components':[
        dict(id='legacy-'+period+'-'+metric,metric=metric,period=period,weight=weight,direction=direction,required=required,kind='all',enabled=True,normalization='percentile',transform='identity',min=0,max=100,exponent=1)
        for metric,period,weight,direction,required in specs]}
    return validate(c)
