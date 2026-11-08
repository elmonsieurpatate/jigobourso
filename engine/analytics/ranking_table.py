"""Tableau « Classement » : tous les titres notés avec les deux scores V4, leurs rangs et les valeurs des filtres secondaires.

Lecture seule. Aucun score n'est recalculé ici : ils viennent du moteur commun (`score_service.score_book`, mis en cache) ; le tri, les filtres et la pagination se font dans la page.
Une donnée absente reste None (jamais 0). Les groupes pays / secteur / place / type reprennent exactement les correspondances de l'administration (`secondary_metadata_groups.json`).
"""
import json
import os

from engine.market.collect import latest_rates, to_eur_factor

from . import criteria as CR, scores_admin, score_service, service

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'app', 'config', 'secondary_metadata_groups.json')
ACCENTS = str.maketrans({'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a', 'â': 'a', 'ä': 'a', 'á': 'a', 'ã': 'a', 'å': 'a', 'î': 'i', 'ï': 'i', 'í': 'i', 'ì': 'i', 'ô': 'o', 'ö': 'o', 'ó': 'o',
                         'ò': 'o', 'õ': 'o', 'û': 'u', 'ü': 'u', 'ú': 'u', 'ù': 'u', 'ç': 'c', 'ñ': 'n', 'ý': 'y', 'ÿ': 'y'})
MISSING = {'', 'unknown', 'inconnu', 'inconnue', 'n/a', 'n.a.', 'none', 'null', 'not available', 'unavailable', '-', '—'}
WINDOWS = {'week': 5, 'month': 21, 'quarter': 63, 'half': 126}
REFERENCE = 21                                           # fenêtre des mesures affichées (un mois)
QUALITY = {'ok': 0, 'insufficient': 1, 'incomplete': 1, 'stale': 1, 'inconsistent_adjustments': 2, 'break': 2}


def _config():
    with open(CONFIG, encoding='utf-8') as f:
        return json.load(f)


def _key(value):
    return ' '.join((value or '').strip().lower().translate(ACCENTS).split())


def classify(cfg, which, raw, kind=None):
    """Identifiant de groupe d'un pays, d'un secteur ou d'une place (même règle que app/services/secondary_metadata.php)."""
    key = _key(raw)
    if key in MISSING:
        return 'unknown'
    if which == 'country':
        return cfg['country_aliases'].get(key, 'country:other')
    if which == 'market':
        return cfg['mic_groups'].get((raw or '').strip().upper(), 'unknown')
    mapping = cfg['equity_sectors'] if kind == 'equity' else cfg['etf_categories'] if kind == 'etf' else {}
    return mapping.get(key, 'sector:other')


def _num(v):
    return None if v is None else round(float(v), 4)             # 4 décimales suffisent à l'affichage et aux catégories : réponse plus légère


def _fetch(conn, ids):
    marks = ','.join(['%s'] * len(ids))
    out = {i: {} for i in ids}
    with conn.cursor() as cur:
        cur.execute(f"""SELECT l.id, l.symbol, l.mic, l.currency, i.name, i.kind, i.isin, i.country, i.category, p.price, p.price_time, p.avg_volume_3m, p.analyst_rating,
                               s.last_close_date, s.close_px, s.daily_change, s.quality, s.coverage_252, q.turnover_eur, q.source AS liquidity_source, q.days AS liquidity_days
                        FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id LEFT JOIN series_state s ON s.listing_id=l.id
                        LEFT JOIN liquidity_state q ON q.listing_id=l.id WHERE l.id IN ({marks})""", ids)
        for r in cur.fetchall():
            out[r['id']].update(r)
        cur.execute(f"SELECT listing_id, sessions, slope, r2, perf, volatility, drawdown, coverage FROM strategy_metrics WHERE listing_id IN ({marks}) AND sessions IN (1,5,21,63,126,252)", ids)
        for r in cur.fetchall():
            out[r['listing_id']].setdefault('m', {})[r['sessions']] = r
        cur.execute(f"SELECT listing_id, up_fraction, spike_share FROM score_inputs WHERE listing_id IN ({marks}) AND sessions=%s", ids + [REFERENCE])
        for r in cur.fetchall():
            out[r['listing_id']]['x'] = r
    return out


CRITERIA_FIELDS = {'min_slope': 'slope', 'min_r2': 'r2'}      # critères de RECHERCHE : granularités actives, pente et R² seulement ; rendement, volatilité, drawdown n'y sont jamais des seuils


def criteria(conn=None, request=None):
    """Critères de recherche historiques des stratégies intégrées, lus dans la source centralisée `scores_admin.V4_STRATEGIES` : {identifiant du Classement: {période: {critère: valeur}}}.
    Ce sont des critères de RECHERCHE (affichage) : ils n'entrent ni dans les notes ni dans les rangs. Une stratégie sans critère (Momentum) renvoie des périodes vides."""
    out = {}
    for ct_id, name in scores_admin.CT_BUILTIN.items():
        cfg = scores_admin.V4_STRATEGIES[name]['build']()
        per = {}
        for p in cfg['periods']:
            if p['id'] in scores_admin.SCORING_PERIODS and p.get('enabled'):
                per[p['id']] = {CRITERIA_FIELDS[f]: p[f] for f in CRITERIA_FIELDS if p.get(f) is not None}
        out[ct_id] = {'name': name, 'periods': per}
    return {'criteria': out}


def _ties(ranks):
    """{rang: nombre de titres à ce rang} (1 = rang unique)."""
    out = {}
    for r in ranks.values():
        out[r] = out.get(r, 0) + 1
    return out


def default_norm(ct_id):
    """Critères normalisés d'une stratégie intégrée (valeurs historiques centralisées) ; None pour un identifiant inconnu."""
    item = criteria().get('criteria', {}).get(ct_id)
    return None if item is None else CR.normalize(CR.default_spec(item['periods']))


def norm_of(request):
    """Critères à appliquer : `spec` transmis (réglages enregistrés ou brouillon) sinon valeurs par défaut de la stratégie intégrée. None = contexte absent."""
    spec = request.get('spec')
    if isinstance(spec, dict):
        return CR.normalize(spec)
    return default_norm(request.get('ct_id') or '')


def _base(conn, request):
    scores_admin.refresh(conn)
    if request.get('ct_id'):                                                       # stratégie du Classement : ses propres réglages de scores
        name = scores_admin.resolve(conn, request['ct_id'], request.get('user_id') or 0)
    else:
        name = request.get('strategy') or 'growth_v4'
    if not scores_admin.known(name):
        name = 'growth_v4'
    cfg = scores_admin.build_config(conn, name)
    book = score_service.score_book(conn, cfg, service.data_version(conn))
    return name, cfg, book


def evaluable(book):
    """Titres du classement : notés (au moins un des deux scores)."""
    return [i for i in sorted(book) if book[i]['simple'] is not None or book[i]['complex'] is not None]


def verdicts(conn, request):
    """Statut de stratégie de chaque titre évaluable, pour des critères donnés. Aucun score ni rang n'est touché."""
    _, _, book = _base(conn, request)
    ids = [i for i in evaluable(book)]
    data = _fetch(conn, ids) if ids else {}
    norm = norm_of(request)
    status = {}
    for lid in ids:
        d = data.get(lid) or {}
        if not d:
            continue
        status[lid] = CR.evaluate(norm, {'m': d.get('m'), 'avg_volume': d.get('avg_volume_3m')})['status']
    return {'status': status, 'counts': CR.counts(status.values()), 'context': 'missing' if norm is None else 'ok', 'active': 0 if norm is None else len(norm['primary']) + len(norm['extra'])}


def table(conn, request):
    """Toutes les lignes du classement, avec scores et rangs généraux (indépendants des filtres, du tri et de la page)."""
    name, cfg, book = _base(conn, request)
    norm = norm_of(request)
    ids = evaluable(book)
    simple, rank_s, pos_s = scores_admin.ordered(book, 'simple')            # même fonction que l'administration des scores : même ordre, mêmes rangs
    complex_, rank_c, pos_c = scores_admin.ordered(book, 'complex')
    tie_s, tie_c = _ties(rank_s), _ties(rank_c)
    data = _fetch(conn, ids) if ids else {}
    curves = scores_admin.series(conn, ids, REFERENCE) if ids and request.get('include_curves', True) is not False else {}
    rates = latest_rates(conn)
    groups = _config()
    rows = []
    for lid in ids:
        d, e = data.get(lid) or {}, book[lid]
        if not d or (e['simple'] is None and e['complex'] is None):
            continue
        m = d.get('m') or {}
        mo = m.get(REFERENCE) or {}
        verdict = CR.evaluate(norm, {'m': m, 'avg_volume': d.get('avg_volume_3m')})
        factor = to_eur_factor(d.get('currency'), rates)
        price = _num(d.get('price'))
        if price is None:
            price = _num(d.get('close_px'))
        up = _num((d.get('x') or {}).get('up_fraction'))
        spike = _num((d.get('x') or {}).get('spike_share'))
        perf = {k: _num((m.get(n) or {}).get('perf')) for k, n in WINDOWS.items()}
        quality = QUALITY.get(d.get('quality'))
        extra = {'up_fraction': None if up is None else round(100 * up, 3), 'gain_share': None if spike is None else round(100 * spike, 3), 'quality': quality,
                 'coverage': None if d.get('coverage_252') is None else round(100 * float(d['coverage_252']), 3)}
        rows.append({
            'id': lid, 'symbol': d['symbol'], 'name': d['name'], 'mic': d['mic'], 'currency': d.get('currency'), 'kind': d['kind'], 'isin': d.get('isin'),
            'country': d.get('country'), 'category': d.get('category'),
            'group': {'country': classify(groups, 'country', d.get('country')), 'market': classify(groups, 'market', d['mic']),
                      'sector': classify(groups, 'sector', d.get('category'), d['kind']), 'asset': 'asset:' + d['kind']},
            'price': None if price is None else round(price, 4), 'price_eur': None if price is None or not factor else round(price * factor, 4), 'price_time': d['price_time'].isoformat() if d.get('price_time') else None,
            'last_close': d['last_close_date'].isoformat() if d.get('last_close_date') else None, 'change': _num(d.get('daily_change')),
            'periods': {str(n): {'slope': _num(v.get('slope')), 'r2': _num(v.get('r2'))} for n, v in m.items() if n > 1},
            'slope': _num(mo.get('slope')), 'r2': _num(mo.get('r2')), 'perf': perf, 'volatility': _num(mo.get('volatility')), 'drawdown': _num(mo.get('drawdown')),
            'turnover_eur': _num(d.get('turnover_eur')), 'liquidity_source': d.get('liquidity_source'), 'avg_volume': _num(d.get('avg_volume_3m')),
            'analyst': d.get('analyst_rating'), 'quality': d.get('quality'),
            'simple': _num(e['simple']), 'complex': _num(e['complex']), 'simple_status': e['simple_status'], 'complex_status': e['complex_status'],
            'rank_simple': rank_s.get(lid), 'rank_complex': rank_c.get(lid), 'pos_simple': pos_s.get(lid), 'pos_complex': pos_c.get(lid),
            'status': verdict['status'], 'tie_simple': tie_s.get(rank_s.get(lid), 1), 'tie_complex': tie_c.get(rank_c.get(lid), 1), 'curve': [round(x, 2) for x in curves.get(lid, [])], 'extra': extra})
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM v_recommendable')
        universe = int(cur.fetchone()['n'])
    counts = CR.counts(r['status'] for r in rows)
    return {'strategy': name, 'label': scores_admin.spec(name)['label'], 'counts': counts, 'context': 'missing' if norm is None else 'ok', 'reference_sessions': REFERENCE, 'universe': universe, 'evaluated': len(rows),
            'scored': {'simple': len(simple), 'complex': len(complex_)}, 'default_sort': 'complex', 'rows': rows}      # tri par défaut systématique : score complexe


def curves(conn, request):
    """Courbes des seuls titres visibles, bornées à une page ; ne charge ni notes ni critères."""
    ids = request.get('ids')
    if not isinstance(ids, list) or len(ids) > 100 or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError('Une page de 100 identifiants de titres maximum est requise')
    return {'curves': scores_admin.series(conn, list(dict.fromkeys(ids)), REFERENCE) if ids else {}}
