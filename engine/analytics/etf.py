"""ETF : information seulement. Aucun effet sur les scores, la sélection ni l'ordre des classements.

Similarité (méthode « hebdomadaire en euros ») : rendements logarithmiques entre deux clôtures du MÊME jour de semaine à sept jours d'écart, convertis en EUR au taux
historique de chaque date, sur les 52 dernières semaines. Chaque jour de semaine fournit une série de rendements qui NE SE CHEVAUCHENT PAS (une semaine après l'autre) :
on calcule donc cinq corrélations indépendantes de tout recouvrement artificiel (lundi, mardi, …) et on retient leur moyenne ; l'écart entre elles et la comparaison des deux
moitiés de la période servent à signaler un résultat instable. Aucune clôture n'est inventée : un rendement manque si l'une des deux dates n'a pas de clôture.
Pourquoi pas le quotidien : deux ETF du même indice cotés à Xetra et à New York ne clôturent pas à la même heure (VOO / SXR8.DE : 0,64 en quotidien, 0,89 en hebdomadaire).
"""
import datetime as dt
import json
import math
from collections import defaultdict

from .series import prepare_series
from ..shared.db import ensure

WEEKS = 52                 # fenêtre : 52 semaines calendaires
MIN_WEEKS = 40             # rendements hebdomadaires indépendants exigés dans chaque série de même jour de semaine
MIN_PARTITIONS = 3         # jours de semaine exploitables exigés (sur 5)
STRONG = 0.90              # « très proches » : seuil des familles et des alertes de portefeuille
NEAR_IDENTICAL = 0.97      # « quasi identiques »
SPREAD_LIMIT = 0.15        # écart maximal entre les cinq corrélations avant de déclarer le résultat instable
HALF_LIMIT = 0.20          # écart maximal entre la première et la seconde moitié de la période
VERSION = 2
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
    assets = number(data.get('total_assets'))
    dist = number(data.get('yield'))
    data.update(holdings=holdings, sectors=sectors, expense_ratio=fee if fee is not None and 0 <= fee <= 100 else None,
                total_assets=assets if assets is not None and assets > 0 else None, **{'yield': dist if dist is not None and 0 <= dist <= 100 else None})
    weights = [h['weight'] for h in holdings if h['weight'] is not None]
    data['top10_weight'] = round(sum(weights), 1) if len(holdings) == len(weights) == 10 and sum(weights) <= 100 else None
    data['known_holdings_weight'] = sum(weights) if weights and sum(weights) <= 100 else None
    return data


def window_start(day):
    return day - dt.timedelta(weeks=WEEKS)


def returns_eur(bars, splits, currency, fx, start, end=None):
    """Rendements hebdomadaires en EUR, clés = date de FIN (le rendement couvre les sept jours qui précèdent). Pas de remplissage : les deux dates doivent avoir une clôture
    et aucune rupture de cours ne doit se trouver entre elles. Change à la date de chaque clôture (dernier taux antérieur, 7 jours maximum), jamais le taux actuel."""
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
    px = {}
    for day, close in zip(dates, closes):
        r = rate(day)
        if r is not None:
            px[day] = close * scale * r
    out = {}
    if end and dates and dt.date.fromisoformat(dates[-1]) < end - dt.timedelta(days=7):
        return out                                                                  # série arrêtée : non comparable
    break_days = [dates[i] for i in breaks]
    for day, value in px.items():
        if day < start.isoformat():
            continue
        prev = (dt.date.fromisoformat(day) - dt.timedelta(days=7)).isoformat()
        if prev in px and not any(prev < bd <= day for bd in break_days):
            out[day] = math.log(value / px[prev])
    return out


def _pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    vx, vy = sum((v - mx) ** 2 for v in x), sum((v - my) ** 2 for v in y)
    if vx <= 1e-15 or vy <= 1e-15:
        return None
    return max(-1.0, min(1.0, sum((u - mx) * (v - my) for u, v in zip(x, y)) / math.sqrt(vx * vy)))


def correlate(a, b):
    """Corrélation hebdomadaire en EUR : moyenne de cinq corrélations, une par jour de semaine (séries sans recouvrement). None si les données ne suffisent pas.
    `weeks` = rendements indépendants dans la série la moins fournie ; `spread` = écart entre les cinq corrélations ; `halves` = corrélation de chaque moitié de la période."""
    keys = sorted(a.keys() & b.keys())
    by_day = defaultdict(list)
    for k in keys:
        by_day[dt.date.fromisoformat(k).weekday()].append(k)
    parts = {}
    for wd, ks in by_day.items():
        if len(ks) >= MIN_WEEKS:
            r = _pearson([a[k] for k in ks], [b[k] for k in ks])
            if r is not None:
                parts[wd] = (r, len(ks))
    if len(parts) < MIN_PARTITIONS:
        return None
    rs = [r for r, _ in parts.values()]
    mid = len(keys) // 2
    h1, h2 = _pearson([a[k] for k in keys[:mid]], [b[k] for k in keys[:mid]]), _pearson([a[k] for k in keys[mid:]], [b[k] for k in keys[mid:]])
    spread = max(rs) - min(rs)
    gap = abs(h1 - h2) if h1 is not None and h2 is not None else None
    start = (dt.date.fromisoformat(keys[0]) - dt.timedelta(days=7)).isoformat()
    return {'coefficient': round(sum(rs) / len(rs), 4), 'weeks': min(n for _, n in parts.values()), 'partitions': len(parts), 'spread': round(spread, 3),
            'halves': [round(h1, 3), round(h2, 3)] if gap is not None else None, 'stable': spread <= SPREAD_LIMIT and (gap is None or gap <= HALF_LIMIT),
            'start': start, 'end': keys[-1], 'method': 'weekly-eur'}


def tier(coefficient):
    """Libellé d'une corrélation (seuils fixes, voir docs/ETF_V1.md)."""
    return 'quasi identiques' if coefficient >= NEAR_IDENTICAL else 'très proches' if coefficient >= STRONG else 'proches' if coefficient >= 0.75 else 'distincts'


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
    import numpy as np
    day = now.date()
    start = window_start(day)
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
                                 similar=[], observations=len(v), reason=None if len(v) >= MIN_WEEKS * MIN_PARTITIONS else f'Moins de {MIN_WEEKS * MIN_PARTITIONS} rendements hebdomadaires en EUR exploitables : historique, fraîcheur ou change insuffisant.',
                                 start=start.isoformat(), end=day.isoformat(), currency='EUR', min_weeks=MIN_WEEKS, method='weekly-eur', method_version=VERSION))
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
        valid = (count >= MIN_WEEKS * MIN_PARTITIONS) & (vx > 1e-15) & (vy > 1e-15)
        cor = np.full(count.shape, -2.0)
        np.divide(x[sl] @ x.T - sx * sy / safe, den, out=cor, where=valid)
        for local, i in enumerate(range(off, min(off + 32, n))):
            # Même ISIN/instrument : autre cotation, pas un autre fonds.
            candidates = [j for j in np.argsort(-cor[local], kind='stable') if j != i and cor[local, j] >= 0.8 and meta[j]['instrument_id'] != meta[i]['instrument_id']]
            kept = 0
            for j in candidates[:14]:          # la matrice groupée ne sert qu'à présélectionner ; la valeur affichée est la corrélation par jour de semaine
                c = correlate(vectors[i], vectors[j])
                if c and c['coefficient'] >= 0.8:
                    payloads[i]['similar'].append(dict(c, id=meta[j]['id'], symbol=meta[j]['symbol'], name=meta[j]['name'], tier=tier(c['coefficient'])))
                    kept += 1
                    if kept == 5:
                        break
            payloads[i]['similar'].sort(key=lambda x: -x['coefficient'])
    stamp = now.replace(tzinfo=None, microsecond=0)
    ensure(conn)                               # le calcul ci-dessus n'interroge pas la base ; rien n'est encore écrit
    with conn.cursor() as c:
        c.executemany('INSERT INTO etf_analysis(listing_id,built_at,payload,returns_json) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE built_at=VALUES(built_at),payload=VALUES(payload),returns_json=VALUES(returns_json)',
                      [(m['id'], stamp, json.dumps(p, default=str, allow_nan=False), json.dumps({k: round(x_, 6) for k, x_ in v.items()}, allow_nan=False)) for m, p, v in zip(meta, payloads, vectors)])
    conn.commit()
    return {'etfs': n, 'with_minimum_history': sum(len(v) >= MIN_WEEKS * MIN_PARTITIONS for v in vectors), 'built_at': str(stamp)}


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


WARM_LIMIT = 40            # profils Yahoo récupérés au plus par passage de maintenance (jamais de collecte massive)
PROFILE_FRESH_DAYS = 30


def warm_profiles(conn, client, now, limit=WARM_LIMIT):
    """Rafraîchit, par petits lots, le profil Yahoo des ETF dont l'utilisateur a besoin : ceux qu'il détient et ceux du haut des classements de la veille (dix premiers de
    chaque profil). Un profil récent (30 jours, dernière version du lecteur) n'est jamais redemandé ; un profil indisponible n'est réessayé qu'après un jour."""
    from engine.market import etf_profile
    from engine.market.yahoo import RateLimited
    with conn.cursor() as c:
        c.execute("""SELECT l.id,l.symbol FROM listings l JOIN instruments i ON i.id=l.instrument_id
                     WHERE i.kind='etf' AND l.id IN (SELECT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL)""")
        wanted = c.fetchall()
        c.execute("""SELECT DISTINCT l.id,l.symbol FROM ranking_snapshots s JOIN listings l ON l.id=s.listing_id
                     WHERE s.grp='etf' AND s.rank_pos<=10 AND s.snap_date=(SELECT MAX(snap_date) FROM ranking_snapshots)""")
        wanted += c.fetchall()
    seen, todo = set(), []
    profiles = read_profiles(conn)
    stamp = now.replace(tzinfo=None, microsecond=0)
    for r in wanted:
        if r['id'] in seen:
            continue
        seen.add(r['id'])
        p = profiles.get(r['id'])
        age = (stamp - p['fetched_at']).days if p else None
        if p is None or p['version'] < etf_profile.VERSION or (p['state'] == 'ok' and age >= PROFILE_FRESH_DAYS) or (p['state'] != 'ok' and age >= 1):
            todo.append(r)
    done = unavailable = 0
    for r in todo[:limit]:
        try:
            data, state = etf_profile.fetch_profile(client.transport, r['symbol']), 'ok'
            if data is None:
                state = 'unavailable'
        except RateLimited:
            break
        except Exception:                                                              # noqa: BLE001 : réponse absente ou illisible : réessai plus tard
            continue
        if state == 'ok' or r['id'] not in profiles:
            with conn.cursor() as c:
                c.execute("""INSERT INTO etf_profiles(listing_id,fetched_at,version,state,data_json) VALUES (%s,%s,%s,%s,%s)
                             ON DUPLICATE KEY UPDATE fetched_at=VALUES(fetched_at), version=VALUES(version), state=VALUES(state), data_json=VALUES(data_json)""",
                          (r['id'], stamp, etf_profile.VERSION, state, json.dumps(data or {})))
            conn.commit()
        done += state == 'ok'
        unavailable += state != 'ok'
    return {'wanted': len(seen), 'to_refresh': len(todo), 'fetched': done, 'unavailable': unavailable, 'limit': limit}


def families(items, cached, threshold=STRONG):
    """Regroupe des ETF qui évoluent presque comme un seul (corrélation hebdomadaire >= seuil, lien direct ou en chaîne). items : [{'listing_id', 'symbol'}] ;
    cached : etf.load(..., True). Renvoie (groupes de 2 ETF ou plus, paires évaluées, nombre de paires non comparables)."""
    ids = [int(x['listing_id']) for x in items]
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    links, unavailable = [], 0
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            ca, cb = cached.get(a, {}), cached.get(b, {})
            c = None if ca.get('stale', True) or cb.get('stale', True) else correlate(ca.get('returns', {}), cb.get('returns', {}))
            if c is None:
                unavailable += 1
            elif c['coefficient'] >= threshold:
                parent[find(a)] = find(b)
                links.append((a, b, c))
    members = defaultdict(list)
    for i in ids:
        members[find(i)].append(i)
    out = []
    for root, ms in members.items():
        if len(ms) < 2:
            continue
        mine = [(a, b, c) for a, b, c in links if find(a) == root]
        out.append({'members': ms, 'min_coefficient': min(c['coefficient'] for _, _, c in mine), 'unstable': any(not c['stable'] for _, _, c in mine),
                    'links': [{'a': a, 'b': b, 'coefficient': c['coefficient'], 'stable': c['stable']} for a, b, c in mine]})
    return sorted(out, key=lambda g: -len(g['members'])), unavailable


def concentration(conn, ids):
    """Familles d'ETF qui évoluent presque comme un seul parmi `ids` (les dix premiers ETF d'une vue). Trois ETF ou plus dans une même famille déclenchent l'information.
    La catégorie FinanceDatabase ne sert qu'à NOMMER la famille ; le regroupement, lui, repose sur la corrélation observée."""
    cached = load(conn, ids, True)
    items = [{'listing_id': i, 'symbol': cached.get(i, {}).get('meta', {}).get('symbol')} for i in ids]
    fams, unavailable = families(items, cached)
    groups = []
    for n, g in enumerate(fams):
        if len(g['members']) < 3:
            continue
        labels = defaultdict(int)
        for i in g['members']:
            lab = cached[i].get('exposure', {}).get('label') or cached[i].get('meta', {}).get('category')
            if lab:
                labels[lab] += 1
        names = [k for k, _ in sorted(labels.items(), key=lambda kv: -kv[1])][:2]
        groups.append({'id': chr(65 + len(groups)), 'size': len(g['members']), 'members': g['members'], 'symbols': [cached[i]['meta']['symbol'] for i in g['members']],
                       'label': ' · '.join(names) if names else None, 'min_coefficient': g['min_coefficient'], 'unstable': g['unstable'],
                       'basis': 'Corrélation des rendements hebdomadaires en EUR >= %s (52 semaines)' % STRONG})
    return {'sample': len(ids), 'analysed': sum(1 for i in ids if i in cached and not cached[i].get('stale', True) and cached[i].get('returns')), 'groups': groups,
            'unavailable_pairs': unavailable, 'note': 'Information seulement : ni les scores ni l\'ordre ne changent. Corrélation des rendements ne signifie pas participations communes.'}


def holdings_overlap(a, b):
    """Chevauchement PARTIEL des principales lignes connues (poids de A et de B valides, mêmes titres). Borne basse : le reste des fonds n'est pas comparé.
    Renvoie None si l'un des deux n'a pas au moins cinq lignes pondérées."""
    def known(p):
        return {(h.get('symbol') or h.get('name') or '').strip().upper(): (h.get('name') or h.get('symbol'), h['weight'])
                for h in (p or {}).get('holdings', []) if h.get('weight') is not None and (h.get('symbol') or h.get('name'))}
    ka, kb = known(a), known(b)
    if len(ka) < 5 or len(kb) < 5:
        return None
    shared = [(ka[k][0], ka[k][1], kb[k][1]) for k in ka if k in kb]
    return {'shared_weight': round(sum(min(wa, wb) for _, wa, wb in shared), 1), 'shared': [{'name': n, 'a': wa, 'b': wb} for n, wa, wb in sorted(shared, key=lambda x: -min(x[1], x[2]))[:6]],
            'known_a': round(sum(w for _, w in ka.values()), 1), 'known_b': round(sum(w for _, w in kb.values()), 1)}


def _chain(a, b):
    """Plus longue suite de semaines CONSÉCUTIVES communes pour un même jour de semaine (somme des rendements = rendement cumulé sans trou). Renvoie (clés, jour)."""
    best = ([], None)
    keys = sorted(a.keys() & b.keys())
    for wd in range(5):
        ks = [k for k in keys if dt.date.fromisoformat(k).weekday() == wd]
        run = []
        for k in ks:
            if run and (dt.date.fromisoformat(k) - dt.date.fromisoformat(run[-1])).days != 7:
                if len(run) > len(best[0]):
                    best = (run, wd)
                run = []
            run.append(k)
        if len(run) > len(best[0]):
            best = (run, wd)
    return best


def compare(conn, lid, limit=4):
    """Aide à départager des ETF presque identiques : frais, liquidité, place, devise, émetteur, actifs, distribution, écart de performance observé (EUR, prix, même période),
    principales lignes communes. Aucune recommandation ; les valeurs inconnues restent inconnues."""
    cached = load(conn, [lid], True)
    me = cached.get(lid)
    if not me:
        return None
    sim = [s for s in me.get('similar', []) if s['coefficient'] >= STRONG][:limit] or me.get('similar', [])[:3]
    other = load(conn, [s['id'] for s in sim], True)
    ids = [lid] + [s['id'] for s in sim]
    with conn.cursor() as c:
        c.execute('SELECT l.id,l.mic,l.currency,p.price,p.currency pcur,p.avg_volume_3m FROM listings l LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.id IN (' + ','.join(['%s'] * len(ids)) + ')', ids)
        info = {r['id']: r for r in c.fetchall()}
        c.execute('SELECT currency,to_eur FROM fx_rates f WHERE rate_date=(SELECT MAX(rate_date) FROM fx_rates WHERE currency=f.currency)')
        rates = {r['currency']: float(r['to_eur']) for r in c.fetchall()}
    from engine.market.collect import to_eur_factor

    def row(i, p, sim_info=None):
        d, r = (p or {}).get('profile') or {}, info.get(i) or {}
        f = to_eur_factor(r.get('pcur') or r.get('currency'), rates)
        liq = float(r['price']) * r['avg_volume_3m'] * f if r.get('price') is not None and r.get('avg_volume_3m') and f else None
        return {'id': i, 'symbol': (p or {}).get('meta', {}).get('symbol'), 'name': (p or {}).get('meta', {}).get('name'), 'mic': r.get('mic'), 'currency': r.get('pcur') or r.get('currency'),
                'family': d.get('family'), 'expense_ratio': d.get('expense_ratio'), 'liquidity_eur_day': liq, 'total_assets': d.get('total_assets'), 'yield': d.get('yield'),
                'profile_known': bool(d), 'coefficient': (sim_info or {}).get('coefficient'), 'stable': (sim_info or {}).get('stable')}
    rows = [row(lid, me)] + [row(s['id'], other.get(s['id']), s) for s in sim]
    base = me.get('returns', {})
    for r in rows[1:]:
        o = other.get(r['id'], {})
        chain, wd = _chain(base, o.get('returns', {}))
        r['gap_weeks'] = len(chain) if len(chain) >= MIN_WEEKS else None
        r['gap_log'] = round(sum(base[k] for k in chain) - sum(o['returns'][k] for k in chain), 4) if len(chain) >= MIN_WEEKS else None
        r['gap_period'] = [(dt.date.fromisoformat(chain[0]) - dt.timedelta(days=7)).isoformat(), chain[-1]] if len(chain) >= MIN_WEEKS else None
        r['overlap'] = holdings_overlap(me.get('profile'), o.get('profile'))
    return {'rows': rows, 'note': 'Écart = rendement de A moins rendement de l\'ETF affiché, en EUR, sur les semaines consécutives communes ; cours hors dividendes.'}


def portfolio(conn, positions):
    """Valeur ACTUELLE en EUR, pas quantités ni coûts d'acquisition. Inconnu explicite. Familles d'ETF presque identiques pesées en valeur."""
    from . import signals
    items = [p for p in positions if p.get('kind') == 'etf' and p.get('listing_id')]
    cached = load(conn, [int(p['listing_id']) for p in items], True)
    unpriced = sum(number(p.get('value')) is None for p in positions)
    total = sum(max(0, number(p.get('value')) or 0) for p in positions)
    complete = bool(total) and not unpriced
    amounts, known = defaultdict(float), 0.0
    no_profile = []
    for p in positions:
        value = number(p.get('value'))
        c = cached.get(int(p.get('listing_id') or 0), {})
        usable = c.get('profile_usable') and not c.get('stale', True)
        sectors = c.get('exposure', {}).get('sectors', {}) if usable else {}
        if p.get('kind') == 'etf' and not sectors and value:
            no_profile.append({'symbol': p.get('symbol'), 'value_eur': value})
        # Dans cette V1 les actions directes ne sont pas ventilées : restent inconnues.
        if value is not None and value > 0:
            for sector, w in sectors.items():
                amounts[sector] += value * w / 100
                known += value * w / 100
    ids = {int(p['listing_id']): p for p in items}
    fams, unavailable = families(items, cached)
    family_rows, pairs = [], []
    for g in fams:
        value = sum(number(ids[i].get('value')) or 0 for i in g['members'])
        family_rows.append({'symbols': [ids[i]['symbol'] for i in g['members']], 'value_eur': value, 'percent': 100 * value / total if complete else None,
                            'min_coefficient': g['min_coefficient'], 'unstable': g['unstable']})
        pairs += [dict(l, a=ids[l['a']]['symbol'], b=ids[l['b']]['symbol']) for l in g['links']]
    unknown_eur = max(0, total - known)
    unknown_percent = 100 * unknown_eur / total if complete else None
    sig = [signals.unknown_share(unknown_percent)]
    if family_rows:
        sig.insert(0, signals.family_share(max((f['percent'] for f in family_rows if f['percent'] is not None), default=None) if complete else None))
    return {'valuation_basis': 'Valeurs actuelles en EUR des positions valorisables ; pas coûts d’achat.',
            'total_priced_eur': total, 'unpriced_positions': unpriced, 'known_eur': known,
            'unknown_eur': unknown_eur, 'unknown_percent': unknown_percent,
            'sectors': [{'name': k, 'value_eur': v, 'percent': 100 * v / total if complete else None} for k, v in sorted(amounts.items(), key=lambda kv: -kv[1])],
            'families': family_rows, 'etf_count': len(items), 'etf_without_composition': no_profile, 'signals': sig,
            'similar_pairs': sorted(pairs, key=lambda x: -x['coefficient']), 'unavailable_pairs': unavailable}
