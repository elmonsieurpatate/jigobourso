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

VERSION = 3
KAPPA = 0.7                  # poids automatiques : ω_p ∝ n_p^(1−κ) − n_{p−1}^(1−κ) ; κ = 0,7 redonne les 41,6 % / 58,4 % semaine / mois de V1
COVERAGE_THRESHOLD = 0.75    # seuil de FIABILITÉ (information) : ne supprime plus aucune note
MIN_SESSIONS = 3             # R² et volatilité n'existent pas sous 3 séances : la granularité « jour » n'entre jamais dans un score
SAT_A, SAT_B = 17.0, 0.52    # croissance lissée qui sature la note de dynamique : 17·(n/5)^0,52 % (90e percentile observé, titres admis V1)
GATE_FLOOR = 32.0            # note de dynamique (0-100) en dessous de laquelle régularité et risque d'une période sont amortis
RELIABILITY_SESSIONS = 21    # le R² d'une fenêtre plus courte est bruité : poids min(1, n/21) dans la moyenne des R²
ANCHOR_LAMBDA = 0.5          # ancrage récent du score complexe : × (1 − λ(1 − g_court)) ; λ réglable dans l'administration (0 = neutralisé, 1 = maximal)
LIQUIDITY_FLOOR_EUR, LIQUIDITY_CEIL_EUR = 2e6, 50e6      # échelle logarithmique 0 → 100 de la liquidité (valeur échangée par jour, en euros)

COMPLEX_WEIGHTS = {'dynamics': 40, 'r2': 15, 'up_days': 5, 'concentration': 7, 'volatility': 15, 'drawdown': 8, 'liquidity': 10, 'acceleration': 0}
COMPLEX_LABELS = {'dynamics': 'Dynamique', 'r2': 'Régularité (R²)', 'up_days': 'Séances positives', 'concentration': 'Concentration des gains',
                  'volatility': 'Volatilité', 'drawdown': 'Drawdown', 'liquidity': 'Liquidité', 'acceleration': 'Accélération'}
PER_PERIOD = ('dynamics', 'r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'acceleration')
GATED = ('r2', 'up_days', 'concentration', 'volatility', 'drawdown')


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def saturation(n):
    """Croissance lissée (en %) sur n séances au-delà de laquelle la dynamique vaut 100."""
    return SAT_A * (n / 5.0) ** SAT_B


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


def period_components(m, n):
    """Notes 0-100 d'une période depuis ses mesures brutes. m : {slope, r2, volatility, drawdown, up_fraction, spike_share, accel, r2_prev}.
    Chaque note absente reste None (jamais 0). Renvoie None si la pente n'est pas mesurable."""
    if not m or m.get('slope') is None or n < MIN_SESSIONS:
        return None
    growth = period_growth(m['slope'], n)
    dyn = 100 * clamp(growth / saturation(n))
    c = {'growth': growth, 'dynamics': dyn, 'gate': clamp(dyn / GATE_FLOOR), 'raw': {k: m.get(k) for k in ('slope', 'r2', 'volatility', 'drawdown', 'up_fraction', 'spike_share', 'accel')}}
    r2, up, spike, vol, dd = m.get('r2'), m.get('up_fraction'), m.get('spike_share'), m.get('volatility'), m.get('drawdown')
    c['r2'] = None if r2 is None else 100 * clamp((r2 - 0.5) / 0.45)
    c['up_days'] = None if up is None else 100 * clamp((up - 0.4) / 0.4)
    c['concentration'] = None if spike is None else 100 * clamp((0.60 - spike) / 0.50)
    c['volatility'] = None if vol is None else 100 * clamp((5 - vol) / 4)
    c['drawdown'] = None if dd is None else 100 * clamp((15 - dd) / 15)
    accel, r2p = m.get('accel'), m.get('r2_prev')
    if accel is None or r2p is None or r2 is None:
        c['acceleration'] = None
    else:
        ref = saturation(n) / n * 0.4
        c['acceleration'] = 50 + 50 * clamp(accel / ref, -1, 1) * clamp(min(r2, r2p) / 0.6)
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


def score_title(inputs, liquidity, periods, weights=None, kappa=KAPPA, required=(), threshold=COVERAGE_THRESHOLD, complex_weights=None, anchor=ANCHOR_LAMBDA):
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
    comps = {p['id']: period_components(inputs.get(p['sessions']), p['sessions']) for p in periods}
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
    res['complex'] = _complex(avail, comps, weights, eff, period_cover, res['liquidity']['note'], threshold, dict(COMPLEX_WEIGHTS, **(complex_weights or {})), anchor)
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


def _complex(avail, comps, weights, eff, period_cover, liquidity_score, threshold, cw, anchor):
    """Score complexe = moyenne pondérée de notes 0-100 : dynamique, régularité, séances positives, concentration, volatilité, drawdown, liquidité (+ accélération si pondérée).
    Une composante indisponible sort du calcul et les poids restants sont renormalisés : elle ne vaut ni zéro ni note favorable.
    `coverage` = part du poids de référence réellement disponible (composantes × périodes ; information de fiabilité)."""
    total = coverage = 0.0
    contributions = {}
    wsum = float(sum(cw.values())) or 1.0
    ref_w = sum(weights.get(p['id'], 0.0) for p in avail) or 1.0
    for key, weight in cw.items():
        if weight <= 0:
            continue
        w = weight / wsum
        if key == 'liquidity':
            if liquidity_score is not None:
                total += w * liquidity_score / 100; coverage += w
                contributions[key] = {'weight': w, 'value': liquidity_score, 'points': w * liquidity_score}
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
        total += w * s / 100; coverage += w * cv
        contributions[key] = {'weight': w, 'value': s, 'points': w * s, 'coverage': cv}
    if coverage <= 1e-12:
        return {'score': None, 'status': 'inconnu', 'coverage': 0.0, 'reliable': False, 'why': 'calcul impossible : aucune composante mesurable', 'contributions': contributions}
    for k, v in contributions.items():            # poids effectif après renormalisation sur les composantes disponibles
        if v.get('value') is not None:
            v['weight_effective'] = v['weight'] / coverage
            v['points_effective'] = v['weight_effective'] * v['value']      # somme = note brute avant ancrage
    base = total / coverage
    coverage *= period_cover
    short = comps[avail[0]['id']]                  # période la plus courte réellement mesurable (pas de pénalité si la plus courte n'existe pas)
    mult = 1 - anchor * (1 - short['gate'])        # ralentissement ou retournement récent : pénalité progressive, jamais une multiplication brutale
    return {'score': 100 * base * mult, 'status': _status(coverage), 'coverage': coverage, 'reliable': coverage >= threshold - 1e-12, 'anchor': mult, 'anchor_gate': short['gate'], 'anchor_lambda': anchor,
            'raw_total': 100 * base, 'contributions': contributions}


def rank_positions(scores):
    """{clé: score|None} → {clé: rang 1..N} sur les seuls scores connus, ex æquo départagés par la clé (stable, indépendant des filtres)."""
    known = sorted(((k, v) for k, v in scores.items() if v is not None), key=lambda kv: (-kv[1], str(kv[0])))
    return {k: i for i, (k, _) in enumerate(known, 1)}
