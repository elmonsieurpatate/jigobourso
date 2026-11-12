"""Profils de score : réglages officiels et personnels, application, nettoyage et construction de la configuration d'une stratégie."""
import copy
from engine.shared import settings
from ..explorer import explorer_config as C
from ..scoring import score_service
from ..scoring import scores as SC
from .scores_specs import DAY_THRESHOLDS, LIQUIDITY, PROFILES, SCORING_PERIODS, THRESHOLDS, TOLERANCE, USER, spec, user_key

PERIOD_LABELS = {'day': 'Jour', 'week': 'Semaine', 'month': 'Mois', 'quarter': 'Trimestre', 'half': 'Semestre', 'year': 'Année'}


def design():
    return {'kappa': SC.KAPPA, 'threshold': SC.COVERAGE_THRESHOLD, 'anchor': SC.ANCHOR_LAMBDA, 'complex_weights': dict(SC.COMPLEX_WEIGHTS), 'tuning': dict(TUNING_DEFAULTS),
            'tuning_ranges': {'sat_a': list(SC.SAT_A_RANGE), 'accel_ref': list(SC.ACCEL_REF_RANGE)}, 'vol_modes': list(SC.VOL_MODES), 'momentum_horizons': list(SC.MOMENTUM_HORIZONS)}


def formula():
    """Constantes de conception des deux scores (lecture seule : changer une formule est une décision de conception, pas un réglage)."""
    return {'saturation': {'a': SC.SAT_A, 'b': SC.SAT_B}, 'accel': {'k': SC.ACCEL_REF, 'r2': SC.ACCEL_R2}, 'gate_floor': SC.GATE_FLOOR,
            'reliability_sessions': SC.RELIABILITY_SESSIONS, 'min_sessions': SC.MIN_SESSIONS,
            'liquidity_floor_eur': SC.LIQUIDITY_FLOOR_EUR, 'liquidity_ceil_eur': SC.LIQUIDITY_CEIL_EUR}


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
        if p['id'] == 'day' and 'day' not in (profile.get('periods') or {}) and isinstance(profile.get('day_filter'), dict):      # profil antérieur à la granularité Jour : ancien filtre « dernier jour »
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
            p['enabled'], p['min_return'] = False, None                   # (jamais atteint tant que Jour est une granularité ; conservé par sécurité)
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
        if pid == 'day' and not isinstance(pp, dict):         # profil enregistré avant l'ajout de Jour : Jour désactivé (ou ancien filtre « dernier jour » repris tel quel)
            old = raw.get('day_filter') if isinstance(raw.get('day_filter'), dict) else {}
            pp = {'enabled': bool(old.get('enabled')), 'require_history': False, 'min_return': old.get('min_return') if old.get('enabled') else None}
        if not isinstance(pp, dict):
            raise ValueError(f'Granularité manquante : {PERIOD_LABELS[pid]}')
        item = {'enabled': bool(pp.get('enabled')), 'require_history': bool(pp.get('require_history'))}
        for f, (lo, hi) in THRESHOLDS.items():
            item[f] = None if pid == 'day' and f not in DAY_THRESHOLDS else C.number(pp.get(f), lo, hi, f'{PERIOD_LABELS[pid]} : {f}')
        out['periods'][pid] = item
    active = [pid for pid in SCORING_PERIODS if out['periods'][pid]['enabled']]
    if not active:
        raise ValueError('Au moins une granularité doit rester active')
    d = out['periods']['day']                         # champ conservé pour les anciens lecteurs : reflet de la granularité Jour
    out['day_filter'] = {'enabled': d['enabled'], 'min_return': d['min_return'] if d['min_return'] is not None else 0.0}
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
        vals = {pid: C.number(weights.get(pid, 0 if pid == 'day' else None), 0, 100, f'Poids {PERIOD_LABELS[pid]}') for pid in active}      # Jour sans poids saisi : 0 %
        if any(v is None for v in vals.values()):
            raise ValueError('Chaque granularité active doit avoir un poids')
        if abs(sum(vals.values()) - 100) > TOLERANCE:
            raise ValueError(f'Le total des poids des périodes doit faire 100 % (actuellement {sum(vals.values()):g} %)')
        out['weights'] = vals
    day_on = out['periods']['day']['enabled']
    if not [pid for pid in active if pid != 'day'] and not (mode == 'custom' and day_on and out['weights'].get('day', 0) > 0):
        raise ValueError('Jour seul n’a aucun poids automatique : activez une autre granularité ou donnez-lui un poids personnalisé')
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


def global_profiles(conn):
    return settings.get(conn, PROFILES, {}) or {}


def user_profiles(conn, uid):
    return settings.get(conn, user_key(uid), {}) or {}


def stored_profiles(conn):
    """Profils effectifs : références officielles, puis adaptations de l'utilisateur de la requête (propres à son compte)."""
    g = global_profiles(conn)
    return {**g, **user_profiles(conn, USER['id'])} if USER['id'] else g


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
