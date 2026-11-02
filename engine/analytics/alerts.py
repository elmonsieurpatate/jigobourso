"""Alertes de vente, calculées ACHAT PAR ACHAT (lot) : chaque achat garde sa stratégie et ses propres réglages.

Rien n'est vendu : une alerte dit « surveiller », « alléger », « vente à envisager », « réexaminer » ou « rééquilibrer », avec la raison chiffrée.
Valeurs par défaut tirées de research/RESULTATS_SORTIES.md (test chronologique 1993-2026, exploratoire) :
  - conserver plus longtemps a toujours rapporté plus : le rappel de durée vient vers 6 mois (126 séances ≈ 182 jours), pas au bout de quelques semaines ;
  - le stop suiveur −20 % coupe les pires positions (au prix d'un peu de rendement) : alerte « surveiller » (« alléger » pour la croissance rapide) ;
  - Momentum : la meilleure sortie testée est « le momentum 6-1 du titre devient négatif » ;
  - Rebond : « le cours passe sous sa moyenne 50 jours » fait mieux qu'une durée fixe équivalente ;
  - la sortie du classement (Top 50) n'a montré aucun avantage : elle est signalée pour information seulement.
"""
import datetime

from . import strategy
from .series import prepare_series

RANK_LIMIT = 50


def fr(x, digits=1):
    """Nombre à la française (virgule décimale) pour les messages."""
    return f'{x:.{digits}f}'.replace('.', ',')

DEFAULT_DAYS = 182
DEFAULT_DROP = 20.0
MOMENTUM = ('momentum', 'momentum12', 'momentum_risk')
STRATEGIES = tuple(strategy.PRESETS) + ('prudent',)
NAMES = {'regular': 'Croissance régulière', 'fast': 'Croissance rapide', 'recovery': 'Rebond', 'low_volatility': 'Hausse calme', 'momentum': 'Momentum 6 mois',
         'momentum12': 'Momentum 12 mois', 'momentum_risk': 'Momentum ajusté au risque', 'prudent': 'Prudente (ETF par zone)', 'custom': 'Stratégie du portefeuille'}


def defaults(name):
    """Réglages par défaut d'une stratégie : durée (jours), chute depuis le plus haut (%), action conseillée sur chute, règle de sortie propre."""
    if name == 'prudent':
        return {'days': 365, 'drop': None, 'drop_action': None, 'days_action': 'rééquilibrer', 'exit': None, 'rank_exit': False}
    out = {'days': DEFAULT_DAYS, 'drop': DEFAULT_DROP, 'drop_action': 'alléger' if name == 'fast' else 'surveiller', 'days_action': 'réexaminer',
           'exit': 'momentum_negative' if name in MOMENTUM else 'below_ma50' if name == 'recovery' else None, 'rank_exit': True}
    return out


def rules_for(name, settings):
    """Réglages effectifs d'un achat : ceux de la stratégie, remplacés par les réglages personnels de l'achat quand ils existent."""
    r = defaults(name)
    s = settings or {}
    if s.get('alert_days') is not None:
        r['days'] = int(s['alert_days'])
    if s.get('alert_drop_pct') is not None:
        r['drop'] = float(s['alert_drop_pct'])
        r['drop_action'] = r['drop_action'] or 'surveiller'
    r['off'] = bool(s.get('alerts_off'))
    r['personal'] = any(s.get(k) is not None for k in ('alert_days', 'alert_drop_pct')) or r['off']
    return r


def lot_measures(trade_date, dates, closes):
    """Plus haut depuis l'achat et chute depuis ce plus haut (%), sur la série corrigée des splits (le prix payé n'est pas utilisé : il n'est pas corrigé)."""
    since = [c for d, c in zip(dates, closes) if d >= trade_date]
    if not since:
        return None
    high = max(since)
    return {'high': high, 'last': since[-1], 'drop_pct': 100 * (1 - since[-1] / high) if high > 0 else None, 'sessions': len(since)}


def evaluate(lot, rules, measures, state, rank, today):
    """Liste d'alertes {kind, level, action, message} pour un achat. level : 'info' < 'watch' < 'act'."""
    if rules.get('off'):
        return []
    out = []
    held = (today - datetime.date.fromisoformat(lot['trade_date'])).days
    if rules.get('days') and held >= rules['days']:
        out.append({'kind': 'duration', 'level': 'watch', 'action': rules['days_action'], 'value': held, 'threshold': rules['days'],
                    'message': f"Détenu depuis {held} jours (repère : {rules['days']} jours)."})
    if rules.get('drop') and measures and measures.get('drop_pct') is not None and measures['drop_pct'] >= rules['drop']:
        out.append({'kind': 'drop', 'level': 'act' if rules['drop_action'] == 'alléger' else 'watch', 'action': rules['drop_action'], 'value': round(measures['drop_pct'], 1), 'threshold': rules['drop'],
                    'message': f"Le cours a perdu {fr(measures['drop_pct'])} % depuis son plus haut depuis l'achat (seuil : {fr(rules['drop'], 0) if float(rules['drop']).is_integer() else fr(rules['drop'])} %)."})
    st = state or {}
    if rules.get('exit') == 'momentum_negative' and st.get('momentum_6m') is not None and st['momentum_6m'] < 0:
        out.append({'kind': 'momentum', 'level': 'act', 'action': 'vente à envisager', 'value': round(100 * st['momentum_6m'], 1), 'threshold': 0,
                    'message': f"Le momentum 6 mois du titre est devenu négatif ({fr(100 * st['momentum_6m'])} %) : c'est la meilleure règle de sortie testée pour le Momentum."})
    if rules.get('exit') == 'below_ma50' and st.get('close') and st.get('ma50') and st['close'] < st['ma50']:
        out.append({'kind': 'ma50', 'level': 'act', 'action': 'vente à envisager', 'value': st['close'], 'threshold': st['ma50'],
                    'message': 'Le cours est passé sous sa moyenne 50 jours : fin probable du rebond.'})
    if rules.get('rank_exit') and rank is not False and (rank is None or rank > RANK_LIMIT):
        out.append({'kind': 'rank', 'level': 'info', 'action': 'information', 'value': rank, 'threshold': RANK_LIMIT,
                    'message': ("N'est plus retenu par sa stratégie." if rank is None else f"N'est plus dans les {RANK_LIMIT} premiers de sa stratégie (rang {rank}).")
                               + ' Pour information : sortir à ce signal n\'a pas montré d\'avantage.'})
    return out


def _series(conn, ids):
    out = {}
    if not ids:
        return out
    marks = ','.join(['%s'] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f'SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({marks}) ORDER BY listing_id, price_date', list(ids))
        bars = {}
        for r in cur.fetchall():
            bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
        cur.execute(f"SELECT listing_id, event_date, ratio FROM corporate_events WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split')", list(ids))
        splits = {}
        for r in cur.fetchall():
            splits.setdefault(r['listing_id'], []).append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
        cur.execute(f'SELECT listing_id, close_px, ma50, momentum_6m FROM series_state WHERE listing_id IN ({marks})', list(ids))
        states = {r['listing_id']: {'close': None if r['close_px'] is None else float(r['close_px']), 'ma50': None if r['ma50'] is None else float(r['ma50']),
                                    'momentum_6m': None if r['momentum_6m'] is None else float(r['momentum_6m'])} for r in cur.fetchall()}
    for lid in ids:
        dates, closes, _, _ = prepare_series(bars.get(lid, []), splits.get(lid, ()))
        out[lid] = (dates, closes, states.get(lid))
    return out


def _ranks(conn, name, config):
    """{listing_id: rang} des titres retenus par la stratégie (verdicts en cache, comme l'Explorer)."""
    from . import service
    cfg = strategy.validate(config) if config else strategy.validate(strategy.preset(name))
    return {e['id']: e['rank'] for e in service.cached_verdicts(conn, cfg) if e['status'] == 'retained' and e.get('rank') is not None}


def lot_alerts(conn, request, today=None):
    """request : {portfolio_strategy: {name, config}|None, lots: [{tx_id, listing_id, trade_date, strategy, alert_days, alert_drop_pct, alerts_off}]}."""
    today = today or datetime.date.today()
    pf = request.get('portfolio_strategy') or {}
    pf_name = pf.get('name') if pf.get('name') in strategy.PRESETS else ('custom' if pf.get('config') else 'regular')
    lots = [l for l in request.get('lots', []) if l.get('listing_id')]
    series = _series(conn, sorted({int(l['listing_id']) for l in lots}))
    rank_cache, out = {}, {}
    for lot in lots:
        own = lot.get('strategy') if lot.get('strategy') in STRATEGIES else None
        name = own or pf_name
        rules = rules_for('regular' if name == 'custom' else name, lot)
        dates, closes, state = series.get(int(lot['listing_id']), ([], [], None))
        m = lot_measures(lot['trade_date'], dates, closes)
        rank = False
        if rules.get('rank_exit') and not rules.get('off'):
            if name not in rank_cache:
                try:
                    rank_cache[name] = _ranks(conn, name, pf.get('config') if name == 'custom' else None)
                except Exception:                    # classement indisponible : l'alerte de classement est simplement omise
                    rank_cache[name] = None
            rank = False if rank_cache[name] is None else rank_cache[name].get(int(lot['listing_id']))
        alerts = evaluate(lot, rules, m, state, rank, today)
        out[str(lot['tx_id'])] = {'strategy': name, 'strategy_label': NAMES.get(name, name), 'own_strategy': own is not None,
                                  'rules': {k: rules.get(k) for k in ('days', 'drop', 'drop_action', 'days_action', 'exit', 'off', 'personal')},
                                  'measures': m, 'rank': rank if rank is not False else None, 'alerts': alerts,
                                  'level': max((a['level'] for a in alerts), key=('info', 'watch', 'act').index, default=None)}
    return {'lots': out, 'rank_limit': RANK_LIMIT, 'strategies': {k: NAMES[k] for k in STRATEGIES}}
