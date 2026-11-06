"""Scores V4 de tout l'univers : lecture des mesures stockées, calcul titre par titre, cache, rangs.

Garanties (testées) :
  * un score ne dépend que des mesures du titre et des paramètres de score (granularités actives, poids, κ, seuil de couverture) ;
  * ni les filtres de conformité, ni les seuils de la stratégie, ni la population affichée n'y entrent ; la clé de cache les ignore aussi ;
  * le rang « global » est le rang parmi TOUS les titres notés du même groupe (actions / ETF), pas parmi les titres retenus.
"""
import datetime
import hashlib
import json
from collections import defaultdict

from . import explorer_config as C, scores as SC

CACHE_FORMAT = 1
FIELDS = ('id', 'simple', 'simple_status', 'simple_coverage', 'complex', 'complex_status', 'complex_coverage', 'why')


def v4(config):
    return config if config.get('version') == 4 else C.upgrade(config)


def is_scores_mode(config):
    return config.get('version') == 4 and config['ranking']['mode'] == C.SCORES_MODE


def params_for(config, kind):
    """Paramètres de score d'un type (action / ETF) : granularités ACTIVES de ce type (≥ 3 séances), obligatoires, poids, κ, seuil."""
    cfg = C.effective(v4(config), kind)
    sc = cfg.get('scoring') or C.validate_scoring(None, cfg['periods'])
    active = [dict(id=p['id'], sessions=p['sessions']) for p in cfg['periods'] if p['enabled'] and p['sessions'] >= SC.MIN_SESSIONS]
    custom = sc['weights']
    if custom and active and all(custom.get(p['id']) is not None for p in active):
        for p in active:
            p['weight'] = float(custom[p['id']])
    return {'periods': active, 'required': [p['id'] for p in cfg['periods'] if p['enabled'] and p.get('require_history') and p['sessions'] >= SC.MIN_SESSIONS],
            'kappa': float(sc['kappa']), 'complex_weights': {k: float(v) for k, v in dict(SC.COMPLEX_WEIGHTS, **sc['complex_weights']).items()}, 'threshold': float(sc['threshold']), 'anchor': float(sc.get('anchor', SC.ANCHOR_LAMBDA))}


def _f(v):
    return None if v is None else float(v)


def load_inputs(conn, sessions, ids=None):
    """Mesures stockées des titres recommandables : {id: {'kind','mic','inputs': {sessions: mesures}, 'liquidity': {...}}}."""
    scope = ''
    args = []
    if ids:
        scope = f' AND r.listing_id IN ({",".join(["%s"] * len(ids))})'
        args = list(ids)
    out = {}
    with conn.cursor() as cur:
        cur.execute(f"""SELECT r.listing_id, i.kind, l.mic, ls.turnover_eur, ls.source, ls.days FROM v_recommendable r JOIN listings l ON l.id=r.listing_id
                        JOIN instruments i ON i.id=l.instrument_id LEFT JOIN liquidity_state ls ON ls.listing_id=r.listing_id WHERE 1=1{scope}""", args)
        for r in cur.fetchall():
            out[r['listing_id']] = {'kind': 'etf' if r['kind'] == 'etf' else 'equity', 'mic': r['mic'], 'inputs': {},
                                    'liquidity': {'turnover_eur': _f(r['turnover_eur']), 'source': r['source'], 'days': r['days']}}
        if sessions:
            marks = ','.join(['%s'] * len(sessions))
            cur.execute(f"""SELECT m.listing_id, m.sessions, m.slope, m.r2, m.volatility, m.drawdown, m.coverage, x.up_fraction, x.spike_share, x.accel, x.r2_prev
                            FROM strategy_metrics m JOIN v_recommendable r ON r.listing_id=m.listing_id LEFT JOIN score_inputs x ON x.listing_id=m.listing_id AND x.sessions=m.sessions
                            WHERE m.sessions IN ({marks}){scope}""", list(sessions) + args)
            for r in cur.fetchall():
                if r['listing_id'] in out:
                    out[r['listing_id']]['inputs'][r['sessions']] = {k: _f(r[k]) for k in ('slope', 'r2', 'volatility', 'drawdown', 'coverage', 'up_fraction', 'spike_share', 'accel', 'r2_prev')}
    return out


def _score_all(data, config):
    params = {k: params_for(config, k) for k in ('equity', 'etf')}
    result = {}
    for lid, d in data.items():
        p = params[d['kind']]
        result[lid] = SC.score_title(d['inputs'], d['liquidity'], p['periods'], kappa=p['kappa'], required=p['required'], threshold=p['threshold'], complex_weights=p['complex_weights'], anchor=p['anchor'])
    return result


def _key(config, version):
    # `required` (périodes obligatoires) et `threshold` (fiabilité) n'ont plus d'effet sur les notes (V4.2) : ils ne font pas partie de la clé
    payload = {'format': CACHE_FORMAT, 'score_version': SC.VERSION,
               'params': {k: {f: v for f, v in params_for(config, k).items() if f not in ('required', 'threshold')} for k in ('equity', 'etf')}}
    return hashlib.sha1(('scores-v1:' + json.dumps(payload, sort_keys=True, separators=(',', ':'))).encode()).hexdigest()


def score_book(conn, config, data_version):
    """Scores légers de tout l'univers, mis en cache selon les seuls paramètres de score et la version des données."""
    from .service import packed, unpacked
    key = _key(config, data_version)
    with conn.cursor() as cur:
        cur.execute('SELECT data_version, payload FROM result_cache WHERE cache_key=%s', (key,))
        hit = cur.fetchone()
    if hit and hit['data_version'] == data_version:
        return {e[0]: dict(zip(FIELDS, e)) for e in unpacked(hit['payload'])}
    sessions = sorted({p['sessions'] for k in ('equity', 'etf') for p in params_for(config, k)['periods']})
    results = _score_all(load_inputs(conn, sessions), config)
    entries = []
    for lid, r in results.items():
        s, c = r['simple'], r['complex']
        entries.append([lid, _r(s['score']), s['status'], _r(s['coverage'], 4), _r(c['score']), c['status'], _r(c['coverage'], 4), s.get('why') or c.get('why')])
    with conn.cursor() as cur:
        cur.execute('REPLACE INTO result_cache(cache_key, data_version, built_at, payload) VALUES (%s,%s,%s,%s)',
                    (key, data_version, datetime.datetime.utcnow().replace(microsecond=0), packed(entries)))
    conn.commit()
    return {e[0]: dict(zip(FIELDS, e)) for e in entries}


def _r(v, places=4):
    return None if v is None else round(v, places)


def attach(conn, config, entries, data_version):
    """Ajoute à chaque entrée du classement ses deux scores et ses rangs globaux (indépendants des filtres). En mode « scores », score et rang reprennent le score choisi."""
    book = score_book(conn, config, data_version)
    ranks = {}
    for kind in ('equity', 'etf'):
        group = [e for e in entries if e['group'] == kind]
        ranks[('simple', kind)] = SC.rank_positions({e['id']: (book.get(e['id']) or {}).get('simple') for e in group})
        ranks[('complex', kind)] = SC.rank_positions({e['id']: (book.get(e['id']) or {}).get('complex') for e in group})
    mode = is_scores_mode(config)
    choice = config['ranking'].get('sort', 'simple') if mode else None
    for e in entries:
        b = book.get(e['id']) or {}
        e.update(score_simple=b.get('simple'), score_complex=b.get('complex'), score_simple_status=b.get('simple_status', 'inconnu'), score_complex_status=b.get('complex_status', 'inconnu'),
                 score_coverage=b.get('simple_coverage'), score_why=b.get('why'),
                 score_rank_simple=ranks[('simple', e['group'])].get(e['id']), score_rank_complex=ranks[('complex', e['group'])].get(e['id']))
        if mode:
            e['score'] = e['score_simple'] if choice == 'simple' else e['score_complex']
            e['rank'] = e['score_rank_simple'] if choice == 'simple' else e['score_rank_complex']
            e['score_parts'] = []
    return entries


def details(conn, config, ids):
    """Décomposition complète (par granularité, par composante, manquants, liquidité) pour une page de résultats."""
    if not ids:
        return {}
    sessions = sorted({p['sessions'] for k in ('equity', 'etf') for p in params_for(config, k)['periods']})
    return _score_all(load_inputs(conn, sessions, ids), config)


def summary(config, entries):
    """Paramètres effectifs et compteurs de l'univers noté (pour l'interface)."""
    counts = defaultdict(lambda: defaultdict(int))
    for e in entries:
        counts[e['group']]['simple_' + e.get('score_simple_status', 'inconnu')] += 1
        counts[e['group']]['complex_' + e.get('score_complex_status', 'inconnu')] += 1
    params = {k: params_for(config, k) for k in ('equity', 'etf')}
    out = {}
    for kind, p in params.items():
        weights = SC.resolve_weights(p['periods'], p['kappa']) if p['periods'] else {}
        out[kind] = {'periods': [dict(x, weight=weights.get(x['id'])) for x in p['periods']], 'required': p['required'], 'kappa': p['kappa'],
                     'threshold': p['threshold'], 'complex_weights': dict(SC.COMPLEX_WEIGHTS, **p['complex_weights']), 'counts': dict(counts[kind])}
    return out


SETTING = 'scores_v4'


def admin_defaults(conn):
    """Réglages globaux des scores saisis dans l'administration ({kappa, complex_weights, threshold}) ; vide = valeurs de conception."""
    from engine.shared import settings
    raw = settings.get(conn, SETTING, {}) or {}
    return C.validate_scoring(raw, [])


def apply_global(conn, config):
    """Superpose les réglages communs (κ, seuil de couverture, poids complexes hérités) aux paramètres de score restés à leur valeur de conception.
    Une valeur propre à la stratégie (différente de la conception) l'emporte. Ne concerne jamais les seuils de conformité."""
    if config.get('version') != 4:
        return config
    base = C.validate_scoring(None, [])
    admin = admin_defaults(conn)
    sc = dict(config.get('scoring') or base)
    for field in ('kappa', 'threshold', 'complex_weights', 'anchor'):
        if sc.get(field) == base[field]:
            sc[field] = admin[field]
    return dict(config, scoring=sc)


def apply_admin(conn, config):
    """Configuration d'une stratégie avec les réglages d'administration : profil de la stratégie (si V4 et enregistré), puis réglages communs."""
    if config.get('version') != 4:
        return config
    if config.get('ranking', {}).get('mode') == C.SCORES_MODE:
        from . import scores_admin
        if config.get('name') in scores_admin.V4_STRATEGIES:
            prof = scores_admin.stored_profiles(conn).get(config['name'])
            config = scores_admin.apply_profile(config, scores_admin.clean_profile(prof)) if prof else scores_admin.neutral(config)
    return apply_global(conn, config)
