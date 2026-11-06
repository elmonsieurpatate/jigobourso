"""Administration des scores V4 : un seul moteur de notation, des profils de stratégie (granularités, poids, seuils) et le suivi des calculs.

Le moteur (scores.py) n'est jamais modifié ici : l'administration ne règle que des paramètres.
  - `scores_v4`        réglages communs : κ (poids automatiques des périodes) et seuil de couverture ;
  - `scores_profiles`  réglages propres à une stratégie V4 : granularités actives, seuils de conformité, poids des périodes, poids du score complexe.
Les seuils de conformité (pente, R², rendement) filtrent ; ils n'entrent jamais dans une note."""
import copy

from engine.shared import settings

from . import explorer_config as C, score_service, scores as SC

PROFILES = 'scores_profiles'
SCORING_PERIODS = tuple(p for p in C.PERIODS if C.SESSIONS[p] >= SC.MIN_SESSIONS)
THRESHOLDS = {'min_slope': (-100, 100), 'min_r2': (0, 1), 'min_return': (-100, 10000)}
V4_STRATEGIES = {'growth_v1': {'label': 'Croissance rapide (V4)', 'build': C.growth_v1}}
LEGACY_LABELS = {'regular': 'Croissance régulière', 'fast': 'Croissance rapide', 'recovery': 'Rebond', 'low_volatility': 'Hausse calme',
                 'momentum': 'Momentum 6 mois (expérimental)', 'momentum12': 'Momentum 12 mois (expérimental)', 'momentum_risk': 'Momentum ajusté du risque (expérimental)'}
PERIOD_LABELS = {'week': 'Semaine', 'month': 'Mois', 'quarter': 'Trimestre', 'half': 'Semestre', 'year': 'Année'}
TOLERANCE = 0.05


def design():
    return {'kappa': SC.KAPPA, 'threshold': SC.COVERAGE_THRESHOLD, 'complex_weights': dict(SC.COMPLEX_WEIGHTS)}


def formula():
    """Constantes de conception des deux scores (lecture seule : changer une formule est une décision de conception, pas un réglage)."""
    return {'saturation': {'a': SC.SAT_A, 'b': SC.SAT_B}, 'gate_floor': SC.GATE_FLOOR, 'acceleration_amplitude': SC.ACC_AMPLITUDE,
            'reliability_sessions': SC.RELIABILITY_SESSIONS, 'min_sessions': SC.MIN_SESSIONS, 'anchor': SC.ANCHOR_LAMBDA,
            'liquidity_floor_eur': SC.LIQUIDITY_FLOOR_EUR, 'liquidity_ceil_eur': SC.LIQUIDITY_CEIL_EUR}


# ───────────── profils ─────────────

def profile_of(config):
    """Forme éditable d'un profil, lue dans une configuration V4."""
    sc = config.get('scoring') or {}
    weights = sc.get('weights') or {}
    return {'periods': {p['id']: {'sessions': p['sessions'], 'enabled': p['enabled'], 'require_history': p['require_history'],
                                  'min_slope': p['min_slope'], 'min_r2': p['min_r2'], 'min_return': p['min_return']}
                        for p in config['periods'] if p['id'] in SCORING_PERIODS},
            'weights_mode': 'custom' if weights else 'auto', 'weights': dict(weights),
            'complex_weights': dict(SC.COMPLEX_WEIGHTS, **(sc.get('complex_weights') or {}))}


def apply_profile(config, profile):
    """Superpose un profil enregistré à la configuration de base de la stratégie ; le résultat est revalidé."""
    c = copy.deepcopy(config)
    for p in c['periods']:
        pp = (profile.get('periods') or {}).get(p['id'])
        if pp is None or p['id'] not in SCORING_PERIODS:
            continue
        for f in ('enabled', 'require_history'):
            if f in pp:
                p[f] = bool(pp[f])
        for f in THRESHOLDS:
            if f in pp:
                p[f] = pp[f]
    sc = dict(c.get('scoring') or {})
    sc['weights'] = dict(profile.get('weights') or {}) if profile.get('weights_mode') == 'custom' else {}
    if profile.get('complex_weights'):
        sc['complex_weights'] = dict(profile['complex_weights'])
    c['scoring'] = sc
    return C.validate(c)


def clean_profile(raw):
    """Valide un profil saisi dans l'administration. ValueError avec un message lisible."""
    if not isinstance(raw, dict):
        raise ValueError('Profil invalide')
    periods = raw.get('periods') or {}
    out = {'periods': {}}
    for pid in SCORING_PERIODS:
        pp = periods.get(pid)
        if not isinstance(pp, dict):
            raise ValueError(f'Granularité manquante : {PERIOD_LABELS[pid]}')
        item = {'enabled': bool(pp.get('enabled')), 'require_history': bool(pp.get('require_history'))}
        for f, (lo, hi) in THRESHOLDS.items():
            item[f] = C.number(pp.get(f), lo, hi, f'{PERIOD_LABELS[pid]} : {f}')
        out['periods'][pid] = item
    active = [pid for pid in SCORING_PERIODS if out['periods'][pid]['enabled']]
    if not active:
        raise ValueError('Au moins une granularité doit rester active')
    mode = raw.get('weights_mode', 'auto')
    if mode not in ('auto', 'custom'):
        raise ValueError('Mode de pondération inconnu')
    out['weights_mode'] = mode
    out['weights'] = {}
    if mode == 'custom':
        weights = raw.get('weights') or {}
        vals = {pid: C.number(weights.get(pid), 0, 100, f'Poids {PERIOD_LABELS[pid]}') for pid in active}
        if any(v is None for v in vals.values()):
            raise ValueError('Chaque granularité active doit avoir un poids')
        if abs(sum(vals.values()) - 100) > TOLERANCE:
            raise ValueError(f'Le total des poids des périodes doit faire 100 % (actuellement {sum(vals.values()):g} %)')
        out['weights'] = vals
    cw = raw.get('complex_weights') or {}
    if set(cw) != set(SC.COMPLEX_WEIGHTS):
        raise ValueError('Poids du score complexe incomplets')
    cw = {k: C.number(v, 0, 100, 'Poids du score complexe') for k, v in cw.items()}
    if any(v is None for v in cw.values()):
        raise ValueError('Poids du score complexe invalides')
    if abs(sum(cw.values()) - 100) > TOLERANCE:
        raise ValueError(f'Le total des poids du score complexe doit faire 100 % (actuellement {sum(cw.values()):g} %)')
    out['complex_weights'] = cw
    return out


def stored_profiles(conn):
    return settings.get(conn, PROFILES, {}) or {}


def base_config(name):
    return V4_STRATEGIES[name]['build']()


def build_config(conn, name, profile=None, glob=None):
    """Configuration effective d'une stratégie V4. `profile` / `glob` : brouillon non enregistré (simulation) ; absents : réglages enregistrés."""
    cfg = base_config(name)
    prof = profile if profile is not None else stored_profiles(conn).get(name)
    if prof:
        cfg = apply_profile(cfg, clean_profile(prof))
    cfg = score_service.apply_global(conn, cfg) if glob is None else _with_global(cfg, glob)
    return cfg


def _with_global(config, glob):
    g = C.validate_scoring({k: glob.get(k) for k in ('kappa', 'threshold')}, [])
    return dict(config, scoring=dict(config['scoring'], kappa=g['kappa'], threshold=g['threshold']))


def auto_weights(kappa, period_ids):
    """Poids automatiques (en %) d'un jeu de granularités actives pour un κ donné."""
    k = C.validate_scoring({'kappa': kappa}, [])['kappa']
    ids = [p for p in SCORING_PERIODS if p in period_ids]
    if not ids:
        return {}
    w = SC.resolve_weights([{'id': p, 'sessions': C.SESSIONS[p]} for p in ids], k)
    return {p: 100 * w[p] for p in ids}


# ───────────── état et enregistrement ─────────────

def strategies(conn):
    from . import strategy
    glob = score_service.admin_defaults(conn)
    stored = stored_profiles(conn)
    out = []
    for name, spec in V4_STRATEGIES.items():
        base = base_config(name)
        cfg = build_config(conn, name)
        current = profile_of(cfg)
        active = [p for p in SCORING_PERIODS if current['periods'][p]['enabled']]
        auto = auto_weights(glob['kappa'], active)
        out.append({'name': name, 'label': spec['label'], 'engine': 'v4', 'sort': cfg['ranking'].get('sort'), 'defaults': profile_of(base), 'current': current,
                    'customised': name in stored, 'auto_weights': auto, 'saved_at': _iso(settings.saved_at(conn, PROFILES)) if name in stored else None})
    for name in strategy.PRESETS:
        cfg = C.editable(strategy.preset(name))
        comps = [dict(id=c['id'], metric=c['metric'], period=c['period'], weight=c['weight']) for c in (cfg['ranking'].get('components') or []) if c.get('enabled', True) and c.get('weight')]
        out.append({'name': name, 'label': LEGACY_LABELS.get(name, name), 'engine': 'historic', 'periods': [p['id'] for p in cfg['periods'] if p['enabled']], 'components': comps})
    return out


def _iso(v):
    import datetime
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=' ')
    return v.isoformat() if isinstance(v, datetime.date) else v


def state(conn):
    cur = score_service.admin_defaults(conn)
    stored = settings.get(conn, score_service.SETTING, None)
    return {'design': design(), 'formula': formula(), 'version': SC.VERSION, 'period_labels': PERIOD_LABELS, 'scoring_periods': list(SCORING_PERIODS),
            'global': {'kappa': cur['kappa'], 'threshold': cur['threshold'], 'customised': bool(stored), 'saved_at': _iso(settings.saved_at(conn, score_service.SETTING)) if stored else None},
            'strategies': strategies(conn), 'volume_collection': bool(settings.get(conn, 'volume_collection', False))}


def save(conn, request):
    """Enregistre les réglages communs et/ou le profil d'une stratégie V4 ; `reset` : 'global', 'profile' (avec `name`) ou 'all'."""
    reset = request.get('reset')
    if reset in ('global', 'all'):
        settings.put(conn, score_service.SETTING, {})
    if reset in ('profile', 'all'):
        profiles = stored_profiles(conn)
        if reset == 'profile':
            name = request.get('name')
            if name not in V4_STRATEGIES:
                raise ValueError('Stratégie V4 inconnue')
            profiles.pop(name, None)
        else:
            profiles = {}
        settings.put(conn, PROFILES, profiles)
    if reset:
        return state(conn)
    if isinstance(request.get('global'), dict):
        g = request['global']
        clean = C.validate_scoring({k: g.get(k) for k in ('kappa', 'threshold')}, [])
        settings.put(conn, score_service.SETTING, {'kappa': clean['kappa'], 'threshold': clean['threshold']})
    elif any(k in request for k in ('kappa', 'threshold', 'complex_weights')):       # ancienne forme (réglages communs seuls)
        clean = C.validate_scoring({k: request.get(k) for k in ('kappa', 'threshold', 'complex_weights')}, [])
        if not any(clean['complex_weights'].get(k, SC.COMPLEX_WEIGHTS[k]) > 0 for k in SC.COMPLEX_WEIGHTS):
            raise ValueError('Le score complexe doit garder au moins un poids positif')
        settings.put(conn, score_service.SETTING, clean)
    if isinstance(request.get('profile'), dict):
        name = request['profile'].get('name')
        if name not in V4_STRATEGIES:
            raise ValueError('Stratégie V4 inconnue')
        clean = clean_profile(request['profile'])
        apply_profile(base_config(name), clean)                                   # revalidation complète de la configuration résultante
        profiles = stored_profiles(conn)
        profiles[name] = clean
        settings.put(conn, PROFILES, profiles)
    return state(conn)


def preview(conn, request):
    ids = [p for p in (request.get('periods') or []) if p in SCORING_PERIODS]
    return {'weights': auto_weights(request.get('kappa', SC.KAPPA), ids)}


# ───────────── simulation ─────────────

def _titles(conn, ids):
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(f"""SELECT l.id, l.symbol, l.mic, i.name, i.kind, i.isin FROM listings l JOIN instruments i ON i.id=l.instrument_id
                        WHERE l.id IN ({','.join(['%s'] * len(ids))})""", list(ids))
        return {r['id']: r for r in cur.fetchall()}


def _search(conn, q):
    like = '%' + q.replace('%', '').replace('_', '') + '%'
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id FROM listings l JOIN instruments i ON i.id=l.instrument_id JOIN v_recommendable r ON r.listing_id=l.id
                       WHERE l.symbol LIKE %s OR i.name LIKE %s OR i.isin=%s ORDER BY (l.symbol=%s) DESC, i.name LIMIT 8""", (like, like, q.upper(), q.upper()))
        return [r['id'] for r in cur.fetchall()]


def simulate(conn, request):
    """Décomposition des deux scores d'un titre réel avec la configuration enregistrée ou un brouillon. Aucune donnée n'est inventée : sans données, la réponse le dit."""
    from . import service
    name = request.get('strategy')
    if name not in V4_STRATEGIES:
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    book = score_service.score_book(conn, cfg, service.data_version(conn))
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
            return {'empty': False, 'not_found': True, 'candidates': [], 'suggestions': _suggestions(conn, book)}
    if lid is None:
        return {'empty': False, 'candidates': [], 'suggestions': _suggestions(conn, book)}
    lid = int(lid)
    scored = score_service.details(conn, cfg, [lid]).get(lid)
    info = _titles(conn, [lid]).get(lid)
    if scored is None or info is None:
        return {'empty': False, 'not_found': True, 'candidates': candidates, 'suggestions': _suggestions(conn, book)}
    params = score_service.params_for(cfg, info['kind'])
    return {'empty': False, 'title': dict(id=lid, symbol=info['symbol'], mic=info['mic'], name=info['name'], kind=info['kind'], isin=info['isin']),
            'candidates': candidates, 'result': scored, 'periods': [dict(id=p['id'], sessions=p['sessions']) for p in params['periods']],
            'kappa': params['kappa'], 'suggestions': _suggestions(conn, book)}


def _suggestions(conn, book, n=8):
    top = sorted((e for e in book.values() if e['simple'] is not None), key=lambda e: -e['simple'])[:n]
    info = _titles(conn, [e['id'] for e in top])
    return [dict(id=e['id'], symbol=info[e['id']]['symbol'], mic=info[e['id']]['mic'], name=info[e['id']]['name'], simple=e['simple'], complex=e['complex'])
            for e in top if e['id'] in info]


# ───────────── suivi des calculs ─────────────

def coverage(conn):
    """Origine de la liquidité des titres notés : volumes quotidiens réels, estimation (proxy) ou inconnue."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM v_recommendable")
        total = int(cur.fetchone()['n'])
        cur.execute("SELECT source, COUNT(*) AS n, MAX(computed_at) AS at, MAX(volume_checked_at) AS checked FROM liquidity_state GROUP BY source")
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS n FROM score_inputs")
        inputs = int(cur.fetchone()['n'])
    by = {r['source']: int(r['n']) for r in rows}
    known = by.get('daily', 0) + by.get('estimated', 0)
    return {'universe': total, 'daily': by.get('daily', 0), 'estimated': by.get('estimated', 0), 'unknown': max(0, total - known),
            'computed_at': _iso(max((r['at'] for r in rows if r['at']), default=None)), 'volume_checked_at': _iso(max((r['checked'] for r in rows if r['checked']), default=None)), 'score_inputs': inputs}


def monitor(conn):
    """Suivi : titres notés, couverture, fraîcheur des données, origine de la liquidité, dernières erreurs de calcul."""
    from . import service
    cfg = build_config(conn, 'growth_v1')
    book = score_service.score_book(conn, cfg, service.data_version(conn))
    counts = {'simple': {'ok': 0, 'partiel': 0, 'inconnu': 0}, 'complex': {'ok': 0, 'partiel': 0, 'inconnu': 0}}
    covs = []
    for e in book.values():
        counts['simple'][e['simple_status']] = counts['simple'].get(e['simple_status'], 0) + 1
        counts['complex'][e['complex_status']] = counts['complex'].get(e['complex_status'], 0) + 1
        if e['simple_coverage'] is not None:
            covs.append(e['simple_coverage'])
    covs.sort()
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(last_close_date) AS last_close, MAX(computed_at) AS computed_at FROM series_state")
        fresh = cur.fetchone() or {}
        stale = 0
        if fresh.get('last_close'):
            cur.execute("SELECT COUNT(*) AS n FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id WHERE s.last_close_date < DATE_SUB(%s, INTERVAL 5 DAY)", (fresh['last_close'],))
            stale = int(cur.fetchone()['n'])
        cur.execute("""SELECT id, job_type, status, started_at, finished_at, items_error, summary FROM jobs WHERE job_type IN ('maintenance','metrics')
                       ORDER BY started_at DESC LIMIT 12""")
        jobs = cur.fetchall()
    last_ok = next((j for j in jobs if j['status'] in ('completed', 'completed_with_errors')), None)
    problems = [dict(id=j['id'], type=j['job_type'], status=j['status'], at=_iso(j['started_at']), errors=int(j['items_error'] or 0), summary=j['summary']) for j in jobs
                if j['status'] in ('failed', 'interrupted', 'completed_with_errors')][:5]
    return {'rated': len(book), 'counts': counts, 'coverage': {'median': covs[len(covs) // 2] if covs else None, 'min': covs[0] if covs else None, 'full': sum(1 for c in covs if c >= 0.999)},
            'freshness': {'last_close': _iso(fresh.get('last_close')), 'computed_at': _iso(fresh.get('computed_at')), 'stale_titles': stale},
            'last_success': None if not last_ok else dict(type=last_ok['job_type'], at=_iso(last_ok['finished_at'] or last_ok['started_at'])),
            'liquidity': coverage(conn), 'problems': problems, 'volume_collection': bool(settings.get(conn, 'volume_collection', False))}
