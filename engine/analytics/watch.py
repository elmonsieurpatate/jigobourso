"""Surveillance : modèles de règles par stratégie (seuils lus dans la configuration réelle de la stratégie) et évaluation des règles d'un portefeuille.
Une règle est évaluée sur des données réelles ; sans donnée suffisante son état est « insufficient », jamais « normal ». Aucune vente automatique : une règle ne fait que signaler."""
import datetime, math
from . import measures, strategy, history
from .series import prepare_series

SESSIONS = strategy.DEFAULT_SESSIONS
GRAN = {'day': 'jour', 'week': 'semaine', 'month': 'mois', 'quarter': 'trimestre', 'half': 'semestre', 'year': 'année'}
# kind: (libellé, unité, opérateur d'alerte, la valeur observée déclenche si elle est ...)
KINDS = {
    'price_below': ('Cours inférieur à', 'cours', '<'), 'price_above': ('Cours supérieur à', 'cours', '>'), 'target': ('Objectif de cours', 'cours', '>='),
    'gain_pct_above': ('Gain personnel au moins', '%', '>='), 'loss_pct': ('Perte personnelle d’au moins', '%', '>='),
    'gain_eur_above': ('Gain personnel au moins', '€', '>='), 'loss_eur': ('Perte personnelle d’au moins', '€', '>='),
    'drawdown_from_high': ('Recul du cours depuis son sommet', '%', '>='), 'gain_giveback': ('Gain rendu depuis le meilleur gain', 'points', '>='),
    'daily_move': ('Variation sur une séance', '%', '>='),
    'slope_min': ('Pente minimale', '% par séance', '<'), 'r2_min': ('R² minimal', 'ratio', '<'), 'vol_max': ('Volatilité maximale', '% par séance', '>'),
    'drawdown_max': ('Recul maximal sur la fenêtre', '%', '>'), 'momentum_min': ('Progression minimale', '%', '<'), 'ma_below': ('Cours sous la moyenne mobile', 'séances', 'below'),
}
STRATEGY_KINDS = ('slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min')


def template(name, config=None):
    """Règles proposées pour une stratégie : uniquement des critères réellement actifs dans sa configuration, avec ses seuils.
    Stratégies sans seuil (momentum) : une règle de dégradation du momentum à seuil 0 % (progression négative), explicitement marquée « à confirmer »."""
    cfg = config or strategy.preset(name)
    out = []
    for p in cfg.get('periods', []):
        if not p.get('enabled'):
            continue
        g = p['id']
        if p.get('min_slope') is not None and p['min_slope'] > -100:
            out.append({'kind': 'slope_min', 'granularity': g, 'threshold': p['min_slope'], 'severity': 'vigilance', 'source': 'strategy'})
        if p.get('min_r2') is not None:
            out.append({'kind': 'r2_min', 'granularity': g, 'threshold': p['min_r2'], 'severity': 'vigilance', 'source': 'strategy'})
        if p.get('max_volatility') is not None:
            out.append({'kind': 'vol_max', 'granularity': g, 'threshold': p['max_volatility'], 'severity': 'vigilance', 'source': 'strategy'})
        if p.get('max_drawdown') is not None:
            out.append({'kind': 'drawdown_max', 'granularity': g, 'threshold': p['max_drawdown'], 'severity': 'vigilance', 'source': 'strategy'})
        if p.get('min_return') is not None and p['min_return'] > 0:
            out.append({'kind': 'momentum_min', 'granularity': g, 'threshold': p['min_return'], 'severity': 'vigilance', 'source': 'strategy'})
    mode = (cfg.get('ranking') or {}).get('mode')
    if not out and mode in ('momentum', 'momentum12', 'momentum_risk'):
        g = 'year' if mode == 'momentum12' else 'half'
        out.append({'kind': 'momentum_min', 'granularity': g, 'threshold': 0.0, 'severity': 'vigilance', 'source': 'strategy', 'confirm': True})
    return out


def _closes(conn, ids):
    bars, splits, unit, (fx, meta) = history._load(conn, ids, datetime.date(2000, 1, 1))
    out = {}
    for lid in ids:
        dates, closes, _, _ = prepare_series(bars.get(lid, []), sorted(splits.get(lid, [])))
        out[lid] = (dates, closes)
    return out, meta


def _tail(closes, n):
    return closes[-(n + 1):] if len(closes) >= n + 1 else None


def evaluate(conn, request):
    rules = request.get('rules', [])
    txs = request.get('transactions', [])
    ids = sorted({int(r['listing_id']) for r in rules if r.get('listing_id')})
    if not ids:
        return {'results': {}}
    series, meta = _closes(conn, ids)
    lines = {}
    if txs:
        h = history.portfolio_history(conn, {'transactions': txs})
        lines = {l['key']: l for l in h.get('lines', [])}
    results = {}
    for r in rules:
        lid = int(r['listing_id']); dates, closes = series.get(lid, ([], []))
        results[str(r['id'])] = _one(r, lid, dates, closes, meta.get(lid) or {}, lines.get(str(lid)), h['dates'] if txs else [])
    return {'results': results}


def _res(state, value=None, reason=None):
    return {'state': state, 'value': value, 'reason': reason}


def _one(r, lid, dates, closes, meta, line, hdates):
    kind, thr, g = r['kind'], r.get('threshold'), r.get('granularity')
    if thr is None and kind not in ('ma_below',):
        return _res('insufficient', None, 'Seuil non renseigné.')
    thr = float(thr)
    price = meta.get('price') if meta.get('price') is not None else (closes[-1] if closes else None)
    price = None if price is None else float(price)
    if kind in ('price_below', 'price_above', 'target'):
        if price is None: return _res('insufficient', None, 'Aucun cours disponible.')
        hit = price < thr if kind == 'price_below' else price >= thr if kind == 'target' else price > thr
        return _res('triggered' if hit else 'normal', price)
    if kind in ('gain_pct_above', 'loss_pct', 'gain_eur_above', 'loss_eur', 'gain_giveback'):
        if not line: return _res('insufficient', None, 'Aucune position valorisée.')
        gains, purch = line['gain'], line['purchases']
        k = next((i for i in range(len(gains) - 1, -1, -1) if gains[i] is not None), None)
        if k is None or not purch[k] or purch[k] <= 0: return _res('insufficient', None, 'Gain personnel non calculable (cours ou change manquant).')
        g_now, base = gains[k], purch[k]
        if kind == 'gain_giveback':
            pcts = [100 * gains[i] / purch[i] for i in range(len(gains)) if gains[i] is not None and purch[i] and purch[i] > 0]
            val = max(pcts) - 100 * g_now / base
            return _res('triggered' if val >= thr else 'normal', val)
        val = {'gain_pct_above': 100 * g_now / base, 'loss_pct': -100 * g_now / base, 'gain_eur_above': g_now, 'loss_eur': -g_now}[kind]
        return _res('triggered' if val >= thr else 'normal', val)
    if kind == 'drawdown_from_high':
        first = r.get('since')
        px = [c for d, c in zip(dates, closes) if not first or d >= first]
        if len(px) < 2: return _res('insufficient', None, 'Historique de cours insuffisant depuis l’achat.')
        val = 100 * (1 - px[-1] / max(px))
        return _res('triggered' if val >= thr else 'normal', val)
    if kind == 'daily_move':
        if len(closes) < 2: return _res('insufficient', None, 'Historique de cours insuffisant.')
        val = abs(100 * (closes[-1] / closes[-2] - 1)); return _res('triggered' if val >= thr else 'normal', val)
    if kind == 'ma_below':
        n = int(thr or 50)
        if len(closes) < n: return _res('insufficient', None, f'Moins de {n} séances de cours.')
        ma = sum(closes[-n:]) / n; return _res('triggered' if closes[-1] < ma else 'normal', closes[-1] / ma - 1 if ma else None)
    n = SESSIONS.get(g or '')
    if not n: return _res('insufficient', None, 'Granularité inconnue.')
    w = _tail(closes, n)
    if w is None: return _res('insufficient', None, f'Moins de {n + 1} clôtures disponibles pour cette granularité.')
    m = measures.window_metrics(w)
    if not m: return _res('insufficient', None, 'Fenêtre de cours invalide.')
    key = {'slope_min': 'slope', 'r2_min': 'r2', 'vol_max': 'volatility', 'drawdown_max': 'drawdown', 'momentum_min': 'perf'}[kind]
    val = m.get(key)
    if val is None: return _res('insufficient', None, 'Mesure non définie sur cette fenêtre.')
    hit = val < thr if kind in ('slope_min', 'r2_min', 'momentum_min') else val > thr
    return _res('triggered' if hit else 'normal', val)


MESSAGES = {'triggered': 'Condition atteinte', 'normal': 'Retour à la normale', 'insufficient': 'Données insuffisantes'}


def run_all(conn, now=None, user_id=None, force=False):
    """Évalue les règles actives (toutes, ou celles d'un utilisateur) et enregistre états et événements.
    Une règle déjà déclenchée ne génère pas de nouvel événement tant que sa condition persiste (pas de répétition à chaque passage)."""
    now = now or datetime.datetime.utcnow()
    with conn.cursor() as cur:
        if not force and user_id is None:
            cur.execute('SELECT MAX(last_eval_at) m FROM alert_rules')
            m = (cur.fetchone() or {}).get('m')
            if m and (now - m).total_seconds() < 600:
                return {'skipped': True}
        sql = 'SELECT * FROM alert_rules WHERE enabled=1' + (' AND user_id=%s' if user_id is not None else '')
        cur.execute(sql, [user_id] if user_id is not None else [])
        rules = cur.fetchall()
    by_pf = {}
    for r in rules:
        by_pf.setdefault(r['portfolio_id'], []).append(r)
    stats = {'rules': len(rules), 'triggered': 0}
    for pid, rs in by_pf.items():
        with conn.cursor() as cur:
            cur.execute('SELECT id, listing_id, symbol, name, side, quantity, unit_price, currency, fx_to_eur, fees, trade_at FROM portfolio_transactions WHERE portfolio_id=%s ORDER BY trade_at, id', [pid])
            txs = cur.fetchall()
            cur.execute("SELECT listing_id, MIN(trade_at) f FROM portfolio_transactions WHERE portfolio_id=%s AND side='buy' GROUP BY listing_id", [pid])
            first = {x['listing_id']: str(x['f'])[:10] for x in cur.fetchall()}
        req = {'transactions': [dict(t, trade_at=str(t['trade_at'])) for t in txs],
               'rules': [{'id': r['id'], 'listing_id': r['listing_id'], 'kind': r['kind'], 'granularity': r['granularity'], 'threshold': None if r['threshold'] is None else float(r['threshold']), 'since': first.get(r['listing_id'])} for r in rs]}
        try:
            res = evaluate(conn, req)['results']
        except Exception as e:                                                  # noqa: BLE001
            res = {str(r['id']): {'state': 'error', 'value': None, 'reason': ('Erreur d’évaluation : ' + str(e))[:190]} for r in rs}
        for r in rs:
            o = res.get(str(r['id'])) or {'state': 'error', 'value': None, 'reason': 'Aucun résultat.'}
            old, new = r['state'], o['state']
            sets = {'state': new, 'last_eval_at': now, 'last_value': o['value'], 'last_reason': (o['reason'] or None)}
            event = None
            if new == 'triggered' and old != 'triggered':
                sets.update(triggered_at=now, acked_at=None); event = 'triggered'; stats['triggered'] += 1
            elif new == 'normal' and old == 'triggered':
                sets.update(normal_at=now, acked_at=None); event = 'normal'
            elif new in ('insufficient', 'error') and old != new:
                event = 'insufficient'
            with conn.cursor() as cur:
                cur.execute('UPDATE alert_rules SET ' + ', '.join(f'{k}=%s' for k in sets) + ' WHERE id=%s', list(sets.values()) + [r['id']])
                if event:
                    cur.execute('INSERT INTO alert_events(rule_id, user_id, at, event, value_obs, threshold, message) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                                [r['id'], r['user_id'], now, event, o['value'], r['threshold'], (o['reason'] or MESSAGES[event])[:250]])
        conn.commit()
    return stats
