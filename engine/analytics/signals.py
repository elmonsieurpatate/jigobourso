"""Pastilles d'information (régularité, risque, liquidité, données, similarité, composition, diversification).

Chaque signal = un niveau, un mot court, une phrase d'explication et le rappel du seuil. Aucun effet sur les scores, la sélection ni l'ordre des classements.
Niveaux : 'ok' (vert : favorable selon nos critères), 'warn' (orange : point de vigilance), 'bad' (rouge : risque important ou anomalie), 'unknown' (gris : inconnu,
insuffisant, OU « rien détecté » : une absence de problème détecté n'est jamais présentée comme une garantie).
Les seuils reprennent les critères existants : régularité = niveaux de R² des profils (strategy.R2_LEVELS), risque = profil « faible volatilité » (1,5 % par séance, repli 20 %),
liquidité = minima du préfiltre (réglables dans l'administration) multipliés par 4.
"""
import math

from . import strategy

R2_OK = strategy.R2_LEVELS['balanced']        # 0,75
R2_WARN = strategy.R2_LEVELS['flexible']      # 0,556 : seuil du profil « croissance régulière »
VOL_OK, DD_OK = 1.5, 20.0                     # profil « faible volatilité »
RISK_FACTOR = 2.0                             # orange jusqu'à deux fois ces seuils
LIQ_FACTOR = 4.0                              # vert à partir de quatre fois le minimum du préfiltre
DEFAULT_MIN_LIQUIDITY = {'etf': 250_000.0, 'equity': 1_000_000.0}
TOP10_WARN, TOP10_BAD = 40.0, 70.0            # poids des dix premières lignes d'un ETF
FAMILY_WARN, FAMILY_BAD = 30.0, 50.0          # part de la valeur d'un portefeuille dans une même famille d'ETF


def sig(key, level, label, text, tip=None, **extra):
    return {'key': key, 'level': level, 'label': label, 'text': text, 'tip': tip, **extra}


PERIODS = {1: '1 jour', 5: '1 semaine', 21: '1 mois', 63: '3 mois', 126: '6 mois', 252: '1 an'}


def period_label(sessions):
    """Durée en clair d'une fenêtre de séances (21 → « 1 mois ») ; une fenêtre inhabituelle garde son nombre de séances."""
    return PERIODS.get(sessions) or (f'{sessions} séances' if sessions else None)


def _num(v):
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _eur(v):
    return f'{v / 1e6:.1f} M€'.replace('.', ',') if v >= 1e6 else f'{round(v / 1e3):d} k€'


def regularity(r2, sessions=None, extra=''):
    r2, win, period = _num(r2), f' sur {sessions} séances' if sessions else '', period_label(sessions)
    tip = f'Vert : R² ≥ {R2_OK:.2f} · orange : ≥ {R2_WARN:.2f} (seuil du profil « croissance régulière ») · rouge : en dessous.'
    if r2 is None:
        return sig('regularity', 'unknown', 'Régularité inconnue', 'Régularité non calculable (historique trop court ou rupture de cours).', tip, period=period)
    pct = round(100 * r2)
    text = f'La courbe suit une droite à {pct} %{win}.{extra}'
    if r2 >= R2_OK:
        return sig('regularity', 'ok', 'Régulière', text, tip, period=period)
    if r2 >= R2_WARN:
        return sig('regularity', 'warn', 'Moyennement régulière', text, tip, period=period)
    return sig('regularity', 'bad', 'Irrégulière', text + ' Hausse en dents de scie.', tip, period=period)


def risk(vol, dd, sessions=None):
    vol, dd, win, period = _num(vol), _num(dd), f' sur {sessions} séances' if sessions else '', period_label(sessions)
    tip = (f'Vert : variation ≤ {VOL_OK:g} %/séance et repli ≤ {DD_OK:g} % (profil « faible volatilité») · orange : jusqu\'à {RISK_FACTOR:g} fois · rouge : au-delà.')
    if vol is None and dd is None:
        return sig('risk', 'unknown', 'Volatilité inconnue', 'Volatilité et repli non calculables.', tip, period=period)
    parts = []
    if vol is not None:
        parts.append(f'variation moyenne de {vol:.1f} % par séance'.replace('.', ','))
    if dd is not None:
        parts.append(f'repli maximal de {dd:.0f} %')
    text = (' et '.join(parts)).capitalize() + win + '.'
    ratios = [r for r in ((vol / VOL_OK) if vol is not None else None, (dd / DD_OK) if dd is not None else None) if r is not None]
    worst = max(ratios)
    if worst <= 1:
        return sig('risk', 'ok', 'Volatilité faible', text, tip, period=period)
    if worst <= RISK_FACTOR:
        return sig('risk', 'warn', 'Volatilité modérée', text, tip, period=period)
    return sig('risk', 'bad', 'Volatilité forte', text, tip, period=period)


LIQUIDITY_PERIOD = '3 mois'                    # vraie durée de la mesure (volume moyen 3 mois × cours), indépendante de la période de la stratégie
STALE_QUOTE_DAYS = 10                          # un volume moyen plus ancien n'est plus une preuve : « non déterminée », jamais « peu négociable »
FLOOR_FACTOR = 2.0                             # sous 2 fois le minimum du préfiltre (ordre de 10 000 € ≤ 0,5 % de la valeur d'un jour pour une action, ≤ 2 % pour un ETF) : négociabilité limitée


def liquidity_levels(kind, prefilter=None):
    """(plancher, confort) en €/jour : sous le plancher « limitée » (masquée par le filtre), jusqu'au confort « à surveiller », au-delà « facilement négociable »."""
    rule = (prefilter or {}).get('liquidity_etf' if kind == 'etf' else 'liquidity_equity') or {}
    minimum = _num(rule.get('min_eur')) or DEFAULT_MIN_LIQUIDITY['etf' if kind == 'etf' else 'equity']
    return minimum * FLOOR_FACTOR, minimum * LIQ_FACTOR


def liquidity(daily_eur, kind, prefilter=None, quote_age_days=None):
    """Statut de négociabilité d'un titre : une seule source pour la pastille, le filtre « Titres facilement négociables » et la fiche. Mesure : volume moyen 3 mois × cours
    (estimation Yahoo, pas du volume exécuté). Une donnée absente ou périmée donne « non déterminée », jamais « limitée »."""
    floor, comfort = liquidity_levels(kind, prefilter)
    daily_eur = _num(daily_eur)
    tip = f'Facilement négociable : ≥ {_eur(comfort)}/jour · à surveiller : ≥ {_eur(floor)} · limitée : en dessous. Volume moyen 3 mois × cours (estimation Yahoo).'
    period = LIQUIDITY_PERIOD
    values = {'daily_eur': daily_eur, 'floor_eur': floor, 'comfort_eur': comfort, 'quote_age_days': quote_age_days}
    if daily_eur is None:
        return sig('liquidity', 'unknown', 'Négociabilité non déterminée', 'Volume ou cours non disponible.', tip, values=values, reason='missing', period=period)
    if quote_age_days is not None and quote_age_days > STALE_QUOTE_DAYS:
        return sig('liquidity', 'unknown', 'Négociabilité non déterminée', f'Les données de volume datent de {quote_age_days:.0f} jours.', tip, values=values, reason='stale', period=period)
    text = f'{_eur(daily_eur)} échangés par jour en moyenne.'
    if daily_eur >= comfort:
        return sig('liquidity', 'ok', 'Facilement négociable', text, tip, values=values, period=period)
    if daily_eur >= floor:
        return sig('liquidity', 'warn', 'Négociabilité à surveiller', text + ' Peut coûter plus cher à revendre.', tip, values=values, period=period)
    return sig('liquidity', 'bad', 'Négociabilité limitée', text + f' Sous {_eur(floor)} par jour.', tip, values=values, period=period)


def row_signals(aux, kind, ref_sessions, prefilter=None, quote_age_days=None):
    """Les trois pastilles d'une ligne de classement, depuis les mesures de la fenêtre de référence (les mêmes que les colonnes du tableau)."""
    aux = aux or {}
    price, volume = _num(aux.get('price_eur')), _num(aux.get('volume'))
    return [regularity(aux.get('r2'), ref_sessions), risk(aux.get('volatility'), aux.get('drawdown'), ref_sessions),
            liquidity(price * volume if price is not None and volume is not None else None, kind, prefilter, quote_age_days)]


# ───────── appréciation globale (descriptive) ─────────
# Aucune formule de score : un petit jeu de règles lisibles, appliqué aux indicateurs qui existent déjà (pente et performance de la fenêtre de la stratégie, pastilles de
# régularité / volatilité / négociabilité, qualité des données). Ce n'est ni un conseil d'achat ou de vente, ni une entrée du score, du filtre ou du classement.
APPRECIATIONS = {'very_favorable': ('Très favorable', 'ok'), 'favorable': ('Favorable', 'ok'), 'mixed': ('Mitigé', 'warn'), 'unfavorable': ('Défavorable', 'bad'), 'undetermined': ('Indéterminé', 'unknown')}
APPRECIATION_RULES = [
    ('Très favorable', 'hausse forte sur la période de la stratégie, avec régularité, volatilité et négociabilité toutes favorables et aucun autre point de vigilance.'),
    ('Favorable', 'hausse sur la période, aucun risque important et au plus un point de vigilance.'),
    ('Mitigé', 'hausse mais avec un ou deux risques importants, plusieurs points de vigilance, une tendance récente qui contredit celle de fond, ou pas de tendance nette.'),
    ('Défavorable', 'courbe en baisse sur la période, ou trois risques importants ou plus.'),
    ('Indéterminé', 'mesures absentes, historique trop court ou plusieurs indicateurs non évaluables : rien n’est supposé.')]
EXTREME_RISE = 100.0          # hausse (%) sur la période de la stratégie à partir de laquelle on signale qu'un mouvement aussi rapide peut se retourner vite
BACKGROUND_MOVE, RECENT_DROP, RECENT_RISE = 10.0, -5.0, 10.0        # tendance de fond (%), repli récent (%), rebond récent (%) qui rendent la tendance « contradictoire »
CLOSING = 'Une tendance peut s’arrêter à tout moment : cette appréciation décrit le profil observé, ce n’est pas un conseil d’achat ou de vente.'


def _pct(v):
    return f'{v:+.0f} %'.replace('-', '−')


def trend_class(slope, perf):
    """Tendance de la fenêtre de référence : 'strong' (forte), 'steady' (soutenue), 'gentle' (douce), 'flat' (pas de tendance nette), 'down' (baisse) ; None si non mesurée.
    Les niveaux de pente sont ceux des profils de stratégie (temps pour doubler : 2 ans, 4 ans, 8 ans)."""
    slope, perf = _num(slope), _num(perf)
    if slope is None or perf is None:
        return None
    if perf < 0:
        return 'down'
    if slope <= 0:
        return 'flat'
    for name, key in (('strong', 'strong'), ('moderate', 'steady'), ('gentle', 'gentle')):
        if slope >= strategy.SLOPE_LEVELS[name]:
            return key
    return 'flat'


def contradiction(measures):
    """Tendance récente qui contredit celle de fond, d'après les performances déjà mesurées : repli récent après une hausse de fond, ou rebond récent dans une baisse de fond. None sinon (ou si les mesures manquent)."""
    perf = {n: _num((m or {}).get('perf')) for n, m in (measures or {}).items()}
    for short in (21, 5):
        for long in (252, 126, 63, 21):
            if long <= short or perf.get(short) is None or perf.get(long) is None:
                continue
            if perf[long] >= BACKGROUND_MOVE and perf[short] <= RECENT_DROP:
                return {'kind': 'drop', 'text': f'Repli récent ({_pct(perf[short])} sur {period_label(short)}) alors que la tendance de fond est à la hausse ({_pct(perf[long])} sur {period_label(long)}).'}
            if perf[long] <= -BACKGROUND_MOVE and perf[short] >= RECENT_RISE:
                return {'kind': 'rise', 'text': f'Rebond récent ({_pct(perf[short])} sur {period_label(short)}) dans une tendance de fond à la baisse ({_pct(perf[long])} sur {period_label(long)}).'}
    return None


def _lc(text):
    """Première lettre en minuscule seulement : « 2,3 M€ échangés » garde son « M »."""
    return text[:1].lower() + text[1:]


def _fr(v, digits=3):
    return f'{v:.{digits}f}'.replace('.', ',')


def assessment(measures, ref, pills, quality=None):
    """Appréciation descriptive du profil : Très favorable / Favorable / Mitigé / Défavorable / Indéterminé, avec points forts et points de vigilance.
    `measures` : {séances: mesures}, `ref` : fenêtre de la stratégie, `pills` : signaux de la fiche (régularité, risque, négociabilité, données, risques spécifiques ETF).
    Un titre ne peut pas être « très favorable » (ni « favorable ») si l'un de ses risques est important, même s'il monte fortement."""
    measures = {int(k): v for k, v in (measures or {}).items() if v}
    by_key = {p['key']: p for p in pills or []}
    m = measures.get(ref) or {}
    trend, period, perf, slope, r2 = trend_class(m.get('slope'), m.get('perf')), period_label(ref), _num(m.get('perf')), _num(m.get('slope')), _num(m.get('r2'))
    reg, rsk, liq, data, spec = (by_key.get(k) for k in ('regularity', 'risk', 'liquidity', 'data', 'risks'))
    up = trend in ('strong', 'steady', 'gentle')
    strengths, cautions, unknowns, big, minor = [], [], [], [], []       # big : risques importants (rouge) ; minor : points de vigilance (orange)

    def note(level, short, long):
        cautions.append(long)
        (big if level == 'bad' else minor).append(short)

    if trend == 'strong':
        strengths.append(f'{"très forte" if slope >= strategy.SLOPE_LEVELS["very_strong"] else "forte"} hausse sur {period} ({_pct(perf)})')
    elif trend == 'steady':
        strengths.append(f'hausse soutenue sur {period} ({_pct(perf)})')
    noun = 'montée' if up else 'courbe'
    if reg:
        if reg['level'] == 'ok':
            strengths.append(f'{noun} {"très " if r2 is not None and r2 >= strategy.R2_LEVELS["strict"] else ""}régulière')
        elif reg['level'] in ('warn', 'bad'):
            word = 'moyennement régulière' if reg['level'] == 'warn' else 'irrégulière, en dents de scie'
            note(reg['level'], f'{noun} {word.split(",")[0]}', f'{noun} {word}')
        else:
            unknowns.append('régularité')
    if rsk:
        if rsk['level'] == 'ok':
            strengths.append('variations faibles')
        elif rsk['level'] in ('warn', 'bad'):
            word = 'modérée' if rsk['level'] == 'warn' else 'forte'
            note(rsk['level'], f'volatilité {word}', f'volatilité {word} ({_lc(rsk["text"].rstrip("."))})')
        else:
            unknowns.append('volatilité')
    if liq:
        if liq['level'] == 'ok':
            strengths.append('facilement négociable')
        elif liq['level'] in ('warn', 'bad'):
            word = 'à surveiller' if liq['level'] == 'warn' else 'limitée'
            note(liq['level'], f'négociabilité {word}', f'négociabilité {word} ({_lc(liq["text"].split(".")[0])})')
        else:
            unknowns.append('négociabilité')
    if data and data['level'] in ('warn', 'bad'):
        note(data['level'], data['label'].lower(), data['label'].lower())
    if spec and spec['level'] in ('warn', 'bad'):
        note(spec['level'], spec['label'].lower(), spec['label'].lower())
    if perf is not None and perf >= EXTREME_RISE and up:
        note('warn', f'hausse de {_pct(perf)} en {period}', f'hausse de {_pct(perf)} en {period} : un mouvement aussi rapide peut se retourner vite')
    contra = contradiction(measures)
    if contra:
        cautions.append(_lc(contra['text'].rstrip('.')))
    horizons = [{'period': period_label(n), 'perf': _num(measures[n].get('perf'))} for n in sorted(measures) if _num(measures[n].get('perf')) is not None]
    why = None
    if trend is None:
        why = f'tendance non mesurée sur {period}'
    elif data and data['level'] == 'unknown':
        why = data['label'].lower()
    elif len([p for p in (reg, rsk, liq) if p and p['level'] == 'unknown']) >= 2:
        why = 'plusieurs indicateurs non évaluables'
    if why:
        code, reason = 'undetermined', f'Données insuffisantes ({why}).'
    elif trend == 'down':
        code, reason = 'unfavorable', f'La courbe baisse sur {period} ({_pct(perf)}).'
    elif len(big) >= 3:
        code, reason = 'unfavorable', 'Trois risques importants ou plus : ' + ', '.join(big[:4]) + '.'
    elif trend == 'flat':
        code, reason = 'mixed', f'Pas de tendance nette sur {period}.'
    elif big:
        code, reason = 'mixed', (f'Un risque important : {big[0]}.' if len(big) == 1 else f'{len(big)} risques importants : ' + ', '.join(big) + '.')
    elif contra:
        code, reason = 'mixed', 'La tendance récente contredit celle de fond.'
    elif not minor and not unknowns and trend == 'strong':
        code, reason = 'very_favorable', f'Hausse forte sur {period}, avec régularité, volatilité et négociabilité favorables.'
    elif len(minor) <= 1:
        tail = f', avec un point de vigilance ({minor[0]})' if minor else ''
        tail += f' ; non évalué : {", ".join(unknowns)}' if unknowns else ''
        code, reason = 'favorable', f'Hausse sur {period}, sans risque important{tail}.'
    else:
        code, reason = 'mixed', f'{len(minor)} points de vigilance : ' + ', '.join(minor[:3]) + '.'
    label, level = APPRECIATIONS[code]
    facts = [f'Période de la stratégie : {period}. Pente {_fr(slope)} %/séance, performance {_pct(perf)}.'] if trend is not None else []
    return {'code': code, 'level': level, 'label': label, 'period': period, 'reason': reason, 'strengths': strengths, 'cautions': cautions, 'unknowns': unknowns,
            'contradiction': contra, 'horizons': horizons, 'facts': facts, 'rules': [{'label': l, 'rule': r} for l, r in APPRECIATION_RULES], 'closing': CLOSING,
            'nothing_flagged': not cautions and not unknowns and code != 'undetermined'}


def history_facts(closes, sessions):
    """Détails pédagogiques de la fiche : part de séances en hausse et poids du meilleur jour dans la hausse (cours de la fenêtre, jamais d'interpolation)."""
    c = [x for x in closes[-(sessions + 1):] if x and x > 0]
    if len(c) < 10:
        return {}
    steps = [math.log(c[i + 1] / c[i]) for i in range(len(c) - 1)]
    total = math.log(c[-1] / c[0])
    out = {'up_days_percent': round(100 * sum(1 for s in steps if s > 0) / len(steps))}
    if total > 0:
        out['best_day_share'] = round(100 * max(steps) / total)
    return out


def regularity_extra(facts):
    bits = []
    if 'up_days_percent' in facts:
        bits.append(f'{facts["up_days_percent"]} % de séances en hausse')
    if 'best_day_share' in facts:
        bits.append(f'meilleur jour = {facts["best_day_share"]} % de la hausse')
    return (' ' + ', '.join(bits).capitalize() + '.') if bits else ''


def data_quality(quality, corrections, price_stale, break_dates=None, coverage=None, observed=None, expected=None):
    tip = 'Fraîcheur et continuité des cours. Ce n\'est pas un jugement sur le titre ni sur la régularité de sa courbe.'
    if quality == 'insufficient':
        return sig('data', 'unknown', 'Historique court', 'Moins de 22 clôtures : les mesures sont peu fiables ou absentes.', tip)
    if quality == 'break':
        return sig('data', 'bad', 'Rupture de cours', 'Un saut de cours inexpliqué dans l\'année rend certaines périodes non évaluables' + (f' (dates : {break_dates}).' if break_dates else '.'), tip)
    if quality == 'stale' or price_stale:
        return sig('data', 'warn', 'Cours ancien', 'La dernière clôture ou le dernier cours est plus ancien que prévu pour cette place.', tip)
    if quality == 'incomplete':
        if observed is not None and expected:
            text = f'Historique incomplet : {int(observed)} clôtures disponibles sur {int(expected)} séances attendues. Les indicateurs qui nécessitent chaque clôture ne sont pas calculés.'
        elif coverage is not None:
            text = f'Historique incomplet : {round(100 * coverage)} % des clôtures attendues sont présentes. Les indicateurs qui nécessitent chaque clôture ne sont pas calculés.'
        else:
            text = 'Historique incomplet : des séances attendues sont absentes. Les indicateurs concernés ne sont pas calculés.'
        return sig('data', 'warn', 'Historique incomplet', text, tip)
    if corrections:
        return sig('data', 'warn', 'Données corrigées', f'{len(corrections)} correction(s) d\'unité ou de cours aberrant appliquée(s) : voir le détail.', tip)
    return sig('data', 'ok', 'Données à jour', 'Cours à jour et série continue sur l\'année.', tip)


def similarity(analysis):
    tip = 'Corrélation des rendements hebdomadaires en EUR sur 52 semaines. Ce n\'est pas une composition commune ; un ETF sans jumeau détecté n\'est pas pour autant « diversifiant ».'
    if not analysis or analysis.get('reason'):
        return sig('similarity', 'unknown', 'Similarité non calculée', (analysis or {}).get('reason') or 'Analyse pas encore préparée pour cet ETF.', tip)
    sim = analysis.get('similar') or []
    twins = [s for s in sim if s['coefficient'] >= 0.97]
    close = [s for s in sim if 0.90 <= s['coefficient'] < 0.97]
    unstable = any(not s.get('stable', True) for s in twins + close)
    if twins:
        return sig('similarity', 'warn', f'{len(twins)} ETF quasi identique{"s" if len(twins) > 1 else ""}', 'Évolue presque exactement comme ' + ', '.join(s['symbol'] for s in twins[:3]) + '.' + (' Résultat instable sur la période.' if unstable else ''), tip)
    if close:
        return sig('similarity', 'warn', f'{len(close)} ETF très proche{"s" if len(close) > 1 else ""}', 'Évolue de façon très proche de ' + ', '.join(s['symbol'] for s in close[:3]) + '.' + (' Résultat instable sur la période.' if unstable else ''), tip)
    return sig('similarity', 'unknown', 'Aucun jumeau détecté', 'Aucun ETF comparable avec une corrélation de 0,90 ou plus (cela ne prouve pas une bonne diversification).', tip)


def composition(profile):
    tip = f'Poids des dix premières lignes déclarées par Yahoo : vert < {TOP10_WARN:g} % · orange < {TOP10_BAD:g} % · rouge au-delà. Date effective de la composition inconnue.'
    top10 = _num((profile or {}).get('top10_weight'))
    if top10 is None:
        return sig('composition', 'unknown', 'Composition inconnue', 'Pondérations des dix premières lignes non fournies ou incomplètes.', tip)
    text = f'Les dix premières lignes pèsent {top10:.0f} % du fonds.'
    if top10 < TOP10_WARN:
        return sig('composition', 'ok', 'Peu concentré', text, tip)
    if top10 < TOP10_BAD:
        return sig('composition', 'warn', 'Assez concentré', text, tip)
    return sig('composition', 'bad', 'Très concentré', text + ' Normal pour un ETF sectoriel, mais le risque dépend de peu d\'entreprises.', tip)


def specific_risks(name, category, leveraged_name=False):
    """Uniquement ce qui est vérifié par le nom ou la catégorie du catalogue. « Rien détecté » n'est PAS « sans risque »."""
    tip = 'Contrôles faits : effet de levier ou inverse (d\'après le nom), matières premières et contrats à terme (d\'après la catégorie). Réplication synthétique, domicile et fiscalité ne sont pas contrôlés.'
    cat = (category or '').casefold()
    if leveraged_name:
        return sig('risks', 'bad', 'Levier ou inverse', 'Le nom indique un effet de levier ou une exposition inverse : la performance dérive de celle de l\'indice sur la durée.', tip)
    if cat in ('commodities', 'derivatives'):
        return sig('risks', 'warn', 'Matières premières / dérivés', 'Catégorie « ' + category + ' » : ces fonds peuvent utiliser des contrats à terme ; leur rendement n\'est pas celui d\'actions.', tip)
    return sig('risks', 'unknown', 'Aucun risque spécifique détecté', 'Aucun point de vigilance trouvé par ces contrôles. Cela ne signifie pas « sans risque ».', tip)


def family_share(percent):
    tip = f'Part de la valeur du portefeuille dans des ETF qui évoluent presque comme un seul : vert < {FAMILY_WARN:g} % · orange < {FAMILY_BAD:g} % · rouge au-delà.'
    if percent is None:
        return sig('family', 'unknown', 'Concentration inconnue', 'Valeur du portefeuille incomplète : pourcentage non calculable.', tip)
    text = f'{percent:.0f} % de la valeur du portefeuille.'
    if percent < FAMILY_WARN:
        return sig('family', 'ok', 'Famille peu pesante', text, tip)
    if percent < FAMILY_BAD:
        return sig('family', 'warn', 'Famille importante', text, tip)
    return sig('family', 'bad', 'Famille dominante', text, tip)


def unknown_share(percent):
    tip = 'Part de la valeur dont l\'exposition n\'est pas connue (actions détenues en direct, ETF sans composition, profils absents ou anciens). L\'inconnu reste inconnu.'
    if percent is None:
        return sig('unknown_share', 'unknown', 'Part inconnue non calculable', 'Valeur du portefeuille incomplète.', tip)
    return sig('unknown_share', 'unknown', f'{percent:.0f} % d\'exposition inconnue', 'Cette part n\'est ni diversifiée ni concentrée : elle n\'est pas documentée.', tip)
