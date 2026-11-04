"""Configurable contributions shared by all user strategies; no V1-specific branch."""
import math
from . import explorer_config as C


def active_components(config):
    active={p['id'] for kind in ('equity','etf') for p in C.effective(config,kind)['periods'] if p['enabled']}
    return [p for p in config['ranking'].get('components',[]) if p['enabled'] and p['weight']!=0 and p['period'] in active]


def applies(part,verdict,config):
    return part['kind'] in ('all',verdict['group']) and any(p['enabled'] and p['id']==part['period'] for p in C.effective(config,verdict['group'])['periods'])


def value(part,verdict,config):
    metric=part['metric'];tech=verdict.get('technical',{})
    if metric=='quoted_avg_volume':v=tech.get('quoted_avg_volume')
    elif metric in ('momentum6','momentum12'):
        m=verdict.get('momentum');v=m.get('6m' if metric=='momentum6' else '12m') if isinstance(m,dict) else None
    elif metric in ('above_ma50','above_ma200'):
        ma=tech.get('ma50' if metric=='above_ma50' else 'ma200');close=tech.get('close');v=None if ma is None or close is None else float(close>ma)
    elif metric=='ma50_trend':
        ma,old=tech.get('ma50'),tech.get('ma50_prev');v=None if ma is None or not old else 100*(ma/old-1)
    elif metric in C.TECHNICAL:v=tech.get(metric)
    else:
        period=next(p for p in config['periods'] if p['id']==part['period']);m=verdict.get('measures',{}).get(period['sessions']) or {};v=m.get(metric)
        if metric=='slope' and v is not None:v=C.period_slope(v,period['sessions'])
    if v is None or not math.isfinite(v):return None
    transform=part.get('transform','identity')
    if transform=='log1p':return math.log1p(v) if v>-1 else None
    if transform=='sqrt':return math.sqrt(v) if v>=0 else None
    if transform=='power':
        try:result=math.copysign(abs(v)**part['exponent'],v)
        except OverflowError:return None
        return result if math.isfinite(result) else None
    return v


def rank(config, verdicts, percentiles):
    ranking = config['ranking']
    parts = active_components(config)
    groups = {v['group'] for v in verdicts}
    effective = {kind: C.effective(config, kind) for kind in groups}
    active = {kind: {p['id'] for p in cfg['periods'] if p['enabled']} for kind, cfg in effective.items()}
    applicable = {kind: [p for p in parts if p['kind'] in ('all', kind) and p['period'] in active[kind]] for kind in groups}
    for verdict in verdicts:
        verdict.update(score=None, rank=None, score_parts=[], score_missing=0)
    members = [v for v in verdicts if v['status'] == 'retained']
    # Compute each value once. Effective type rules and transformations are shared
    # by selection, strict missing checks and full-population normalization.
    values = {p['id']: {} for p in parts}
    for verdict in members:
        for part in applicable[verdict['group']]:
            values[part['id']][verdict['key']] = value(part, verdict, effective[verdict['group']])
    for verdict in members:
        missing = [p for p in applicable[verdict['group']] if values[p['id']][verdict['key']] is None]
        if missing and (ranking['missing'] == 'unknown' or any(p.get('required') for p in missing)):
            verdict['status'] = 'unknown'
            verdict['reasons'] += [dict(period=p['period'], criterion='score_data', metric=p['metric'], value=None,
                                       threshold='mesure nécessaire au score', result='missing') for p in missing]
    members = [v for v in members if v['status'] == 'retained']
    populations = {v['group'] if ranking['grouping'] == 'asset_kind' else 'combined' for v in members}
    for group in populations:
        items = [v for v in members if ranking['grouping'] == 'combined' or v['group'] == group]
        keys = {v['key'] for v in items}
        normalized = {}
        for part in parts:
            vals = {k: x for k, x in values[part['id']].items() if k in keys and x is not None}
            if part['normalization'] == 'percentile':
                norm = percentiles(vals)
                if part['direction'] == 'lower': norm = {k: 100-x for k, x in norm.items()}
            elif part['normalization'] == 'linear':
                norm = {k: 100*max(0, min(1, (x-part['min'])/(part['max']-part['min']))) for k, x in vals.items()}
                if part['direction'] == 'lower': norm = {k: 100-x for k, x in norm.items()}
            else:
                norm = {k: x*(1 if part['direction'] == 'higher' else -1) for k, x in vals.items()}
            normalized[part['id']] = norm
        for verdict in items:
            available = [p for p in applicable[verdict['group']] if verdict['key'] in normalized[p['id']]]
            denominator = sum(abs(p['weight']) for p in available) if ranking['aggregation'] == 'mean' else 1
            for part in available:
                norm = normalized[part['id']][verdict['key']]
                weight = part['weight']/denominator if denominator else 0
                verdict['score_parts'].append(dict(id=part['id'], metric=part['metric'], period=part['period'],
                    raw=values[part['id']][verdict['key']], normalized=norm, weight=part['weight'],
                    effective_weight=weight, contribution=norm*weight, direction=part['direction'],
                    normalization=part['normalization'], transform=part['transform']))
            if available and denominator: verdict['score'] = sum(p['contribution'] for p in verdict['score_parts'])
            verdict['score_missing'] = len(applicable[verdict['group']])-len(available)
        ordered = sorted((v for v in items if v['score'] is not None), key=lambda v: (-v['score'], v['symbol'], str(v['key'])))
        for i, verdict in enumerate(ordered, 1): verdict['rank'] = i
    return verdicts
