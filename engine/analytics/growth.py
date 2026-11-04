"""Explorer growth-1: absolute, decomposable scores; no provider or database."""
import copy
import math
import re

VERSION = 'growth-1'
PRIMARY = ('week', 'month', 'quarter')
COMPONENTS = ('force', 'regularity', 'evolution', 'risk', 'continuity')
COLORS = ['#166534', '#1d4ed8', '#9a3412', '#b91c1c']


def defaults():
    specs = {
        'volatility': ('Volatilité', '%/séance', [1.5, 3, 5], ['Faible', 'Modérée', 'Élevée', 'Très élevée'], COLORS),
        'turnover_eur': ('Montant historique', '€/séance', [1e6, 2e6, 4e6], ['Limité', 'Intermédiaire', 'Important', 'Très important'], COLORS[::-1]),
        'quoted_turnover': ('Montant coté Yahoo, trois mois', '€/jour', [1e6, 2e6, 4e6], ['Limité', 'Intermédiaire', 'Important', 'Très important'], COLORS[::-1]),
        'avg_volume': ('Volume historique', 'titres/séance', [1e4, 1e5, 1e6], ['Très faible', 'Faible', 'Moyen', 'Important'], ['#475569', '#334155', '#1e40af', '#1e3a8a']),
        'up_fraction': ('Séances positives', 'proportion 0–1', [.4, .55, .7], ['Peu fréquentes', 'Partagées', 'Fréquentes', 'Très fréquentes'], COLORS[::-1]),
        'largest_day': ('Meilleure séance', '%', [3, 7, 15], ['Limitée', 'Marquée', 'Forte', 'Très forte'], COLORS),
        'worst_day': ('Pire séance', '%', [-10, -5, -2], ['Très forte baisse', 'Forte baisse', 'Baisse modérée', 'Baisse limitée'], COLORS[::-1]),
        'gain_share': ('Meilleure hausse log / hausses log positives', '%', [20, 40, 60], ['Répartie', 'Modérée', 'Concentrée', 'Très concentrée'], COLORS),
        'gain_net_share': ('Meilleure hausse simple / gain net simple', '%', [25, 50, 100], ['Limitée', 'Modérée', 'Importante', 'Supérieure au gain net'], COLORS),
        'log_net_share': ('Meilleure hausse log / gain net log', '%', [25, 50, 100], ['Limitée', 'Modérée', 'Importante', 'Supérieure au gain net'], COLORS),
        'drawdown': ('Repli maximal', '%', [5, 10, 20], ['Faible', 'Modéré', 'Élevé', 'Très élevé'], COLORS),
        'current_drawdown': ('Recul actuel', '%', [3, 7, 15], ['Proche du sommet', 'Repli', 'Recul marqué', 'Recul important'], COLORS),
        'er': ('Efficacité du chemin', '−1 à 1', [0, .3, .7], ['Négative ou nulle', 'Faible', 'Moyenne', 'Élevée'], COLORS[::-1]),
        'perf': ('Rendement observé', '%', [0, 5, 15], ['Nul ou négatif', 'Hausse limitée', 'Hausse marquée', 'Hausse forte'], COLORS[::-1]),
        'coverage': ('Couverture', 'proportion 0–1', [0, .999999], ['Absente', 'Partielle', 'Complète'], ['#475569', '#9a3412', '#166534']),
        'freshness': ('Fraîcheur des clôtures', 'code 0 récent / 1 ancien', [.5], ['À jour', 'Ancienne'], ['#166534','#9a3412']),
        'quality': ('Continuité des données', 'code 0 complète / 1 partielle / 2 rupture', [.5,1.5], ['Complète', 'Partielle', 'Rupture'], ['#166534','#9a3412','#b91c1c']),
    }
    categories = {}
    for key, (label, unit, bounds, labels, colors) in specs.items():
        categories[key] = dict(label=label, unit=unit, bounds=bounds,
                               labels=labels, colors=colors, unknown_label='Inconnu', unknown_color='#475569')
    return dict(schema=1, periods={p: dict(sessions=n, min_slope=.08, min_r2=r, enabled=p!='quarter')
                                  for p,n,r in [('week',5,.65),('month',21,.70),('quarter',63,.75)]},
                weights=dict(simple=dict(force=35,regularity=35,evolution=30),
                             complex=dict(force=25,regularity=25,evolution=20,risk=20,continuity=10)),
                categories=categories, filters={k:['c'+str(i) for i in range(len(v['labels']))]+['unknown'] for k,v in categories.items()},
                historical_visible=[])


def weights(raw):
    if not isinstance(raw,dict) or set(raw)!= {'simple','complex'}:raise ValueError('Deux jeux de poids attendus')
    out=copy.deepcopy(raw)
    for name, keys in [('simple',COMPONENTS[:3]),('complex',COMPONENTS)]:
        w=raw[name]
        if not isinstance(w,dict) or set(w)!=set(keys):raise ValueError('Composantes de score incorrectes')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>100 for v in w.values()) or abs(sum(w.values())-100)>1e-8:
            raise ValueError('Les poids non négatifs doivent totaliser 100 %')
        out[name]={k:float(v) for k,v in w.items()}
    return out


def validate_settings(raw):
    d=defaults()
    if not isinstance(raw,dict) or raw.get('schema')!=1:raise ValueError('Réglages Explorer de schéma 1 attendus')
    out=copy.deepcopy(raw);out['weights']=weights(raw.get('weights'))
    if not isinstance(raw.get('periods'),dict) or set(raw['periods'])!=set(PRIMARY):raise ValueError('Trois périodes primaires attendues')
    for key,p in raw['periods'].items():
        if not isinstance(p,dict) or set(p)!=set(d['periods'][key]) or p.get('sessions')!=d['periods'][key]['sessions'] or type(p.get('enabled')) is not bool:raise ValueError('Période invalide : seuls pente, R², activation et séances sont attendus')
        for field,lo,hi in [('min_slope',0,100),('min_r2',0,1)]:
            v=p.get(field)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi or (field=='min_slope' and v<=0):raise ValueError('Pente strictement positive et R² entre 0 et 1 requis')
    if not any(p['enabled'] for p in raw['periods'].values()):raise ValueError('Au moins une période active')
    if not isinstance(raw.get('categories'),dict) or set(raw['categories'])!=set(d['categories']):raise ValueError('Indicateurs secondaires incorrects')
    for key,cat in raw['categories'].items():
        if not isinstance(cat,dict) or cat.get('unit')!=d['categories'][key]['unit']:raise ValueError('Unité de catégorie incorrecte')
        bounds=cat.get('bounds');labels=cat.get('labels');colors=cat.get('colors')
        if not isinstance(bounds,list) or not 1<=len(bounds)<=7 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in bounds) or bounds!=sorted(set(bounds)):raise ValueError('Bornes finies strictement croissantes requises')
        if not isinstance(labels,list) or len(labels)!=len(bounds)+1 or any(not isinstance(x,str) or not x.strip() or len(x)>80 for x in labels) or len(set(labels))!=len(labels):raise ValueError('Libellés distincts requis')
        if not isinstance(colors,list) or len(colors)!=len(labels) or any(not isinstance(x,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',x) for x in colors+[cat.get('unknown_color','')]):raise ValueError('Couleurs hexadécimales #RRGGBB requises')
        for field in ('label','unknown_label'):
            if not isinstance(cat.get(field),str) or not cat[field].strip() or len(cat[field])>100:raise ValueError('Libellé manquant')
    if not isinstance(raw.get('filters'),dict) or set(raw['filters'])!=set(d['filters']):raise ValueError('Filtres par défaut incorrects')
    for key,chosen in raw['filters'].items():
        allowed={'unknown'}|{'c'+str(i) for i in range(len(raw['categories'][key]['labels']))}
        if not isinstance(chosen,list) or any(x not in allowed for x in chosen) or len(set(chosen))!=len(chosen):raise ValueError('Catégorie de filtre inconnue')
    if not isinstance(raw.get('historical_visible'),list) or any(x not in ('regular','fast','recovery','low_volatility','momentum','momentum12','momentum_risk') for x in raw['historical_visible']):raise ValueError('Profil historique inconnu')
    return out


def preset(params=None):
    from . import explorer_config as C
    params=validate_settings(params or defaults());c=C.empty();c['name']='growth_v4'
    c['growth']=dict(version=VERSION, weights=params['weights'])
    c['selection']['require_fresh']=True
    for p in c['periods']:
        if p['id'] in PRIMARY:
            p.update(params['periods'][p['id']]);p['require_history']=p['enabled']
    return C.validate(c)


def classify(value, category):
    if value is None or not math.isfinite(value):
        return dict(id='unknown',label=category['unknown_label'],color=category['unknown_color'],value=None,unit=category['unit'])
    i=next((i for i,b in enumerate(category['bounds']) if value<=b),len(category['bounds']))
    return dict(id='c'+str(i),label=category['labels'][i],color=category['colors'][i],value=value,unit=category['unit'],
                lower=category['bounds'][i-1] if i else None,upper=category['bounds'][i] if i<len(category['bounds']) else None,
                interval='borne basse exclue, borne haute incluse')


def score(config, verdict):
    selected=[p for p in config['periods'] if p['enabled'] and p['id'] in PRIMARY]
    ms={p['sessions']:verdict['measures'].get(p['sessions']) for p in selected}
    result=dict(version=VERSION, simple=None, complex=None, parts={'simple':[],'complex':[]},
                status='non_admis' if verdict['status']=='rejected' else 'indisponible', not_applicable=[])
    if verdict['status']!='retained':return result
    if not ms or any(not m or m.get('slope') is None or m.get('r2') is None or m.get('coverage')!=1 for m in ms.values()):return result
    mean=lambda xs:sum(xs)/len(xs)
    force=mean([100*max(0,m['slope'])/(max(0,m['slope'])+.15) for m in ms.values()])
    regularity=mean([100*m['r2'] for m in ms.values()]);changes=[]
    for a,b in zip(sorted(ms),sorted(ms)[1:]):
        x,y=ms[a],ms[b];c=x.get('gain_share')
        if c is None:return result
        c/=100;den=abs(x['slope'])+abs(y['slope']);delta=(x['slope']-y['slope'])/den if den else 0
        q=min(1,(2/a)/c)*max(0,(1-c)/(1-1/a)) if c else 0
        changes.append(math.tanh(2*delta)*math.sqrt(x['r2']*y['r2'])*q)
    evolution=50+50*mean(changes) if changes else None
    if not changes:result['not_applicable'].append('evolution : une seule période sélectionnée')
    path_known=all(all(m.get(k) is not None for k in ('volatility','drawdown','up_fraction','gain_share')) for m in ms.values())
    risk=mean([100/(1+max(m['volatility']/1.5,m['drawdown']/20)**2) for m in ms.values()]) if path_known else None
    continuity=mean([100*min(m['up_fraction'],max(0,min(1,(1-m['gain_share']/100)/(1-1/n)))) for n,m in ms.items()]) if path_known else None
    values=dict(force=force,regularity=regularity,evolution=evolution,risk=risk,continuity=continuity)
    sources=dict(force=['slope'],regularity=['r2'],evolution=['slope','r2','gain_share'],risk=['volatility','drawdown'],continuity=['up_fraction','gain_share'])
    formulas=dict(force='moyenne(100*s/(s+0.15)), s en %/séance',regularity='100*moyenne(R²)',
                  evolution='50+50*moyenne(tanh(2*delta_pente)*sqrt(R²court*R²long)*frein_concentration)',
                  risk='moyenne(100/(1+max(vol/1.5,drawdown/20)^2))',
                  continuity='moyenne(100*min(proportion_positive,borne((1-concentration)/(1-1/N),0,1)))')
    for name in ('simple','complex'):
        ws=config['growth']['weights'][name];active={k:w for k,w in ws.items() if w>0 and not (k=='evolution' and not changes)}
        if not active or any(values[k] is None for k in active):continue
        total=sum(active.values())
        for key,w in active.items():
            result['parts'][name].append(dict(metric=key,raw=values[key],normalized=values[key],weight=w,
                 effective_weight=w/total,contribution=values[key]*w/total,periods=[p['id'] for p in selected],
                 coverage={str(n):m['coverage'] for n,m in ms.items()},normalization=formulas[key],
                 inputs={str(n):{metric:m.get(metric) for metric in sources[key]} for n,m in ms.items()}))
        result[name]=max(0,min(100,sum(p['contribution'] for p in result['parts'][name])))
    result['status']='disponible' if result['simple'] is not None else 'indisponible'
    return result


def rank(config, verdicts):
    for v in verdicts:
        v['scores']=score(config,v);v['score']=v['scores']['simple'];v['rank']=None
        v['score_parts']=v['scores']['parts']['simple'];v['score_missing']=int(v['score'] is None)
    for i,v in enumerate(sorted((v for v in verdicts if v['score'] is not None),key=lambda v:(-v['score'],v['symbol'],str(v['key']))),1):v['rank']=i
    return verdicts
