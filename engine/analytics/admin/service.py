"""Services de lecture pour le site : l'Explorer (liste filtrée, triée et paginée d'un univers jugé). Entrée/sortie JSON (voir engine.cli).

L'univers évalué est v_recommendable. La recherche explicite d'un titre (nom, symbole, ISIN) peut aussi renvoyer des titres exclus,
toujours étiquetés « exclu » avec leur motif : ils ne reçoivent ni rang ni verdict de stratégie."""
import datetime
import json
from collections import Counter, defaultdict
from engine.catalogue.rules import MARKETS
from engine.shared import settings as settings_mod
from engine.market import hours
from engine.market.collect import latest_rates, to_eur_factor
from engine.market.calendar import window_calendars
from ..series import signals
from ..explorer import strategy
from ..explorer import explorer_config
from ..scoring import score_service
from ..market_views import geography
from ..series.series import prepare_series
from ..market_views.market_facts import analyst_view, expected_close, last_collection, pea_status, size_key
from .universe_verdicts import cached_verdicts, compact_parts, data_version, expanded_parts, judge_universe

STATUS_LABELS = {'retained': 'Retenu', 'rejected': 'Écarté', 'unknown': 'Non évaluable', 'excluded': 'Exclu'}


REF_FIELDS = ('slope', 'r2', 'perf', 'volatility', 'drawdown')


EXPORT_LIMIT = 20000


def request_config(request):
    cfg = request.get('config')
    if isinstance(cfg, str) or cfg is None:
        cfg = strategy.preset(cfg or 'regular')
    return strategy.validate(cfg)


def _row(v, rates, conn=None):
    u = v['row']
    cur = u['price_currency'] or u['currency']
    factor = to_eur_factor(cur, rates)
    price = float(u['price']) if u['price'] is not None else None
    return {'id': u['id'], 'symbol': u['symbol'], 'name': u['name'], 'isin': u['isin'], 'mic': u['mic'], 'market': MARKETS.get(u['mic'], u['mic']),
            'kind': u['kind'], 'category': u['category'], 'country': u['country'], 'pea': pea_status(u['kind'], u['country'], u['mic']) == 'probable',
            'currency': cur, 'price': price, 'price_eur': price * factor if price is not None and factor else None,
            'price_time': u['price_time'].isoformat(sep=' ') if u['price_time'] else None, 'quote_at': u['quote_at'].isoformat(sep=' ') if u.get('quote_at') else None, 'price_source': u['price_source'],
            'status': v['status'], 'status_label': STATUS_LABELS[v['status']], 'score': v['score'], 'rank': v['rank'], 'momentum': v.get('momentum'),
            'quality': u['quality'], 'price_stale': hours.price_is_stale(u['mic'], u['price_time'], hours.utcnow(), expected_close(conn, u['mic']) if conn is not None else None, last_collection(conn, u['mic']) if conn is not None else None), 'measures': {str(n): dict(m,slope_period=explorer_config.period_slope(m.get('slope'),n)) if m else None for n, m in v['measures'].items()}, 'reasons': v['reasons']}


def masked_by_tradability(entry, aux_row, prefilter_cfg, query=''):
    """Vrai si le filtre « Titres facilement négociables » masque ce titre : seulement une négociabilité LIMITÉE (donnée présente, récente et basse). Une donnée absente ou périmée ne masque jamais.
    Un titre retrouvé par son symbole ou son ISIN exact n'est jamais masqué."""
    level = signals.liquidity(_daily_eur(aux_row), entry['kind'], prefilter_cfg, aux_row.get('quote_age_days'))['level']
    return level == 'bad' and not (query and query in (entry['symbol'].casefold(), (entry['isin'] or '').casefold()))


LEVEL_FILTERS = ('regularity', 'risk', 'liquidity')          # clés de vue = clés des pastilles ; valeurs : ok, warn, bad, unknown


def row_levels(entry, aux_row, ref, prefilter_cfg):
    """Niveau de chaque pastille d'une ligne (même calcul que les pastilles affichées) : {'regularity': 'ok', 'risk': 'warn', 'liquidity': 'unknown'}."""
    return {s['key']: s['level'] for s in signals.row_signals(aux_row, entry['kind'], ref, prefilter_cfg, aux_row.get('quote_age_days'))}


def level_filtered_rows(rows, aux, ref, prefilter_cfg, wanted, query='', always_shown=()):
    """Filtres Régularité / Volatilité / Négociabilité : MASQUENT seulement, après le classement (rang et score restent ceux du catalogue, l'ordre relatif ne change pas).
    `wanted` : {clé: ensemble de niveaux} ; une clé absente ou vide ne filtre rien. Un titre retrouvé par son symbole ou son ISIN exact n'est jamais masqué.
    Renvoie (lignes gardées, effectifs par niveau avant filtre {clé: {niveau: n}})."""
    counts = {k: defaultdict(int) for k in LEVEL_FILTERS}
    kept = []
    for e in rows:
        levels = row_levels(e, aux.get(e['id'], {}), ref, prefilter_cfg)
        for k in LEVEL_FILTERS:
            counts[k][levels.get(k, 'unknown')] += 1
        exact = query and query in (e['symbol'].casefold(), (e['isin'] or '').casefold())
        if e['id'] in always_shown or exact or all(not wanted.get(k) or levels.get(k, 'unknown') in wanted[k] for k in LEVEL_FILTERS):
            kept.append(e)
    return kept, {k: dict(v) for k, v in counts.items()}


def tradable_rows(rows, aux, prefilter_cfg, query='', always_shown=()):
    """Les lignes que le filtre « Titres facilement négociables » laisse passer. `always_shown` : uniquement la vue « Titres détenus », pour qu'elle reste complète ;
    partout ailleurs un titre détenu est masqué comme les autres (ses portefeuilles, eux, ne sont jamais filtrés)."""
    return [e for e in rows if e['id'] in always_shown or not masked_by_tradability(e, aux.get(e['id'], {}), prefilter_cfg, query)]


def _daily_eur(a):
    """Valeur échangée par jour (€) : volume moyen 3 mois × cours converti ; None si l'une des deux données manque."""
    return a['price_eur'] * a['volume'] if a.get('price_eur') is not None and a.get('volume') is not None else None


def _aux(conn, ref, rates):
    """Données de filtre et de tri pour tout l'univers : prix, volume, fraîcheur et mesures de la fenêtre de référence `ref`."""
    with conn.cursor() as cur:
        cur.execute("""SELECT p.listing_id id, p.price, COALESCE(p.currency, l.currency) cur, p.avg_volume_3m volume, p.avg_volume_10d volume_10d, p.expense_ratio fee, p.analyst_rating analyst, p.market_cap, p.quote_at, l.mic, s.last_close_date, s.quality
                       FROM latest_prices p JOIN listings l ON l.id=p.listing_id LEFT JOIN series_state s ON s.listing_id=l.id""")
        out = {}
        for r in cur.fetchall():
            price = None if r['price'] is None else float(r['price'])
            f = to_eur_factor(r['cur'], rates)
            age = None if r['quote_at'] is None else max(0.0, (hours.utcnow().replace(tzinfo=None) - r['quote_at']).total_seconds() / 86400)
            out[r['id']] = {'price': price, 'price_eur': price * f if price is not None and f else None, 'cap': size_key(r['market_cap'], r['cur'], rates), 'volume': r['volume'], 'volume_10d': r['volume_10d'], 'fee': None if r['fee'] is None else float(r['fee']), 'analyst': r['analyst'], 'quote_age_days': age,
                            'last_close': r['last_close_date'], 'quality': 'stale' if r['last_close_date'] and str(r['last_close_date']) < expected_close(conn, r['mic']) else r['quality']}
        cur.execute('SELECT listing_id, slope, r2, perf, volatility, drawdown FROM strategy_metrics WHERE sessions=%s', (ref,))
        for r in cur.fetchall():
            if r['listing_id'] in out:
                out[r['listing_id']].update({k: None if r[k] is None else float(r[k]) for k in REF_FIELDS})
    return out


def reference_window(config, stored=(1, 5, 21, 63, 126, 252)):
    """Fenêtre servant aux filtres et tris de colonnes : la plus longue période active, ramenée à une fenêtre précalculée."""
    longest = max((p['sessions'] for p in config['periods'] if p['enabled']),default=21)
    return min(stored, key=lambda n: (abs(n - longest), n))


SORT_KEYS = {'score_simple': lambda e, a: e.get('score_simple'), 'score_complex': lambda e, a: e.get('score_complex'), 'name': lambda e, a: (e['name'] or '').casefold(), 'symbol': lambda e, a: e['symbol'].casefold(), 'score': lambda e, a: e['score'],
             'price': lambda e, a: a.get('price_eur'), 'volume': lambda e, a: a.get('volume'), 'fresh': lambda e, a: a.get('last_close') and a['last_close'].toordinal(),
             'slope': lambda e, a: a.get('slope'), 'r2': lambda e, a: a.get('r2'), 'perf': lambda e, a: a.get('perf'),
             'volatility': lambda e, a: a.get('volatility'), 'drawdown': lambda e, a: a.get('drawdown')}


def _num(view, key):
    v = view.get(key)
    return None if v in (None, '') else float(v)


def _aum_eur(entry, rates):
    if entry.get('kind') != 'etf' or not entry.get('net_assets'):
        return None
    factor = to_eur_factor(entry.get('price_currency') or entry.get('currency'), rates)
    return float(entry['net_assets']) * factor if factor is not None else None


def scoped_entries(conn, config, view, rates=None, aux=None, now=None):
    """Étapes 1 à 3 de la recherche : univers complet des titres éligibles → filtres de l'utilisateur → évaluation et classement DANS cette sélection.
    Renvoie (entrées de l'univers, entrées examinées avec statut, rang et score recalculés dans la sélection, fenêtre de référence, données de filtre).
    Rang et score sont des percentiles parmi les titres retenus de la sélection (par groupe action / ETF) : changer les filtres change le classement."""
    rates = rates if rates is not None else latest_rates(conn)
    now = now or hours.utcnow()
    entries = cached_verdicts(conn, config)         # verdict de chaque titre éligible pour CETTE configuration (jamais pour un préréglage par défaut)
    if config.get('version') in (3, 4):
        entries = score_service.attach(conn, config, entries, data_version(conn))       # scores simple et complexe : calculés hors filtres, jamais recalculés dans la sélection
    ref = reference_window(config)
    aux = aux if aux is not None else _aux(conn, ref, rates)
    kind, market = view.get('kind') or '', view.get('market') or ''
    requested_kind = kind
    if requested_kind == 'large_etf':
        kind = 'etf'
    region = view.get('geo_region') or ''
    etf_data = {}
    etf_ids = [e['id'] for e in entries if e['kind'] == 'etf']
    if etf_ids and (region or requested_kind == 'large_etf'):
        with conn.cursor() as cur:
            for offset in range(0, len(etf_ids), 1000):
                part = etf_ids[offset:offset + 1000]
                cur.execute("SELECT listing_id,data_json FROM etf_profiles WHERE state='ok' AND listing_id IN (%s)" % ','.join(['%s'] * len(part)), part)
                for p in cur.fetchall():
                    try:
                        etf_data[p['listing_id']] = json.loads(p['data_json']) if isinstance(p['data_json'], str) else p['data_json']
                    except (TypeError, ValueError):
                        etf_data[p['listing_id']] = {}
    # Encours Yahoo, converti dans une devise commune. Chaque instrument n'est compté
    # qu'une fois même si plusieurs cotations subsistent dans l'univers.
    aum_listing_values = {}
    aum_by_instrument = {}
    if requested_kind == 'large_etf':
        for e in entries:
            if e['kind'] != 'etf':
                continue
            iid = e.get('instrument_id', e['id'])
            if not e.get('net_assets'):
                continue
            factor = to_eur_factor(e.get('price_currency') or e.get('currency'), rates)
            if factor is None:
                continue
            amount = float(e['net_assets']) * factor
            aum_listing_values[e['id']] = amount
            aum_by_instrument[iid] = max(amount, aum_by_instrument.get(iid, 0))
    large_instruments = set()
    if aum_by_instrument:
        ordered_aum = sorted(aum_by_instrument.values(), reverse=True)
        cutoff = ordered_aum[max(0, -(-len(ordered_aum) // 10) - 1)]        # tri décroissant : le seuil est la valeur du dernier ETF du premier dixième
        large_instruments = {iid for iid, amount in aum_by_instrument.items() if amount >= cutoff}
    countries, categories = _choices(view.get('country')), {c.casefold() for c in _choices(view.get('category'))}         # plusieurs choix possibles, séparés par « | »
    caps = {c for c in _choices(view.get('cap')) if c in ('micro', 'small', 'mid', 'large', 'mega')}
    owned = set(view.get('owned_ids') or [])
    base = [e for e in entries if (not kind or e['kind'] == kind) and (requested_kind != 'large_etf' or e['kind'] == 'etf' and e.get('instrument_id', e['id']) in large_instruments)
            and (not region or (geography.equity_region(e.get('country')) if e['kind'] == 'equity' else (etf_data.get(e['id'], {}).get('geography_region') or geography.etf_region(etf_data.get(e['id'], {}).get('category')))) == region)
            and (not market or e['mic'] == market)
            and (not countries or e['country'] in countries) and (not categories or (e['category'] or '').casefold() in categories)]
    if view.get('pea'):
        base = [e for e in base if pea_status(e['kind'], e['country'], e['mic']) == 'probable']
    if view.get('owned_only'):
        base = [e for e in base if e['id'] in owned]
    if view.get('open_now'):
        base = [e for e in base if e['mic'] in hours.HOURS and hours.is_open(e['mic'], now)]
    budget, min_price, max_price, max_vol, max_dd, min_volume = (_num(view, k) for k in ('budget', 'min_price', 'max_price', 'max_volatility', 'max_drawdown', 'min_volume'))
    max_fee = _num(view, 'max_fee')                 # frais courants maximaux d'un ETF, en % par an ; sans effet sur les actions

    def keep(e):
        a = aux.get(e['id'], {})
        if view.get('currency') and (e.get('price_currency') or e.get('currency')) not in _choices(view['currency']):return False
        aum=_aum_eur(e,rates) if e['kind']=='etf' else None
        for field,compare in [('min_aum',lambda v,t:v>=t),('max_aum',lambda v,t:v<=t)]:
            threshold=_num(view,field)
            if threshold is not None and e['kind']=='etf' and (aum is None or not compare(aum,threshold)):return False
        price = a.get('price_eur')
        if (budget is not None and (price is None or price > budget)) or (min_price is not None and (price is None or price < min_price)) or (max_price is not None and (price is None or price > max_price)):
            return False
        if max_vol is not None and (a.get('volatility') is None or a['volatility'] > max_vol):
            return False
        if max_dd is not None and (a.get('drawdown') is None or a['drawdown'] > max_dd):
            return False
        if min_volume is not None and (a.get('volume') is None or a['volume'] < min_volume):
            return False
        if max_fee is not None and e['kind'] == 'etf' and (a.get('fee') is None or a['fee'] > max_fee):     # frais inconnus : l'ETF n'est pas retenu
            return False
        if caps and (e['kind'] != 'equity' or a.get('cap') not in caps):       # la taille ne concerne que les actions : un ETF n'a pas de capitalisation boursière
            return False
        return not (view.get('fresh_only') and a.get('quality') != 'ok')
    base = [e for e in base if keep(e)]
    if len(base) != len(entries) and not score_service.is_scores_mode(config):                   # sélection plus étroite que l'univers : on reclasse les retenus entre eux
        retained = [e['id'] for e in base if e['status'] == 'retained']
        ranked = {v['key']: v for v in judge_universe(conn, config, retained)} if retained else {}
        out = []
        for e in base:
            v = ranked.get(e['id'])
            out.append(dict(e, rank=v['rank'] if v else None, score=None if not v or v['score'] is None else round(v['score'], 4),score_parts=compact_parts(v) if v else [],score_missing=v.get('score_missing',0) if v else 0))
        base = out
    return entries, base, ref, aux


def score_view(entry, detail):
    """Les deux scores d'un titre avec leur décomposition ; rangs globaux (parmi tous les titres notés du groupe), jamais ceux de la page ou du filtre."""
    out = {'rank_simple': entry.get('score_rank_simple'), 'rank_complex': entry.get('score_rank_complex')}
    if detail is None:
        return dict(out, simple={'score': entry.get('score_simple'), 'status': entry.get('score_simple_status')}, complex={'score': entry.get('score_complex'), 'status': entry.get('score_complex_status')})
    return dict(out, simple=detail['simple'], complex=detail['complex'], weights=detail['weights'], periods=detail['periods'], missing=detail['missing'], liquidity=detail['liquidity'])


def explore(conn, request):
    config = score_service.apply_admin(conn, request_config(request))
    view = request.get('view') or {}
    export = bool(view.get('export'))
    page, size = max(1, int(view.get('page', 1))), min(100, max(1, int(view.get('page_size', 24))))
    status = view.get('status', 'retained')
    query = (view.get('q') or '').strip().casefold()[:100]
    rates = latest_rates(conn)
    now = hours.utcnow()
    entries, base, ref, aux = scoped_entries(conn, config, view, rates, None, now)
    kind, market = view.get('kind') or '', view.get('market') or ''
    if kind == 'large_etf':
        kind = 'etf'
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
    prefilter_cfg = settings_mod.prefilter_rules(conn)
    masked = 0
    if view.get('tradable', True):
        # Titres facilement négociables : MASQUE seulement, après le classement. Rang et score restent ceux du catalogue (aucun recalcul) ; les suivants remontent dans la liste.
        # Un titre retrouvé par son symbole ou son ISIN exact reste affiché (avec sa mention), pour qu'une recherche précise n'échoue jamais en silence.
        kept = tradable_rows(rows, aux, prefilter_cfg, query, set(view.get('owned_ids') or []) if view.get('owned_only') else set())
        masked, rows = len(rows) - len(kept), kept
    wanted = {k: _choices(view.get(k)) & {'ok', 'warn', 'bad', 'unknown'} for k in LEVEL_FILTERS}
    rows, level_counts = level_filtered_rows(rows, aux, ref, prefilter_cfg, wanted, query, set(view.get('owned_ids') or []) if view.get('owned_only') else set())
    level_masked = sum(level_counts['regularity'].values()) - len(rows)
    sort, desc = view.get('sort', 'rank'), view.get('dir') == 'desc'
    proximity_order = status == 'rejected' and (sort == 'proximity' or sort == 'rank' and not score_service.is_scores_mode(config))
    if proximity_order:
        rows = sorted(rows,key=lambda e: (*(e.get('proximity') or [999,999,float('inf')]), e['symbol']))
    elif sort in SORT_KEYS:
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
    score_detail = score_service.details(conn, config, wanted)
    out = []
    from ..market_views import etf
    etf_top = [e['id'] for e in rows if e.get('group') == 'etf'][:10]          # dix premiers ETF de la vue, avant pagination, dans l'ordre déjà déterminé
    etf_concentration = etf.concentration(conn, etf_top)
    page_etf = [e['id'] for e in page_rows if e not in excluded_hits and e.get('group') == 'etf']
    fund_natures = {}
    if page_etf:
        with conn.cursor() as cur:
            cur.execute("SELECT listing_id,data_json FROM etf_profiles WHERE state='ok' AND listing_id IN (%s)" % ','.join(['%s'] * len(page_etf)), page_etf)
            for profile in cur.fetchall():
                data = etf.decode(profile['data_json'])
                fund_natures[profile['listing_id']] = next((str(data.get(k)).strip() for k in ('category', 'family', 'legal_type') if data.get(k)), None)
    cache = etf.load(conn, set(page_etf) | set(etf_top))
    pgroups = etf.page_groups(cache, page_etf) if len(page_etf) > 1 else []          # toute la page, depuis les liens précalculés : aucune corrélation recalculée ici
    group_of, group_info = {}, {}
    for g in pgroups:
        group_of[g['leader']] = g['id']
        group_info[g['leader']] = {'leader': True, 'size': len(g['members']) + 1, 'index': g['index']}
        for r in g['rows']:
            group_of[r['id']] = g['id']
            group_info[r['id']] = {'leader': False, 'why': r['why'], 'diff': r['diff'], 'coefficient': r['coefficient']}
    banner = []                                          # le bandeau reprend la même méthode (lien direct avec le chef, même couverture), appliquée aux dix premiers ETF de la vue
    for g in etf.page_groups(cache, etf_top):
        m = [g['leader']] + g['members']
        if len(m) >= 3:
            banner.append({'id': g['id'], 'size': len(m), 'members': m, 'symbols': [cache[i]['meta']['symbol'] for i in m], 'label': g['index'], 'min_coefficient': g['min_coefficient'],
                           'unstable': False, 'basis': 'Corrélation des rendements hebdomadaires en EUR >= %s (52 semaines), lien direct avec le chef du groupe' % etf.NEAR_IDENTICAL})
    etf_concentration['groups'] = banner
    for position, e in enumerate(page_rows, (page - 1) * size + 1):
        if e in excluded_hits:
            out.append(e)
            continue
        v = detail[e['id']]
        v['rank'], v['score'] = e['rank'], e['score']      # rang et score viennent de la sélection complète, pas de la page
        r = _row(v, rates, conn)
        r['score_parts']=expanded_parts(e,config);r['score_missing']=e.get('score_missing',0)
        r['scores']=score_view(e,score_detail.get(e['id']))
        a = aux.get(e['id'], {})
        r.update({'position': position, 'volume': a.get('volume'), 'last_close': a['last_close'].isoformat() if a.get('last_close') else None,
                  'analyst': analyst_view(a.get('analyst')) if e['kind'] == 'equity' else None, 'ref': {k: a.get(k) for k in REF_FIELDS}, 'open': e['mic'] in hours.HOURS and hours.is_open(e['mic'], now),
                  'signals': signals.row_signals(a, e['kind'], ref, prefilter_cfg, a.get('quote_age_days')), 'etf_group': group_of.get(e['id']), 'etf_group_info': group_info.get(e['id']),
                  'aum_eur': _aum_eur(e, rates), 'fee': a.get('fee') if e['kind'] == 'etf' else None})
        if e['kind'] == 'etf':
            r['fund_nature'] = fund_natures.get(e['id'])
        out.append(r)
    if not export:
        if config.get('version')==4:
            for kind in ('equity','etf'):
                subset=[r for r in out if r['kind']==kind];effective=explorer_config.effective(config,kind);n=max((p['sessions'] for p in effective['periods'] if p['enabled']),default=ref)
                _attach_analysis_curves(conn,subset,n)
                for r in subset:r['curve_sessions']=n;r['curve_label']=signals.period_label(n)
        else:_attach_curves(conn, out, ref)
    reasons = defaultdict(int)
    for e in base:
        if e['status'] != 'retained':
            for f in e['fails']:
                reasons[f] += 1
    markets, countries, categories = defaultdict(int), defaultdict(int), defaultdict(int)
    for e in entries:
        markets[e['mic']] += 1
        if e['country']:
            countries[e['country']] += 1
        if e['category']:
            categories[e['category']] += 1
    return {'scoring': score_service.summary(config, entries), 'etf_concentration': etf_concentration, 'config': config, 'total': total, 'page': page, 'pages': max(1, -(-total // size)), 'rows': out, 'ref_sessions': ref, 'curve_label': signals.period_label(ref), 'ordering': 'proximity' if proximity_order else sort if sort in SORT_KEYS else 'rank',
            'universe': len(entries), 'examined': len(base), 'tradable': {'on': bool(view.get('tradable', True)), 'masked': masked}, 'level_filters': {'masked': level_masked, 'counts': level_counts},
            'counts': {g: dict(c) for g, c in counts.items()}, 'scope_counts': scope_counts, 'populations': {g: sum(c.values()) for g, c in counts.items()},
            'reasons': dict(reasons), 'facets': {'markets': dict(markets), 'countries': dict(sorted(countries.items())), 'categories': dict(sorted(categories.items()))}}


def filter_metadata_coverage(conn):
    """Couverture AUM et région sur les instruments recommandables; compte sans double compte des cotations."""
    from ..market_views import etf
    profiles = etf.read_profiles(conn)
    rates = latest_rates(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id,l.instrument_id,i.kind,i.country,p.net_assets,p.currency AS price_currency,l.currency
                       FROM v_recommendable r JOIN listings l ON l.id=r.listing_id
                       JOIN instruments i ON i.id=l.instrument_id
                       LEFT JOIN latest_prices p ON p.listing_id=l.id""")
        rows = cur.fetchall()
    instruments = {}
    aum_values = {}
    for r in rows:
        item = instruments.setdefault(r['instrument_id'], {'kind': r['kind'], 'country': r['country'], 'aum': False, 'region': None})
        if r['kind'] == 'equity':
            item['region'] = item['region'] or geography.equity_region(r['country'])
        else:
            profile = profiles.get(r['id'])
            data = etf.profile_data(etf.decode(profile['data_json'])) if profile and profile.get('state') == 'ok' else {}
            region = data.get('geography_region') or geography.etf_region(data.get('category'))
            if region:
                item['region'] = region
            fx = to_eur_factor(r.get('price_currency') or r.get('currency'), rates)
            item['aum'] = item['aum'] or bool(r.get('net_assets') and float(r['net_assets']) > 0 and fx is not None)
            if r.get('net_assets') and float(r['net_assets']) > 0 and fx is not None:
                aum_values[r['instrument_id']] = max(aum_values.get(r['instrument_id'], 0), float(r['net_assets']) * fx)
    ordered = sorted(aum_values.values(), reverse=True)
    cutoff = ordered[max(0, -(-len(ordered) // 10) - 1)] if ordered else None
    groups = Counter((v['kind'], 'known' if v['region'] else 'unknown') for v in instruments.values())
    etfs = [v for v in instruments.values() if v['kind'] == 'etf']
    equities = [v for v in instruments.values() if v['kind'] == 'equity']
    return {'instruments': len(instruments), 'etfs': {'total': len(etfs), 'aum_known': sum(v['aum'] for v in etfs), 'large_by_aum': sum(a >= cutoff for a in aum_values.values()) if cutoff is not None else 0, 'aum_decile_cutoff_eur': cutoff,
            'region_known': groups[('etf', 'known')], 'region_unknown': groups[('etf', 'unknown')]},
            'equities': {'total': len(equities), 'region_known': groups[('equity', 'known')], 'region_unknown': groups[('equity', 'unknown')]}}


def _choices(value):
    """Valeurs d'un filtre à choix multiple (« A|B ») ; une liste est aussi acceptée."""
    items = value if isinstance(value, (list, tuple)) else str(value or '').split('|')
    return {x.strip() for x in items if x and x.strip()}


def _search_excluded(conn, query, kind, market):
    """Cotations exclues correspondant à une recherche : étiquetées, avec leur motif, sans verdict de stratégie."""
    like = '%' + query.replace('%', '') + '%'
    sql = """SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, i.name, i.isin, i.kind, i.country, i.category, p.price, p.price_time, p.quote_at, p.source AS price_source, p.currency AS price_currency
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
             'quote_at': r['quote_at'].isoformat(sep=' ') if r['quote_at'] else None,
             'price_source': r['price_source'], 'status': 'excluded' if r['status'] == 'excluded' else 'unknown',
             'status_label': 'Exclu' if r['status'] == 'excluded' else 'En attente d’analyse', 'excluded_reason': r['excluded_reason'], 'score': None, 'rank': None,
             'quality': None, 'measures': {}, 'reasons': []} for r in rows]


def downsample(values, points):
    """Au plus `points` valeurs réparties régulièrement, première et dernière comprises (la forme de la courbe est conservée)."""
    if len(values) <= points:
        return list(values)
    last = len(values) - 1
    return [values[round(i * last / (points - 1))] for i in range(points)]


def _attach_curves(conn, rows, sessions=63, points=66):
    """Petite courbe « Tendance » de chaque ligne : les `sessions` dernières clôtures, c'est-à-dire la période la plus longue de la stratégie (la même que la fenêtre de référence
    des colonnes), ramenées à `points` valeurs au plus."""
    ids = [r['id'] for r in rows]
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute(f"SELECT listing_id, price_date, close_px FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(ids))}) AND price_date >= %s ORDER BY listing_id, price_date",
                    ids + [datetime.date.today() - datetime.timedelta(days=int(sessions * 1.6) + 12)])
        curves = defaultdict(list)
        for r in cur.fetchall():
            curves[r['listing_id']].append(float(r['close_px']))
    for r in rows:
        r['curve'] = downsample(curves.get(r['id'], [])[-(sessions + 1):], points)


def _attach_analysis_curves(conn, rows, sessions, points=66):
    """V4 sparklines use the same confirmed market dates and split basis as analysis."""
    if not rows:return
    calendars={m:window_calendars(m,expected_close(conn,m),[sessions]).get(sessions,[]) for m in {r['mic'] for r in rows}}
    starts=[ds[0] for ds in calendars.values() if ds]
    if not starts:return
    ids=[r['id'] for r in rows];marks=','.join(['%s']*len(ids));bars=defaultdict(list);splits=defaultdict(list)
    with conn.cursor() as cur:
        cur.execute(f'SELECT listing_id,price_date,close_px,adj_close_px FROM daily_prices WHERE listing_id IN ({marks}) AND price_date>=%s ORDER BY listing_id,price_date',ids+[min(starts)])
        for b in cur.fetchall():bars[b['listing_id']].append((str(b['price_date']),float(b['close_px']),None if b['adj_close_px'] is None else float(b['adj_close_px'])))
        cur.execute(f"SELECT listing_id,event_date,ratio FROM corporate_events WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split')",ids)
        for e in cur.fetchall():splits[e['listing_id']].append((str(e['event_date']),float(e['ratio']) if e['ratio'] else None))
    for row in rows:
        ds=calendars[row['mic']]
        dates,prices,_,breaks=prepare_series([b for b in bars[row['id']] if ds and b[0]<=ds[-1]],splits[row['id']])
        observations=dict(zip(dates,prices));broken={dates[i] for i in breaks}
        values=[None if d in broken else observations.get(d) for d in ds]
        row['curve']=downsample(values,points);row['curve_dates']=downsample(ds,points)
