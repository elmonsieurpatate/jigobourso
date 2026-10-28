"""Stratégies : configuration, préréglages, évaluation d'un titre et classement.

Une stratégie = des périodes (nombre de séances) avec des critères chacune + des filtres techniques + un mode de classement.
Un titre est :
  retained  tous les critères actifs sont satisfaits sur toutes les périodes actives
  rejected  au moins un critère mesuré échoue (même si une autre mesure manque)
  unknown   rien n'échoue mais une mesure est indisponible (historique court, rupture de cours, cours périmé)
Chaque verdict porte la liste structurée des raisons (période, critère, valeur, seuil, résultat) : l'interface
et, plus tard, l'assistant de décision génèrent leurs explications à partir d'elle.

Ce module ne connaît ni la base ni le réseau. Il ne décide jamais de l'éligibilité d'un titre à la recommandation :
l'appelant ne lui fournit que des cotations recommandables (`v_recommendable`) ; un titre détenu mais exclu n'y passe pas.
"""
import copy
import math
from collections import defaultdict

from .measures import window_metrics, technical_state
from .series import usable_closes, find_breaks, clean_window

VERSION = 3
PERIOD_IDS = ('day', 'week', 'month', 'quarter', 'half', 'year')
DEFAULT_SESSIONS = {'day': 1, 'week': 5, 'month': 21, 'quarter': 63, 'half': 126, 'year': 252}
LABELS = {'day': 'Dernier jour', 'week': 'Dernière semaine', 'month': 'Dernier mois',
          'quarter': 'Trois mois', 'half': 'Six mois', 'year': 'Un an'}
RANK_MODES = ('trend', 'performance', 'regularity', 'stability')

# Pente minimale définie par le temps qu'il faudrait pour doubler à ce rythme (en % par séance, 252 séances/an).
SLOPE_LEVELS = {name: 100 * math.expm1(math.log(2) / (years * 252))
                for name, years in (('gentle', 8), ('moderate', 4), ('strong', 2), ('very_strong', 1))}
# Régularité : résidu de la droite au plus 2/3, 1/2, 1/3 de la dispersion totale (R² = 1 − ratio²).
R2_LEVELS = {'none': None, 'flexible': 1 - (2 / 3) ** 2, 'balanced': 1 - 0.5 ** 2, 'strict': 1 - (1 / 3) ** 2}

CRITERIA = (  # (champ de config, mesure, sens)  sens : '>=' seuil minimal, '<=' seuil maximal
    ('min_slope', 'slope', '>='), ('min_r2', 'r2', '>='), ('min_er', 'er', '>='),
    ('min_return', 'perf', '>='), ('max_return', 'perf', '<='),
    ('max_volatility', 'volatility', '<='), ('max_drawdown', 'drawdown', '<='))
TECHNICAL = ('above_ma50', 'ma50_rising', 'max_daily_change', 'max_gap_ma20')


def _period(pid, enabled=False, **thresholds):
    p = {'id': pid, 'sessions': DEFAULT_SESSIONS[pid], 'enabled': enabled}
    p.update({field: None for field, _, _ in CRITERIA})
    p.update(thresholds)
    return p


def preset(name):
    """Les quatre profils de départ. Ce sont des propositions de réglage, pas des vérités : tout est modifiable.
    Calibrés le 28/10/2026 sur ~9 700 titres réels pour retenir environ 4 à 8 % de l'univers (voir docs/METHODE.md)."""
    slope, reg = SLOPE_LEVELS['moderate'], R2_LEVELS['flexible']
    periods = {pid: _period(pid) for pid in PERIOD_IDS}
    rank = 'regularity'
    if name == 'regular':       # hausse soutenue ET régulière sur un mois et un trimestre
        for pid in ('month', 'quarter'):
            periods[pid].update(enabled=True, min_slope=slope, min_r2=reg)
    elif name == 'fast':        # hausse rapide, régularité non exigée
        rank = 'performance'
        periods['week'].update(enabled=True, min_slope=SLOPE_LEVELS['very_strong'], min_return=0.0)
        periods['month'].update(enabled=True, min_slope=SLOPE_LEVELS['very_strong'], min_return=12.0)
    elif name == 'recovery':    # rebond : repart à la hausse après une longue période sans progrès
        for pid in ('week', 'month'):
            periods[pid].update(enabled=True, min_slope=SLOPE_LEVELS['gentle'], min_r2=R2_LEVELS['flexible'])
        periods['half'].update(enabled=True, min_slope=-100.0, max_return=10.0)
        rank = 'trend'
    elif name == 'low_volatility':   # hausse douce avec variations quotidiennes faibles
        rank = 'stability'
        for pid in ('month', 'quarter'):
            periods[pid].update(enabled=True, min_slope=SLOPE_LEVELS['gentle'], min_r2=R2_LEVELS['flexible'],
                                max_volatility=1.5, max_drawdown=20.0)
    else:
        raise ValueError('Stratégie inconnue : ' + str(name))
    return {'version': VERSION, 'name': name,
            'periods': [periods[pid] for pid in PERIOD_IDS],
            'technical': {'above_ma50': False, 'ma50_rising': False, 'max_daily_change': None, 'max_gap_ma20': None},
            'ranking': {'mode': rank, 'weights': {}}}


PRESETS = ('regular', 'fast', 'recovery', 'low_volatility')


def _number(v, lo, hi, what):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f'{what} invalide')
    return float(v)


def validate(config):
    """Contrôle strict d'une configuration ; renvoie une copie normalisée ou lève ValueError (message affichable)."""
    if not isinstance(config, dict) or config.get('version') != VERSION:
        raise ValueError('Configuration de stratégie absente ou obsolète')
    c = copy.deepcopy(config)
    periods = c.get('periods')
    if not isinstance(periods, list) or [p.get('id') for p in periods if isinstance(p, dict)] != list(PERIOD_IDS):
        raise ValueError('Les six périodes doivent être définies, dans l’ordre')
    ranges = {'min_slope': (-100, 100), 'min_r2': (0, 1), 'min_er': (-1, 1), 'min_return': (-100, 10000),
              'max_return': (-100, 10000), 'max_volatility': (0, 100), 'max_drawdown': (0, 100)}
    active = 0
    for p in periods:
        if type(p.get('enabled')) is not bool:
            raise ValueError('Activation de période invalide')
        n = p.get('sessions')
        pid = p['id']
        if type(n) is not int or not 1 <= n <= 252 or (pid == 'day' and n != 1) or (pid != 'day' and n < 2):
            raise ValueError('Nombre de séances invalide (1 à 252 ; au moins 2 hors « jour »)')
        for field, (lo, hi) in ranges.items():
            p[field] = _number(p.get(field), lo, hi, field)
        if n < 3 and p['max_volatility'] is not None:
            raise ValueError('Volatilité non définie sur moins de 3 séances')
        if n < 3 and (p['min_r2'] is not None or p['min_er'] is not None):
            raise ValueError('R² et ER non définis sur moins de 3 séances')
        active += p['enabled']
    if not active:
        raise ValueError('Choisis au moins une période')
    t = c.get('technical') or {}
    c['technical'] = {'above_ma50': bool(t.get('above_ma50')), 'ma50_rising': bool(t.get('ma50_rising')),
                      'max_daily_change': _number(t.get('max_daily_change'), 0, 1000, 'max_daily_change'),
                      'max_gap_ma20': _number(t.get('max_gap_ma20'), 0, 1000, 'max_gap_ma20')}
    r = c.get('ranking') or {}
    if r.get('mode') not in RANK_MODES:
        raise ValueError('Mode de classement invalide')
    weights = r.get('weights') or {}
    if not isinstance(weights, dict) or any(k not in PERIOD_IDS for k in weights):
        raise ValueError('Poids de période invalides')
    c['ranking'] = {'mode': r['mode'], 'weights': {k: _number(v, 0, 100, 'poids') for k, v in weights.items()}}
    return c


def required_sessions(config):
    """Fenêtres à mesurer pour cette configuration (utile au calcul nocturne)."""
    return sorted({p['sessions'] for p in config['periods'] if p['enabled']})


def _check(period, criterion, metric, value, threshold, op):
    if threshold is None:
        return None
    if value is None:
        result = 'missing'
    else:
        result = 'pass' if (value >= threshold if op == '>=' else value <= threshold) else 'fail'
    return {'period': period, 'criterion': criterion, 'metric': metric, 'value': value, 'threshold': threshold, 'result': result}


def evaluate_one(config, candidate):
    """Évalue un titre depuis ses clôtures. candidate : {'bars': [(date, close, adj)], 'split_dates', 'expected_last_date'}.
    Renvoie {'status', 'reasons', 'measures' {séances: mesures|None}, 'technical', 'basis', 'breaks'}."""
    dates, closes, basis = usable_closes(candidate.get('bars') or [])
    breaks = find_breaks(dates, closes, basis, candidate.get('split_dates') or ())
    measures, missing = {}, {}
    for p in config['periods']:
        if p['enabled']:
            window, why = clean_window(closes, p['sessions'], breaks)
            measures[p['sessions']] = window_metrics(window) if window else None
            if measures[p['sessions']] is None:
                missing[p['sessions']] = why or 'invalid'
    verdict = judge(config, measures, technical_state(closes), missing, dates[-1] if dates else None, candidate.get('expected_last_date'))
    verdict.update(basis=basis, breaks=[dates[i] for i in breaks])
    return verdict


def judge(config, measures, tech, missing, last_close_date=None, expected_last_date=None):
    """Applique les critères à des mesures déjà calculées (fenêtres absentes : `missing` {séances: 'history'|'break'|'invalid'}).
    Même jugement que les mesures viennent du calcul direct ou de strategy_metrics."""
    reasons = []
    if expected_last_date and last_close_date and last_close_date < expected_last_date:
        reasons.append({'period': None, 'criterion': 'freshness', 'metric': 'last_close_date', 'value': last_close_date, 'threshold': expected_last_date, 'result': 'missing'})
    for p in config['periods']:
        if not p['enabled']:
            continue
        m = measures.get(p['sessions'])
        if m is None:
            reasons.append({'period': p['id'], 'criterion': 'data', 'metric': missing.get(p['sessions'], 'history'), 'value': None, 'threshold': p['sessions'] + 1, 'result': 'missing'})
            continue
        for field, metric, op in CRITERIA:
            chk = _check(p['id'], field, metric, m.get(metric), p[field], op)
            if chk:
                reasons.append(chk)
    t = config['technical']
    for name, metric, value, threshold, ok in (
            ('above_ma50', 'close', tech.get('close'), tech.get('ma50'), lambda a, b: a > b),
            ('ma50_rising', 'ma50', tech.get('ma50'), tech.get('ma50_prev'), lambda a, b: a > b),
            ('max_daily_change', 'daily_change', tech.get('daily_change'), t['max_daily_change'], lambda a, b: abs(a) <= b),
            ('max_gap_ma20', 'gap_to_ma20', tech.get('gap_to_ma20'), t['max_gap_ma20'], lambda a, b: abs(a) <= b)):
        enabled = bool(t[name]) if name in ('above_ma50', 'ma50_rising') else t[name] is not None
        if not enabled:
            continue
        result = 'missing' if value is None or threshold is None else ('pass' if ok(value, threshold) else 'fail')
        reasons.append({'period': 'technical', 'criterion': name, 'metric': metric, 'value': value, 'threshold': threshold, 'result': result})
    results = {r['result'] for r in reasons}
    status = 'rejected' if 'fail' in results else ('unknown' if 'missing' in results else 'retained')
    return {'status': status, 'reasons': reasons, 'measures': measures, 'technical': tech}


def rank(config, verdicts):
    """Ajoute 'score' (0-100) et 'rang' (dans le groupe) aux verdicts retenus. Verdicts : dicts avec key, group, symbol, status, measures."""
    mode, weights = config['ranking']['mode'], config['ranking']['weights']
    active = [p for p in config['periods'] if p['enabled']]
    retained = [v for v in verdicts if v['status'] == 'retained']
    pct = defaultdict(dict)
    for group in {v['group'] for v in retained}:
        members = [v for v in retained if v['group'] == group]
        for p in active:
            scores = {v['key']: _score(mode, v['measures'].get(p['sessions'])) for v in members}
            pct[(group, p['id'])] = _percentiles({k: x for k, x in scores.items() if x is not None})
    for v in verdicts:
        v['score'] = v['rank'] = None
    for v in retained:
        parts = [(pct[(v['group'], p['id'])].get(v['key']), float(weights.get(p['id'], 1))) for p in active]
        parts = [(x, w) for x, w in parts if x is not None and w > 0]
        v['score'] = sum(x * w for x, w in parts) / sum(w for _, w in parts) if parts else None
    for group in {v['group'] for v in retained}:
        ranked = sorted((v for v in retained if v['group'] == group and v['score'] is not None),
                        key=lambda v: (-v['score'], v['symbol'], str(v['key'])))
        for i, v in enumerate(ranked, 1):
            v['rank'] = i
    return verdicts


def _score(mode, m):
    if m is None:
        return None
    if mode == 'trend':
        return m['slope']
    if mode == 'performance':
        return m['perf']
    if mode == 'regularity':
        return m['r2']
    return -m['volatility'] if m['volatility'] is not None else None   # stability : volatilité faible = bon


def _percentiles(values):
    """values : {clé: score}. Percentile 0..100 (ex æquo = moyenne des rangs). Un seul élément : 50."""
    ordered = sorted(values.items(), key=lambda kv: (kv[1], str(kv[0])))
    n, out, i = len(ordered), {}, 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][1] == ordered[i][1]:
            j += 1
        pct = 50.0 if n == 1 else 100.0 * ((i + j - 1) / 2) / (n - 1)
        for k, _ in ordered[i:j]:
            out[k] = pct
        i = j
    return out


def evaluate(config, candidates):
    """candidates : liste de {'key', 'group': 'equity'|'etf', 'symbol', 'bars', …}. Renvoie les verdicts classés (même ordre).
    Les percentiles sont calculés par groupe : un ETF n'est jamais classé contre une action."""
    config = validate(config)
    verdicts = [dict(evaluate_one(config, c), key=c['key'], group=c.get('group', 'equity'), symbol=c.get('symbol', '')) for c in candidates]
    return rank(config, verdicts)
