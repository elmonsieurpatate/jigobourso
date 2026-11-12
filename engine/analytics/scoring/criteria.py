"""Moteur unique de décision « ce titre répond-il aux critères de recherche d'une stratégie ? ».

Utilisé par le Classement (Explorer), le classement de l'administration des scores et la fiche d'un titre : mêmes critères, mêmes seuils, même logique.
Indépendant des scores V4 : il ne lit ni ne modifie aucune note ni aucun rang. Un titre « exclu » garde son score et son rang général.

Statuts : retained (retenue), excluded (exclue : au moins un critère actif mesuré et non respecté), undetermined (aucun critère n'est violé
mais au moins une mesure nécessaire manque : jamais traité comme une exclusion).

Unités : pente en % PAR SÉANCE (100·(exp(pente de la régression du log) − 1)), identique dans les seuils et dans les mesures ; R² entre 0 et 1 ;
performance, volatilité et repli en % ; volume en titres/jour.
"""
import operator

RETAINED, EXCLUDED, UNDETERMINED = 'retained', 'excluded', 'undetermined'
PERIODS = {'day': 1, 'week': 5, 'month': 21, 'quarter': 63, 'half': 126, 'year': 252, 'two_year': 504}
PERIOD_LABELS = {'day': 'Jour', 'week': 'Semaine', 'month': 'Mois', 'quarter': 'Trimestre', 'half': '6 mois', 'year': '1 an', 'two_year': '2 ans'}
METRIC_LABELS = {'slope': 'Pente', 'r2': 'R²', 'volatility': 'Volatilité', 'drawdown': 'Repli maximal', 'return': 'Performance', 'volume': 'Volume moyen'}
UNITS = {'slope': '% par séance', 'r2': '', 'volatility': '%', 'drawdown': '%', 'return': '%', 'volume': 'titres/jour'}
OPS = {'>=': operator.ge, '<=': operator.le, '>': operator.gt, '<': operator.lt, '=': operator.eq}
REFERENCE = 21                                           # volatilité et repli sont mesurés sur un mois


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float('inf') else None


def default_spec(periods):
    """Critères d'une stratégie intégrée depuis `ranking_table.criteria()['criteria'][id]['periods']` : {période: {slope, r2}} (valeur absente = pas de seuil)."""
    return {'periods': {k: {'enabled': True, 'slope': _num(v.get('slope')) or 0.0, 'r2': _num(v.get('r2')) or 0.0} for k, v in (periods or {}).items()}, 'extra': [], 'join': 'and'}


def normalize(spec):
    """Liste ordonnée de critères actifs {metric, period, op, value, group} et combinaison des règles facultatives.
    Une période sans seuil (pente et R² à 0) n'est pas un critère. Retourne None si `spec` n'est pas exploitable (jamais une liste vide implicite)."""
    if not isinstance(spec, dict):
        return None
    periods = spec.get('periods')
    if not isinstance(periods, dict):
        return None
    primary, extra = [], []
    for k, v in periods.items():
        if k not in PERIODS or not isinstance(v, dict) or v.get('enabled') is False:
            continue
        if k == 'day':                                       # Jour (1 séance) : seule la variation sert de critère ; ni pente ni R² sur une séance. Activée sans seuil : aucun critère.
            val = _num(v.get('return'))
            if v.get('enabled') is True and val is not None and not isinstance(spec.get('tree'), dict):      # avec un arbre de règles, la règle Jour de l'arbre fait foi
                primary.append({'metric': 'return', 'period': 'day', 'op': '>=', 'value': val})
            continue
        for metric in ('slope', 'r2'):
            val = _num(v.get(metric))
            if val is not None and val > 0:
                primary.append({'metric': metric, 'period': k, 'op': '>=', 'value': val})
    tree = spec.get('tree')
    leaves = _leaves(tree) if isinstance(tree, dict) else None
    if leaves is not None:                                   # règles « variation 1J » de l'arbre : critères principaux (ET), comme pente et R², pas des seuils facultatifs
        for x in leaves:
            val = _num(x.get('value'))
            if x.get('metric') == 'return' and x.get('period') == 'day' and x.get('op') in OPS and val is not None:
                primary.append({'metric': 'return', 'period': 'day', 'op': x['op'], 'value': val})
        leaves = [x for x in leaves if not (x.get('metric') == 'return' and x.get('period') == 'day')]
    source = [x for x in leaves if x['metric'] not in ('slope', 'r2')] if leaves is not None else (spec.get('extra') or [])
    for x in source:
        if not isinstance(x, dict) or x.get('metric') not in ('volatility', 'drawdown', 'return', 'volume') or x.get('op') not in OPS:
            continue
        val = _num(x.get('value'))
        if val is None:
            continue
        period = x.get('period') if x.get('period') in PERIODS else 'month'
        extra.append({'metric': x['metric'], 'period': period, 'op': x['op'], 'value': val})
    join = 'or' if spec.get('join') == 'or' else 'and'
    return {'primary': primary, 'extra': extra, 'join': join}


def _leaves(n, depth=0):
    if not isinstance(n, dict) or depth > 6:
        return []
    if n.get('kind') == 'rule':
        return [n]
    return [x for c in (n.get('children') or []) for x in _leaves(c, depth + 1)]


def measure(metrics, metric, period):
    """Valeur mesurée d'un titre pour un critère, ou None. `metrics` = {'m': {séances: {...}}, 'avg_volume': ...}."""
    m = metrics.get('m') or {}
    if metric in ('slope', 'r2'):
        if period == 'day':
            return None                                      # pente et R² n'existent pas sur une séance : jamais inventés
        return _num((m.get(PERIODS[period]) or {}).get(metric))
    if metric in ('volatility', 'drawdown'):
        return _num((m.get(REFERENCE) or {}).get(metric))
    if metric == 'return':
        return _num((m.get(PERIODS[period]) or {}).get('perf'))
    if metric == 'volume':
        return _num(metrics.get('avg_volume'))
    return None


def _check(metrics, c):
    value = measure(metrics, c['metric'], c['period'])
    ok = None if value is None else bool(OPS[c['op']](value, c['value']))
    label = 'Variation 1J' if c['metric'] == 'return' and c['period'] == 'day' else METRIC_LABELS[c['metric']]
    return {'metric': c['metric'], 'period': c['period'], 'period_label': PERIOD_LABELS[c['period']], 'op': c['op'], 'threshold': c['value'], 'value': value,
            'unit': UNITS[c['metric']], 'label': label, 'result': 'unknown' if ok is None else 'pass' if ok else 'fail', 'optional': False}


def evaluate(norm, metrics):
    """{status, checks, active}. `norm` = résultat de `normalize` (None : contexte absent ⇒ indéterminé, jamais retenu)."""
    if norm is None:
        return {'status': UNDETERMINED, 'checks': [], 'active': 0, 'reason': 'context_missing'}
    checks = [_check(metrics, c) for c in norm['primary']]
    extra = [_check(metrics, c) for c in norm['extra']]
    for x in extra:
        x['optional'] = True
    if extra:
        results = [x['result'] for x in extra]
        if norm['join'] == 'or':
            group = 'pass' if 'pass' in results else 'unknown' if 'unknown' in results else 'fail'
        else:
            group = 'fail' if 'fail' in results else 'unknown' if 'unknown' in results else 'pass'
    else:
        group = 'pass'
    results = [c['result'] for c in checks]
    if 'fail' in results or group == 'fail':
        status = EXCLUDED
    elif 'unknown' in results or group == 'unknown':
        status = UNDETERMINED
    else:
        status = RETAINED
    return {'status': status, 'checks': checks + extra, 'active': len(checks) + len(extra), 'join': norm['join'] if extra else None,
            'reason': None if status != UNDETERMINED else 'missing_data'}


def counts(statuses):
    out = {RETAINED: 0, EXCLUDED: 0, UNDETERMINED: 0}
    for s in statuses:
        out[s] += 1
    out['all'] = sum(out.values())
    return out
