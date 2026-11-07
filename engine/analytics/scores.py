"""Scores V4 : score simple et score complexe, de 0 à 100, calculés titre par titre.

Principes (validés le 2026-11-06, voir docs/SCORES_V4.md) :
  * Les scores ne dépendent QUE des mesures du titre, des granularités actives et de leurs poids. Ils ne dépendent ni des filtres de
    conformité, ni des seuils de la stratégie, ni des autres titres de l'univers (aucun percentile) : changer un critère ne change aucune note.
  * Chaque mesure est calculée par granularité (fenêtres cumulées de n séances), notée sur une échelle absolue, puis agrégée avec des poids
    qui somment à 1 sur les seules granularités actives. De 1 à 6 granularités : rien n'est codé pour deux ou trois périodes.
  * Donnée absente : jamais zéro « mesuré » ni note favorable. La composante manquante sort du calcul et les poids restants sont renormalisés
    (V4.2). Trois cas : historique suffisant (« ok »), historique réduit (note calculée, « partiel », couverture et fiabilité indiquées),
    calcul impossible (« inconnu », raison explicite). Le seuil de couverture n'élimine plus aucun titre.
  * Une mesure globale (liquidité) est comptée une seule fois, pas par granularité.
  * Les événements externes (résultats, rachat) n'entrent jamais dans les scores.

Le module ne connaît ni la base ni le réseau.
"""
import math

VERSION = 5   # 5 : dénominateur du score complexe aligné sur son numérateur (composantes mesurables sur une partie seulement des périodes)
KAPPA = 0.7                  # poids automatiques : ω_p ∝ n_p^(1−κ) − n_{p−1}^(1−κ) ; κ = 0,7 redonne les 41,6 % / 58,4 % semaine / mois de V1
COVERAGE_THRESHOLD = 0.75    # seuil de FIABILITÉ (information) : ne supprime plus aucune note
MIN_SESSIONS = 3             # R² et volatilité n'existent pas sous 3 séances : la granularité « jour » n'entre jamais dans un score
SAT_A, SAT_B = 17.0, 0.52    # croissance lissée qui sature la note de dynamique : A·(n/5)^0,52 %. A = 17 par défaut (90e percentile observé, titres admis V1) ; A est réglable par stratégie (SAT_A_RANGE)
SAT_A_RANGE = (5.0, 200.0)   # bornes de A (croissance, en %, sur 5 séances à laquelle la dynamique vaut 100)
ACCEL_REF, ACCEL_REF_RANGE = 0.4, (0.05, 5.0)   # coefficient k de la référence d'accélération : ref = saturation(n)/n × k (écart de pente par séance, en %, pour lequel la note d'accélération vaut 100)
ACCEL_R2 = 0.6               # garde-fou de régularité de l'accélération : facteur clamp(min(R², R²_préc)/0,6)
VOL_MODES = ('absolute', 'relative')   # volatilité : seuils absolus (1 % → 5 %/séance) ou rapportée à la pente (rapport volatilité/pente, plancher de pente VOL_SLOPE_FLOOR)
VOL_SLOPE_FLOOR = 0.3        # %/séance : pente minimale retenue au dénominateur du mode « relative » (évite les divisions instables)
VOL_RATIO_BEST, VOL_RATIO_WORST = 1.0, 4.0     # mode « relative » : rapport volatilité/pente ≤ 1 → 100, ≥ 4 → 0
MOMENTUM_HORIZONS = ('6m', '12m', 'blend')
RECOVERY_BEST, RECOVERY_WORST = -10.0, 20.0     # contexte de rebond : rendement du semestre (%) ≤ −10 → 100, ≥ +20 → 0 (le titre n'a pas déjà progressé)
MOMENTUM_SAT = {'6m': 60.0, '12m': 100.0}      # variation (%) J−126→J−21 / J−252→J−21 pour laquelle la note de momentum vaut 100
GATE_FLOOR = 32.0            # note de dynamique (0-100) en dessous de laquelle régularité et risque d'une période sont amortis
RELIABILITY_SESSIONS = 21    # le R² d'une fenêtre plus courte est bruité : poids min(1, n/21) dans la moyenne des R²
ANCHOR_LAMBDA = 0.5          # ancrage récent du score complexe : × (1 − λ(1 − g_court)) ; λ réglable dans l'administration (0 = neutralisé, 1 = maximal)
LIQUIDITY_FLOOR_EUR, LIQUIDITY_CEIL_EUR = 2e6, 50e6      # échelle logarithmique 0 → 100 de la liquidité (valeur échangée par jour, en euros)

COMPLEX_WEIGHTS = {'dynamics': 40, 'r2': 15, 'up_days': 5, 'concentration': 7, 'volatility': 15, 'drawdown': 8, 'liquidity': 10, 'acceleration': 0, 'momentum': 0, 'recovery': 0}
COMPLEX_LABELS = {'dynamics': 'Dynamique', 'r2': 'Régularité (R²)', 'up_days': 'Séances positives', 'concentration': 'Concentration des gains',
                  'volatility': 'Volatilité', 'drawdown': 'Drawdown', 'liquidity': 'Liquidité', 'acceleration': 'Accélération', 'momentum': 'Momentum (6/12 mois)', 'recovery': 'Contexte de rebond'}
PER_PERIOD = ('dynamics', 'r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'acceleration')
GATED = ('r2', 'up_days', 'concentration', 'volatility', 'drawdown')


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def saturation(n, sat_a=SAT_A):
    """Croissance lissée (en %) sur n séances au-delà de laquelle la dynamique vaut 100 (sat_a : réglage de la stratégie)."""
    return sat_a * (n / 5.0) ** SAT_B


def vol_note(vol, slope, mode='absolute'):
    """Note 0-100 de volatilité. absolute : (5 − vol)/4 ; relative : rapport vol/max(pente, plancher), 1 → 100 et 4 → 0 (une forte hausse à forte volatilité n'est plus écrasée, une pente nulle ou négative l'est)."""
    if vol is None:
        return None
    if mode == 'relative':
        if slope is None:
            return None
        ratio = vol / max(slope, VOL_SLOPE_FLOOR)
        return 100 * clamp((VOL_RATIO_WORST - ratio) / (VOL_RATIO_WORST - VOL_RATIO_BEST))
    return 100 * clamp((5 - vol) / 4)


def recovery_note(perf_half):
    """Note 0-100 du contexte de rebond : un titre dont le semestre n'a presque pas progressé (ou a reculé) et qui repart. Rendement absent : None."""
    if perf_half is None:
        return None
    return 100 * clamp((RECOVERY_WORST - perf_half) / (RECOVERY_WORST - RECOVERY_BEST))


def momentum_note(momentum, horizon='6m'):
    """Note 0-100 du momentum (variation en % hors dernier mois). Absent : None ; négatif : 0."""
    m = momentum or {}
    keys = ('6m', '12m') if horizon == 'blend' else (horizon,)
    vals = [100 * clamp(m[k] / MOMENTUM_SAT[k]) for k in keys if m.get(k) is not None]
    return sum(vals) / len(vals) if vals else None


def period_growth(slope, n):
    """Pente (% par séance) ramenée à une croissance composée sur n séances, en %."""
    if slope is None:
        return None
    if slope <= -100:
        return -100.0
    return 100 * math.expm1(n * math.log1p(slope / 100))


def auto_weights(sessions, kappa=KAPPA):
    """{n: poids} qui somment à 1 ; chaque anneau de séances (n_{p−1}, n_p] compte une fois, avec un exposant κ < 1 qui allège les longues fenêtres."""
    ns = sorted(set(sessions))
    if not ns:
        return {}
    if not 0 <= kappa < 1:
        raise ValueError('κ doit être dans [0, 1[')
    prev, raw = 1, {}
    for n in ns:
        raw[n] = max(n ** (1 - kappa) - prev ** (1 - kappa), 1e-12)
        prev = n
    total = sum(raw.values())
    return {n: w / total for n, w in raw.items()}


def resolve_weights(periods, kappa=KAPPA):
    """periods : [{'id','sessions','weight'|None,...}] actives uniquement. Poids personnalisés (renormalisés) si tous fournis et positifs, sinon automatiques.
    Renvoie {id: poids} qui somme à 1 ; une période absente de la liste n'a aucun poids (pas de poids implicite)."""
    if not periods:
        return {}
    custom = [p.get('weight') for p in periods]
    if all(isinstance(w, (int, float)) and not isinstance(w, bool) and math.isfinite(w) and w >= 0 for w in custom) and sum(custom) > 0:
        total = float(sum(custom))
        return {p['id']: p['weight'] / total for p in periods}
    auto = auto_weights([p['sessions'] for p in periods], kappa)
    return {p['id']: auto[p['sessions']] for p in periods}


def liquidity_note(turnover_eur):
    """Note 0-100 de la valeur échangée par jour. Donnée absente ou invalide (None, non finie, négative) : inconnue (None), la composante sort du calcul.
    Valeur connue égale à zéro (volumes réels, aucun échange) : note 0, qui compte dans le calcul."""
    if turnover_eur is None or not math.isfinite(turnover_eur) or turnover_eur < 0:
        return None
    if turnover_eur == 0:
        return 0.0
    return 100 * clamp(math.log10(max(turnover_eur, 1) / LIQUIDITY_FLOOR_EUR) / math.log10(LIQUIDITY_CEIL_EUR / LIQUIDITY_FLOOR_EUR))


def period_components(m, n, sat_a=SAT_A, accel_ref=ACCEL_REF, vol_mode='absolute'):
    """Notes 0-100 d'une période depuis ses mesures brutes. m : {slope, r2, volatility, drawdown, up_fraction, spike_share, accel, r2_prev}.
    Chaque note absente reste None (jamais 0). Renvoie None si la pente n'est pas mesurable."""
    if not m or m.get('slope') is None or n < MIN_SESSIONS:
        return None
    growth = period_growth(m['slope'], n)
    dyn = 100 * clamp(growth / saturation(n, sat_a))
    c = {'growth': growth, 'dynamics': dyn, 'gate': clamp(dyn / GATE_FLOOR), 'raw': {k: m.get(k) for k in ('slope', 'r2', 'volatility', 'drawdown', 'up_fraction', 'spike_share', 'accel')}}
    r2, up, spike, vol, dd = m.get('r2'), m.get('up_fraction'), m.get('spike_share'), m.get('volatility'), m.get('drawdown')
    c['r2'] = None if r2 is None else 100 * clamp((r2 - 0.5) / 0.45)
    c['up_days'] = None if up is None else 100 * clamp((up - 0.4) / 0.4)
    c['concentration'] = None if spike is None else 100 * clamp((0.60 - spike) / 0.50)
    c['volatility'] = vol_note(vol, m.get('slope'), vol_mode)
    c['drawdown'] = None if dd is None else 100 * clamp((15 - dd) / 15)
    accel, r2p = m.get('accel'), m.get('r2_prev')
    if accel is None or r2p is None or r2 is None:
        c['acceleration'] = None
    else:
        ref = saturation(n, sat_a) / n * accel_ref
        c['accel_ref'] = ref
        c['accel_reliability'] = clamp(min(r2, r2p) / ACCEL_R2)        # garde-fou : une accélération entre deux fenêtres irrégulières compte moins
        c['acceleration'] = 50 + 50 * clamp(accel / ref, -1, 1) * c['accel_reliability']
    # Qualité de trajectoire de la période (forme V1) : R² × (1 − ½ pic) × (½ + ½ séances positives)
    c['spike_factor'] = None if spike is None else 1 - 0.5 * clamp(spike)
    c['up_factor'] = None if up is None else 0.5 + 0.5 * up
    return c


def _missing_taxonomy(periods, comps, required):
    """Trois cas distincts : période obligatoire non évaluable / période facultative sans historique / mesure secondaire absente."""
    out = {'required_periods': [], 'optional_periods': [], 'secondary': []}
    for p in periods:
        c = comps[p['id']]
        if c is None:
            out['required_periods' if p['id'] in required else 'optional_periods'].append(p['id'])
        else:
            for k in ('r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'acceleration'):
                if c.get(k) is None:
                    out['secondary'].append(f"{p['id']}:{k}")
    return out


def score_title(inputs, liquidity, periods, weights=None, kappa=KAPPA, required=(), threshold=COVERAGE_THRESHOLD, complex_weights=None, anchor=ANCHOR_LAMBDA,
                sat_a=SAT_A, accel_ref=ACCEL_REF, vol_mode='absolute', momentum=None, momentum_horizon='6m', recovery_perf=None):
    """Calcule les deux scores d'un titre.

    inputs     {sessions: mesures brutes de la fenêtre | None}
    liquidity  {'turnover_eur': float|None, 'source': 'daily'|'estimated'|None}
    periods    granularités ACTIVES : [{'id','sessions','weight'?}], de la plus courte à la plus longue (trié ici)
    required   conservé pour compatibilité et pour l'information (`missing`) : une période obligatoire manquante n'annule plus la note
    threshold  seuil de FIABILITÉ (information) : en dessous, la note est calculée mais marquée « peu fiable »
    Politique des données absentes (V4.2) : trois cas.
      * historique suffisant      → status 'ok'
      * historique réduit         → note calculée sur les seules composantes disponibles, poids renormalisés (ni bonus ni pénalité), status 'partiel'
      * calcul mathématiquement impossible (aucune période mesurable, ou aucune régularité mesurable) → score None, status 'inconnu', raison explicite
    Renvoie {'simple': {...}, 'complex': {...}, 'weights', 'weights_effective', 'periods', 'missing', 'liquidity'}.
    """
    periods = sorted([dict(p) for p in periods if p['sessions'] >= MIN_SESSIONS], key=lambda p: p['sessions'])
    if weights is None:
        weights = resolve_weights(periods, kappa)
    comps = {p['id']: period_components(inputs.get(p['sessions']), p['sessions'], sat_a, accel_ref, vol_mode) for p in periods}
    miss = _missing_taxonomy(periods, comps, set(required))
    avail = [p for p in periods if comps[p['id']] is not None and weights.get(p['id'], 0.0) > 0]
    wtot = sum(weights[p['id']] for p in avail)
    eff = {p['id']: weights[p['id']] / wtot for p in avail} if wtot > 0 else {}
    res = {'weights': weights, 'weights_effective': eff, 'missing': miss, 'version': VERSION,
           'periods': {p['id']: None if comps[p['id']] is None else {k: v for k, v in comps[p['id']].items()} for p in periods},
           'liquidity': {'turnover_eur': (liquidity or {}).get('turnover_eur'), 'source': (liquidity or {}).get('source'),
                         'note': liquidity_note((liquidity or {}).get('turnover_eur'))}}
    if not avail:
        dead = {'score': None, 'status': 'inconnu', 'coverage': 0.0, 'reliable': False,
                'why': 'calcul impossible : aucune période active mesurable' if periods else 'aucune période active'}
        res.update(simple=dead, complex=dict(dead))
        return res
    res['simple'] = _simple(periods, comps, weights, eff, threshold)
    period_cover = wtot / (sum(weights.get(p['id'], 0.0) for p in periods) or 1.0)
    res['complex'] = _complex(avail, comps, weights, eff, period_cover, res['liquidity']['note'], threshold, dict(COMPLEX_WEIGHTS, **(complex_weights or {})), anchor,
                          {'momentum': momentum_note(momentum, momentum_horizon), 'recovery': recovery_note(recovery_perf)})
    res['tuning'] = {'sat_a': sat_a, 'accel_ref': accel_ref, 'vol_mode': vol_mode, 'momentum_horizon': momentum_horizon}
    return res


def _status(coverage):
    return 'ok' if coverage >= 0.999 else 'partiel'


def _simple(periods, comps, weights, eff, threshold):
    """Score simple (V4.3) = 100 × Dynamique × Régularité, plafonné à 100 : uniquement la pente et le R² des périodes sélectionnées.
    Dynamique = Σ ω_p × note de pente de la période p (poids renormalisés sur les périodes mesurables).
    Régularité = moyenne pondérée des R², chaque R² pesant min(1, n/21) (un R² sur peu de séances est bruité) ; périodes sans R² écartées.
    Pics, séances positives, accélération, volatilité, drawdown et liquidité n'y entrent pas : ils ne servent qu'au score complexe."""
    D = cd = 0.0
    r_num = r_den = 0.0
    parts = {}
    for p in periods:
        c = comps[p['id']]
        w0, w = weights.get(p['id'], 0.0), eff.get(p['id'], 0.0)
        if c is None or w <= 0:
            continue
        D += w * c['dynamics'] / 100
        rel = None
        if c['r2'] is not None:
            rel = min(1.0, p['sessions'] / RELIABILITY_SESSIONS)
            r_num += w * rel * max(c['raw']['r2'], 0.0); r_den += w * rel
            cd += w0
        parts[p['id']] = {'weight': w, 'dynamics': c['dynamics'], 'slope': c['raw']['slope'], 'r2': c['raw']['r2'], 'r2_reliability': rel}
    cover_w = sum(weights.get(p['id'], 0.0) for p in periods) or 1.0
    coverage = cd / cover_w                           # part du poids de référence dont la pente ET le R² sont mesurés
    if r_den <= 0:
        return {'score': None, 'status': 'inconnu', 'coverage': coverage, 'reliable': False, 'why': 'calcul impossible : régularité (R²) non mesurable sur aucune période', 'parts': parts}
    Q = r_num / r_den
    return {'score': min(100.0, 100 * D * Q), 'status': _status(coverage), 'coverage': coverage, 'reliable': coverage >= threshold - 1e-12,
            'dynamics': D, 'quality': Q, 'parts': parts}


def _complex(avail, comps, weights, eff, period_cover, liquidity_score, threshold, cw, anchor, extras=None):
    """Score complexe = moyenne pondérée de notes 0-100 : dynamique, régularité, séances positives, concentration, volatilité, drawdown, liquidité (+ accélération si pondérée).
    Une composante indisponible sort du calcul et les poids restants sont renormalisés : elle ne vaut ni zéro ni note favorable.
    `coverage` = part du poids de référence réellement disponible (composantes × périodes ; information de fiabilité)."""
    total = coverage = avail_w = 0.0                # avail_w : poids des composantes disponibles = dénominateur de la moyenne (cohérent avec `total`) ; coverage : fiabilité, information seulement
    contributions = {}
    wsum = float(sum(cw.values())) or 1.0
    ref_w = sum(weights.get(p['id'], 0.0) for p in avail) or 1.0
    for key, weight in cw.items():
        if weight <= 0:
            continue
        w = weight / wsum
        if key in ('liquidity', 'momentum', 'recovery'):           # composantes du titre (pas par période)
            score = liquidity_score if key == 'liquidity' else (extras or {}).get(key)
            if score is not None:
                total += w * score / 100; coverage += w; avail_w += w
                contributions[key] = {'weight': w, 'value': score, 'points': w * score}
            else:
                contributions[key] = {'weight': w, 'value': None, 'points': None, 'unavailable': True}
            continue
        s = cv = 0.0
        for p in avail:
            c, pw = comps[p['id']], eff.get(p['id'], 0.0)
            if c.get(key) is None or pw <= 0:
                continue
            gate = 1.0 if key in ('dynamics', 'acceleration') else c['gate']
            s += pw * gate * c[key]; cv += pw
        if cv <= 0:
            contributions[key] = {'weight': w, 'value': None, 'points': None, 'unavailable': True}
            continue
        s /= cv                                   # moyenne sur les seules périodes où la mesure existe
        total += w * s / 100; coverage += w * cv; avail_w += w      # la composante compte pour son poids entier (sa note est déjà la moyenne des périodes mesurées) ; cv n'alimente que la fiabilité
        contributions[key] = {'weight': w, 'value': s, 'points': w * s, 'coverage': cv}
    if avail_w <= 1e-12:
        return {'score': None, 'status': 'inconnu', 'coverage': 0.0, 'reliable': False, 'why': 'calcul impossible : aucune composante mesurable', 'contributions': contributions}
    for k, v in contributions.items():            # poids effectif après renormalisation sur les composantes disponibles
        if v.get('value') is not None:
            v['weight_effective'] = v['weight'] / avail_w
            v['points_effective'] = v['weight_effective'] * v['value']      # somme = note brute avant ancrage
    base = total / avail_w
    coverage *= period_cover
    short = comps[avail[0]['id']]                  # période la plus courte réellement mesurable (pas de pénalité si la plus courte n'existe pas)
    mult = 1 - anchor * (1 - short['gate'])        # ralentissement ou retournement récent : pénalité progressive, jamais une multiplication brutale
    return {'score': 100 * base * mult, 'status': _status(coverage), 'coverage': coverage, 'reliable': coverage >= threshold - 1e-12, 'anchor': mult, 'anchor_gate': short['gate'], 'anchor_lambda': anchor,
            'raw_total': 100 * base, 'contributions': contributions}


def _id_key(k):
    """Clé de départage déterministe : identifiants numériques dans l'ordre numérique, le reste dans l'ordre du texte."""
    return (0, k, '') if isinstance(k, int) else (1, 0, str(k))


def rank_order(scores, others=None, common=True):
    """{clé: score|None} → (ordre, rangs). Ordre : score décroissant, puis l'autre score décroissant, puis l'identifiant (stable, indépendant des filtres).
    Rang : avec `common`, 1 + nombre de scores strictement plus grands (valeurs brutes, pas arrondies) : les ex æquo réels partagent le rang ; sinon rang = position."""
    others = others or {}
    known = [(k, v) for k, v in scores.items() if v is not None]
    known.sort(key=lambda kv: (-kv[1], -(others.get(kv[0]) if others.get(kv[0]) is not None else float('-inf')), _id_key(kv[0])))
    ranks, last, rank = {}, None, 0
    for pos, (k, v) in enumerate(known, 1):
        if not common or last is None or v != last:
            rank = pos
        last = v
        ranks[k] = rank
    return [k for k, _ in known], ranks


def rank_positions(scores):
    """{clé: score|None} → {clé: rang 1..N} sur les seuls scores connus (rang = position). Usage historique (fiche titre)."""
    return rank_order(scores, common=False)[1]
