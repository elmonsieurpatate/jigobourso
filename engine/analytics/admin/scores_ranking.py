"""Classement et simulation des scores pour l'administration : livre de scores, aperçu, listes paginées, courbes et statuts."""
from engine.shared import settings
from ..scoring import criteria as _CR
from ..explorer import explorer_config as C
from ..scoring import score_categories
from ..scoring import score_service
from ..scoring import scores as SC
from .scores_specs import CT_BUILTIN, SCORING_PERIODS, known, refresh
from .scores_profiles import TUNING_DEFAULTS, build_config

def _titles(conn, ids):
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(f"""SELECT l.id, l.symbol, l.mic, i.name, i.kind, i.isin, s.daily_change FROM listings l JOIN instruments i ON i.id=l.instrument_id
                        LEFT JOIN series_state s ON s.listing_id=l.id WHERE l.id IN ({','.join(['%s'] * len(ids))})""", list(ids))
        return {r['id']: r for r in cur.fetchall()}


def _search(conn, q):
    like = '%' + q.replace('%', '').replace('_', '') + '%'
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id FROM listings l JOIN instruments i ON i.id=l.instrument_id JOIN v_recommendable r ON r.listing_id=l.id
                       WHERE l.symbol LIKE %s OR i.name LIKE %s OR i.isin=%s ORDER BY (l.symbol=%s) DESC, i.name LIMIT 8""", (like, like, q.upper(), q.upper()))
        return [r['id'] for r in cur.fetchall()]


def simulate(conn, request):
    """Décomposition des deux scores d'un titre réel avec la configuration enregistrée ou un brouillon. Aucune donnée n'est inventée : sans données, la réponse le dit."""
    refresh(conn)
    from . import universe_verdicts
    name = request.get('strategy')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    book = score_service.score_book(conn, cfg, universe_verdicts.data_version(conn))
    eq = score_service.params_for(cfg, 'equity')
    gran = _granularity(eq)
    meta = {'granularity': gran, 'periods': [dict(id=p['id'], sessions=p['sessions']) for p in eq['periods']]}
    if not book:
        return {'empty': True, 'reason': 'Aucun titre noté : les mesures de score sont vides (calcul nocturne non exécuté sur cette base).', 'suggestions': [], 'candidates': []}
    lid = request.get('listing_id')
    candidates = []
    q = (request.get('q') or '').strip()
    if lid is None and q:
        found = [i for i in _search(conn, q) if i in book]
        info = _titles(conn, found)
        candidates = [dict(id=i, symbol=info[i]['symbol'], mic=info[i]['mic'], name=info[i]['name']) for i in found if i in info]
        lid = candidates[0]['id'] if candidates else None
        if lid is None:
            return {'empty': False, 'not_found': True, 'candidates': [], 'suggestions': _suggestions(conn, book, sessions=gran), **meta}
    if lid is None:
        return {'empty': False, 'candidates': [], 'suggestions': _suggestions(conn, book, sessions=gran), **meta}
    lid = int(lid)
    scored = score_service.details(conn, cfg, [lid]).get(lid)
    info = _titles(conn, [lid]).get(lid)
    if scored is None or info is None:
        return {'empty': False, 'not_found': True, 'candidates': candidates, 'suggestions': _suggestions(conn, book, sessions=gran), **meta}
    params = score_service.params_for(cfg, info['kind'])
    return {'empty': False, 'title': dict(id=lid, symbol=info['symbol'], mic=info['mic'], name=info['name'], kind=info['kind'], isin=info['isin']),
            'candidates': candidates, 'result': scored, 'periods': [dict(id=p['id'], sessions=p['sessions']) for p in params['periods']],
            'kappa': params['kappa'], 'tuning': {k: params[k] for k in TUNING_DEFAULTS}, 'suggestions': _suggestions(conn, book, sessions=gran),
            'curve': dated_series(conn, lid, max(CURVE_SESSIONS, _granularity(params))),
            'windows': [dict(id=x, sessions=C.SESSIONS[x], active=any(q['id'] == x for q in params['periods'])) for x in SCORING_PERIODS if x != 'day' and C.SESSIONS[x] <= max(CURVE_SESSIONS, _granularity(params))], 'granularity': _granularity(params), 'ranks': _rank_of(book, lid)}


def _rank_of(book, lid):
    """Rang général du titre pour chaque score, sur l'ensemble des titres notés."""
    out = {}
    for key in ('simple', 'complex'):
        ranks = _ranks(book, key)
        out[key] = {'rank': ranks.get(lid), 'of': len(ranks)}
    return out


def _suggestions(conn, book, n=8, sessions=0):
    """Titres les mieux notés (score simple), avec leurs deux scores, leur rang et leur courbe."""
    ranks = _ranks(book, 'simple')
    top = ordered(book, 'simple')[0][:n]
    info = _titles(conn, [e['id'] for e in top])
    curves = series(conn, [e['id'] for e in top], sessions)
    return [dict(id=e['id'], symbol=info[e['id']]['symbol'], mic=info[e['id']]['mic'], name=info[e['id']]['name'], simple=e['simple'], complex=e['complex'],
                 rank=ranks.get(e['id']), curve=curves.get(e['id'], []))
            for e in top if e['id'] in info]


BUCKETS = 10


def _distribution(values):
    """Histogramme en 10 tranches de 10 points et quantiles d'une liste de notes."""
    hist = [0] * BUCKETS
    for v in values:
        hist[min(BUCKETS - 1, int(v // (100 / BUCKETS)))] += 1
    vals = sorted(values)
    def q(f):
        return None if not vals else round(vals[min(len(vals) - 1, int(f * len(vals)))], 2)
    return {'histogram': hist, 'min': q(0), 'p25': q(0.25), 'median': q(0.5), 'p75': q(0.75), 'p90': q(0.9), 'max': None if not vals else round(vals[-1], 2)}


def _book_summary(book, threshold, universe):
    """Ce que le moteur produit : combien de titres sont notés et classés, combien sont indisponibles (et pourquoi), comment les notes se répartissent."""
    out = {'universe': universe, 'with_inputs': len(book)}
    for key in ('simple', 'complex'):
        rated = [e[key] for e in book.values() if e[key] is not None]
        statuses = {'ok': 0, 'partiel': 0, 'inconnu': 0}
        unreliable = 0
        for e in book.values():
            statuses[e[key + '_status']] = statuses.get(e[key + '_status'], 0) + 1
            if e[key] is not None and (e[key + '_coverage'] or 0) < threshold - 1e-12:
                unreliable += 1
        out[key] = {'rated': len(rated), 'ranked': len(rated), 'unavailable': universe - len(rated), 'complete': statuses['ok'], 'reduced_history': statuses['partiel'],
                    'unreliable': unreliable, 'distribution': _distribution(rated)}
    reasons = {}
    for e in book.values():
        if e['simple'] is None or e['complex'] is None:
            why = e.get('why') or 'raison non renseignée'
            reasons[why] = reasons.get(why, 0) + 1
    out['unavailable_reasons'] = sorted(({'reason': k, 'count': v} for k, v in reasons.items()), key=lambda x: -x['count'])[:6]
    out['no_inputs'] = max(0, universe - len(book))
    return out


def ordered(book, key):
    """Source unique de l'ordre et des rangs d'un score (simple ou complexe) : (entrées triées, {id: rang}, {id: position}).
    Ordre : score décroissant, puis l'autre score, puis l'identifiant. Rang commun uniquement pour des scores bruts strictement identiques."""
    other = 'complex' if key == 'simple' else 'simple'
    order, ranks = SC.rank_order({l: e[key] for l, e in book.items()}, {l: e[other] for l, e in book.items()})
    return [book[l] for l in order], ranks, {l: i for i, l in enumerate(order, 1)}


def _ranks(book, key):
    return ordered(book, key)[1]


def _movement(saved, draft, key, top=20):
    """Effet d'un changement de réglage sur le classement général : titres qui bougent, entrées / sorties du haut du classement."""
    a, b = _ranks(saved, key), _ranks(draft, key)
    both = [l for l in b if l in a]
    shifts = sorted(abs(a[l] - b[l]) for l in both)
    ta, tb = {l for l, r in a.items() if r <= top}, {l for l, r in b.items() if r <= top}
    return {'compared': len(both), 'median_shift': shifts[len(shifts) // 2] if shifts else 0, 'moved_over_10': sum(1 for x in shifts if x > 10),
            'top': top, 'top_kept': len(ta & tb), 'top_entered': len(tb - ta), 'top_left': len(ta - tb),
            'score_changed': sum(1 for l in both if abs((saved[l][key] or 0) - (draft[l][key] or 0)) > 0.005)}


def _top(conn, book, key, n=10):
    entries, ranks, _ = ordered(book, key)
    ranked = entries[:n]
    info = _titles(conn, [e['id'] for e in ranked])
    return [dict(rank=ranks[e['id']], id=e['id'], symbol=info[e['id']]['symbol'], name=info[e['id']]['name'], score=e[key], other=e['complex' if key == 'simple' else 'simple'],
                 status=e[key + '_status']) for e in ranked if e['id'] in info]


PAGE = 25


CURVE_SESSIONS = max(C.SESSIONS[p] for p in C.PERIODS if p in ('week', 'month', 'quarter'))   # la courbe de simulation couvre la plus longue granularité de notation


CATEGORY_FILE = 'app/config/explorer_secondary_filters.json'


def _definitions(conn):
    """Définitions des filtres de l'administration (réglages), sinon fichier livré avec l'application. Lecture seule."""
    import json
    import os
    d = settings.get(conn, score_categories.SETTING)
    if isinstance(d, dict) and d.get('filters'):
        return d
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), CATEGORY_FILE)
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'filters': []}


def _closes(conn, ids, sessions):
    """Dernières clôtures sur la même base ajustée que la fiche et les performances."""
    from ..series.series import prepare_series
    ids = list(ids)
    out = {i: [] for i in ids}
    if not ids or sessions < 1:
        return out
    import datetime
    since = datetime.date.today() - datetime.timedelta(days=int(sessions * 2 + 10))
    with conn.cursor() as cur:
        for k in range(0, len(ids), 200):
            part = ids[k:k + 200]
            marks = ','.join(['%s'] * len(part))
            cur.execute(f"""SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices
                            WHERE listing_id IN ({marks}) AND price_date>=%s
                            ORDER BY listing_id, price_date""", part + [since])
            bars = {i: [] for i in part}
            for r in cur.fetchall():
                bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']) if r['close_px'] is not None else None,
                                             float(r['adj_close_px']) if r['adj_close_px'] is not None else None))
            cur.execute(f"""SELECT listing_id, event_date, ratio FROM corporate_events
                            WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split') AND event_date>=%s
                            ORDER BY event_date""", part + [since])
            splits = {i: [] for i in part}
            for r in cur.fetchall():
                splits[r['listing_id']].append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
            for lid in part:
                dates, closes, _, _ = prepare_series(bars[lid], splits[lid])
                out[lid] = list(zip(dates, closes))[-(sessions + 1):]
    return out


def series(conn, ids, sessions):
    """Dernières clôtures (sessions + 1 points) de chaque titre : petites courbes du classement. Un titre sans historique n'a pas de courbe (liste vide)."""
    return {i: [round(px, 4) for _, px in v] for i, v in _closes(conn, ids, sessions).items()}


def dated_series(conn, lid, sessions):
    """Courbe détaillée d'un titre : date ISO et cours de chaque séance, pour l'infobulle de la simulation."""
    return [{'d': d.isoformat() if hasattr(d, 'isoformat') else str(d), 'p': round(px, 4)} for d, px in _closes(conn, [lid], sessions).get(lid, [])]


def _granularity(params):
    return max((p['sessions'] for p in params['periods']), default=0)


SORT_KEYS = ('rank', 'simple', 'complex', 'name', 'status', 'kind', 'market', 'change')


STATUS_ORDER = {'retained': 0, 'undetermined': 1, 'excluded': 2}


def _sorted(conn, entries, sort, key, rank_of, statuses):
    """Tri complet de la liste (pas seulement de la page) : jusqu'à trois critères, valeurs absentes toujours en dernier, repli stable sur l'ordre général du classement puis l'identifiant.
    Le rang affiché reste le rang général : il ne dépend pas de ce tri."""
    info = _titles(conn, [e['id'] for e in entries]) if any(s['key'] in ('name', 'kind', 'market', 'change') for s in sort) else {}
    def value(e, k):
        if k == 'rank':
            return rank_of.get(e['id'])
        if k in ('simple', 'complex'):
            return e[k]
        if k == 'status':
            return STATUS_ORDER.get((statuses or {}).get(e['id'], 'undetermined'))
        t = info.get(e['id']) or {}
        if k == 'change':                                           # Var. 1J : variation entre les deux dernières séances clôturées
            return None if t.get('daily_change') is None else float(t['daily_change'])
        v = {'name': t.get('name'), 'kind': t.get('kind'), 'market': t.get('mic')}[k]
        return None if v is None else str(v).casefold()
    base = {e['id']: i for i, e in enumerate(entries)}
    out = list(entries)
    out.sort(key=lambda e: base[e['id']])
    for s in reversed(sort):                                        # tris successifs stables : le dernier critère est appliqué en premier
        k, desc = s['key'], s['dir'] == 'desc'
        present = [e for e in out if value(e, k) is not None]
        absent = [e for e in out if value(e, k) is None]
        present.sort(key=lambda e: value(e, k), reverse=desc)
        out = present + absent
    return out


def _listing(conn, book, which, category, offset, limit, cats, sessions, statuses=None, verdict='all', sort=None, info_all=None):
    """Classement d'un score, éventuellement restreint à une catégorie de note. Le rang est le rang GÉNÉRAL (sur tous les titres notés) : une catégorie ne le change pas."""
    key = 'simple' if which == 'simple' else 'complex'
    ranked, rank_of, _ = ordered(book, key)
    counts = {c['id']: 0 for c in cats}
    for e in ranked:
        cid = score_categories.assign(e[key], cats)
        if cid in counts:
            counts[cid] += 1
    scoped = [e for e in ranked if category in (None, '') or score_categories.assign(e[key], cats) == category]
    scope_counts = _CR.counts((statuses or {}).get(e['id'], _CR.UNDETERMINED) for e in scoped) if statuses is not None else None
    chosen = [e for e in scoped if verdict == 'all' or statuses is None or statuses.get(e['id'], _CR.UNDETERMINED) == verdict]
    if sort:
        chosen = _sorted(conn, chosen, sort, key, rank_of, statuses)
    page = chosen[offset:offset + limit]
    info = _titles(conn, [e['id'] for e in page])
    curves = series(conn, [e['id'] for e in page], sessions)
    rows = [dict(rank=rank_of[e['id']], id=e['id'], symbol=info[e['id']]['symbol'], mic=info[e['id']]['mic'], name=info[e['id']]['name'], kind=info[e['id']]['kind'],
                 status=(statuses or {}).get(e['id']), change=None if info[e['id']].get('daily_change') is None else round(float(info[e['id']]['daily_change']), 4), simple=e['simple'], complex=e['complex'], simple_status=e['simple_status'], complex_status=e['complex_status'],
                 coverage=e[key + '_coverage'], curve=curves.get(e['id'], [])) for e in page if e['id'] in info]
    return {'which': key, 'category': category or None, 'verdict': verdict, 'counts': scope_counts, 'total': len(chosen), 'offset': offset, 'rows': rows,
            'categories': [dict(id=c['id'], name=c['name'], color=c.get('color'), min=c.get('min'), max=c.get('max'), minIncluded=c.get('minIncluded'), maxIncluded=c.get('maxIncluded'),
                                count=counts.get(c['id'], 0)) for c in cats if not c.get('unknown')]}


def _ct_id(name):
    """Identifiant du Classement correspondant à une stratégie V4 (intégrée ou personnelle `ct:<utilisateur>:<id>`), ou None."""
    for ct_id, n in CT_BUILTIN.items():
        if n == name:
            return ct_id
    parts = name.split(':')
    return parts[2] if len(parts) == 3 and parts[0] == 'ct' else None


def _statuses(conn, book, name, request):
    """Statut de stratégie (critères de recherche) de chaque titre noté : même moteur que le Classement et la fiche. Ne touche ni scores ni rangs."""
    from ..scoring import ranking_table
    ct_id = _ct_id(name)
    spec = (request.get('ct_specs') or {}).get(ct_id) if ct_id else None
    norm = ranking_table.norm_of({'ct_id': ct_id, 'spec': spec})
    ids = ranking_table.evaluable(book)
    data = ranking_table._fetch(conn, ids) if ids else {}
    out = {i: _CR.evaluate(norm, {'m': (data.get(i) or {}).get('m'), 'avg_volume': (data.get(i) or {}).get('avg_volume_3m')})['status'] for i in ids}
    return out, ('missing' if norm is None else 'ok')


def ranking(conn, request):
    """Résultat principal d'un réglage : titres notés et classés, indisponibles, répartition des notes, poids réels des périodes et effet par rapport au réglage enregistré.
    Aucun filtre n'intervient : les seuils facultatifs ne retirent aucun titre de ce classement."""
    refresh(conn)
    from . import universe_verdicts
    name = request.get('strategy')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    version = universe_verdicts.data_version(conn)
    book = score_service.score_book(conn, cfg, version)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM v_recommendable')
        universe = int(cur.fetchone()['n'])
    params = score_service.params_for(cfg, 'equity')
    weights = SC.resolve_weights(params['periods'], params['kappa'])
    out = {'strategy': name, 'engine_version': SC.VERSION, 'summary': _book_summary(book, params['threshold'], universe),
           'weights': [dict(id=p['id'], sessions=p['sessions'], weight=weights[p['id']], custom='weight' in p) for p in params['periods']],
           'kappa': params['kappa'], 'reliability_threshold': params['threshold'],
           'top': {k: _top(conn, book, k) for k in ('simple', 'complex')}, 'compared': None}
    which = 'complex' if request.get('which') == 'complex' else 'simple'
    cats, _ = score_categories.measure(_definitions(conn), which)
    sessions = _granularity(params)
    cat = request.get('category')
    off = max(0, int(request.get('offset') or 0))
    lim = max(1, min(100, int(request.get('limit') or PAGE)))
    out['granularity'] = {'sessions': sessions, 'periods': [dict(id=p['id'], sessions=p['sessions']) for p in params['periods']]}
    statuses, context = _statuses(conn, book, name, request)
    sort = [x for x in (request.get('sort') or []) if isinstance(x, dict) and x.get('key') in SORT_KEYS and x.get('dir') in ('asc', 'desc')][:3]
    verdict = request.get('verdict') if request.get('verdict') in (_CR.RETAINED, _CR.EXCLUDED, _CR.UNDETERMINED) else 'all'
    out['listing'] = _listing(conn, book, which, cat if isinstance(cat, str) else None, off, lim, cats, sessions, statuses, verdict, sort)
    out['listing']['context'] = context
    if draft:
        saved_book = score_service.score_book(conn, build_config(conn, name), version)
        out['compared'] = {k: _movement(saved_book, book, k) for k in ('simple', 'complex')}
    return out
