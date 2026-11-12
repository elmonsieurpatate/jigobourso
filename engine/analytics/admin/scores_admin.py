"""Administration des scores : état, comparaison des profils, enregistrement (officiel et personnel), aperçu de couverture et suivi."""
from ..shared.dates import iso
from engine.shared import settings
from ..scoring import criteria as _CR
from ..explorer import explorer_config as C
from ..scoring import score_service
from ..scoring import scores as SC
from .scores_specs import CT_BUILTIN, DYNAMIC, PROFILES, SCORING_PERIODS, USER, V4_STRATEGIES, known, refresh, user_key
from .scores_profiles import PERIOD_LABELS, apply_profile, auto_weights, base_config, build_config, clean_profile, design, formula, global_profiles, profile_of, stored_profiles, tuning_of, user_profiles

def strategies(conn):
    refresh(conn)
    glob = score_service.admin_defaults(conn)
    stored = stored_profiles(conn)
    out = []
    for name, sp in list(V4_STRATEGIES.items()) + list(DYNAMIC.items()):
        if not known(name):
            continue                                                                          # stratégie personnelle d'un autre utilisateur
        base = base_config(name)
        cfg = build_config(conn, name)
        current = clean_profile(stored[name]) if name in stored else profile_of(base)       # valeurs saisies (seuils conservés même si les filtres sont désactivés)
        current.setdefault('tuning', tuning_of(base.get('scoring')))                          # profil enregistré avant les réglages de normalisation : valeurs de la stratégie
        for pid in SCORING_PERIODS:
            current['periods'][pid].setdefault('sessions', C.SESSIONS[pid])                  # le profil enregistré ne garde pas la durée : l'affichage en a besoin
        active = [p for p in SCORING_PERIODS if current['periods'][p]['enabled']]
        out.append({'name': name, 'label': sp['label'], 'note': sp['note'], 'engine': 'v4', 'sort': cfg['ranking'].get('sort'), 'defaults': profile_of(base), 'current': current,
                    'customised': name in stored, 'official': official_clean(conn, name), 'modified': profile_diff(current, official_clean(conn, name)) if name in V4_STRATEGIES else [],
                    'auto_weights': auto_weights(glob['kappa'], active), 'saved_at': iso(settings.saved_at(conn, PROFILES)) if name in stored else None})
    return out


def _flat(v, prefix=''):
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            out.update(_flat(x, f'{prefix}{k}.'))
        return out
    return {prefix[:-1]: v}


def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def profile_diff(a, b):
    """Paramètres de score qui diffèrent entre deux profils (chemins pointés) ; vide si identiques. `sessions` et `day_filter` sont dérivés : ignorés."""
    if a is None or b is None:
        return []
    fa, fb = _flat(a), _flat(b)
    keys = sorted(k for k in set(fa) | set(fb) if '.sessions' not in k and not k.startswith('day_filter'))
    return [k for k in keys if not _same(fa.get(k), fb.get(k))]


def diff_rows(a, b):
    """Comparaison lisible : [{key, official, mine}] pour chaque paramètre de score qui diffère (a = adapté, b = officiel)."""
    fa, fb = _flat(a), _flat(b)
    return [{'key': k, 'official': fb.get(k), 'mine': fa.get(k)} for k in profile_diff(a, b)]


def official_clean(conn, name):
    """Profil de référence d'une stratégie intégrée : définition du code, puis réglage officiel de l'administrateur s'il existe. None pour une stratégie personnelle."""
    if name not in V4_STRATEGIES:
        return None
    g = global_profiles(conn)
    return clean_profile(g[name]) if name in g else clean_profile(profile_of(base_config(name)))


def criteria_diff(official_periods, spec):
    """Critères de recherche qui diffèrent de la référence : liste de « métrique:période ». `spec` = configuration enregistrée par l'utilisateur."""
    mine = _CR.normalize(spec)
    ref = _CR.normalize(_CR.default_spec(official_periods))
    if mine is None or ref is None:
        return []
    def table(n):
        return {f"{c['metric']}:{c['period']}:{c['op']}": c['value'] for c in n['primary'] + n['extra']}
    a, b = table(mine), table(ref)
    out = sorted({k.rsplit(':', 1)[0] for k in set(a) | set(b) if not (k in a and k in b and _same(a[k], b[k]))})
    if mine['extra'] and mine['join'] != ref['join']:
        out.append('join')
    return out


def criteria_rows(official_periods, spec):
    """Comparaison lisible des critères : [{key: « métrique:période », official, mine}] (None = pas de seuil)."""
    mine = _CR.normalize(spec)
    ref = _CR.normalize(_CR.default_spec(official_periods))
    if mine is None or ref is None:
        return []
    def table(n):
        return {f"{c['metric']}:{c['period']}": c['value'] for c in n['primary'] + n['extra']}
    a, b = table(mine), table(ref)
    keys = criteria_diff(official_periods, spec)
    return [{'key': k, 'official': b.get(k), 'mine': a.get(k)} for k in keys]


LABELS = {'growth_v4': 'Croissance rapide', 'growth_regular': 'Croissance régulière', 'calm_rise': 'Hausse calme', 'rebound': 'Rebond',
          'momentum_6m': 'Momentum 6 mois', 'momentum_12m': 'Momentum 12 mois', 'momentum_risk': 'Momentum ajusté au risque'}


def strategies_status(conn, request):
    """Statut de chaque stratégie intégrée et personnelle de l'utilisateur : une seule entrée par stratégie intégrée, Officielle ou Adaptée ; critères et scores jugés séparément.
    `ct_items` : stratégies enregistrées par l'utilisateur (surcharges de critères et stratégies personnelles)."""
    from ..scoring import ranking_table
    refresh(conn)
    items = {i['id']: i for i in (request.get('ct_items') or []) if isinstance(i, dict) and isinstance(i.get('id'), str)}
    crit = ranking_table.criteria()['criteria']
    mine = user_profiles(conn, USER['id']) if USER['id'] else {}
    out = []
    for ct_id, name in CT_BUILTIN.items():
        it = items.get(ct_id)
        cmod = criteria_diff(crit[ct_id]['periods'], it.get('config')) if it and it.get('builtin') and isinstance(it.get('config'), dict) else []
        smod = profile_diff(clean_profile(mine[name]), official_clean(conn, name)) if name in mine else []
        out.append({'id': ct_id, 'name': name, 'label': LABELS[name], 'kind': 'builtin', 'status': 'adapted' if cmod or smod else 'official',
                    'criteria': {'state': 'adapted' if cmod else 'official', 'modified': len(cmod), 'details': criteria_rows(crit[ct_id]['periods'], it.get('config')) if cmod else []},
                    'scores': {'state': 'adapted' if smod else 'official', 'modified': len(smod), 'details': diff_rows(clean_profile(mine[name]), official_clean(conn, name)) if smod else []}})
    for ct_id, it in items.items():
        if not it.get('builtin') and ct_id not in CT_BUILTIN:
            out.append({'id': ct_id, 'name': f"ct:{USER['id']}:{ct_id}", 'label': it.get('name') or ct_id, 'kind': 'personal', 'status': 'personal',
                        'criteria': {'state': 'personal', 'modified': 0, 'details': []}, 'scores': {'state': 'personal', 'modified': 0, 'details': []}})
    return {'strategies': out}


def user_save(conn, request):
    """Adaptation de scores propre à l'utilisateur : n'écrit jamais les références. Un profil identique à la référence redevient « Officiel » (l'adaptation est supprimée)."""
    uid = USER['id']
    if not uid:
        raise ValueError('Utilisateur requis')
    refresh(conn)
    mine = user_profiles(conn, uid)
    prof = request.get('profile') if isinstance(request.get('profile'), dict) else None
    name = request.get('name') or (prof or {}).get('name')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    reset = request.get('reset')
    if reset == 'profile':
        mine.pop(name, None)
    elif prof is not None:
        clean = clean_profile(prof)
        apply_profile(base_config(name), clean)                                   # revalidation complète de la configuration résultante
        ref = official_clean(conn, name)
        if ref is not None and not profile_diff(clean, ref):
            mine.pop(name, None)
        else:
            mine[name] = clean
    else:
        raise ValueError('Demande invalide')
    settings.put(conn, user_key(uid), mine)
    return user_state(conn, request)


def user_state(conn, request=None):
    st = state(conn)
    st['personal'] = None                                                            # statistiques d'administration : jamais exposées
    st['volume_collection'] = None
    return st


def references():
    """Préréglages applicables à un profil V4 (jamais appliqués sans action de l'administrateur)."""
    return {'balanced': profile_of(base_config('growth_v4'))}


def personal(conn):
    """Stratégies personnelles : combien utilisent déjà le moteur commun (mode « scores »), combien gardent un ancien moteur. Lecture seule, aucune migration."""
    import json
    out = {'total': 0, 'common_engine': 0, 'historic': 0, 'configurable': []}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, name, payload, active FROM explorer_saved WHERE kind='strategy'")
            rows = cur.fetchall()
    except Exception:                                     # noqa: BLE001 : table absente sur une très ancienne base
        return out
    for r in rows:
        out['total'] += 1
        try:
            payload = r['payload'] if isinstance(r['payload'], dict) else json.loads(r['payload'])
            cfg = payload.get('config') if isinstance(payload.get('config'), dict) else payload
            engine = (cfg.get('ranking') or {}).get('mode')
        except (ValueError, TypeError, AttributeError):
            engine = None
        if engine == C.SCORES_MODE:
            out['common_engine'] += 1
            out['configurable'].append({'id': r['id'], 'name': r['name'], 'active': bool(r['active'])})
        else:
            out['historic'] += 1
    return out


def state(conn):
    cur = score_service.admin_defaults(conn)
    stored = settings.get(conn, score_service.SETTING, None)
    return {'design': design(), 'formula': formula(), 'version': SC.VERSION, 'period_labels': PERIOD_LABELS, 'scoring_periods': list(SCORING_PERIODS),
            'global': {'kappa': cur['kappa'], 'threshold': cur['threshold'], 'anchor': cur['anchor'], 'customised': bool(stored), 'saved_at': iso(settings.saved_at(conn, score_service.SETTING)) if stored else None},
            'strategies': strategies(conn), 'references': references(), 'personal': personal(conn), 'volume_collection': bool(settings.get(conn, 'volume_collection', False))}


def save(conn, request):
    """Enregistre les réglages communs et/ou le profil d'une stratégie V4 ; `reset` : 'global', 'profile' (avec `name`) ou 'all'."""
    refresh(conn)
    reset = request.get('reset')
    if reset in ('global', 'all'):
        settings.put(conn, score_service.SETTING, {})
    if reset in ('profile', 'all'):
        profiles = global_profiles(conn)
        if reset == 'profile':
            name = request.get('name')
            if not known(name):
                raise ValueError('Stratégie V4 inconnue')
            profiles.pop(name, None)
        else:
            profiles = {}
        settings.put(conn, PROFILES, profiles)
    if reset:
        return state(conn)
    if isinstance(request.get('global'), dict):
        g = request['global']
        clean = C.validate_scoring({k: g.get(k) for k in ('kappa', 'threshold', 'anchor')}, [])
        settings.put(conn, score_service.SETTING, {'kappa': clean['kappa'], 'threshold': clean['threshold'], 'anchor': clean['anchor']})
    elif any(k in request for k in ('kappa', 'threshold')):                          # ancienne forme (réglages communs seuls) : les poids du score complexe sont propres aux profils
        clean = C.validate_scoring({k: request.get(k) for k in ('kappa', 'threshold')}, [])
        settings.put(conn, score_service.SETTING, {'kappa': clean['kappa'], 'threshold': clean['threshold'], 'anchor': clean['anchor']})
    if isinstance(request.get('profile'), dict):
        name = request['profile'].get('name')
        if not known(name):
            raise ValueError('Stratégie V4 inconnue')
        clean = clean_profile(request['profile'])
        apply_profile(base_config(name), clean)                                   # revalidation complète de la configuration résultante
        profiles = global_profiles(conn)
        profiles[name] = clean
        settings.put(conn, PROFILES, profiles)
    return state(conn)


def preview(conn, request):
    ids = [p for p in (request.get('periods') or []) if p in SCORING_PERIODS]
    return {'weights': auto_weights(request.get('kappa', SC.KAPPA), ids)}


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
            'computed_at': iso(max((r['at'] for r in rows if r['at']), default=None)), 'volume_checked_at': iso(max((r['checked'] for r in rows if r['checked']), default=None)), 'score_inputs': inputs}


def monitor(conn):
    """Suivi : titres notés, couverture, fraîcheur des données, origine de la liquidité, dernières erreurs de calcul."""
    from . import universe_verdicts
    cfg = build_config(conn, 'growth_v4')
    book = score_service.score_book(conn, cfg, universe_verdicts.data_version(conn))
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
    problems = [dict(id=j['id'], type=j['job_type'], status=j['status'], at=iso(j['started_at']), errors=int(j['items_error'] or 0), summary=j['summary']) for j in jobs
                if j['status'] in ('failed', 'interrupted', 'completed_with_errors')][:5]
    return {'rated': len(book), 'counts': counts, 'coverage': {'median': covs[len(covs) // 2] if covs else None, 'min': covs[0] if covs else None, 'full': sum(1 for c in covs if c >= 0.999)},
            'freshness': {'last_close': iso(fresh.get('last_close')), 'computed_at': iso(fresh.get('computed_at')), 'stale_titles': stale},
            'last_success': None if not last_ok else dict(type=last_ok['job_type'], at=iso(last_ok['finished_at'] or last_ok['started_at'])),
            'liquidity': coverage(conn), 'problems': problems, 'volume_collection': bool(settings.get(conn, 'volume_collection', False))}
