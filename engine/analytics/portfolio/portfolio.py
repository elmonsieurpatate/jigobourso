"""Personal open-lot monitoring. No orders, predictions or Explorer ranking changes.

FIFO remaining quantities/costs are provided by PHP. Aggregate monitoring follows the
current cohort from its latest acquisition; individual historical peaks are never added.
Accounting PMP results remain exclusively in ledger.php.
"""
import datetime as dt
import math

from engine.market import hours
from ..series import signals
from ..explorer import strategy


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def protection(lots, dates, closes, euro_rates, current_eur, current_native, today, basis_cost=None, current_date=None):
    qty = sum(number(l.get('remaining')) or 0 for l in lots)
    costs = [number(l.get('remaining_cost')) for l in lots]
    start = max((l['trade_date'] for l in lots), default=None)
    unavailable = {'available': False, 'start': start, 'reason': 'Coût ou historique insuffisant pour suivre les gains de ces achats.'}
    if not start or qty <= 0 or any(c is None for c in costs) or sum(costs) <= 0:
        return unavailable
    if any(l.get('manual_split') for l in lots):
        return dict(unavailable, reason='Correction de split saisie manuellement : suivi par lot non comparable ; le résultat comptable reste disponible.')
    cost = number(basis_cost) if basis_cost is not None else sum(costs)
    if cost is None or cost <= 0: return unavailable
    current_eur, current_native = number(current_eur), number(current_native)
    observed = [(d, c, euro_rates.get(d)) for d, c in zip(dates, closes) if start <= d <= today]
    # Older-than-retained history cannot establish a true peak since acquisition.
    complete = not any(l.get('history_incomplete') for l in lots) and bool(dates and dates[0] <= start and observed and all(rate is not None for _, _, rate in observed))
    if not complete or current_eur is None or current_native is None:
        return dict(unavailable, reason='Début d’historique, change ou cours actuel manquant : sommet depuis l’achat indéterminé.')
    current_date = current_date or today
    if not start <= current_date <= today:
        return dict(unavailable, reason='Cours antérieur à l’achat ou daté dans le futur : suivi non comparable.')
    euros = [(d, qty * c * rate) for d, c, rate in observed]
    euros.append((current_date, qty * current_eur))
    peak_date, peak_value = max(euros, key=lambda x: x[1])
    value = qty * current_eur
    peak_pct, current_pct = 100 * (peak_value / cost - 1), 100 * (value / cost - 1)
    peak_native = max([c for _, c, _ in observed] + [current_native])
    return {'available': True, 'start': start, 'cost_eur': cost, 'value_eur': value,
            'gain_eur': value - cost, 'gain_pct': current_pct, 'peak_gain_pct': peak_pct,
            'peak_gain_eur': peak_value - cost, 'peak_date': peak_date, 'value_date': current_date,
            'given_back_pp': max(0.0, max(0.0, peak_pct) - max(0.0, current_pct)),
            'drop_pct': 100 * (1 - current_native / peak_native), 'high': peak_native}


def diagnose(position, lot_info, state, measures, personal, today):
    """Watch level is the existing lot alert severity, with existing signals as context."""
    state = state or {}
    all_alerts = [a for l in lot_info for a in l.get('alerts', [])]
    distinct = {}
    for alert in all_alerts:
        key = (alert['kind'], alert.get('threshold'), alert.get('action')) if alert['kind'] == 'duration' else (alert['kind'], alert['message'])
        count = distinct.get(key, {}).get('count', 0) + 1
        if key not in distinct or ('info', 'watch', 'act').index(alert['level']) > ('info', 'watch', 'act').index(distinct[key]['level']):
            distinct[key] = dict(alert)
        distinct[key]['count'] = count
        if alert['kind'] == 'duration' and count > 1:
            distinct[key]['message'] = f"Rappel de durée atteint pour {count} achats (repère : {alert.get('threshold')} jours)."
    reasons = list(distinct.values())
    quality = state.get('quality')
    stamp = position.get('price_time')
    try:
        stamp = dt.datetime.fromisoformat(str(stamp)).replace(tzinfo=dt.timezone.utc)
        stale = hours.price_is_stale(position.get('mic'), stamp, hours.utcnow(), expected=position.get('expected_close'), checked=position.get('collected_at'))
        expected = position.get('expected_close') or hours.expected_last_close(position.get('mic'), hours.utcnow())
        stale = stale or not state.get('last_close_date') or state['last_close_date'] < expected
    except (TypeError, ValueError, KeyError):
        stale = True
    reliable = position.get('value') is not None and quality == 'ok' and not stale and state.get('close') is not None and bool(measures.get(21))
    personal_config = position.get('portfolio_config')
    try:
        personal_config = strategy.validate(personal_config) if personal_config else None
    except (ValueError, TypeError, KeyError):
        personal_config = None
    for item in lot_info:
        if item.get('strategy') in ('momentum', 'momentum12', 'momentum_risk') and state.get('momentum_6m') is None: reliable = False
        if item.get('strategy') == 'custom' and personal_config is None: reliable = False
        if item.get('strategy') == 'recovery' and state.get('ma50') is None: reliable = False
    disabled = bool(lot_info) and all(l.get('rules', {}).get('off') for l in lot_info)
    if disabled: reasons.append({'kind': 'disabled', 'level': 'info', 'action': 'surveillance désactivée', 'message': 'Les alertes de tous ces achats sont désactivées ; l’absence de signal n’est pas un avis favorable.'})
    technical = signals.contradiction(measures)
    if reliable and technical:
        reasons.append({'kind': 'context', 'level': 'watch' if technical['kind'] == 'drop' else 'info',
                        'action': 'surveiller' if technical['kind'] == 'drop' else 'information', 'message': technical['text']})
    if reliable:
        checked_configs = set()
        for item in lot_info:
            name = item.get('strategy')
            if name in checked_configs or item.get('rules', {}).get('off'): continue
            checked_configs.add(name)
            config = strategy.preset(name) if name in strategy.PRESETS else personal_config if name == 'custom' else None
            if not config: continue
            for period in config.get('periods', []):
                if not period.get('enabled'): continue
                observed = measures.get(period['sessions'], {})
                for field, metric, label in (('max_volatility', 'volatility', 'Volatilité'), ('max_drawdown', 'drawdown', 'Repli maximal')):
                    value, limit = observed.get(metric), period.get(field)
                    if value is not None and limit is not None and value > limit:
                        value_text = f'{value:.2f}'.replace('.', ',')
                        limit_text = f'{limit:.2f}'.replace('.', ',')
                        reasons.append({'kind': metric, 'level': 'watch', 'action': 'surveiller', 'value': value, 'threshold': limit,
                                        'message': f"{label} sur {period['sessions']} séances : {value_text} %, au-dessus du plafond {limit_text} % de la stratégie de cet achat."})
    levels = position.get('levels') or {}
    if position.get('price') is not None and levels.get('stop') and position['price'] <= levels['stop']:
        reasons.append({'kind': 'stop', 'level': 'act', 'action': 'examiner', 'message': 'Le filet personnel est atteint. Examiner la position ; aucun ordre n’est envoyé.'})
    actionable = [r for r in reasons if r['level'] != 'info']
    severity = max((r['level'] for r in actionable), key=('watch', 'act').index, default=None)
    status = 'unknown' if not reliable else 'act' if severity == 'act' else 'watch' if severity else 'normal'
    if reliable: reasons.sort(key=lambda r: (('info','watch','act').index(r['level']), r['kind'] in ('momentum','ma50','stop'), r['kind'] != 'duration'), reverse=True)
    if not reliable:
        reasons.insert(0, {'kind': 'data', 'level': 'info', 'action': 'vérifier les données', 'message': 'Cours ancien, données insuffisantes ou indicateurs non fiables : aucun diagnostic rassurant n’est possible.'})
    gain = number(position.get('unrealized'))
    personal_text = 'Résultat personnel indisponible.' if gain is None else 'Position bénéficiaire depuis les achats.' if gain > 0 else 'Position en perte depuis les achats.' if gain < 0 else 'Position à l’équilibre.'
    labels = {'normal': 'Normal', 'watch': 'À surveiller', 'act': 'À examiner', 'unknown': 'Données insuffisantes'}
    next_step = {'normal': 'Aucun signal notable selon les règles disponibles ; continuer le suivi.',
                 'watch': 'Examiner les raisons de la dégradation et la cohérence avec la stratégie.',
                 'act': 'Examiner l’opportunité de protéger les gains ou de réévaluer la position ; ce n’est pas un ordre de vente.',
                 'unknown': 'Vérifier les données avant de décider.'}[status]
    if status == 'watch' and actionable and all(r['kind'] == 'duration' for r in actionable):
        next_step = 'Rappel périodique de stratégie atteint : réexaminer l’investissement, sans conclure à une dégradation du titre.'
    trend = signals.trend_class((measures.get(21) or {}).get('slope'), (measures.get(21) or {}).get('perf'))
    if disabled and status == 'normal':
        status = 'unknown'; labels['unknown'] = 'Surveillance désactivée'; next_step = 'Réactiver les alertes pour un suivi selon les règles des achats.'
    return {'status': status, 'label': labels[status], 'personal_text': personal_text, 'next_step': next_step,
            'reasons': reasons, 'protection': personal,
            'market': {'trend': trend, 'momentum_6m': state.get('momentum_6m'), 'ma50': state.get('ma50'),
                       'ma200': state.get('ma200'), 'close': state.get('close'), 'quality': quality,
                       'as_of': state.get('last_close_date'), 'reliable': reliable,
                       'volatility': (measures.get(63) or {}).get('volatility'), 'recent_change': technical}}


def enrich(conn, request, series, alerts, today):
    lots, positions = request.get('lots', []), request.get('positions', [])
    if not positions:
        return {}
    ids = [int(p['listing_id']) for p in positions if p.get('listing_id')]
    metrics, fx = {}, {'EUR': {}}
    with conn.cursor() as cur:
        if ids:
            cur.execute('SELECT listing_id,sessions,slope,perf,volatility,drawdown FROM strategy_metrics WHERE listing_id IN (%s) AND sessions IN (5,21,63,126,252)' % ','.join(['%s'] * len(ids)), ids)
            for r in cur.fetchall(): metrics.setdefault(r['listing_id'], {})[r['sessions']] = {k: number(r[k]) for k in ('slope', 'perf', 'volatility', 'drawdown')}
        currencies = sorted({{'GBp': 'GBP', 'GBX': 'GBP', 'ZAc': 'ZAR', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(p.get('price_currency'), p.get('price_currency')) for p in positions if p.get('price_currency') and p['price_currency'] != 'EUR'})
        if currencies:
            cur.execute('SELECT currency,rate_date,to_eur FROM fx_rates WHERE currency IN (%s) ORDER BY rate_date' % ','.join(['%s'] * len(currencies)), currencies)
            for r in cur.fetchall(): fx.setdefault(r['currency'], {})[str(r['rate_date'])] = float(r['to_eur'])
    from engine.market.collect import to_eur_factor
    from ..series.history import _Carry
    result = {}
    for p in positions:
        lid = p.get('listing_id'); own = [l for l in lots if l.get('listing_id') == lid] if lid else []
        dates, closes, state = series.get(lid, ([], [], None))
        rates = {}
        carries = {currency: _Carry(sorted((d, (d, rate)) for d, rate in values.items())) for currency, values in fx.items()}
        for day in dates:
            daily = {'EUR': 1}
            for cur, carry in carries.items():
                latest = carry.at(day)
                if latest and (dt.date.fromisoformat(day) - dt.date.fromisoformat(latest[0])).days <= 7:
                    daily[cur] = latest[1]
            rates[day] = to_eur_factor(p.get('price_currency'), daily)
        from engine.market.calendar import session_dates
        expected = session_dates(p.get('mic'), dates[-1], len(dates) + 30) if dates else None
        observed_dates = set(dates)
        own = [dict(l, history_incomplete=(state or {}).get('quality') in ('break', 'inconsistent_adjustments', 'calendar_unknown', 'stale') or expected is None or any(d not in observed_dates for d in (expected or []) if l['trade_date'] <= d <= today.isoformat())) for l in own]
        args = (dates, closes, rates, p.get('price_eur'), p.get('price'), today.isoformat())
        for l in own:
            if str(l['tx_id']) in alerts:
                alerts[str(l['tx_id'])]['protection'] = dict(protection([l], *args, current_date=str(p.get('price_time') or '')[:10] or None), currency=p.get('price_currency'))
        personal = dict(protection(own, *args, basis_cost=p.get('cost'), current_date=str(p.get('price_time') or '')[:10] or None), currency=p.get('price_currency'))
        from ..admin.service import expected_close, last_collection
        context = dict(p, portfolio_config=(request.get('portfolio_strategy') or {}).get('config'), expected_close=expected_close(conn, p['mic']), collected_at=last_collection(conn, p['mic'])) if p.get('mic') else p
        result[p['key']] = diagnose(context, [alerts[str(l['tx_id'])] for l in own if str(l['tx_id']) in alerts], state, metrics.get(lid, {}), personal, today.isoformat())
    return result
