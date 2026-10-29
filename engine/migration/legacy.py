"""Reprise des données de l'ancien Jigobourso (export JSON en lecture seule) dans le schéma V2.

Rien n'est modifié côté ancien système. La reprise est idempotente et vérifiable :
  - les identifiants de comptes, portefeuilles et transactions sont conservés ;
  - les transactions sans lien avec le catalogue (anciennes saisies à la main) sont rattachées à une cotation par symbole
    lorsque la correspondance est unique et sûre, sinon conservées telles quelles (sans cours) et signalées ;
  - la configuration de stratégie v2 est convertie en v3 : réglages de l'utilisateur conservés, « accélération » abandonnée.
"""
import json

from engine.analytics import strategy

OLD_KEYS = ('day', 'week', 'month', 'quarter', 'half', 'year')
OLD_ALIASES = {'daily': 'day', 'weekly': 'week', 'monthly': 'month', 'quarterly': 'quarter', 'semiannual': 'half', 'annual': 'year'}
OLD_PRESETS = {'regular': 'regular', 'fast': 'fast', 'recovery': 'recovery', 'low_volatility': 'low_volatility'}


def convert_config(old):
    """Ancienne configuration (v2) -> configuration V3 valide, ou None si illisible. Les seuils de l'utilisateur sont conservés."""
    if isinstance(old, str):
        try:
            old = json.loads(old)
        except ValueError:
            return None
    if not isinstance(old, dict) or not isinstance(old.get('periods'), dict):
        return None
    base = strategy.preset(OLD_PRESETS.get(old.get('strategy'), 'regular'))
    base['name'] = old.get('strategy') if old.get('strategy') in OLD_PRESETS else 'custom'
    periods = {p['id']: p for p in base['periods']}
    for key, src in old['periods'].items():
        pid = OLD_ALIASES.get(key, key)
        if pid not in periods or not isinstance(src, dict):
            continue
        p = periods[pid]
        p['enabled'] = bool(src.get('enabled', False))
        if isinstance(src.get('sessions'), int):
            p['sessions'] = src['sessions']
        for field in ('min_slope', 'min_r2', 'min_er', 'min_return', 'max_volatility', 'max_drawdown'):
            p[field] = src.get(field)
        p['max_return'] = None
    tech = old.get('technical_filters') or {}
    base['technical'] = {'above_ma50': bool((tech.get('price_above_ma50') or {}).get('enabled')),
                         'ma50_rising': bool((tech.get('ma50_ascending') or {}).get('enabled')),
                         'max_daily_change': (tech.get('max_daily_change') or {}).get('value') if (tech.get('max_daily_change') or {}).get('enabled') else None,
                         'max_gap_ma20': (tech.get('max_gap_to_ma20') or {}).get('value') if (tech.get('max_gap_to_ma20') or {}).get('enabled') else None}
    r = old.get('ranking') or {}
    weights = r.get('weights') if isinstance(r.get('weights'), dict) else {}
    base['ranking'] = {'mode': r.get('mode') if r.get('mode') in strategy.RANK_MODES else 'trend',
                       'weights': {k: v for k, v in weights.items() if k in strategy.PERIOD_IDS and isinstance(v, (int, float))}}
    try:
        return strategy.validate(base)
    except ValueError:
        return None


def _find_listing(cur, symbol, mic=None):
    """Cotation du catalogue pour un symbole : unique et sûre, sinon None. Renvoie (id, note)."""
    cur.execute('SELECT l.id, l.mic, l.is_primary, l.status FROM listings l WHERE UPPER(l.symbol)=UPPER(%s)', (symbol,))
    rows = cur.fetchall()
    if mic:
        rows = [r for r in rows if r['mic'] == mic] or rows
    if len(rows) == 1:
        return rows[0]['id'], None
    primaries = [r for r in rows if r['is_primary']]
    if len(primaries) == 1:
        return primaries[0]['id'], 'plusieurs cotations de ce symbole : la principale a été retenue'
    return None, 'symbole absent du catalogue' if not rows else 'symbole ambigu (' + ', '.join(sorted({r['mic'] for r in rows})) + ')'


def migrate(conn, data):
    """Importe comptes, portefeuilles et transactions. Renvoie un rapport {compteurs, avertissements}."""
    report = {'users': 0, 'portfolios': 0, 'transactions': 0, 'linked': 0, 'unlinked': 0, 'config_converted': 0, 'config_dropped': 0, 'warnings': []}
    old_listing = {int(l['listing_id']): l for l in data.get('listings') or []}
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM users')
        if cur.fetchone()['n'] and not data.get('_force'):
            raise RuntimeError('La base V2 contient déjà des comptes : reprise refusée (aucune donnée écrasée).')
        for u in data['jb_users']:
            cur.execute('INSERT INTO users(id,username,email,pass_hash,is_admin,active,created_at,last_login) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                        (u['id'], u['username'], u.get('email') or None, u['pass_hash'], u['is_admin'], u['active'], u['created_at'], u.get('last_login')))
            report['users'] += 1
        for p in data['jb_portfolios']:
            cfg = convert_config(p.get('strategy_config')) if p.get('strategy_config') else None
            if p.get('strategy_config'):
                report['config_converted' if cfg else 'config_dropped'] += 1
            cur.execute('INSERT INTO portfolios(id,user_id,name,is_default,strategy_config,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                        (p['id'], p['user_id'], p['name'], p['is_default'], json.dumps(cfg) if cfg else None, p['created_at'], p['updated_at']))
            report['portfolios'] += 1
        for t in sorted(data['jb_portfolio_transactions'], key=lambda x: x['id']):
            listing_id, note = None, None
            hint = old_listing.get(int(t['listing_id'])) if t.get('listing_id') else None
            listing_id, note = _find_listing(cur, (hint or {}).get('symbol') or t['symbol'], (hint or {}).get('mic'))
            if listing_id:
                report['linked'] += 1
            else:
                report['unlinked'] += 1
            if note:
                report['warnings'].append(f"transaction {t['id']} ({t['symbol']}) : {note}")
            cur.execute("""INSERT INTO portfolio_transactions(id,portfolio_id,listing_id,symbol,name,isin,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,note,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (t['id'], t['portfolio_id'], listing_id, t['symbol'], t.get('name') or None, (t.get('isin') or None), t['side'], t['quantity'], t['unit_price'],
                         ('GBX' if t.get('currency_code') in ('GBp','GBX') else t.get('currency_code')) or None, t.get('fx_to_eur'), t.get('fees') or 0, t.get('trade_at') or (t['trade_date'] + ' 12:00:00'), t.get('note'), t['created_at']))
            if not t.get('fx_to_eur') and t.get('currency_code') != 'EUR':
                report['warnings'].append(f"transaction {t['id']} : taux historique manquant, à confirmer explicitement")
            report['transactions'] += 1
    conn.commit()
    return report


def verify(conn, data):
    """Compare la V2 à l'export : comptes, quantités et coûts par portefeuille et par titre. Renvoie la liste des écarts (vide = conforme)."""
    problems = []
    with conn.cursor() as cur:
        for table, key, label in (('users', 'jb_users', 'comptes'), ('portfolios', 'jb_portfolios', 'portefeuilles'), ('portfolio_transactions', 'jb_portfolio_transactions', 'transactions')):
            cur.execute(f'SELECT COUNT(*) n FROM {table}')
            if cur.fetchone()['n'] != len(data[key]):
                problems.append(f'{label} : {cur.fetchone()} au lieu de {len(data[key])}')
        want = {}
        for t in data['jb_portfolio_transactions']:
            k = (t['portfolio_id'], t['symbol'])
            q = float(t['quantity']) * (1 if t['side'] == 'buy' else -1)
            want[k] = want.get(k, 0.0) + q
        cur.execute('SELECT portfolio_id, symbol, SUM(IF(side=%s,quantity,-quantity)) q FROM portfolio_transactions GROUP BY portfolio_id, symbol', ('buy',))
        got = {(r['portfolio_id'], r['symbol']): float(r['q']) for r in cur.fetchall()}
        for k, q in want.items():
            if abs(got.get(k, 0.0) - q) > 1e-9:
                problems.append(f'quantité {k}: {got.get(k)} au lieu de {q}')
        cur.execute('SELECT SUM(quantity*unit_price*COALESCE(fx_to_eur,1)) c FROM portfolio_transactions WHERE side=%s', ('buy',))
        got_cost = float(cur.fetchone()['c'] or 0)
        want_cost = sum(float(t['quantity']) * float(t['unit_price']) * float(t.get('fx_to_eur') or 1) for t in data['jb_portfolio_transactions'] if t['side'] == 'buy')
        if abs(got_cost - want_cost) > 0.005:
            problems.append(f'coût d’achat total : {got_cost:.4f} au lieu de {want_cost:.4f}')
        cur.execute('SELECT username, pass_hash FROM users')
        hashes = {r['username']: r['pass_hash'] for r in cur.fetchall()}
        for u in data['jb_users']:
            if hashes.get(u['username']) != u['pass_hash']:
                problems.append(f"compte {u['username']} : mot de passe non repris")
    return problems
