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


def sig(key, level, label, text, tip=None):
    return {'key': key, 'level': level, 'label': label, 'text': text, 'tip': tip}


def _num(v):
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _eur(v):
    return f'{v / 1e6:.1f} M€'.replace('.', ',') if v >= 1e6 else f'{round(v / 1e3):d} k€'


def regularity(r2, sessions=None, extra=''):
    r2, win = _num(r2), f' sur {sessions} séances' if sessions else ''
    tip = f'Vert : R² ≥ {R2_OK:.2f} · orange : ≥ {R2_WARN:.2f} (seuil du profil « croissance régulière ») · rouge : en dessous.'
    if r2 is None:
        return sig('regularity', 'unknown', 'Régularité inconnue', 'Régularité non calculable (historique trop court ou rupture de cours).', tip)
    pct = round(100 * r2)
    text = f'La courbe suit une droite à {pct} %{win}.{extra}'
    if r2 >= R2_OK:
        return sig('regularity', 'ok', 'Régulière', text, tip)
    if r2 >= R2_WARN:
        return sig('regularity', 'warn', 'Moyennement régulière', text, tip)
    return sig('regularity', 'bad', 'Irrégulière', text + ' Hausse en dents de scie.', tip)


def risk(vol, dd, sessions=None):
    vol, dd, win = _num(vol), _num(dd), f' sur {sessions} séances' if sessions else ''
    tip = (f'Vert : variation ≤ {VOL_OK:g} %/séance et repli ≤ {DD_OK:g} % (profil « faible volatilité») · orange : jusqu\'à {RISK_FACTOR:g} fois · rouge : au-delà.')
    if vol is None and dd is None:
        return sig('risk', 'unknown', 'Volatilité inconnue', 'Volatilité et repli non calculables.', tip)
    parts = []
    if vol is not None:
        parts.append(f'variation moyenne de {vol:.1f} % par séance'.replace('.', ','))
    if dd is not None:
        parts.append(f'repli maximal de {dd:.0f} %')
    text = (' et '.join(parts)).capitalize() + win + '.'
    ratios = [r for r in ((vol / VOL_OK) if vol is not None else None, (dd / DD_OK) if dd is not None else None) if r is not None]
    worst = max(ratios)
    if worst <= 1:
        return sig('risk', 'ok', 'Volatilité faible', text, tip)
    if worst <= RISK_FACTOR:
        return sig('risk', 'warn', 'Volatilité modérée', text, tip)
    return sig('risk', 'bad', 'Volatilité forte', text, tip)


def liquidity(daily_eur, kind, prefilter=None):
    minimum = DEFAULT_MIN_LIQUIDITY['etf' if kind == 'etf' else 'equity']
    rule = (prefilter or {}).get('liquidity_etf' if kind == 'etf' else 'liquidity_equity') or {}
    minimum = _num(rule.get('min_eur')) or minimum
    daily_eur = _num(daily_eur)
    tip = f'Vert : ≥ {_eur(minimum * LIQ_FACTOR)}/jour (4 fois le minimum du préfiltre) · orange : ≥ {_eur(minimum)} · rouge : en dessous. Volume moyen 3 mois × cours.'
    if daily_eur is None:
        return sig('liquidity', 'unknown', 'Liquidité inconnue', 'Volume ou cours non disponible.', tip)
    text = f'{_eur(daily_eur)} échangés par jour en moyenne.'
    if daily_eur >= minimum * LIQ_FACTOR:
        return sig('liquidity', 'ok', 'Très liquide', text, tip)
    if daily_eur >= minimum:
        return sig('liquidity', 'warn', 'Liquidité correcte', text + ' Peut coûter plus cher à revendre.', tip)
    return sig('liquidity', 'bad', 'Peu liquide', text + ' Sous le minimum retenu pour la sélection.', tip)


def row_signals(aux, kind, ref_sessions, prefilter=None):
    """Les trois pastilles d'une ligne de classement, depuis les mesures de la fenêtre de référence (les mêmes que les colonnes du tableau)."""
    aux = aux or {}
    price, volume = _num(aux.get('price_eur')), _num(aux.get('volume'))
    return [regularity(aux.get('r2'), ref_sessions), risk(aux.get('volatility'), aux.get('drawdown'), ref_sessions),
            liquidity(price * volume if price is not None and volume is not None else None, kind, prefilter)]


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
