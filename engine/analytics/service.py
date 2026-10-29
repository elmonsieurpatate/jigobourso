"""Services de lecture pour le site : Explorer et fiche d'un titre. Entrée/sortie JSON (voir engine.cli).

L'univers évalué est v_recommendable. La recherche explicite d'un titre (nom, symbole, ISIN) peut aussi renvoyer des titres exclus,
toujours étiquetés « exclu » avec leur motif : ils ne reçoivent ni rang ni verdict de stratégie.
"""
import datetime
import hashlib
import json
import re
from collections import defaultdict

from engine.catalogue.rules import MARKETS, is_leveraged_name
from engine.market import hours
from engine.market.collect import effective_expected_close, latest_rates, to_eur_factor
from . import strategy
from .measures import window_metrics
from .series import usable_closes, find_breaks, clean_window, analyze_series, prepare_series, data_corrections

# PEA : actions d'une société dont le siège est dans l'UE ou l'EEE (Islande, Liechtenstein et Norvège compris ; pas le Royaume-Uni ni la Suisse),
# achetées sur une place européenne (c'est ce que les courtiers acceptent dans un PEA). Une action américaine d'une société irlandaise n'est donc
# pas « PEA probable ». Les ETF dépendent de leur indice et de leur domicile : toujours « à vérifier ».
PEA_COUNTRIES = {'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece',
                 'Hungary', 'Iceland', 'Ireland', 'Italy', 'Latvia', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta', 'Netherlands', 'Norway', 'Poland',
                 'Portugal', 'Romania', 'Slovakia', 'Slovenia', 'Spain', 'Sweden'}
PEA_MICS = {'XPAR', 'XAMS', 'XBRU', 'XLIS', 'XETR', 'XFRA', 'XSTU', 'XBER', 'XDUS', 'XHAM', 'XMUN', 'XHAN', 'XMIL', 'XMAD', 'XSTO', 'XOSL', 'XHEL', 'XCSE',
            'XWBO', 'XDUB', 'XATH', 'XWAR', 'XPRA', 'XBUD', 'XBSE', 'XICE', 'XLUX'}


def pea_status(kind, country, mic):
    """'probable' (action d'un pays éligible cotée en Europe) | 'a_verifier' (ETF) | 'non'."""
    if kind == 'etf':
        return 'a_verifier'
    return 'probable' if country in PEA_COUNTRIES and mic in PEA_MICS else 'non'


def last_collection(conn, mic):
    """Fin de la dernière collecte de 15 minutes réussie de la place (UTC naïf), ou None : c'est elle qui dit si NOS données sont à jour pendant la séance."""
    now = hours.utcnow()
    memo = conn.__dict__.setdefault('_jigo_collected', {})
    key = (mic, now.replace(second=0, microsecond=0))
    if key not in memo:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(finished_at) f FROM jobs WHERE job_type=%s AND status IN ('completed','completed_with_errors')", ('intraday:' + mic,))
            memo[key] = cur.fetchone()['f']
    return memo[key]


def expected_close(conn, mic):
    """Dernière clôture due pour la place, jours fériés déduits des données (mémorisée par connexion et par minute)."""
    now = hours.utcnow()
    memo = conn.__dict__.setdefault('_jigo_expected', {})
    key = (mic, now.replace(second=0, microsecond=0))
    if key not in memo:
        memo[key] = effective_expected_close(conn, mic, now)
    return memo[key]


STATUS_LABELS = {'retained': 'Retenu', 'rejected': 'Écarté', 'unknown': 'Non évaluable', 'excluded': 'Exclu'}
REF_FIELDS = ('slope', 'r2', 'perf', 'volatility', 'drawdown')
EXPORT_LIMIT = 20000


def _config(request):
    cfg = request.get('config')
    if isinstance(cfg, str) or cfg is None:
        cfg = strategy.preset(cfg or 'regular')
    return strategy.validate(cfg)


def _load_universe(conn, windows, ids=None):
    only = f' WHERE l.id IN ({",".join(["%s"] * len(ids))})' if ids else ''
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.symbol, l.mic, l.currency, i.name, i.isin, i.kind, i.country, i.category,
                              p.price, p.price_time, p.source AS price_source, p.currency AS price_currency, p.avg_volume_3m,
                              s.last_close_date, s.closes_count, s.close_px, s.ma20, s.ma50, s.ma50_prev, s.daily_change, s.gap_to_ma20, s.quality, s.break_dates
                       FROM v_recommendable r JOIN listings l ON l.id=r.listing_id JOIN instruments i ON i.id=l.instrument_id
                       LEFT JOIN latest_prices p ON p.listing_id=l.id LEFT JOIN series_state s ON s.listing_id=l.id""" + only, list(ids or []))
        universe = cur.fetchall()
        marks = ','.join(['%s'] * len(windows))
        scope = f' AND listing_id IN ({",".join(["%s"] * len(ids))})' if ids else ''
        cur.execute(f'SELECT listing_id, sessions, slope, slope_log, r2, perf, volatility, drawdown, er FROM strategy_metrics WHERE sessions IN ({marks})' + scope, list(windows) + list(ids or []))
        stored = defaultdict(dict)
        for r in cur.fetchall():
            stored[r['listing_id']][r['sessions']] = {k: (None if v is None else float(v)) for k, v in r.items() if k not in ('listing_id',)}
        cur.execute('SELECT mic, MAX(last_close_date) d FROM series_state s JOIN listings l ON l.id=s.listing_id GROUP BY mic')
        latest_by_mic = {r['mic']: r['d'] for r in cur.fetchall()}
    return universe, stored, latest_by_mic


def _live_measures(conn, ids, windows):
    """Mesures des fenêtres absentes de strategy_metrics, calculées depuis les clôtures (chemin lent, fenêtres non standard)."""
    out = defaultdict(dict)
    if not ids or not windows:
        return out
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            cur.execute(f"SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) ORDER BY listing_id, price_date", part)
            bars = defaultdict(list)
            for r in cur.fetchall():
                bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
            cur.execute(f"SELECT listing_id, event_date, ratio FROM corporate_events WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND kind IN ('split','reverse_split')", part)
            splits = defaultdict(list)
            for r in cur.fetchall():
                splits[r['listing_id']].append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
            for lid, rows in bars.items():
                _, _, _, _, measured, _, _ = analyze_series(rows, windows, splits[lid])
                out[lid].update({n: m for n, m in measured.items() if m is not None})
    return out


def judge_universe(conn, config, ids=None):
    """Verdicts de l'univers recommandable (ou d'un sous-ensemble `ids` : rang et score n'y ont alors pas de sens)."""
    windows = strategy.required_sessions(config)
    universe, stored, latest_by_mic = _load_universe(conn, windows, ids)
    absent = sorted({n for n in windows for u in universe if n not in stored.get(u['id'], {})})
    live = _live_measures(conn, [u['id'] for u in universe if any(n not in stored.get(u['id'], {}) for n in windows)], absent) if absent else {}
    verdicts = []
    for u in universe:
        measures = {n: stored.get(u['id'], {}).get(n) or live.get(u['id'], {}).get(n) for n in windows}
        count = u['closes_count'] or 0
        missing = {n: ('history' if count < n + 1 else 'break') for n, m in measures.items() if m is None}
        tech = {k: (None if u[k] is None else float(u[k])) for k in ('close_px', 'ma20', 'ma50', 'ma50_prev', 'daily_change', 'gap_to_ma20')}
        tech['close'] = tech.pop('close_px')
        last = u['last_close_date'].isoformat() if u['last_close_date'] else None
        expected = max(expected_close(conn, u['mic']), str(latest_by_mic.get(u['mic']) or ''))
        if last and last < expected:
            u['quality'] = 'stale'
        v = strategy.judge(config, measures, tech, missing, last, expected or None)
        v.update(key=u['id'], group='etf' if u['kind'] == 'etf' else 'equity', symbol=u['symbol'], row=u)
        verdicts.append(v)
    return strategy.rank(config, verdicts)


def _row(v, rates, conn=None):
    u = v['row']
    cur = u['price_currency'] or u['currency']
    factor = to_eur_factor(cur, rates)
    price = float(u['price']) if u['price'] is not None else None
    return {'id': u['id'], 'symbol': u['symbol'], 'name': u['name'], 'isin': u['isin'], 'mic': u['mic'], 'market': MARKETS.get(u['mic'], u['mic']),
            'kind': u['kind'], 'category': u['category'], 'country': u['country'], 'pea': pea_status(u['kind'], u['country'], u['mic']) == 'probable',
            'currency': cur, 'price': price, 'price_eur': price * factor if price is not None and factor else None,
            'price_time': u['price_time'].isoformat(sep=' ') if u['price_time'] else None, 'price_source': u['price_source'],
            'status': v['status'], 'status_label': STATUS_LABELS[v['status']], 'score': v['score'], 'rank': v['rank'],
            'quality': u['quality'], 'price_stale': hours.price_is_stale(u['mic'], u['price_time'], hours.utcnow(), expected_close(conn, u['mic']) if conn is not None else None, last_collection(conn, u['mic']) if conn is not None else None), 'measures': {str(n): m for n, m in v['measures'].items()}, 'reasons': v['reasons']}


CACHE_FORMAT = 3
MAX_NEW_CONFIGS_PER_HOUR = 60       # calculs d'univers complets (réglages jamais vus ou données changées) acceptés par heure, tous utilisateurs confondus
ENTRY_FIELDS = ('id', 'symbol', 'name', 'isin', 'kind', 'mic', 'country', 'status', 'group', 'rank', 'score', 'category', 'fails')


def _fails(v):
    """Critères non satisfaits ou non mesurables d'un verdict : 'période|critère|f' (échec) ou '|m' (mesure absente)."""
    return [f"{r['period'] or ''}|{r['criterion']}|{r['result'][0]}" for r in v['reasons'] if r['result'] in ('fail', 'missing')]


def data_version(conn):
    """Change quand une donnée qui influence les verdicts change : calcul nocturne, jeu recommandable, traitement terminé."""
    with conn.cursor() as cur:
        cur.execute('SELECT MAX(s.computed_at) t, COUNT(*) n FROM series_state s JOIN v_recommendable r ON r.listing_id = s.listing_id')
        a = cur.fetchone()
        cur.execute("SELECT COALESCE(MAX(id), 0) j FROM jobs WHERE job_type NOT LIKE 'intraday%' AND status IN ('completed', 'completed_with_errors')")
        j = cur.fetchone()['j']
    clock = hashlib.sha1(','.join(hours.expected_last_close(m, hours.utcnow()) for m in sorted(hours.HOURS)).encode()).hexdigest()[:12]
    return f"{clock}.{CACHE_FORMAT}.{strategy.VERSION}|{a['t']}|{a['n']}|{j}"


def cached_verdicts(conn, config):
    """Verdicts légers (identité, statut, groupe, rang, score) de tout l'univers pour cette configuration, mis en cache en base."""
    key = hashlib.sha1(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    version = data_version(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT data_version, payload FROM result_cache WHERE cache_key=%s', (key,))
        hit = cur.fetchone()
    if hit and hit['data_version'] == version:
        return [dict(zip(ENTRY_FIELDS, e)) for e in json.loads(hit['payload'])]
    with conn.cursor() as cur:        # garde-fou : chaque configuration inédite évalue tout l'univers ; on borne le nombre de calculs par heure pour protéger la base partagée
        cur.execute("SELECT COUNT(*) n FROM result_cache WHERE built_at > %s AND data_version <> 'intraday-fetch'", (datetime.datetime.utcnow() - datetime.timedelta(hours=1),))
        if cur.fetchone()['n'] >= MAX_NEW_CONFIGS_PER_HOUR:
            raise ValueError('Trop de réglages différents ont été calculés depuis une heure : réessayez un peu plus tard, ou utilisez un des quatre profils de départ.')
    entries = [[v['key'], v['symbol'], v['row']['name'], v['row']['isin'], v['row']['kind'], v['row']['mic'], v['row']['country'], v['status'], v['group'], v['rank'],
                None if v['score'] is None else round(v['score'], 4), v['row']['category'], _fails(v)] for v in judge_universe(conn, config)]
    with conn.cursor() as cur:
        cur.execute('REPLACE INTO result_cache(cache_key, data_version, built_at, payload) VALUES (%s,%s,%s,%s)',
                    (key, version, datetime.datetime.utcnow().replace(microsecond=0), json.dumps(entries, ensure_ascii=False, separators=(',', ':'))))
        cur.execute('DELETE FROM result_cache WHERE built_at < %s', (datetime.datetime.utcnow() - datetime.timedelta(days=3),))
    conn.commit()
    return [dict(zip(ENTRY_FIELDS, e)) for e in entries]


def _aux(conn, ref, rates):
    """Données de filtre et de tri pour tout l'univers : prix, volume, fraîcheur et mesures de la fenêtre de référence `ref`."""
    with conn.cursor() as cur:
        cur.execute("""SELECT p.listing_id id, p.price, COALESCE(p.currency, l.currency) cur, p.avg_volume_3m volume, l.mic, s.last_close_date, s.quality
                       FROM latest_prices p JOIN listings l ON l.id=p.listing_id LEFT JOIN series_state s ON s.listing_id=l.id""")
        out = {}
        for r in cur.fetchall():
            price = None if r['price'] is None else float(r['price'])
            f = to_eur_factor(r['cur'], rates)
            out[r['id']] = {'price': price, 'price_eur': price * f if price is not None and f else None, 'volume': r['volume'],
                            'last_close': r['last_close_date'], 'quality': 'stale' if r['last_close_date'] and str(r['last_close_date']) < expected_close(conn, r['mic']) else r['quality']}
        cur.execute('SELECT listing_id, slope, r2, perf, volatility, drawdown FROM strategy_metrics WHERE sessions=%s', (ref,))
        for r in cur.fetchall():
            if r['listing_id'] in out:
                out[r['listing_id']].update({k: None if r[k] is None else float(r[k]) for k in REF_FIELDS})
    return out


def _reference_window(config, stored=(1, 5, 21, 63, 126, 252)):
    """Fenêtre servant aux filtres et tris de colonnes : la plus longue période active, ramenée à une fenêtre précalculée."""
    longest = max(p['sessions'] for p in config['periods'] if p['enabled'])
    return min(stored, key=lambda n: (abs(n - longest), n))


SORT_KEYS = {'name': lambda e, a: (e['name'] or '').casefold(), 'symbol': lambda e, a: e['symbol'].casefold(), 'score': lambda e, a: e['score'],
             'price': lambda e, a: a.get('price_eur'), 'volume': lambda e, a: a.get('volume'), 'fresh': lambda e, a: a.get('last_close') and a['last_close'].toordinal(),
             'slope': lambda e, a: a.get('slope'), 'r2': lambda e, a: a.get('r2'), 'perf': lambda e, a: a.get('perf'),
             'volatility': lambda e, a: a.get('volatility'), 'drawdown': lambda e, a: a.get('drawdown')}


def _num(view, key):
    v = view.get(key)
    return None if v in (None, '') else float(v)


def scoped_entries(conn, config, view, rates=None, aux=None, now=None):
    """Étapes 1 à 3 de la recherche : univers complet des titres éligibles → filtres de l'utilisateur → évaluation et classement DANS cette sélection.
    Renvoie (entrées de l'univers, entrées examinées avec statut, rang et score recalculés dans la sélection, fenêtre de référence, données de filtre).
    Rang et score sont des percentiles parmi les titres retenus de la sélection (par groupe action / ETF) : changer les filtres change le classement."""
    rates = rates if rates is not None else latest_rates(conn)
    now = now or hours.utcnow()
    entries = cached_verdicts(conn, config)         # verdict de chaque titre éligible pour CETTE configuration (jamais pour un préréglage par défaut)
    ref = _reference_window(config)
    aux = aux if aux is not None else _aux(conn, ref, rates)
    kind, market, country = view.get('kind') or '', view.get('market') or '', view.get('country') or ''
    category = (view.get('category') or '').casefold()
    owned = set(view.get('owned_ids') or [])
    base = [e for e in entries if (not kind or e['kind'] == kind) and (not market or e['mic'] == market)
            and (not country or e['country'] == country) and (not category or category in (e['category'] or '').casefold())]
    if view.get('pea'):
        base = [e for e in base if pea_status(e['kind'], e['country'], e['mic']) == 'probable']
    if view.get('owned_only'):
        base = [e for e in base if e['id'] in owned]
    if view.get('open_now'):
        base = [e for e in base if e['mic'] in hours.HOURS and hours.is_open(e['mic'], now)]
    budget, min_price, max_price, max_vol, max_dd, min_volume = (_num(view, k) for k in ('budget', 'min_price', 'max_price', 'max_volatility', 'max_drawdown', 'min_volume'))

    def keep(e):
        a = aux.get(e['id'], {})
        price = a.get('price_eur')
        if (budget is not None and (price is None or price > budget)) or (min_price is not None and (price is None or price < min_price)) or (max_price is not None and (price is None or price > max_price)):
            return False
        if max_vol is not None and (a.get('volatility') is None or a['volatility'] > max_vol):
            return False
        if max_dd is not None and (a.get('drawdown') is None or a['drawdown'] > max_dd):
            return False
        if min_volume is not None and (a.get('volume') is None or a['volume'] < min_volume):
            return False
        return not (view.get('fresh_only') and a.get('quality') != 'ok')
    base = [e for e in base if keep(e)]
    if len(base) != len(entries):                   # sélection plus étroite que l'univers : on reclasse les retenus entre eux
        retained = [e['id'] for e in base if e['status'] == 'retained']
        ranked = {v['key']: v for v in judge_universe(conn, config, retained)} if retained else {}
        out = []
        for e in base:
            v = ranked.get(e['id'])
            out.append(dict(e, rank=v['rank'] if v else None, score=None if not v or v['score'] is None else round(v['score'], 4)))
        base = out
    return entries, base, ref, aux


def explore(conn, request):
    config = _config(request)
    view = request.get('view') or {}
    export = bool(view.get('export'))
    page, size = max(1, int(view.get('page', 1))), min(100, max(1, int(view.get('page_size', 24))))
    status = view.get('status', 'retained')
    query = (view.get('q') or '').strip().casefold()[:100]
    rates = latest_rates(conn)
    now = hours.utcnow()
    entries, base, ref, aux = scoped_entries(conn, config, view, rates, None, now)
    kind, market = view.get('kind') or '', view.get('market') or ''
    min_score = _num(view, 'min_score')
    if min_score is not None:
        base = [e for e in base if e['score'] is not None and e['score'] >= min_score]

    counts = {g: defaultdict(int) for g in ('equity', 'etf')}
    for e in entries:
        counts[e['group']][e['status']] += 1
    scope_counts = {k: sum(1 for e in base if e['status'] == k) for k in ('retained', 'rejected', 'unknown')}

    rows = base
    excluded_hits = []
    if query:
        rows = [e for e in rows if query in (e['name'] or '').casefold() or query in e['symbol'].casefold() or query in (e['isin'] or '').casefold()]
        excluded_hits = _search_excluded(conn, query, kind, market)
    elif status != 'all':
        rows = [e for e in rows if e['status'] == status]
    sort, desc = view.get('sort', 'rank'), view.get('dir') == 'desc'
    if sort in SORT_KEYS:
        key = SORT_KEYS[sort]
        have = [e for e in rows if key(e, aux.get(e['id'], {})) is not None]
        none = [e for e in rows if key(e, aux.get(e['id'], {})) is None]
        have.sort(key=lambda e: (key(e, aux.get(e['id'], {})), e['symbol']), reverse=desc)
        rows = have + none
    else:   # rang : retenus par rang, puis écartés, puis non évaluables ; actions avant ETF
        order = {'retained': 0, 'rejected': 1, 'unknown': 2}
        rows.sort(key=lambda e: (order[e['status']], e['group'] == 'etf', e['rank'] or 10 ** 9, e['symbol']), reverse=desc)
    total = len(rows) + len(excluded_hits)
    if export:
        size, page = EXPORT_LIMIT, 1
    page_rows = (rows + excluded_hits)[(page - 1) * size:page * size]      # pagination : uniquement après filtrage, évaluation et classement
    wanted = [e['id'] for e in page_rows if e not in excluded_hits]
    detail = {v['key']: v for v in judge_universe(conn, config, wanted)} if wanted else {}
    out = []
    for e in page_rows:
        if e in excluded_hits:
            out.append(e)
            continue
        v = detail[e['id']]
        v['rank'], v['score'] = e['rank'], e['score']      # rang et score viennent de la sélection complète, pas de la page
        r = _row(v, rates, conn)
        a = aux.get(e['id'], {})
        r.update({'volume': a.get('volume'), 'last_close': a['last_close'].isoformat() if a.get('last_close') else None,
                  'ref': {k: a.get(k) for k in REF_FIELDS}, 'open': e['mic'] in hours.HOURS and hours.is_open(e['mic'], now)})
        out.append(r)
    if not export:
        _attach_curves(conn, out)
    reasons = defaultdict(int)
    for e in base:
        if e['status'] != 'retained':
            for f in e['fails']:
                reasons[f] += 1
    markets, countries = defaultdict(int), defaultdict(int)
    for e in entries:
        markets[e['mic']] += 1
        if e['country']:
            countries[e['country']] += 1
    return {'config': config, 'total': total, 'page': page, 'pages': max(1, -(-total // size)), 'rows': out, 'ref_sessions': ref,
            'universe': len(entries), 'examined': len(base),
            'counts': {g: dict(c) for g, c in counts.items()}, 'scope_counts': scope_counts, 'populations': {g: sum(c.values()) for g, c in counts.items()},
            'reasons': dict(reasons), 'facets': {'markets': dict(markets), 'countries': dict(sorted(countries.items()))}}


def _search_excluded(conn, query, kind, market):
    """Cotations exclues correspondant à une recherche : étiquetées, avec leur motif, sans verdict de stratégie."""
    like = '%' + query.replace('%', '') + '%'
    sql = """SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, i.name, i.isin, i.kind, i.country, i.category, p.price, p.price_time, p.source AS price_source, p.currency AS price_currency
             FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id
             WHERE (l.status='excluded' OR (l.status='candidate' AND l.is_primary=1)) AND (LOWER(i.name) LIKE %s OR LOWER(l.symbol) LIKE %s OR LOWER(i.isin) LIKE %s)"""
    args = [like, like, like]
    if kind:
        sql += ' AND i.kind=%s'; args.append(kind)
    if market:
        sql += ' AND l.mic=%s'; args.append(market)
    with conn.cursor() as cur:
        cur.execute(sql + ' ORDER BY i.name, l.id', args)
        rows = cur.fetchall()
    return [{'id': r['id'], 'symbol': r['symbol'], 'name': r['name'], 'isin': r['isin'], 'mic': r['mic'], 'market': MARKETS.get(r['mic'], r['mic']), 'kind': r['kind'],
             'category': r['category'], 'country': r['country'], 'pea': False, 'currency': r['price_currency'] or r['currency'],
             'price': float(r['price']) if r['price'] is not None else None, 'price_eur': None, 'price_time': r['price_time'].isoformat(sep=' ') if r['price_time'] else None,
             'price_source': r['price_source'], 'status': 'excluded' if r['status'] == 'excluded' else 'unknown',
             'status_label': 'Exclu' if r['status'] == 'excluded' else 'En attente d’analyse', 'excluded_reason': r['excluded_reason'], 'score': None, 'rank': None,
             'quality': None, 'measures': {}, 'reasons': []} for r in rows]


def _attach_curves(conn, rows, points=66):
    ids = [r['id'] for r in rows]
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute(f"SELECT listing_id, price_date, close_px FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(ids))}) AND price_date >= %s ORDER BY listing_id, price_date",
                    ids + [datetime.date.today() - datetime.timedelta(days=110)])
        curves = defaultdict(list)
        for r in cur.fetchall():
            curves[r['listing_id']].append(float(r['close_px']))
    for r in rows:
        r['curve'] = curves.get(r['id'], [])[-points:]


def instrument_sheet(conn, request):
    """Fiche complète d'une cotation : identité, prix, verdict détaillé (toutes périodes, même inactives), séries, qualité."""
    config = _config(request)
    lid = int(request['listing_id'])
    rates = latest_rates(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, l.primary_reason, i.id AS instrument_id, i.name, i.isin, i.kind, i.country, i.category,
                              p.price, p.price_time, p.source AS price_source, p.currency AS price_currency, p.avg_volume_3m, p.market_cap
                       FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.id=%s""", (lid,))
        u = cur.fetchone()
        if not u:
            return {'error': 'Titre introuvable'}
        cur.execute('SELECT price_date, close_px, adj_close_px, volume FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        rows = cur.fetchall()
        daily = [[r['price_date'].isoformat(), float(r['close_px'])] for r in rows]
        daily_volume = [None if r['volume'] is None else int(r['volume']) for r in rows]
        cur.execute("""SELECT l.id, l.mic, l.symbol, l.currency, l.status, l.is_primary FROM listings l WHERE l.instrument_id=%s AND l.id<>%s ORDER BY l.is_primary DESC, l.mic""", (u['instrument_id'], lid))
        siblings = cur.fetchall()
        cur.execute('SELECT quality, closes_count, last_close_date, ma20, ma50, ma50_prev, daily_change, gap_to_ma20, break_dates FROM series_state WHERE listing_id=%s', (lid,))
        state = cur.fetchone() or {}
    price = float(u['price']) if u['price'] is not None else None
    factor = to_eur_factor(u['price_currency'] or u['currency'], rates)
    sheet = {'id': lid, 'symbol': u['symbol'], 'name': u['name'], 'isin': u['isin'], 'kind': u['kind'], 'category': u['category'], 'country': u['country'],
             'mic': u['mic'], 'market': MARKETS.get(u['mic'], u['mic']), 'currency': u['price_currency'] or u['currency'], 'price': price,
             'price_eur': price * factor if price is not None and factor else None, 'price_time': u['price_time'].isoformat(sep=' ') if u['price_time'] else None,
             'price_source': u['price_source'], 'avg_volume_3m': u['avg_volume_3m'], 'market_cap': u['market_cap'],
             'catalogue_status': u['status'], 'excluded_reason': u['excluded_reason'], 'is_primary': bool(u['is_primary']),
             'other_listings': [{'id': s['id'], 'mic': s['mic'], 'symbol': s['symbol'], 'currency': s['currency'], 'status': s['status'], 'is_primary': bool(s['is_primary'])} for s in siblings],
             'daily': daily[-400:], 'daily_volume': daily_volume[-400:], 'state': {k: (float(v) if hasattr(v, 'as_integer_ratio') and not isinstance(v, int) else v) for k, v in state.items() if k != 'break_dates'},
             'break_dates': state.get('break_dates')}
    sheet.update(_sheet_context(conn, u, state, daily))
    # Verdict : uniquement pour une cotation recommandable ; sinon la fiche explique pourquoi elle ne l'est pas.
    all_windows = sorted({1, 5, 21, 63, 126, 252} | {p['sessions'] for p in config['periods']})
    bars = [(r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])) for r in rows]
    with conn.cursor() as cur:
        cur.execute("SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))
        splits = [(r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None) for r in cur.fetchall()]
    dates, closes, basis, breaks, full, missing, tech = analyze_series(bars, all_windows, splits)
    sheet['measures'] = {str(n): m for n, m in full.items()}
    sheet['analysis_basis'] = basis
    chart_dates, chart_closes, _, chart_breaks = prepare_series(bars, splits)
    volumes = dict(zip((d for d, _ in daily), daily_volume))
    sheet['daily_raw'] = sheet['daily']
    sheet['daily'] = [[d, c] for d, c in zip(chart_dates, chart_closes)][-400:]
    sheet['daily_volume'] = [volumes.get(d) for d, _ in sheet['daily']]
    sheet['chart_break_dates'] = [chart_dates[i] for i in chart_breaks]
    sheet['data_corrections'] = data_corrections(bars, splits)
    sheet['price_stale'] = hours.price_is_stale(u['mic'], u['price_time'], hours.utcnow(), expected_close(conn, u['mic']), last_collection(conn, u['mic']))
    if sheet['freshness']['stale']:
        sheet['state']['quality'] = 'stale'

    sheet['missing_measures'] = {str(n): why for n, why in missing.items()}
    if u['status'] == 'selected' and u['is_primary']:
        view = request.get('view') or {}
        entries, scoped, _, _ = scoped_entries(conn, config, view)      # même moteur que l'Explorer : mêmes filtres, mêmes critères, même classement
        mine = next((e for e in scoped if e['id'] == lid), None)
        v = judge_universe(conn, config, [lid])[0]
        group = 'etf' if u['kind'] == 'etf' else 'equity'
        sheet['verdict'] = {'status': v['status'], 'status_label': STATUS_LABELS[v['status']], 'score': mine['score'] if mine else None, 'rank': mine['rank'] if mine else None,
                            'of': sum(1 for e in scoped if e['group'] == group and e['status'] == 'retained'), 'in_scope': mine is not None,
                            'scope_filtered': len(scoped) != len(entries), 'examined': len(scoped), 'universe': len(entries), 'reasons': v['reasons']}
    elif u['status'] == 'excluded':
        sheet['verdict'] = {'status': 'excluded', 'status_label': STATUS_LABELS['excluded'], 'note': u['excluded_reason'] or 'Exclu des recommandations.'}
    elif u['status'] == 'selected':
        sheet['verdict'] = {'status': 'unknown', 'status_label': 'Cotation secondaire', 'note': 'Ce produit est analysé sur sa cotation principale (voir « Autres cotations »).'}
    else:
        sheet['verdict'] = {'status': 'unknown', 'status_label': 'Non analysé', 'note': 'Aucune cotation Yahoo exploitable pour le moment : ce titre n’est pas encore analysé.'}
    if u['kind'] == 'etf':
        sheet['etf_profile'] = _etf_profile(conn, lid, u['symbol'], bool(request.get('fetch_profile')))
    sheet['strategy'] = {'name': config.get('name'), 'ranking': config['ranking']['mode'], 'source': request.get('source') or None,
                         'technical': {k: v for k, v in config['technical'].items() if v},
                         'periods': [{'id': p['id'], 'label': strategy.LABELS[p['id']], 'sessions': p['sessions'], 'criteria': {f: p[f] for f, _, _ in strategy.CRITERIA if p[f] is not None}} for p in config['periods'] if p['enabled']]}
    sheet['config_periods'] = [{'id': p['id'], 'label': strategy.LABELS[p['id']], 'sessions': p['sessions'], 'enabled': p['enabled']} for p in config['periods']]
    return sheet


LEVERAGE = re.compile(r'\b(bull|[235]x|x[235]|-[123]x)\b|levier|effet de levier', re.I)       # compléments de rules.is_leveraged_name pour l'avertissement de la fiche


def _sheet_context(conn, u, state, daily):
    """Sources, fraîcheur, éligibilité PEA probable, avertissement produit : tout ce qui situe la donnée."""
    with conn.cursor() as cur:
        cur.execute('SELECT source_commit, loaded_at FROM catalogue_loads ORDER BY id DESC LIMIT 1')
        cat = cur.fetchone()
        cur.execute("SELECT job_type, status, started_at, finished_at FROM jobs WHERE job_type IN (%s,%s) AND status IN ('completed','completed_with_errors') ORDER BY id DESC LIMIT 2",
                    ('daily:' + u['mic'], 'intraday:' + u['mic']))
        collects = {r['job_type'].split(':')[0]: (r['finished_at'] or r['started_at']).isoformat(sep=' ') for r in cur.fetchall()}
        cur.execute('SELECT MAX(last_close_date) d FROM series_state s JOIN listings l ON l.id=s.listing_id WHERE l.mic=%s', (u['mic'],))
        peer_date = cur.fetchone()['d']
        expected = max(expected_close(conn, u['mic']), str(peer_date or ''))
    pea = pea_status(u['kind'], u['country'], u['mic']) == 'probable'
    warn = None
    text = ' '.join(filter(None, [u['name'], u['category']]))
    if u['kind'] == 'etf' and (is_leveraged_name(text) or LEVERAGE.search(text)):
        warn = 'Ce produit semble à effet de levier ou inversé (d’après son nom). Les effets cumulés quotidiens peuvent différer fortement de l’indice : vérifiez son document d’information.'
    last = state.get('last_close_date')
    return {'pea': {'status': 'probable' if pea else ('a_verifier' if u['kind'] == 'etf' else 'non'),
                    'note': 'Action d’une société de l’Espace économique européen, cotée sur une place européenne : éligibilité PEA probable, à confirmer chez le courtier.' if pea else
                            ('Éligibilité PEA d’un ETF : dépend de son indice et de son domicile, à vérifier dans son document d’information.' if u['kind'] == 'etf' else 'Émetteur hors des pays éligibles, ou action cotée hors d’Europe : pas éligible au PEA par défaut.')},
            'product_warning': warn,
            'sources': {'catalogue': 'FinanceDatabase', 'catalogue_loaded_at': cat['loaded_at'].isoformat(sep=' ') if cat else None, 'catalogue_commit': (cat['source_commit'][:8] if cat else None),
                        'prices': 'Yahoo Finance', 'last_daily_collect': collects.get('daily'), 'last_intraday_collect': collects.get('intraday')},
            'freshness': {'last_close_date': last.isoformat() if last else None, 'market_latest_close': expected or None,
                          'closes_count': state.get('closes_count'), 'first_close_date': daily[0][0] if daily else None, 'stale': bool(last and expected and str(last) < expected)}}


PROFILE_MAX_AGE_DAYS = 30


def _etf_profile(conn, listing_id, symbol, allow_fetch):
    """Fiche pédagogique en cache ; rafraîchie à la demande (au plus tous les 30 jours, une tentative par jour en cas d'échec)."""
    from engine.market import etf_profile
    from engine.market.yahoo import YahooClient
    now = datetime.datetime.utcnow().replace(microsecond=0)
    with conn.cursor() as cur:
        cur.execute('SELECT fetched_at, version, state, data_json FROM etf_profiles WHERE listing_id=%s', (listing_id,))
        row = cur.fetchone()
    fresh_days = PROFILE_MAX_AGE_DAYS if row and row['state'] == 'ok' else 1
    if allow_fetch and (not row or row['version'] != etf_profile.VERSION or (now - row['fetched_at']).days >= fresh_days):
        try:
            data, state = etf_profile.fetch_profile(YahooClient().transport, symbol), 'ok'
            if data is None:
                state = 'unavailable'
        except Exception:
            data, state = None, 'unavailable'
        if state == 'ok' or not row:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO etf_profiles(listing_id,fetched_at,version,state,data_json) VALUES (%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE fetched_at=VALUES(fetched_at), version=VALUES(version), state=VALUES(state), data_json=VALUES(data_json)""",
                            (listing_id, now, etf_profile.VERSION, state, json.dumps(data or {})))
            conn.commit()
            return {'state': state, 'fetched_at': now.isoformat(sep=' '), 'data': data}
    if row:
        return {'state': row['state'], 'fetched_at': row['fetched_at'].isoformat(sep=' '), 'data': json.loads(row['data_json']) or None}
    return {'state': 'none', 'fetched_at': None, 'data': None}
