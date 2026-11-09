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
# États du conseil (jamais un ordre) : libellé affiché, ton visuel. Priorité décroissante : sortie > réévaluation > vigilance > conserver.
STATES = {'exit': ('Sortie à envisager', 'exit'), 'reevaluate': ('Réévaluer', 'reeval'), 'watch': ('Surveiller', 'watch'), 'keep': ('Conserver', 'ok'), 'na': ('Suivi partiel', 'na')}
RULE_LABELS = {'stop': 'Filet de protection', 'recul': 'Recul maximal depuis le sommet', 'trend': 'Dégradation de tendance (momentum 6−1)',
               'risk': 'Alerte de risque (volatilité élevée)', 'target': 'Objectif de gain personnel'}
RULE_KEYS = tuple(RULE_LABELS)


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
        out.update(status='unavailable', advice=_advice('na', 'Cours actuel manquant : suivi indisponible.', 'Le cours du titre n’est pas disponible, aucun niveau ne peut être calculé.', ['cours manquant']))
        return out
    od = pos.get('open_date') or ''
    since = [(d, c) for d, c in zip(dates, closes) if d >= od]
    if not since:
        out.update(status='unavailable', advice=_advice('na', 'Pas de cours depuis l’ouverture : suivi indisponible.', 'Aucune clôture n’est disponible depuis l’ouverture de la position.', ['historique vide']))
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
    target = pos.get('target_px')
    prices['target'] = target * fx if target else None
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
    out['rules'] = _rules(pos, out, strat, key)
    out['advice'] = _decide(out, strat, key)
    return out


def _advice(state, message, detail, why, rule=None, others=None, protection=None):
    label, tone = STATES[state]
    return {'state': state, 'label': label, 'tone': tone, 'message': message, 'headline': f'{label} — {message}', 'detail': detail, 'why': why, 'rule': rule,
            'others': others or [], 'protection': protection}


def _cfg(pos, key):
    """Réglage d'une règle : activée par défaut, valeur personnalisée absente par défaut (mode automatique)."""
    c = (pos.get('rules') or {}).get(key) or {}
    return {'enabled': c.get('enabled', True) is not False, 'custom': c.get('custom')}


def _rules(pos, plan, strat, key):
    """Les cinq règles de surveillance d'une position : valeur automatique (calculée par le moteur), valeur personnalisée (jamais écrasée), valeur effective, état.
    Une règle personnalisée remplace la valeur automatique pour CETTE règle seulement ; le moteur continue de calculer sa suggestion. Aucune règle n'ordonne de vente."""
    pr, risk, mom, recul = plan['prices'], plan.get('risk'), plan.get('momentum') or {}, plan['recul_pct']
    cur, fx = pr['current'], pr['fx']
    out = []
    # filet de protection : automatique = plus-haut × (1 − repli au centile 90) ; personnalisé = position_levels.stop_px (devise de cotation)
    c = _cfg(pos, 'stop'); stop = pos.get('stop_px')
    mode = 'custom' if stop else 'auto'
    auto = pr.get('suggested'); eff = (pr['personal'] if mode == 'custom' else auto) if c['enabled'] else None
    pr['effective'] = eff; pr['effective_source'] = mode if eff is not None else None
    out.append({'key': 'stop', 'label': RULE_LABELS['stop'], 'enabled': c['enabled'], 'mode': mode, 'auto': auto, 'custom': pr['personal'], 'custom_local': stop, 'effective': eff, 'unit': 'price',
                'available': auto is not None or mode == 'custom', 'triggered': eff is not None and cur <= eff,
                'note': None if auto is not None else f'Protection automatique indisponible : {MIN_SIGMA_CLOSES} clôtures nécessaires.'})
    # recul maximal depuis le sommet : automatique = repli médian à 21 séances de la bande de volatilité (vigilance) ; personnalisé = seuil choisi (réévaluation)
    c = _cfg(pos, 'recul'); custom = c['custom'] if isinstance(c['custom'], (int, float)) and 0 < c['custom'] < 100 else None
    auto = risk['median_dd21'] if risk else None; eff = (custom if custom is not None else auto) if c['enabled'] else None
    out.append({'key': 'recul', 'label': RULE_LABELS['recul'], 'enabled': c['enabled'], 'mode': 'custom' if custom is not None else 'auto', 'auto': auto, 'custom': custom, 'effective': eff, 'unit': 'pct',
                'available': auto is not None or custom is not None, 'triggered': eff is not None and recul > eff, 'note': None if auto is not None else 'Seuil automatique indisponible : historique insuffisant.'})
    # dégradation de tendance : momentum 6−1 négatif après avoir été positif ; réservée aux stratégies pour lesquelles l'étude la soutient
    c = _cfg(pos, 'trend'); supported = strat['support'] in ('validated', 'fragile', 'limited', 'provisional')
    out.append({'key': 'trend', 'label': RULE_LABELS['trend'], 'enabled': c['enabled'], 'mode': 'auto', 'auto': None, 'custom': None, 'effective': None, 'unit': 'flag', 'available': bool(mom.get('available')) and supported,
                'triggered': c['enabled'] and supported and bool(mom.get('active')),
                'note': None if supported else 'Aucune règle de tendance validée pour cette stratégie (risque et recul seulement).' if strat['support'] != 'undefined' else 'Aucune stratégie de surveillance définie.'})
    # alerte de risque : volatilité 63 séances élevée ou très élevée (information de vigilance, jamais de sortie)
    c = _cfg(pos, 'risk')
    out.append({'key': 'risk', 'label': RULE_LABELS['risk'], 'enabled': c['enabled'], 'mode': 'auto', 'auto': None, 'custom': None, 'effective': None, 'unit': 'flag', 'available': risk is not None,
                'triggered': c['enabled'] and bool(risk) and risk['level'] in ('high', 'very_high'), 'note': None if risk else 'Volatilité indisponible : historique insuffisant.'})
    # objectif de gain : jamais automatique ; seulement si l'utilisateur en a défini un
    c = _cfg(pos, 'target'); tgt = pos.get('target_px'); teur = pr.get('target')
    out.append({'key': 'target', 'label': RULE_LABELS['target'], 'enabled': c['enabled'], 'mode': 'custom' if tgt else 'none', 'auto': None, 'custom': teur, 'custom_local': tgt, 'effective': teur if c['enabled'] else None,
                'unit': 'price', 'available': bool(tgt), 'triggered': bool(c['enabled'] and teur and cur >= teur), 'note': 'Aucun objectif automatique : le suivi n’en invente pas.'})
    return out


def _protection_note(plan):
    r = next(x for x in plan['rules'] if x['key'] == 'stop')
    if not r['enabled']:
        return 'Protection désactivée pour cette position.'
    if r['effective'] is None:
        return r['note'] or 'Protection indisponible.'
    if r['mode'] == 'custom':
        return f'Protection personnelle : {_e(r["effective"])}' + (f' (automatique : {_e(r["auto"])}).' if r['auto'] is not None else '.')
    return f'Protection automatique : {_e(r["effective"])}. Tu peux la modifier.'


def _decide(plan, strat, key):
    """Conseil principal : CONSERVER, SURVEILLER, RÉÉVALUER ou SORTIE À ENVISAGER, toujours avec la règle déclenchée et les chiffres qui l'expliquent.
    Priorité figée : sortie (protection effective franchie, objectif personnel atteint) > réévaluation (seuil de recul personnel, momentum négatif + recul) > vigilance (tendance, recul, risque) > conserver.
    Aucune action n'est exécutée ; un repère automatique n'est jamais un ordre de vente ni une prévision."""
    pr, risk, mom, recul = plan['prices'], plan.get('risk'), plan.get('momentum') or {}, plan['recul_pct']
    cur, R = pr['current'], {r['key']: r for r in plan['rules']}
    prot = _protection_note(plan)
    trig = []                                              # (état, règle, message, détail, pourquoi), par ordre de priorité
    s_ = R['stop']
    if s_['triggered']:
        v = s_['effective']
        if s_['mode'] == 'custom':
            trig.append(('exit', 'stop', f'Ta protection personnelle de {_e(v)} est franchie.', f'Le cours ({_e(cur)}) est sous ta protection ({_e(v)}) ou à son niveau. Rien n’est vendu automatiquement : la décision t’appartient.',
                         [f'cours {_e(cur)} ≤ protection personnelle {_e(v)}']))
        else:
            trig.append(('exit', 'stop', f'La protection automatique de {_e(v)} est franchie.',
                         f'Le cours ({_e(cur)}) est sous le repère de risque calculé ({_e(v)}) : le recul de {fr(recul)} % depuis le sommet dépasse le repli que 9 titres comparables sur 10 ne dépassent pas sur 21 séances ({fr(risk["p90_dd21"])} %). '
                         'C’est un repère statistique de surveillance, pas un ordre de vente ni une prévision : dans l’étude, le rendement moyen des séances suivant un tel franchissement n’a pas été négatif, ne pas agir mécaniquement.',
                         [f'cours {_e(cur)} ≤ protection automatique {_e(v)}', f'recul {fr(recul)} % > repli au centile 90 de la bande ({fr(risk["p90_dd21"])} %)', f'σ63 = {fr(risk["sigma63"])} % par séance']))
    t_ = R['target']
    if t_['triggered']:
        v = t_['effective']
        trig.append(('exit', 'target', f'Ton objectif de gain de {_e(v)} est atteint.', f'Le cours ({_e(cur)}) a atteint l’objectif personnel que tu as défini. Le suivi n’en déduit aucune vente : la décision t’appartient.', [f'cours {_e(cur)} ≥ objectif personnel {_e(v)}']))
    rc = R['recul']
    if rc['triggered'] and rc['mode'] == 'custom':
        trig.append(('reevaluate', 'recul', f'Le recul depuis le sommet ({fr(recul)} %) dépasse ton seuil de {fr(rc["effective"])} %.', f'Tu as défini un seuil de recul maximal de {fr(rc["effective"])} % : le cours est {fr(recul)} % sous son plus-haut depuis l’ouverture ({_e(pr["high"])}).',
                     [f'recul {fr(recul)} % > seuil personnel {fr(rc["effective"])} %']))
    tr = R['trend']
    if tr['triggered']:
        since = _d(mom['since'])
        base = f'Le momentum de moyen terme (6−1) est négatif ({fr(mom["value"])} %) depuis le {since}. Il ignore le dernier mois : le titre peut remonter actuellement.'
        why = [f'm6−1 = {fr(mom["value"])} % < 0 depuis le {since}', 'état déjà positif auparavant depuis l’ouverture (alerte armée)']
        if recul >= RECUL_COMBINED and key in COMBINED_OK:
            trig.append(('reevaluate', 'trend', f'Momentum négatif et recul de {fr(recul)} % : règle de réévaluation de la stratégie {strat["label"]}.',
                         base + f' Le recul depuis le sommet atteint {fr(recul)} % : cette combinaison est celle qui a coûté le moins sur la période étudiée pour cette stratégie.', why + [f'recul {fr(recul)} % ≥ {fr(RECUL_COMBINED, 0)} %']))
        else:
            extra = ' Règle provisoire pour cette stratégie : validation insuffisante.' if strat['support'] == 'provisional' else ' Effet historique modeste : l’alerte ne prédit pas la baisse suivante.'
            trig.append(('watch', 'trend', 'Le momentum de moyen terme est devenu négatif : vigilance renforcée.', base + extra, why))
    if rc['triggered'] and rc['mode'] == 'auto':
        trig.append(('watch', 'recul', f'Le titre a reculé de {fr(recul)} % depuis son sommet, plus que le repli médian habituel ({fr(rc["effective"])} %).',
                     f'C’est plus que le repli médian observé sur 21 séances pour une volatilité comparable ({fr(rc["effective"])} %).' + (f' Le repère de protection est à {_e(pr["suggested"])}.' if pr.get('suggested') else ''),
                     [f'recul {fr(recul)} % > repli médian {fr(rc["effective"])} %']))
    if R['risk']['triggered']:
        grade = 'très élevé' if risk['level'] == 'very_high' else 'élevé'
        up = (plan.get('trend') or {}).get('state') == 'up' and recul <= risk['median_dd21']
        trig.append(('watch', 'risk', ('La hausse se poursuit, mais le risque de repli est ' if up else 'Le risque de repli est ') + grade + '.',
                     f'σ63 = {fr(risk["sigma63"])} % par séance. Pour des titres comparables, un repli d’au moins 10 % est observé dans {fr(risk["p_dd10_21"], 0)} % des fenêtres de 21 séances. Un gain important ne protège pas d’un repli.' if (plan['gain']['pct'] or 0) > 20
                     else f'σ63 = {fr(risk["sigma63"])} % par séance. Pour des titres comparables, un repli d’au moins 10 % est observé dans {fr(risk["p_dd10_21"], 0)} % des fenêtres de 21 séances.',
                     [f'σ63 = {fr(risk["sigma63"])} %', f'P(repli ≥ 10 % sur 21 séances) ≈ {fr(risk["p_dd10_21"], 0)} %']))
    if trig:
        order = {'exit': 0, 'reevaluate': 1, 'watch': 2}
        trig.sort(key=lambda t: order[t[0]])                  # tri stable : à état égal, l'ordre de priorité ci-dessus est conservé
        st, rule, msg, detail, why = trig[0]
        others = [{'key': t[1], 'state': t[0], 'label': STATES[t[0]][0], 'text': t[2], 'detail': t[3], 'why': t[4]} for t in trig[1:]]
        return _advice(st, msg, detail, why, rule, others, prot)
    g = plan['gain']['pct']
    if not risk and R['stop']['effective'] is None:
        return _advice('na', 'Historique insuffisant pour mesurer le risque.', 'Pas assez de clôtures pour calculer le risque et la protection automatique. Aucun signal ne peut être affiché ; tes règles personnelles restent surveillées.', ['clôtures insuffisantes'], None, [], prot)
    trend = (plan.get('trend') or {}).get('state')
    sig = f' Cela ne signifie pas que le titre est sans risque (volatilité {fr(risk["sigma63"])} % par séance, niveau {risk["label"].lower()}).' if risk else ''
    if g is not None and g > 0:
        return _advice('keep', 'La position progresse et aucune protection n’est franchie.', f'Le titre est {fr(g)} % au-dessus de ton prix de revient, à {fr(recul)} % de son sommet. Aucun objectif de vente n’est fixé : le suivi sert à laisser courir les gains.' + sig, ['aucun critère de sortie ou de réévaluation déclenché'], None, [], prot)
    return _advice('keep', 'Aucune protection n’est franchie.', f'La position est à {fr(g) if g is not None else "–"} % de ton prix de revient. Une perte latente n’est pas un signal en soi.' + (' La tendance 63 séances est baissière.' if trend == 'down' else '') + sig,
                   ['aucun critère de sortie ou de réévaluation déclenché'], None, [], prot)


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
