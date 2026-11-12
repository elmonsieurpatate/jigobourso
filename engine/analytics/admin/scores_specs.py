"""Catalogue des stratégies de score : références officielles (V4 et historiques), stratégies personnalisées chargées de la base, utilisateur courant."""
from ..explorer import explorer_config as C
from ..scoring import scores as SC
from ..explorer import strategy as LEGACY


PROFILES = 'scores_profiles'                                    # références OFFICIELLES communes (administrateur) : jamais modifiées par un utilisateur


USER = {'id': None}                                             # utilisateur de la requête en cours (un processus par appel) : ses adaptations se superposent aux références


def set_user(uid):
    USER['id'] = int(uid) if isinstance(uid, (int, str)) and str(uid).isdigit() and int(uid) > 0 else None


def user_key(uid):
    return f'scores_profiles_u{int(uid)}'


SCORING_PERIODS = tuple(p for p in C.PERIODS if SC.scorable(C.SESSIONS[p]))           # Jour (1 séance) comprise : facultative, désactivée et à 0 % par défaut


SIMPLE = {'min_slope': (-100, 100), 'min_r2': (0, 1)}                      # mode simple : exactement deux seuils par granularité


ADVANCED = {'min_return': (-100, 10000), 'max_return': (-100, 10000), 'max_spike_share': (0, 1), 'max_volatility': (0, 100), 'min_up_fraction': (0, 1), 'max_drawdown': (0, 100)}


THRESHOLDS = {**SIMPLE, **ADVANCED}


LIQUIDITY = {'min_turnover_eur': (0, 1e12), 'min_turnover_eur_us': (0, 1e12)}


TOLERANCE = 0.05


DAY_THRESHOLDS = ('min_return', 'max_return')              # Jour (1 séance) : seule la variation a un sens, jamais de pente, de R², de volatilité ni de repli


SLOPE, R2 = LEGACY.SLOPE_LEVELS, LEGACY.R2_LEVELS          # niveaux historiques exacts (strategy.py, V2) : pente en % par séance, R² 1 − (2/3)² pour « flexible »


def growth_v4():
    """« Croissance rapide » V4, mode simple : semaine et mois obligatoires, pente et R² minimaux « Équilibré » (valeurs initiales à éprouver, cahier des charges V4 §2).
    Aucun critère avancé, aucune liquidité minimale, aucun filtre sur le dernier jour : rien n'est imposé en silence."""
    c = C.empty()
    c['name'] = 'growth_v4'
    by = {p['id']: p for p in c['periods']}
    by['week'].update(enabled=True, require_history=True, min_slope=SLOPE['very_strong'], min_r2=None)       # critères de recherche historiques (pente « très forte », pas de R²)
    by['month'].update(enabled=True, require_history=True, min_slope=SLOPE['very_strong'], min_r2=None)
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
    crit = dict(min_slope=SLOPE['moderate'], min_r2=R2['flexible'])
    return _historic('growth_regular', {'month': dict(crit), 'quarter': dict(crit)}, {},
                     {'dynamics': 20, 'r2': 35, 'up_days': 15, 'concentration': 10, 'volatility': 5, 'drawdown': 5, 'liquidity': 10, 'acceleration': 0, 'momentum': 0}, {'sat_a': 10.0})


def _rebound():
    """Critères de recherche : semaine et mois. Le semestre n'a ni pente ni R² : il reste une période de CONTEXTE (poids 0) car la note « contexte de rebond » lit son rendement."""
    crit = dict(min_slope=SLOPE['gentle'], min_r2=R2['flexible'])
    return _historic('rebound', {'week': dict(crit), 'month': dict(crit), 'half': {}}, {'week': 50, 'month': 50, 'half': 0},
                     {'dynamics': 15, 'r2': 10, 'up_days': 5, 'concentration': 5, 'volatility': 10, 'drawdown': 5, 'liquidity': 5, 'acceleration': 20, 'momentum': 0, 'recovery': 25}, {'accel_ref': 0.25})


def _calm():
    """Critères de recherche : mois et trimestre (pente, R²). Volatilité et drawdown ne sont plus des seuils : ils pèsent 35 % et 20 % du score complexe."""
    crit = dict(min_slope=SLOPE['gentle'], min_r2=R2['flexible'])
    return _historic('calm_rise', {'month': dict(crit), 'quarter': dict(crit)}, {},
                     {'dynamics': 10, 'r2': 10, 'up_days': 10, 'concentration': 5, 'volatility': 35, 'drawdown': 20, 'liquidity': 10, 'acceleration': 0, 'momentum': 0}, {'sat_a': 10.0})


def _momentum(name, horizon, periods, weights, cw):
    return _historic(name, {pid: {} for pid in periods}, weights, cw, {'momentum_horizon': horizon})


V4_STRATEGIES = {
    'growth_regular': {'label': 'Croissance régulière', 'build': _regular,
                       'note': 'Hausse soutenue ET régulière sur un mois et un trimestre : la régularité (R²), les séances positives et le risque pèsent plus que l’intensité (saturation de dynamique abaissée à 10 %).'},
    'growth_v4': {'label': 'Croissance rapide', 'build': growth_v4,
                  'note': 'Mode simple : pente et R² par granularité, aucun autre filtre imposé.'},
    'rebound': {'label': 'Rebond', 'build': _rebound,
                'note': 'Semaine et mois qui repartent à la hausse (critères de recherche : pente et R² minimaux « douce » / « souple » ; le semestre ne sert qu’au contexte, sans seuil). Contexte de rebond (semestre peu avancé) 25 % et accélération 20 % du score complexe, référence d’accélération abaissée (0,25) : un retournement net suffit.'},
    'calm_rise': {'label': 'Hausse calme', 'build': _calm,
                  'note': 'Mois et trimestre en hausse douce (critères de recherche : pente et R² minimaux « douce » / « souple » ; la volatilité et le repli ne sont pas des seuils). Volatilité 35 % et drawdown 20 % du score complexe.'},
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
CT_BUILTIN = {'fast': 'growth_v4', 'regular': 'growth_regular', 'calm': 'calm_rise', 'rebound': 'rebound', 'mom6': 'momentum_6m', 'mom12': 'momentum_12m', 'momrisk': 'momentum_risk'}      # stratégies d'origine de la page Classement -> stratégie de scores V4


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
                for f, key in (() if pid == 'day' else (('min_slope', 'slope'), ('min_r2', 'r2'))):      # Jour : pas de pente ni de R² sur une séance
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
                if not [pid for pid in active if pid != 'day']:               # Jour seul n'a aucun poids automatique : la stratégie garde alors les scores par défaut
                    continue
                name = f'ct:{uid}:{it["id"]}'
                DYNAMIC[name] = {'label': it.get('name') or name, 'build': _ct_builder(name, active, per), 'note': 'Stratégie personnelle du Classement : granularités actives de cette stratégie, notes réglées ici.'}
        except (ValueError, KeyError, TypeError, AttributeError):
            continue                                                                      # document illisible : ignoré, jamais bloquant


def known(name):
    if name in DYNAMIC and USER['id'] and not str(name).startswith(f"ct:{USER['id']}:"):
        return False                                           # la stratégie personnelle d'un autre utilisateur n'existe pas pour celui-ci
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
