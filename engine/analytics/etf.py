"""ETF : information seulement. Aucun appel fournisseur, aucun effet sur les scores.
Six mois calendaires, rendements EUR, intervalles identiques, au moins 100 observations.
"""
import calendar
import datetime as dt
import json
import math
from collections import defaultdict

from .series import prepare_series

MIN_COMMON = 100
STRONG = 0.90
VERSION = 1
MAX_PROFILE_DAYS = 90


def number(v):
    if isinstance(v, bool):
        return None
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def profile_data(data):
    """Conserve les inconnues. Les poids stockés sont en pour cent, pas en fractions."""
    data = dict(data or {})
    holdings = []
    for h in data.get('holdings') or []:
        w = number(h.get('weight'))
        holdings.append(dict(h, weight=w if w is not None and 0 <= w <= 100 else None))
    sectors = {}
    for name, value in (data.get('sectors') or {}).items():
        w = number(value)
        if w is not None and 0 <= w <= 100:
            sectors[name] = w
    if sum(sectors.values()) > 100.0001:
        sectors = {}                     # incohérence, jamais renormalisée en secret
    fee = number(data.get('expense_ratio'))
    data.update(holdings=holdings, sectors=sectors, expense_ratio=fee if fee is not None and 0 <= fee <= 100 else None)
    weights = [h['weight'] for h in holdings if h['weight'] is not None]
    data['top10_weight'] = round(sum(weights), 1) if len(holdings) == len(weights) == 10 and sum(weights) <= 100 else None
    data['known_holdings_weight'] = sum(weights) if weights and sum(weights) <= 100 else None
    return data


def six_months(day):
    month = day.month - 6
    year = day.year
    if month <= 0:
        year, month = year - 1, month + 12
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def returns_eur(bars, splits, currency, fx, start, end=None):
    """Pas de remplissage des prix. Clés = DEUX dates, afin de ne pas comparer 1 et 2 séances.
    Change à la date de chaque clôture (dernier taux antérieur, 7 jours maximum).
    """
    dates, closes, _, breaks = prepare_series(bars, splits)
    cur = {'GBp': 'GBP', 'GBX': 'GBP', 'ZAc': 'ZAR', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(currency, currency)
    scale = .01 if currency in ('GBp', 'GBX', 'ZAc', 'ZAC', 'ILA') else 1.0
    rates = fx.get(cur, {})
    def rate(day):
        if cur == 'EUR':
            return 1.0
        d = dt.date.fromisoformat(day)
        for lag in range(8):
            r = number(rates.get((d - dt.timedelta(days=lag)).isoformat()))
            if r is not None and r > 0:
                return r
        return None
    converted = []
    for day, close in zip(dates, closes):
        r = rate(day)
        converted.append(close * scale * r if r is not None else None)
    out = {}
    if end and dates and dt.date.fromisoformat(dates[-1]) < end - dt.timedelta(days=7):
        return out
    for i in range(1, len(dates)):
        # Un trou de plus de quatre jours n'est pas un rendement quotidien exploitable.
        gap = (dt.date.fromisoformat(dates[i]) - dt.date.fromisoformat(dates[i - 1])).days
        if dates[i - 1] < start.isoformat() or i in breaks or gap > 4:
            continue
        a, b = converted[i - 1], converted[i]
        if a is not None and b is not None:
            out[dates[i - 1] + '/' + dates[i]] = math.log(b / a)
    return out


def correlate(a, b):
    keys = sorted(a.keys() & b.keys())
    if len(keys) < MIN_COMMON:
        return None
    x, y = [a[k] for k in keys], [b[k] for k in keys]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    vx, vy = sum((v - mx) ** 2 for v in x), sum((v - my) ** 2 for v in y)
    if vx <= 1e-15 or vy <= 1e-15:
        return None
    r = sum((u - mx) * (v - my) for u, v in zip(x, y)) / math.sqrt(vx * vy)
    return {'coefficient': round(max(-1, min(1, r)), 6), 'sessions': len(keys), 'start': keys[0].split('/')[0], 'end': keys[-1].split('/')[1]}


def exposure(meta, profile):
    """Une catégorie catalogue est une indication qualitative, pas une pondération."""
    d = profile_data(profile)
    cat = (meta.get('category') or '').casefold()
    kind = 'Énergie (actions)' if cat == 'energy' else 'Matières premières (hors actions)' if cat == 'commodities' else None
    source = 'FinanceDatabase : catégorie du fonds' if kind else None
    if meta.get('isin') == 'US91288V1035':
        kind, source = 'Pétrole (contrats à terme)', 'FinanceDatabase : description de United States 12 Month Oil Fund'
    return {'label': kind, 'source': source,
            'sectors': {k: v * number(d['stock_position']) / 100 for k, v in d['sectors'].items()} if number(d.get('stock_position')) is not None and 0 <= number(d['stock_position']) <= 100 else {}, 'sector_source': 'Yahoo Finance' if d['sectors'] else None}


def read_profiles(conn):
    with conn.cursor() as c:
        c.execute('SELECT listing_id,fetched_at,version,state,data_json FROM etf_profiles')
        return {r['listing_id']: r for r in c.fetchall()}


def decode(value):
    try:
        return json.loads(value or '{}')
    except (ValueError, TypeError):
        return {}


def coverage(conn):
    """SELECT uniquement ; dénominateurs explicites, zéro % fabriqué."""
    profiles = read_profiles(conn)
    with conn.cursor() as c:
        c.execute("SELECT l.id,l.instrument_id,l.status,l.is_primary FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='etf'")
        rows = c.fetchall()
    def count(scope):
        out = dict(listings=len(scope), instruments=len({r['instrument_id'] for r in scope}), cached=0, state_ok=0,
                   holdings=0, ten_valid_weights=0, some_valid_weights=0, sectors=0, fees=0, legacy_weight_ambiguity=0)
        for r in scope:
            p = profiles.get(r['id'])
            if not p:
                continue
            out['cached'] += 1
            out['state_ok'] += p['state'] == 'ok'
            d = profile_data(decode(p['data_json']))
            h = d['holdings']
            if p['version'] < 2:
                h = [dict(x, weight=None if x['weight'] == 0 else x['weight']) for x in h]
                d = profile_data(dict(d, holdings=h))
            out['holdings'] += bool(h)
            out['some_valid_weights'] += any(x['weight'] is not None for x in h)
            out['ten_valid_weights'] += d['top10_weight'] is not None
            out['sectors'] += bool(d['sectors'])
            out['fees'] += d['expense_ratio'] is not None
            # V1 ancien parseur : les zéros pouvaient être des valeurs absentes.
            out['legacy_weight_ambiguity'] += p['version'] < 2 and any(x['weight'] == 0 for x in h)
        return out
    return {'measured_at': dt.datetime.utcnow().isoformat(), 'all_etf_listings': count(rows),
            'selected_primary': count([r for r in rows if r['status'] == 'selected' and r['is_primary']]),
            'note': 'Compteurs indépendants, non additionnables. Cache ancien : un poids nul peut être ambigu.'}


def build(conn, now):
    """Prétraitement borné en mémoire, jamais exécuté par Explorer ou une fiche."""
    import os
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    import numpy as np
    day = now.date()
    start = six_months(day)
    with conn.cursor() as c:
        c.execute("""SELECT l.id,l.instrument_id,l.symbol,l.currency,l.mic,i.name,i.category,i.isin
                     FROM listings l JOIN instruments i ON i.id=l.instrument_id
                     WHERE i.kind='etf' AND ((l.status='selected' AND l.is_primary=1)
                     OR l.id IN (SELECT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL)) ORDER BY l.id""")
        meta = c.fetchall()
        c.execute('SELECT currency,rate_date,to_eur FROM fx_rates WHERE rate_date >= %s', (start - dt.timedelta(days=10),))
        fx = defaultdict(dict)
        for r in c.fetchall():
            fx[r['currency']][r['rate_date'].isoformat()] = float(r['to_eur'])
        c.execute("SELECT listing_id,event_date,ratio FROM corporate_events WHERE kind IN ('split','reverse_split')")
        splits = defaultdict(list)
        for r in c.fetchall():
            splits[r['listing_id']].append((r['event_date'].isoformat(), number(r['ratio'])))
    profiles = read_profiles(conn)
    vectors, payloads = [], []
    for offset in range(0, len(meta), 200):
        part = meta[offset:offset + 200]
        ids = [r['id'] for r in part]
        bars = defaultdict(list)
        with conn.cursor() as c:
            c.execute('SELECT listing_id,price_date,close_px,adj_close_px FROM daily_prices WHERE listing_id IN (' + ','.join(['%s'] * len(ids)) + ') AND price_date >= %s AND price_date <= %s ORDER BY listing_id,price_date', ids + [start - dt.timedelta(days=10), day])
            for r in c.fetchall():
                bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']), number(r['adj_close_px'])))
        for m in part:
            p = profiles.get(m['id'])
            data = profile_data(decode(p['data_json'])) if p else {}
            if p and p['version'] < 2:
                # Anciens zéros non prouvés : inconnus, jamais des absences d'exposition.
                data['holdings'] = [dict(h, weight=None if h['weight'] == 0 else h['weight']) for h in data.get('holdings', [])]
                data = profile_data(data)
            fetched = p['fetched_at'].isoformat(sep=' ') if p else None
            fresh = bool(p and p['state'] == 'ok' and (now.replace(tzinfo=None) - p['fetched_at']).days <= MAX_PROFILE_DAYS)
            e = exposure(m, data if fresh else {})
            v = returns_eur(bars.get(m['id'], []), splits[m['id']], m['currency'], fx, start, day)
            vectors.append(v)
            payloads.append(dict(meta=m, exposure=e, profile=data, profile_fetched_at=fetched,
                                 profile_state=p['state'] if p else 'none', profile_usable=fresh,
                                 composition_date=None, source='Yahoo Finance (profil mis en cache)',
                                 similar=[], observations=len(v), reason=None if len(v) >= MIN_COMMON else 'Moins de 100 rendements EUR exploitables : historique, fraîcheur ou change insuffisant.',
                                 start=start.isoformat(), end=day.isoformat(), currency='EUR', min_common=MIN_COMMON))
    keys = sorted({k for v in vectors for k in v})
    index = {k: i for i, k in enumerate(keys)}
    n = len(meta)
    x = np.zeros((n, len(keys)), dtype=np.float64)
    mask = np.zeros_like(x)
    for i, v in enumerate(vectors):
        for k, value in v.items():
            x[i, index[k]], mask[i, index[k]] = value, 1
    xx = x * x
    # Blocs 32×N : pas de matrice NxN conservée sur l'hébergement mutualisé.
    for off in range(0, n, 32):
        sl = slice(off, off + 32)
        count = mask[sl] @ mask.T
        sx, sy = x[sl] @ mask.T, mask[sl] @ x.T
        safe = np.maximum(count, 1)
        vx, vy = xx[sl] @ mask.T - sx * sx / safe, mask[sl] @ xx.T - sy * sy / safe
        den = np.sqrt(np.maximum(vx, 0) * np.maximum(vy, 0))
        valid = (count >= MIN_COMMON) & (vx > 1e-15) & (vy > 1e-15)
        cor = np.full(count.shape, -2.0)
        np.divide(x[sl] @ x.T - sx * sy / safe, den, out=cor, where=valid)
        for local, i in enumerate(range(off, min(off + 32, n))):
            # Même ISIN/instrument : autre cotation, pas un autre fonds.
            candidates = [j for j in np.argsort(-cor[local], kind='stable') if j != i and cor[local, j] >= 0.8 and meta[j]['instrument_id'] != meta[i]['instrument_id']]
            for j in candidates[:5]:
                c = correlate(vectors[i], vectors[j])
                if c:
                    payloads[i]['similar'].append(dict(c, id=meta[j]['id'], symbol=meta[j]['symbol'], name=meta[j]['name']))
    stamp = now.replace(tzinfo=None, microsecond=0)
    with conn.cursor() as c:
        c.executemany('INSERT INTO etf_analysis(listing_id,built_at,payload,returns_json) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE built_at=VALUES(built_at),payload=VALUES(payload),returns_json=VALUES(returns_json)',
                      [(m['id'], stamp, json.dumps(p, default=str, allow_nan=False), json.dumps(v, allow_nan=False)) for m, p, v in zip(meta, payloads, vectors)])
    conn.commit()
    return {'etfs': n, 'with_minimum_history': sum(len(v) >= MIN_COMMON for v in vectors), 'built_at': str(stamp)}


def load(conn, ids, with_returns=False):
    ids = list(set(ids))
    if not ids:
        return {}
    with conn.cursor() as c:
        c.execute('SELECT listing_id,built_at,payload' + (',returns_json' if with_returns else '') + ' FROM etf_analysis WHERE listing_id IN (' + ','.join(['%s'] * len(ids)) + ')', ids)
        out = {}
        for r in c.fetchall():
            p = decode(r['payload'])
            p['built_at'] = r['built_at'].isoformat(sep=' ')
            p['stale'] = (dt.datetime.utcnow() - r['built_at']).total_seconds() > 3 * 86400
            if with_returns:
                p['returns'] = decode(r['returns_json'])
            out[r['listing_id']] = p
    return out


def concentration(conn, ids):
    cached = load(conn, ids)
    labels = defaultdict(list)
    for lid in ids:
        p = cached.get(lid, {})
        label = p.get('exposure', {}).get('label')
        if label:
            labels[label].append(p['meta']['symbol'])
    return {'sample': len(ids), 'classified': sum(map(len, labels.values())),
            'alerts': [{'label': k, 'count': len(v), 'symbols': v, 'source': 'FinanceDatabase (catégorie, sans pondération supposée)'} for k, v in labels.items() if len(v) >= 3]}


def portfolio(conn, positions):
    """Valeur ACTUELLE en EUR, pas quantités ni coûts d'acquisition. Inconnu explicite."""
    items = [p for p in positions if p.get('kind') == 'etf' and p.get('listing_id')]
    cached = load(conn, [int(p['listing_id']) for p in items], True)
    unpriced = sum(number(p.get('value')) is None for p in positions)
    total = sum(max(0, number(p.get('value')) or 0) for p in positions)
    amounts, known = defaultdict(float), 0.0
    pairs, unavailable = [], 0
    for p in positions:
        value = number(p.get('value'))
        c = cached.get(int(p.get('listing_id') or 0), {})
        sectors = c.get('exposure', {}).get('sectors', {}) if not c.get('stale', True) else {}
        # Dans cette V1 les actions directes ne sont pas ventilées : restent inconnues.
        if value is not None and value > 0:
            for sector, w in sectors.items():
                amounts[sector] += value * w / 100
                known += value * w / 100
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            ca, cb = cached.get(int(a['listing_id']), {}), cached.get(int(b['listing_id']), {})
            c = None if ca.get('stale', True) or cb.get('stale', True) else correlate(ca.get('returns', {}), cb.get('returns', {}))
            if c is None:
                unavailable += 1
            elif c['coefficient'] >= STRONG:
                pairs.append(dict(c, a=a['symbol'], b=b['symbol']))
    return {'valuation_basis': 'Valeurs actuelles en EUR des positions valorisables ; pas coûts d’achat.',
            'total_priced_eur': total, 'unpriced_positions': unpriced, 'known_eur': known,
            'unknown_eur': max(0, total - known), 'unknown_percent': 100 * max(0, total - known) / total if total and not unpriced else None,
            'sectors': [{'name': k, 'value_eur': v, 'percent': 100 * v / total if total and not unpriced else None} for k, v in sorted(amounts.items(), key=lambda kv: -kv[1])],
            'similar_pairs': sorted(pairs, key=lambda x: -x['coefficient']), 'unavailable_pairs': unavailable}
