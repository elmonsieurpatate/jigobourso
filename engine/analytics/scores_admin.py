"""Administration des scores V4 : un seul moteur de notation, des profils de stratégie (granularités, poids, seuils) et le suivi des calculs.

Le moteur (scores.py) n'est jamais modifié ici : l'administration ne règle que des paramètres.
  - `scores_v4`        réglages communs : κ (poids automatiques des périodes) et seuil de couverture ;
  - `scores_profiles`  réglages propres à une stratégie V4 : granularités actives, seuils de conformité, poids des périodes, poids du score complexe.
Les seuils de conformité (pente, R², rendement) filtrent ; ils n'entrent jamais dans une note."""
import copy

from engine.shared import settings

from . import explorer_config as C, score_categories, score_service, scores as SC

PROFILES = 'scores_profiles'
SCORING_PERIODS = tuple(p for p in C.PERIODS if C.SESSIONS[p] >= SC.MIN_SESSIONS)
SIMPLE = {'min_slope': (-100, 100), 'min_r2': (0, 1)}                      # mode simple : exactement deux seuils par granularité
ADVANCED = {'min_return': (-100, 10000), 'max_return': (-100, 10000), 'max_spike_share': (0, 1), 'max_volatility': (0, 100), 'min_up_fraction': (0, 1), 'max_drawdown': (0, 100)}
THRESHOLDS = {**SIMPLE, **ADVANCED}
LIQUIDITY = {'min_turnover_eur': (0, 1e12), 'min_turnover_eur_us': (0, 1e12)}
TOLERANCE = 0.05


def growth_v4():
    """« Croissance rapide » V4, mode simple : semaine et mois obligatoires, pente et R² minimaux « Équilibré » (valeurs initiales à éprouver, cahier des charges V4 §2).
    Aucun critère avancé, aucune liquidité minimale, aucun filtre sur le dernier jour : rien n'est imposé en silence."""
    c = C.empty()
    c['name'] = 'growth_v4'
    by = {p['id']: p for p in c['periods']}
    by['week'].update(enabled=True, require_history=True, min_slope=0.30, min_r2=0.60)
    by['month'].update(enabled=True, require_history=True, min_slope=0.20, min_r2=0.60)
    c['selection'] = {'combine': 'all', 'missing': 'unknown', 'require_fresh': True}
    c['ranking'] = {'mode': C.SCORES_MODE, 'sort': 'simple'}
    c['scoring'] = {'kappa': SC.KAPPA, 'weights': {}, 'complex_weights': {}, 'threshold': SC.COVERAGE_THRESHOLD}
    return C.validate(c)


def _historic(name, periods, weights, complex_weights, tuning=None, sort='complex'):
    """Stratégie historique transposée dans le moteur V4 : mêmes calculs de score, réglages propres.
    periods : {granularité: seuils d'admission} ; une granularité à poids 0 sert de contexte d'admission (aucune note)."""
    c = growth_v4()
    c['name'] = name
    by = {p['id']: p for p in c['periods']}
    for pid in SCORING_PERIODS:
        by[pid].update(enabled=pid in periods, require_history=pid in periods and weights.get(pid, 0) > 0, **{f: None for f in THRESHOLDS})
        by[pid].update(periods.get(pid, {}))
    c['ranking'] = {'mode': C.SCORES_MODE, 'sort': sort}
    c['scoring'] = dict(c['scoring'], weights=dict(weights), complex_weights=dict(complex_weights), **(tuning or {}))
    return C.validate(c)


def _regular():
    return _historic('growth_regular', {'month': dict(min_slope=0.07, min_r2=0.56), 'quarter': dict(min_slope=0.07, min_r2=0.56)}, {},
                     {'dynamics': 20, 'r2': 35, 'up_days': 15, 'concentration': 10, 'volatility': 5, 'drawdown': 5, 'liquidity': 10, 'acceleration': 0, 'momentum': 0}, {'sat_a': 10.0})


def _rebound():
    return _historic('rebound', {'week': dict(min_slope=0.07, min_r2=0.56), 'month': dict(min_slope=0.07, min_r2=0.56), 'half': dict(max_return=10.0)}, {'week': 50, 'month': 50, 'half': 0},
                     {'dynamics': 15, 'r2': 10, 'up_days': 5, 'concentration': 5, 'volatility': 10, 'drawdown': 5, 'liquidity': 5, 'acceleration': 20, 'momentum': 0, 'recovery': 25}, {'accel_ref': 0.25})


def _calm():
    return _historic('calm_rise', {'month': dict(min_slope=0.07, min_r2=0.56, max_volatility=1.5, max_drawdown=20.0), 'quarter': dict(min_slope=0.07, min_r2=0.56, max_volatility=1.5, max_drawdown=20.0)}, {},
                     {'dynamics': 10, 'r2': 10, 'up_days': 10, 'concentration': 5, 'volatility': 35, 'drawdown': 20, 'liquidity': 10, 'acceleration': 0, 'momentum': 0}, {'sat_a': 10.0})


def _momentum(name, horizon, periods, weights, cw):
    return _historic(name, {pid: {} for pid in periods}, weights, cw, {'momentum_horizon': horizon})


V4_STRATEGIES = {
    'growth_regular': {'label': 'Croissance régulière', 'build': _regular,
                       'note': 'Hausse soutenue ET régulière sur un mois et un trimestre : la régularité (R²), les séances positives et le risque pèsent plus que l’intensité (saturation de dynamique abaissée à 10 %).'},
    'growth_v4': {'label': 'Croissance rapide', 'build': growth_v4,
                  'note': 'Mode simple : pente et R² par granularité, aucun autre filtre imposé.'},
    'rebound': {'label': 'Rebond', 'build': _rebound,
                'note': 'Semaine et mois qui repartent à la hausse alors que le semestre n’a presque pas progressé (admission : rendement 6 mois ≤ 10 %). Contexte de rebond (semestre peu avancé) 25 % et accélération 20 % du score complexe, référence d’accélération abaissée (0,25) : un retournement net suffit.'},
    'calm_rise': {'label': 'Hausse calme', 'build': _calm,
                  'note': 'Mois et trimestre en hausse douce avec peu de variations (admission : volatilité ≤ 1,5 %/séance, repli ≤ 20 %). Volatilité 35 % et drawdown 20 % du score complexe.'},
    'momentum_6m': {'label': 'Momentum 6 mois (expérimental)',
                    'build': lambda: _momentum('momentum_6m', '6m', ('quarter', 'half'), {'quarter': 30, 'half': 70},
                                               {'dynamics': 15, 'r2': 10, 'up_days': 0, 'concentration': 0, 'volatility': 5, 'drawdown': 10, 'liquidity': 10, 'acceleration': 0, 'momentum': 50}),
                    'note': 'Variation du cours entre J−126 et J−21 séances (hors dernier mois), 50 % du score complexe ; le semestre porte la pente et la régularité. Aucun seuil.'},
    'momentum_12m': {'label': 'Momentum 12 mois (expérimental)',
                     'build': lambda: _momentum('momentum_12m', '12m', ('half', 'year'), {'half': 30, 'year': 70},
                                                {'dynamics': 15, 'r2': 10, 'up_days': 0, 'concentration': 0, 'volatility': 5, 'drawdown': 10, 'liquidity': 10, 'acceleration': 0, 'momentum': 50}),
                     'note': 'Variation du cours entre J−252 et J−21 séances (hors dernier mois), 50 % du score complexe ; l’année porte la pente et la régularité. Aucun seuil.'},
    'momentum_risk': {'label': 'Momentum ajusté du risque (expérimental)',
                      'build': lambda: _momentum('momentum_risk', 'blend', ('half', 'year'), {'half': 40, 'year': 60},
                                                 {'dynamics': 0, 'r2': 0, 'up_days': 0, 'concentration': 0, 'volatility': 10, 'drawdown': 10, 'liquidity': 0, 'acceleration': 0, 'momentum': 80}),
                      'note': 'Momentum 6 et 12 mois (moyenne, 80 %) corrigé par la volatilité et le repli maximal des périodes semestre et année (10 % chacun), comme l’ancien profil. Le filtre « au-dessus de la moyenne 200 jours » n’est pas une notation : il reste un filtre d’affichage.'}}
# ───────────── stratégies du Classement (« Blou », Croissance régulière…) : chacune a son propre profil de scores ─────────────
CT_BUILTIN = {'fast': 'growth_v4', 'regular': 'growth_regular', 'calm': 'calm_rise'}      # stratégies d'origine de la page Classement -> stratégie de scores V4
DYNAMIC = {}                                          # nom -> spécification ; rempli par refresh(conn) en tête de chaque appel


def _ct_builder(label, periods, thresholds=None):
    def build():
        c = growth_v4()
        c['name'] = label
        by = {p['id']: p for p in c['periods']}
        for pid in SCORING_PERIODS:
            on = pid in periods
            by[pid]['enabled'] = on
            if on:
                by[pid]['require_history'] = True
                t = (thresholds or {}).get(pid) or {}
                for f, key in (('min_slope', 'slope'), ('min_r2', 'r2')):
                    if isinstance(t.get(key), (int, float)) and not isinstance(t.get(key), bool) and t[key] > 0:
                        by[pid][f] = float(t[key])
        return C.validate(c)
    return build


def refresh(conn):
    """Recense les stratégies du Classement : les deux d'origine (hors Croissance rapide = moteur commun) et les stratégies personnelles de chaque utilisateur."""
    import json
    DYNAMIC.clear()
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT name, value_json FROM settings WHERE name LIKE 'ct\\_strategies:%'")
        docs = cur.fetchall()
    for row in docs:
        try:
            uid = row['name'].split(':', 1)[1]
            doc = json.loads(row['value_json'])
            for it in doc.get('items') or []:
                if it.get('builtin') or not isinstance(it.get('config'), dict) or not it.get('id'):
                    continue
                per = it['config'].get('periods') or {}
                active = tuple(pid for pid in SCORING_PERIODS if (per.get(pid) or {}).get('enabled'))
                if not active:
                    continue
                name = f'ct:{uid}:{it["id"]}'
                DYNAMIC[name] = {'label': it.get('name') or name, 'build': _ct_builder(name, active, per), 'note': 'Stratégie personnelle du Classement : granularités actives de cette stratégie, notes réglées ici.'}
        except (ValueError, KeyError, TypeError, AttributeError):
            continue                                                                      # document illisible : ignoré, jamais bloquant


def known(name):
    return name in V4_STRATEGIES or name in DYNAMIC


def spec(name):
    return V4_STRATEGIES.get(name) or DYNAMIC[name]


def resolve(conn, ct_id, user_id):
    """Nom de la stratégie de scores d'une stratégie du Classement (identifiant de la page) pour un utilisateur."""
    refresh(conn)
    if ct_id in CT_BUILTIN:
        return CT_BUILTIN[ct_id]
    name = f'ct:{int(user_id)}:{ct_id}'
    return name if name in DYNAMIC else 'growth_v4'


PERIOD_LABELS = {'week': 'Semaine', 'month': 'Mois', 'quarter': 'Trimestre', 'half': 'Semestre', 'year': 'Année'}


def design():
    return {'kappa': SC.KAPPA, 'threshold': SC.COVERAGE_THRESHOLD, 'anchor': SC.ANCHOR_LAMBDA, 'complex_weights': dict(SC.COMPLEX_WEIGHTS), 'tuning': dict(TUNING_DEFAULTS),
            'tuning_ranges': {'sat_a': list(SC.SAT_A_RANGE), 'accel_ref': list(SC.ACCEL_REF_RANGE)}, 'vol_modes': list(SC.VOL_MODES), 'momentum_horizons': list(SC.MOMENTUM_HORIZONS)}


def formula():
    """Constantes de conception des deux scores (lecture seule : changer une formule est une décision de conception, pas un réglage)."""
    return {'saturation': {'a': SC.SAT_A, 'b': SC.SAT_B}, 'accel': {'k': SC.ACCEL_REF, 'r2': SC.ACCEL_R2}, 'gate_floor': SC.GATE_FLOOR,
            'reliability_sessions': SC.RELIABILITY_SESSIONS, 'min_sessions': SC.MIN_SESSIONS,
            'liquidity_floor_eur': SC.LIQUIDITY_FLOOR_EUR, 'liquidity_ceil_eur': SC.LIQUIDITY_CEIL_EUR}


# ───────────── profils ─────────────

def profile_of(config):
    """Forme éditable d'un profil, lue dans une configuration V4."""
    sc = config.get('scoring') or {}
    weights = sc.get('weights') or {}
    by = {p['id']: p for p in config['periods']}
    liq = config.get('liquidity') or {}
    day = by['day']
    return {'periods': {pid: dict({'sessions': by[pid]['sessions'], 'enabled': by[pid]['enabled'], 'require_history': by[pid]['require_history']},
                                  **{f: by[pid][f] for f in THRESHOLDS}) for pid in SCORING_PERIODS},
            'day_filter': {'enabled': bool(day['enabled']), 'min_return': day['min_return'] if day['min_return'] is not None else 0.0},
            'liquidity': {f: liq.get(f) for f in LIQUIDITY},
            'technical': {'require_fresh': bool((config.get('selection') or {}).get('require_fresh'))},
            'filters': {'enabled': False},                      # filtres de consultation : désactivés par défaut, jamais appliqués aux notes
            'weights_mode': 'custom' if weights else 'auto', 'weights': dict(weights),
            'complex_weights': dict(SC.COMPLEX_WEIGHTS, **(sc.get('complex_weights') or {})),
            'tuning': tuning_of(sc)}


TUNING_DEFAULTS = {'sat_a': SC.SAT_A, 'accel_ref': SC.ACCEL_REF, 'vol_mode': 'absolute', 'momentum_horizon': '6m'}


def tuning_of(sc):
    """Normalisations réglables d'une stratégie (valeurs de conception si absentes)."""
    return {k: (sc or {}).get(k, v) for k, v in TUNING_DEFAULTS.items()}


def apply_profile(config, profile):
    """Superpose un profil enregistré à la configuration de base de la stratégie ; le résultat est revalidé.
    Les seuils filtrent (conformité) ; seuls granularités actives, poids et κ/couverture touchent aux notes."""
    c = copy.deepcopy(config)
    for p in c['periods']:
        pp = (profile.get('periods') or {}).get(p['id'])
        if pp is not None and p['id'] in SCORING_PERIODS:
            for f in ('enabled', 'require_history'):
                if f in pp:
                    p[f] = bool(pp[f])
            for f in THRESHOLDS:
                if f in pp:
                    p[f] = pp[f]
        if p['id'] == 'day' and isinstance(profile.get('day_filter'), dict):               # filtre facultatif « dernier jour positif » : indépendant de la notation
            p['enabled'] = bool(profile['day_filter'].get('enabled'))
            p['min_return'] = profile['day_filter'].get('min_return', 0.0) if p['enabled'] else None
    if isinstance(profile.get('liquidity'), dict):
        c['liquidity'] = dict(c.get('liquidity') or {}, **{f: profile['liquidity'].get(f) for f in LIQUIDITY})
    if isinstance(profile.get('technical'), dict):
        c['selection'] = dict(c.get('selection') or {}, require_fresh=bool(profile['technical'].get('require_fresh')))
    sc = dict(c.get('scoring') or {})
    sc['weights'] = dict(profile.get('weights') or {}) if profile.get('weights_mode') == 'custom' else {}
    if profile.get('complex_weights'):
        sc['complex_weights'] = dict(profile['complex_weights'])
    if isinstance(profile.get('tuning'), dict):
        sc.update(profile['tuning'])
    c['scoring'] = sc
    if not (profile.get('filters') or {}).get('enabled'):
        return neutral(c)
    return C.validate(c)


def neutral(config):
    """Configuration sans aucun filtre de consultation : seuils, historique exigé, filtre du dernier jour et liquidité minimale sont retirés.
    Les notes ne les utilisent jamais ; ce sont eux qui écartaient des titres du classement général. Les valeurs restent dans le profil, prêtes à être activées.
    Reste seul le contrôle technique (fraîcheur) du profil."""
    c = copy.deepcopy(config)
    for p in c['periods']:
        if p['id'] in SCORING_PERIODS:
            p['require_history'] = False
            for f in THRESHOLDS:
                p[f] = None
        elif p['id'] == 'day':
            p['enabled'], p['min_return'] = False, None
    c['liquidity'] = dict(c.get('liquidity') or {}, **{f: None for f in LIQUIDITY})
    return C.validate(c)


def clean_profile(raw):
    """Valide un profil saisi dans l'administration. ValueError avec un message lisible. Les champs absents prennent la valeur « non renseigné » (aucun seuil)."""
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
    day = raw.get('day_filter') or {}
    out['day_filter'] = {'enabled': bool(day.get('enabled')), 'min_return': C.number(day.get('min_return', 0.0), -100, 100, 'Dernier jour : rendement minimal')}
    if out['day_filter']['min_return'] is None:
        out['day_filter']['min_return'] = 0.0
    liq = raw.get('liquidity') or {}
    out['liquidity'] = {f: C.number(liq.get(f), lo, hi, f) for f, (lo, hi) in LIQUIDITY.items()}
    out['technical'] = {'require_fresh': bool((raw.get('technical') or {}).get('require_fresh'))}
    out['filters'] = {'enabled': bool((raw.get('filters') or {}).get('enabled'))}
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
    cw = dict(raw.get('complex_weights') or {})
    for new in ('momentum', 'recovery'):
        cw.setdefault(new, 0)                             # composantes ajoutées après coup : un profil enregistré sans elles les garde à 0
    if set(cw) != set(SC.COMPLEX_WEIGHTS):
        raise ValueError('Poids du score complexe incomplets')
    cw = {k: C.number(v, 0, 100, 'Poids du score complexe') for k, v in cw.items()}
    if any(v is None for v in cw.values()):
        raise ValueError('Poids du score complexe invalides')
    if abs(sum(cw.values()) - 100) > TOLERANCE:
        raise ValueError(f'Le total des poids du score complexe doit faire 100 % (actuellement {sum(cw.values()):g} %)')
    out['complex_weights'] = cw
    if raw.get('tuning') is not None:
        t = raw['tuning'] if isinstance(raw['tuning'], dict) else {}
        v = C.validate_scoring({k: t.get(k) for k in TUNING_DEFAULTS if t.get(k) is not None}, [])
        out['tuning'] = {k: v[k] for k in TUNING_DEFAULTS}
    return out


def stored_profiles(conn):
    return settings.get(conn, PROFILES, {}) or {}


def base_config(name):
    return spec(name)['build']()


def build_config(conn, name, profile=None, glob=None):
    """Configuration effective d'une stratégie V4. `profile` / `glob` : brouillon non enregistré (simulation) ; absents : réglages enregistrés."""
    cfg = base_config(name)
    prof = profile if profile is not None else stored_profiles(conn).get(name)
    cfg = apply_profile(cfg, clean_profile(prof)) if prof else neutral(cfg)
    cfg = score_service.apply_global(conn, cfg) if glob is None else _with_global(cfg, glob)
    return cfg


def _with_global(config, glob):
    g = C.validate_scoring({k: glob.get(k) for k in ('kappa', 'threshold', 'anchor')}, [])
    return dict(config, scoring=dict(config['scoring'], kappa=g['kappa'], threshold=g['threshold'], anchor=g['anchor']))


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
    refresh(conn)
    glob = score_service.admin_defaults(conn)
    stored = stored_profiles(conn)
    out = []
    for name, sp in list(V4_STRATEGIES.items()) + list(DYNAMIC.items()):
        base = base_config(name)
        cfg = build_config(conn, name)
        current = clean_profile(stored[name]) if name in stored else profile_of(base)       # valeurs saisies (seuils conservés même si les filtres sont désactivés)
        current.setdefault('tuning', tuning_of(base.get('scoring')))                          # profil enregistré avant les réglages de normalisation : valeurs de la stratégie
        for pid in SCORING_PERIODS:
            current['periods'][pid].setdefault('sessions', C.SESSIONS[pid])                  # le profil enregistré ne garde pas la durée : l'affichage en a besoin
        active = [p for p in SCORING_PERIODS if current['periods'][p]['enabled']]
        out.append({'name': name, 'label': sp['label'], 'note': sp['note'], 'engine': 'v4', 'sort': cfg['ranking'].get('sort'), 'defaults': profile_of(base), 'current': current,
                    'customised': name in stored, 'auto_weights': auto_weights(glob['kappa'], active), 'saved_at': _iso(settings.saved_at(conn, PROFILES)) if name in stored else None})
    return out


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


def _iso(v):
    import datetime
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=' ')
    return v.isoformat() if isinstance(v, datetime.date) else v


def state(conn):
    cur = score_service.admin_defaults(conn)
    stored = settings.get(conn, score_service.SETTING, None)
    return {'design': design(), 'formula': formula(), 'version': SC.VERSION, 'period_labels': PERIOD_LABELS, 'scoring_periods': list(SCORING_PERIODS),
            'global': {'kappa': cur['kappa'], 'threshold': cur['threshold'], 'anchor': cur['anchor'], 'customised': bool(stored), 'saved_at': _iso(settings.saved_at(conn, score_service.SETTING)) if stored else None},
            'strategies': strategies(conn), 'references': references(), 'personal': personal(conn), 'volume_collection': bool(settings.get(conn, 'volume_collection', False))}


def save(conn, request):
    """Enregistre les réglages communs et/ou le profil d'une stratégie V4 ; `reset` : 'global', 'profile' (avec `name`) ou 'all'."""
    refresh(conn)
    reset = request.get('reset')
    if reset in ('global', 'all'):
        settings.put(conn, score_service.SETTING, {})
    if reset in ('profile', 'all'):
        profiles = stored_profiles(conn)
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
    refresh(conn)
    from . import service
    name = request.get('strategy')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    book = score_service.score_book(conn, cfg, service.data_version(conn))
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
            'windows': [dict(id=x, sessions=C.SESSIONS[x], active=any(q['id'] == x for q in params['periods'])) for x in SCORING_PERIODS if C.SESSIONS[x] <= max(CURVE_SESSIONS, _granularity(params))], 'granularity': _granularity(params), 'ranks': _rank_of(book, lid)}


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
    top = sorted((e for e in book.values() if e['simple'] is not None), key=lambda e: (-e['simple'], e['id']))[:n]
    info = _titles(conn, [e['id'] for e in top])
    curves = series(conn, [e['id'] for e in top], sessions)
    return [dict(id=e['id'], symbol=info[e['id']]['symbol'], mic=info[e['id']]['mic'], name=info[e['id']]['name'], simple=e['simple'], complex=e['complex'],
                 rank=ranks.get(e['id']), curve=curves.get(e['id'], []))
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
    cfg = build_config(conn, 'growth_v4')
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


# ───────────── conformité (aperçu sur les données réelles) ─────────────

def conformity(conn, request):
    """Effet des seuils d'un profil sur les titres réels : conformes / écartés / non évaluables. Les titres écartés gardent leurs deux scores (calculés hors filtres)."""
    refresh(conn)
    from . import service
    name = request.get('strategy')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    verdicts = service.judge_universe(conn, cfg)
    book = score_service.score_book(conn, cfg, service.data_version(conn))
    counts = {'retained': 0, 'rejected': 0, 'unknown': 0}
    kept = 0
    for v in verdicts:
        counts[v['status']] = counts.get(v['status'], 0) + 1
        b = book.get(v['key'])
        if v['status'] == 'rejected' and b and b['simple'] is not None and b['complex'] is not None:
            kept += 1
    return {'universe': len(verdicts), 'counts': counts, 'rejected_with_both_scores': kept, 'rated': len(book)}


# ───────────── classement général (résultat principal du moteur) ─────────────

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


def _ranks(book, key):
    return {lid: i for i, lid in enumerate(sorted((l for l, e in book.items() if e[key] is not None), key=lambda l: (-book[l][key], l)), 1)}


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
    ranked = sorted((e for e in book.values() if e[key] is not None), key=lambda e: (-e[key], e['id']))[:n]
    info = _titles(conn, [e['id'] for e in ranked])
    return [dict(rank=i, id=e['id'], symbol=info[e['id']]['symbol'], name=info[e['id']]['name'], score=e[key], other=e['complex' if key == 'simple' else 'simple'],
                 status=e[key + '_status']) for i, e in enumerate(ranked, 1) if e['id'] in info]


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
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), CATEGORY_FILE)
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'filters': []}


def _closes(conn, ids, sessions):
    """{listing_id: [(date, cours)]} : les sessions + 1 dernières clôtures réelles de chaque titre (rien d'interpolé)."""
    ids = list(ids)
    out = {i: [] for i in ids}
    if not ids or sessions < 1:
        return out
    import datetime
    since = datetime.date.today() - datetime.timedelta(days=int(sessions * 2 + 10))
    with conn.cursor() as cur:
        for k in range(0, len(ids), 200):
            part = ids[k:k + 200]
            cur.execute(f"""SELECT listing_id, price_date, COALESCE(adj_close_px, close_px) AS px FROM daily_prices
                            WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND price_date>=%s AND COALESCE(adj_close_px, close_px) IS NOT NULL
                            ORDER BY listing_id, price_date""", part + [since])
            for r in cur.fetchall():
                out[r['listing_id']].append((r['price_date'], float(r['px'])))
    return {i: v[-(sessions + 1):] for i, v in out.items()}


def series(conn, ids, sessions):
    """Dernières clôtures (sessions + 1 points) de chaque titre : petites courbes du classement. Un titre sans historique n'a pas de courbe (liste vide)."""
    return {i: [round(px, 4) for _, px in v] for i, v in _closes(conn, ids, sessions).items()}


def dated_series(conn, lid, sessions):
    """Courbe détaillée d'un titre : date ISO et cours de chaque séance, pour l'infobulle de la simulation."""
    return [{'d': d.isoformat() if hasattr(d, 'isoformat') else str(d), 'p': round(px, 4)} for d, px in _closes(conn, [lid], sessions).get(lid, [])]


def _granularity(params):
    return max((p['sessions'] for p in params['periods']), default=0)


def _listing(conn, book, which, category, offset, limit, cats, sessions):
    """Classement d'un score, éventuellement restreint à une catégorie de note. Le rang est le rang GÉNÉRAL (sur tous les titres notés) : une catégorie ne le change pas."""
    key = 'simple' if which == 'simple' else 'complex'
    ranked = sorted((e for e in book.values() if e[key] is not None), key=lambda e: (-e[key], e['id']))
    rank_of = {e['id']: i for i, e in enumerate(ranked, 1)}
    counts = {c['id']: 0 for c in cats}
    for e in ranked:
        cid = score_categories.assign(e[key], cats)
        if cid in counts:
            counts[cid] += 1
    chosen = [e for e in ranked if category in (None, '') or score_categories.assign(e[key], cats) == category]
    page = chosen[offset:offset + limit]
    info = _titles(conn, [e['id'] for e in page])
    curves = series(conn, [e['id'] for e in page], sessions)
    rows = [dict(rank=rank_of[e['id']], id=e['id'], symbol=info[e['id']]['symbol'], mic=info[e['id']]['mic'], name=info[e['id']]['name'], kind=info[e['id']]['kind'],
                 simple=e['simple'], complex=e['complex'], simple_status=e['simple_status'], complex_status=e['complex_status'],
                 coverage=e[key + '_coverage'], curve=curves.get(e['id'], [])) for e in page if e['id'] in info]
    return {'which': key, 'category': category or None, 'total': len(chosen), 'offset': offset, 'rows': rows,
            'categories': [dict(id=c['id'], name=c['name'], color=c.get('color'), min=c.get('min'), max=c.get('max'), minIncluded=c.get('minIncluded'), maxIncluded=c.get('maxIncluded'),
                                count=counts.get(c['id'], 0)) for c in cats if not c.get('unknown')]}


def ranking(conn, request):
    """Résultat principal d'un réglage : titres notés et classés, indisponibles, répartition des notes, poids réels des périodes et effet par rapport au réglage enregistré.
    Aucun filtre n'intervient : les seuils facultatifs ne retirent aucun titre de ce classement."""
    refresh(conn)
    from . import service
    name = request.get('strategy')
    if not known(name):
        raise ValueError('Stratégie V4 inconnue')
    draft = request.get('draft') or {}
    cfg = build_config(conn, name, draft.get('profile'), draft.get('global'))
    version = service.data_version(conn)
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
    out['listing'] = _listing(conn, book, which, cat if isinstance(cat, str) else None, off, lim, cats, sessions)
    if draft:
        saved_book = score_service.score_book(conn, build_config(conn, name), version)
        out['compared'] = {k: _movement(saved_book, book, k) for k in ('simple', 'complex')}
    return out
