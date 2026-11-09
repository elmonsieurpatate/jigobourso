"""Plan de suivi d'une position : tendance, risque, protection indicative et conseil, sans objectif de vente et sans automatisme.

Formules et limites : research/suivi_positions/SPEC_SUIVI_POSITIONS.md (étude locale sur ~9 600 titres, ~400 séances, un seul cycle).
Rien n'est vendu, aucun niveau personnel n'est modifié, aucun objectif de gain n'est inventé : les tests n'ont démontré l'intérêt d'aucun objectif fixe.

Mesures (clôtures corrigées des splits, mêmes définitions que le reste du moteur) :
  σ63            = 100 × écart-type des 63 derniers rendements logarithmiques quotidiens (measures.window_metrics, % par séance)
  m6_1           = 100 × (C[t-21] / C[t-126] − 1)   (même définition que series.momentum_6_1 ; ignore le dernier mois)
  plus haut      = plus haute clôture depuis l'ouverture de la position ; recul = 100 × (1 − cours / plus haut)
  protection     = plus haut × (1 − D(σ63) / 100), D = pire repli à 21 séances au centile 90 observé pour la bande de volatilité
Seuils de risque : bandes de σ63 et centiles mesurés (table BANDS), jamais optimisés ; coupures de niveaux sur les bandes mesurées.
"""
import datetime
import math

from . import measures

MODEL_VERSION = 1
SIGMA_WINDOW = 63
M6_LONG, M6_SKIP = 126, 21
# (borne haute de σ63 en % par séance, niveau, pire repli médian à 21 séances, centile 90 (calibration avant 2026-03-06), P(repli ≥ 10 % sur 21 séances))
BANDS = (
    (1.0, 'low', 2.0, 6.1, 1.4),
    (1.5, 'low', 4.5, 11.0, 8.7),
    (2.0, 'moderate', 6.3, 14.9, 21.3),
    (3.0, 'moderate', 8.5, 19.8, 39.0),
    (4.0, 'high', 11.7, 25.6, 60.5),
    (6.0, 'high', 15.0, 30.3, 74.7),
    (math.inf, 'very_high', 21.3, 40.1, 89.6),
)
LEVELS = {'low': 'Faible', 'moderate': 'Modéré', 'high': 'Élevé', 'very_high': 'Très élevé'}
RECUL_COMBINED = 15.0          # % : seuil de la combinaison « momentum négatif ET recul » testée dans l'étude
MIN_SIGMA_CLOSES = SIGMA_WINDOW + 1
MIN_M6_CLOSES = M6_LONG + 1

# Stratégie de surveillance -> (nom du modèle, niveau de preuve de l'alerte de tendance)
SUPPORT = {
    'regular': ('Croissance régulière', 'validated', 'Alerte de tendance démontrée sur la période étudiée, à effet modeste.'),
    'fast': ('Croissance rapide', 'fragile', 'Alerte de tendance à résultats fragiles : le repli évité dépend de l’aversion au risque et l’alerte ne prédit pas la baisse suivante.'),
    'low_volatility': ('Hausse calme', 'limited', 'Alerte de tendance à bénéfice limité (gains très faibles) sur la période étudiée.'),
    'momentum': ('Momentum 6 mois', 'validated', 'Alerte de tendance démontrée sur la période étudiée, à effet modeste.'),
    'momentum12': ('Momentum 12 mois', 'provisional', 'Règles provisoires : validation hors échantillon insuffisante.'),
    'momentum_risk': ('Momentum ajusté au risque', 'provisional', 'Règles provisoires : validation hors échantillon insuffisante.'),
    'recovery': ('Rebond', 'none', 'Aucune règle de sortie fiable démontrée pour cette stratégie : seuls le risque et le recul sont affichés.'),
}
COMBINED_OK = ('low_volatility', 'momentum')      # stratégies pour lesquelles « momentum < 0 ET recul 15 % » a été testée et soutenue


def band_of(sigma):
    for i, b in enumerate(BANDS):
        if sigma <= b[0]:
            return i, b
    return len(BANDS) - 1, BANDS[-1]


def fr(x, d=1):
    return f'{x:.{d}f}'.replace('.', ',')


def _m6_series(closes, breaks):
    """m6_1 à chaque clôture (None quand indisponible : historique court ou rupture de cours non expliquée après J−126)."""
    last_break = max(breaks) if breaks else -1
    out = [None] * len(closes)
    for i in range(M6_LONG, len(closes)):
        first = i - M6_LONG
        if last_break > first or not (closes[first] > 0):
            continue
        out[i] = 100 * (closes[i - M6_SKIP] / closes[first] - 1)
    return out


def _momentum_state(dates, m6, open_date):
    """État d'armement de l'alerte de tendance depuis l'ouverture : l'alerte n'existe que si le momentum a été ≥ 0 au moins une fois après l'ouverture."""
    idx = [i for i, d in enumerate(dates) if d >= open_date and m6[i] is not None]
    if not idx:
        return {'available': False, 'value': m6[-1] if m6 else None}
    states = [m6[i] < 0 for i in idx]
    cur = m6[-1]
    armed = any(not s for s in states)
    active = cur is not None and cur < 0 and armed
    since = None
    if active:
        j = len(idx) - 1
        while j >= 0 and states[j]:
            j -= 1
        since = dates[idx[j + 1]]
    return {'available': cur is not None, 'value': cur, 'armed': armed, 'active': active, 'since': since,
            'negative_at_open': states[0] and not armed}


def tendance(closes):
    if len(closes) <= SIGMA_WINDOW:
        return None
    m = measures.window_metrics(closes[-(SIGMA_WINDOW + 1):])
    if not m or m['slope'] is None:
        return None
    return {'slope63': m['slope'], 'r2_63': m['r2'], 'label': 'Haussière' if m['slope'] > 0 else 'Baissière' if m['slope'] < 0 else 'Neutre',
            'state': 'up' if m['slope'] > 0 else 'down' if m['slope'] < 0 else 'flat'}


def build(pos, dates, closes, breaks, today=None):
    """pos : {listing_id, qty, avg_cost, price, price_eur, open_date, stop_px, watch_key, watch_label}. Retourne le plan ; chaque valeur manquante reste None (aucune valeur de remplacement)."""
    today = today or datetime.date.today()
    notes = []
    price, price_eur, pru, qty = pos.get('price'), pos.get('price_eur'), pos.get('avg_cost'), pos.get('qty') or 0
    ok_price = price and price > 0 and price_eur and price_eur > 0
    fx = price_eur / price if ok_price else None
    key = pos.get('watch_key') if pos.get('watch_key') in SUPPORT else None
    strat = {'key': key, 'label': SUPPORT[key][0] if key else (pos.get('watch_label') or None), 'support': SUPPORT[key][1] if key else ('custom' if pos.get('watch_label') else 'undefined'),
             'note': SUPPORT[key][2] if key else ('Stratégie personnalisée : aucune règle de tendance validée ne lui est associée. Seuls le risque et le recul sont affichés.' if pos.get('watch_label')
                                                  else 'Aucune stratégie de surveillance définie : suivi neutre (risque et protection indicative seulement).')}
    out = {'model': MODEL_VERSION, 'strategy': strat, 'notes': notes}
    gain_pct = 100 * (price_eur / pru - 1) if ok_price and pru and pru > 0 else None
    out['gain'] = {'pct': gain_pct, 'eur': (price_eur - pru) * qty if gain_pct is not None else None}
    n = len(closes)
    out['sessions'] = n
    if not ok_price:
        out.update(status='unavailable', advice=_advice('na', 'Suivi indisponible : cours actuel manquant.', 'Le cours du titre n’est pas disponible, aucun niveau ne peut être calculé.', ['cours manquant']))
        return out
    od = pos.get('open_date') or ''
    since = [(d, c) for d, c in zip(dates, closes) if d >= od]
    if not since:
        out.update(status='unavailable', advice=_advice('na', 'Suivi indisponible : pas de cours depuis l’ouverture.', 'Aucune clôture n’est disponible depuis l’ouverture de la position.', ['historique vide']))
        return out
    if closes and price / closes[-1] > 1.8 or closes and price / closes[-1] < 1 / 1.8:
        notes.append('Le cours actuel s’écarte fortement de la dernière clôture de l’historique : unités ou split à vérifier, les niveaux sont indicatifs.')
    high_q = max(c for _, c in since)
    high_q = max(high_q, price)                      # le plus haut ne peut pas être sous le cours actuel
    recul = 100 * (1 - price / high_q)
    window63 = closes[-SIGMA_WINDOW:] if n >= SIGMA_WINDOW else closes
    h63 = max(window63 + [price]) if window63 else None
    recul63 = 100 * (1 - price / h63) if h63 else None
    prices = {'current': price_eur, 'pru': pru, 'high': high_q * fx, 'currency': 'EUR', 'local_currency': pos.get('currency'), 'fx': fx, 'high_date': next((d for d, c in since if c == max(c2 for _, c2 in since)), None)}
    stop = pos.get('stop_px')
    prices['personal'] = stop * fx if stop else None
    out.update(prices=prices, recul_pct=recul, recul63_pct=recul63, status='ok')
    out['trend'] = tendance(closes)
    # risque
    risk = None
    if n >= MIN_SIGMA_CLOSES:
        m = measures.window_metrics(closes[-(SIGMA_WINDOW + 1):])
        sigma = m['volatility'] if m else None
        if sigma is not None:
            i, b = band_of(sigma)
            risk = {'sigma63': sigma, 'level': b[1], 'label': LEVELS[b[1]], 'band': i, 'median_dd21': b[2], 'p90_dd21': b[3], 'p_dd10_21': b[4]}
            prices['suggested'] = high_q * (1 - b[3] / 100) * fx
            out['suggested'] = {'distance_pct': b[3], 'sigma63': sigma, 'band_p90': b[3]}
    if risk is None:
        notes.append(f'Risque et protection indicative indisponibles : {MIN_SIGMA_CLOSES} clôtures nécessaires, {n} disponibles.')
        prices['suggested'] = None
    out['risk'] = risk
    # momentum 6-1
    m6 = _m6_series(closes, breaks) if n >= MIN_M6_CLOSES else [None] * n
    mom = _momentum_state(dates, m6, od)
    if not mom.get('available'):
        notes.append(f'Momentum 6−1 indisponible : {MIN_M6_CLOSES} clôtures sans rupture de cours nécessaires.')
    out['momentum'] = mom
    out['advice'] = _decide(out, strat, key)
    return out


def _advice(tone, headline, detail, why):
    return {'tone': tone, 'headline': headline, 'detail': detail, 'why': why}


def _decide(plan, strat, key):
    """Conseil principal : un seul message, toujours accompagné des chiffres qui l'expliquent. Ordre de priorité figé ; aucune action n'est exécutée."""
    pr, risk, mom, recul = plan['prices'], plan.get('risk'), plan.get('momentum') or {}, plan['recul_pct']
    cur = pr['current']
    why = []
    if pr.get('personal') and cur <= pr['personal']:
        return _advice('alert', 'Ton niveau de protection personnel est atteint.',
                       f'Le cours ({_e(cur)}) est au niveau de ta protection ({_e(pr["personal"])}) ou en dessous. Rien n’est vendu automatiquement : la décision t’appartient.',
                       [f'cours {_e(cur)} ≤ protection personnelle {_e(pr["personal"])}'])
    breach = bool(pr.get('suggested') and cur <= pr['suggested'])
    breach_txt = (f' Le cours est aussi sous le repère de risque calculé ({_e(pr["suggested"])}) : le recul de {fr(recul)} % dépasse le repli habituel '
                  f'(9 cas sur 10 restent sous {fr(risk["p90_dd21"])} % sur 21 séances pour une volatilité comparable). C’est un repère de risque, pas un signal de vente.') if breach else ''
    if mom.get('active') and strat['support'] in ('validated', 'fragile', 'limited', 'provisional'):
        since = _d(mom['since'])
        base = f'Le momentum de moyen terme (6−1) est négatif ({fr(mom["value"])} %) depuis le {since}. Il ignore le dernier mois : le titre peut remonter actuellement.'
        why = [f'm6−1 = {fr(mom["value"])} % < 0 depuis le {since}', 'état déjà positif auparavant depuis l’ouverture (alerte armée)']
        if breach:
            why.append(f'cours {_e(cur)} ≤ repère de risque {_e(pr["suggested"])}')
        if recul >= RECUL_COMBINED and key in COMBINED_OK:
            return _advice('watch', 'Vigilance renforcée : momentum négatif et recul important.', base + f' Le recul depuis le sommet atteint {fr(recul)} % : cette combinaison est celle qui a coûté le moins sur la période étudiée pour cette stratégie.' + breach_txt, why + [f'recul {fr(recul)} % ≥ {fr(RECUL_COMBINED, 0)} %'])
        extra = ' Règle provisoire pour cette stratégie : validation insuffisante.' if strat['support'] == 'provisional' else ' Effet historique modeste : l’alerte ne prédit pas la baisse suivante.'
        return _advice('watch', 'Le momentum de moyen terme est devenu négatif : vigilance renforcée.', base + extra + breach_txt, why)
    if breach:
        return _advice('watch', 'Le cours est sous le repère de risque calculé.', f'Le recul depuis le sommet est de {fr(recul)} %.' + breach_txt + ' Dans l’étude, le rendement moyen des séances suivant un tel franchissement n’a pas été négatif : ne pas agir mécaniquement.',
                       [f'recul {fr(recul)} % > repli au centile 90 de la bande ({fr(risk["p90_dd21"])} %)', f'σ63 = {fr(risk["sigma63"])} % par séance'])
    if risk and recul > risk['median_dd21']:
        return _advice('watch', f'Le titre a reculé de {fr(recul)} % depuis son sommet. ' + ('Surveille ton niveau de protection.' if pr.get('personal') else 'Surveille le repère de protection suggéré.'),
                       f'C’est plus que le repli médian observé sur 21 séances pour une volatilité comparable ({fr(risk["median_dd21"])} %), sans dépasser le repère de risque ({_e(pr["suggested"])}).' if pr.get('suggested') else 'Le repère de risque n’est pas disponible.',
                       [f'recul {fr(recul)} % > repli médian {fr(risk["median_dd21"])} %'])
    if risk and risk['level'] in ('high', 'very_high'):
        gain = plan['gain']['pct']
        lead = 'La volatilité est élevée' if risk['level'] == 'high' else 'La volatilité est très élevée'
        tail = ' Un gain important ne protège pas d’un repli.' if gain is not None and gain > 20 else ''
        return _advice('info', f'{lead} : des replis importants restent possibles.',
                       f'σ63 = {fr(risk["sigma63"])} % par séance. Pour des titres comparables, un repli d’au moins 10 % est observé dans {fr(risk["p_dd10_21"], 0)} % des fenêtres de 21 séances.{tail}',
                       [f'σ63 = {fr(risk["sigma63"])} %', f'P(repli ≥ 10 % sur 21 séances) ≈ {fr(risk["p_dd10_21"], 0)} %'])
    if not risk:
        return _advice('na', 'Suivi partiel : historique insuffisant.', 'Pas assez de clôtures pour mesurer le risque. Aucun signal ne peut être affiché.', ['clôtures insuffisantes'])
    g = plan['gain']['pct']
    trend = (plan.get('trend') or {}).get('state')
    if g is not None and g > 0:
        return _advice('ok', 'La position progresse sans signal de vigilance particulier.', f'Le titre est {fr(g)} % au-dessus de ton prix de revient, à {fr(recul)} % de son sommet. Aucun objectif de vente n’est fixé : le suivi sert à laisser courir les gains.', ['aucun signal actif'])
    return _advice('ok', 'Aucun signal de vigilance particulier.', f'La position est à {fr(g) if g is not None else "–"} % de ton prix de revient. Une perte latente n’est pas un signal en soi.' + (' La tendance 63 séances est baissière.' if trend == 'down' else ''), ['aucun signal actif'])


def _e(v):
    return 'n/d' if v is None else f'{v:,.2f}'.replace(',', ' ').replace('.', ',') + ' €'


def _d(iso):
    return iso[8:10] + '/' + iso[5:7] + '/' + iso[0:4] if iso else ''


def _load(conn, ids):
    """{listing_id: (dates, closes, breaks)} : clôtures corrigées des splits (prepare_series) et ruptures de cours non expliquées."""
    from .series import prepare_series
    out = {}
    if not ids:
        return out
    marks = ','.join(['%s'] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f'SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({marks}) ORDER BY listing_id, price_date', list(ids))
        bars = {}
        for r in cur.fetchall():
            bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
        cur.execute(f"SELECT listing_id, event_date, ratio FROM corporate_events WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split')", list(ids))
        splits = {}
        for r in cur.fetchall():
            splits.setdefault(r['listing_id'], []).append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
    for lid in ids:
        dates, closes, _basis, breaks = prepare_series(bars.get(lid, []), splits.get(lid, ()))
        out[lid] = (dates, closes, breaks)
    return out


def run(conn, request, today=None):
    """request : {positions: [{listing_id, qty, avg_cost, price, price_eur, currency, open_date, stop_px, watch_key, watch_label}]}."""
    pos = [p for p in request.get('positions', []) if p.get('listing_id')]
    series = _load(conn, sorted({int(p['listing_id']) for p in pos}))
    out = {}
    for p in pos:
        dates, closes, breaks = series.get(int(p['listing_id']), ([], [], []))
        out[str(p['listing_id'])] = build(p, dates, closes, breaks, today)
    return {'positions': out, 'model': MODEL_VERSION}
