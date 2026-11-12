"""Surveillance : modèles de règles par stratégie (seuils lus dans la configuration réelle de la stratégie) et évaluation des règles d'un portefeuille.
Une règle est évaluée sur des données réelles ; sans donnée suffisante son état est « insufficient », jamais « normal ». Aucune vente automatique : une règle ne fait que signaler."""
import datetime
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
    'momentum6_min': ('Momentum 6 mois minimal (6−1)', '%', '<'), 'momentum12_min': ('Momentum 12 mois minimal (12−1)', '%', '<'),
    'er_min': ('Régularité (efficacité) minimale', 'ratio', '<'), 'ma_falling': ('Moyenne mobile orientée à la baisse', 'séances', 'falling'),
    'gap_ma20_max': ('Écart maximal à la moyenne 20 séances', '%', '>'),
}
STRATEGY_KINDS = ('slope_min', 'r2_min', 'vol_max', 'drawdown_max', 'momentum_min', 'momentum6_min', 'momentum12_min', 'er_min', 'ma_below', 'ma_falling', 'gap_ma20_max', 'daily_move')
MODEL_SCHEMA = 1                                                                # version du format des modèles (pour les futures évolutions)
# Registre des indicateurs : règle -> (mesure réutilisée, calcul source). Aucune formule n'est réécrite ici.
INDICATORS = {
    'slope_min': 'measures.window_metrics.slope', 'r2_min': 'measures.window_metrics.r2', 'vol_max': 'measures.window_metrics.volatility',
    'drawdown_max': 'measures.window_metrics.drawdown', 'momentum_min': 'measures.window_metrics.perf', 'er_min': 'measures.window_metrics.er',
    'momentum6_min': 'series.momentum_6_1', 'momentum12_min': 'series.momentum_12_1', 'ma_below': 'measures.moving_average', 'ma_falling': 'measures.moving_average',
    'gap_ma20_max': 'measures.technical_state.gap_to_ma20', 'daily_move': 'measures.technical_state.daily_change',
}


def _rule(kind, g, thr, why, **kw):
    return dict({'kind': kind, 'granularity': g, 'threshold': thr, 'severity': 'vigilance', 'source': 'strategy', 'why': why}, **kw)


def template(name, config=None):
    """Modèle de règles d'une stratégie, construit uniquement à partir de ses critères réellement actifs (seuil lu dans la configuration, jamais saisi à la main).
    Critère minimum -> alerte sous le seuil ; maximum -> alerte au-dessus ; critère inactif -> aucune règle ; seuil absent -> rien d'inventé.
    Critères d'entrée (rendement maximal du Rebond, pente de -100) : jamais surveillés. Momentum sans seuil : un complément proposé, désactivé tant que l'utilisateur ne le confirme pas."""
    cfg = config or strategy.preset(name)
    out = []
    for p in cfg.get('periods', []):
        if not p.get('enabled'):
            continue
        g = p['id']
        lab = GRAN.get(g, g)
        if p.get('min_slope') is not None and p['min_slope'] > -100:
            out.append(_rule('slope_min', g, p['min_slope'], f'Pente minimale exigée par la stratégie sur 1 {lab}.'))
        if p.get('min_r2') is not None:
            out.append(_rule('r2_min', g, p['min_r2'], f'R² minimal exigé par la stratégie sur 1 {lab}.'))
        if p.get('max_volatility') is not None:
            out.append(_rule('vol_max', g, p['max_volatility'], f'Volatilité maximale admise par la stratégie sur 1 {lab}.'))
        if p.get('max_drawdown') is not None:
            out.append(_rule('drawdown_max', g, p['max_drawdown'], f'Recul maximal admis par la stratégie sur 1 {lab}.'))
        if p.get('min_er') is not None:
            out.append(_rule('er_min', g, p['min_er'], f'Régularité minimale exigée par la stratégie sur 1 {lab}.'))
        if p.get('min_return') is not None and p['min_return'] > 0:
            out.append(_rule('momentum_min', g, p['min_return'], f'Rendement minimal exigé par la stratégie sur 1 {lab}.'))
        # max_return : condition d'entrée (ex. Rebond) -> jamais une alerte négative.
    t = cfg.get('technical') or {}
    if t.get('above_ma50'):
        out.append(_rule('ma_below', None, 50, 'La stratégie exige un cours au-dessus de la moyenne 50 séances.'))
    if t.get('above_ma200'):
        out.append(_rule('ma_below', None, 200, 'La stratégie exige un cours au-dessus de la moyenne 200 séances.'))
    if t.get('ma50_rising'):
        out.append(_rule('ma_falling', None, 50, 'La stratégie exige une moyenne 50 séances orientée à la hausse.'))
    if t.get('ma200_rising'):
        out.append(_rule('ma_falling', None, 200, 'La stratégie exige une moyenne 200 séances orientée à la hausse.'))
    if t.get('max_gap_ma20') is not None:
        out.append(_rule('gap_ma20_max', None, t['max_gap_ma20'], 'Écart maximal au cours moyen 20 séances admis par la stratégie.'))
    if t.get('max_daily_change') is not None:
        out.append(_rule('daily_move', None, t['max_daily_change'], 'Variation maximale sur une séance admise par la stratégie.'))
    mode = (cfg.get('ranking') or {}).get('mode')
    mk = {'momentum': ('momentum6_min', 'half', 'Momentum 6 mois (6−1)'), 'momentum12': ('momentum12_min', 'year', 'Momentum 12 mois (12−1)'), 'momentum_risk': ('momentum6_min', 'half', 'Momentum (6−1)')}.get(mode)
    if mk and not any(r['kind'] == mk[0] for r in out):
        # La stratégie classe par momentum mais n'impose aucun seuil : complément optionnel, désactivé, à confirmer.
        out.append(_rule(mk[0], mk[1], 0.0, f'{mk[2]} : la stratégie classe sans seuil minimal. Complément proposé (progression positive), à confirmer.', confirm=True, enabled=False))
    return out


def _closes(conn, ids):
    bars, splits, unit, (fx, meta) = history._load(conn, ids, datetime.date(2000, 1, 1))
    out = {}
    for lid in ids:
        dates, closes, _, brk = prepare_series(bars.get(lid, []), sorted(splits.get(lid, [])))
        out[lid] = (dates, closes, brk)
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
        lid = int(r['listing_id']); dates, closes, brk = series.get(lid, ([], [], []))
        results[str(r['id'])] = _one(r, lid, dates, closes, meta.get(lid) or {}, lines.get(str(lid)), h['dates'] if txs else [], brk)
    return {'results': results}


def _res(state, value=None, reason=None):
    return {'state': state, 'value': value, 'reason': reason}


def _one(r, lid, dates, closes, meta, line, hdates, brk=()):
    kind, thr, g = r['kind'], r.get('threshold'), r.get('granularity')
    if thr is None and kind not in ('ma_below', 'ma_falling'):
        return _res('insufficient', None, 'Seuil non renseigné.')
    thr = float(thr) if thr is not None else 0.0
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
    if kind in ('momentum6_min', 'momentum12_min'):
        from . import series as _s
        need = 127 if kind == 'momentum6_min' else 253
        if len(closes) < need: return _res('insufficient', None, f'Historique insuffisant : {need} clôtures nécessaires, {len(closes)} disponibles.')
        fn = _s.momentum_6_1 if kind == 'momentum6_min' else _s.momentum_12_1
        val = fn(dates, closes, brk)
        if val is None: return _res('insufficient', None, 'Mesure non fiable (clôture absente ou rupture de cours non expliquée).')
        return _res('triggered' if val < thr else 'normal', val)
    if kind == 'gap_ma20_max':
        if len(closes) < 20: return _res('insufficient', None, 'Moins de 20 séances de cours.')
        ma = sum(closes[-20:]) / 20; val = abs(100 * (closes[-1] / ma - 1)) if ma else None
        if val is None: return _res('insufficient', None, 'Moyenne indisponible.')
        return _res('triggered' if val > thr else 'normal', val)
    if kind == 'ma_falling':
        n = int(thr or 50)
        if len(closes) < n + 5: return _res('insufficient', None, f'Moins de {n + 5} séances de cours.')
        now_, prev = sum(closes[-n:]) / n, sum(closes[-n - 5:-5]) / n
        return _res('triggered' if now_ < prev else 'normal', 100 * (now_ / prev - 1) if prev else None)
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
    key = {'slope_min': 'slope', 'r2_min': 'r2', 'vol_max': 'volatility', 'drawdown_max': 'drawdown', 'momentum_min': 'perf', 'er_min': 'er'}.get(kind)
    if key is None: return _res('insufficient', None, 'Type de règle non évaluable.')
    val = m.get(key)
    if val is None: return _res('insufficient', None, 'Mesure non définie sur cette fenêtre.')
    hit = val < thr if kind in ('slope_min', 'r2_min', 'momentum_min', 'er_min') else val > thr
    return _res('triggered' if hit else 'normal', val)


MESSAGES = {'triggered': 'Condition atteinte', 'normal': 'Retour à la normale', 'insufficient': 'Données insuffisantes'}


# Ancien système « Surveillance » : remplacé par le Plan de suivi (engine/analytics/position_plan.py). Les règles restent en base, intactes ;
# plus aucune évaluation ni aucun événement n'est produit, quel que soit l'appelant (tick planifié, CLI, API). Verrou unique, volontairement en dur.
LEGACY_EXECUTION_ENABLED = False


def run_all(conn, now=None, user_id=None, force=False):
    """Évalue les règles actives (toutes, ou celles d'un utilisateur) et enregistre états et événements.
    Une règle déjà déclenchée ne génère pas de nouvel événement tant que sa condition persiste (pas de répétition à chaque passage).
    DÉSACTIVÉ : renvoie immédiatement, sans lire ni écrire alert_rules / alert_events."""
    if not LEGACY_EXECUTION_ENABLED:
        return {'disabled': True, 'rules': 0, 'triggered': 0}
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
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
