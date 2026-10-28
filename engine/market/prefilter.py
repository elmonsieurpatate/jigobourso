"""Préfiltre de marché (niveau 2 : Yahoo Finance) : écarte les titres trop chers à échanger ou trop peu liquides, d'après Yahoo Quote.

Valeurs par défaut : prix ≥ 2 € ; liquidité (prix × volume moyen 3 mois, en EUR) ≥ 1 M€/jour pour une action, ≥ 250 k€/jour pour un ETF ;
volume inconnu = exclu. Un titre sans cotation Quote reste « candidate » (pas de décision sans donnée).
Exemple : DVDG.DE, 131 titres/jour à 42 € ≈ 5 k€/jour → exclu.
Réglable dans l'administration (settings['prefilter']) : chaque règle s'active ou se désactive et a son seuil. Ce niveau ne connaît ni
les règles du catalogue FinanceDatabase (niveau 1) ni les critères des stratégies (niveau 3).
"""
PREFIX = 'préfiltre'

RULES = (
    {'id': 'price', 'label': 'Prix minimum', 'kinds': ('equity', 'etf'), 'unit': '€', 'step': 0.5, 'key': 'min_eur', 'default': 2.0, 'max': 1000.0,
     'reason': 'cours inférieur', 'role': 'Écarte les titres dont le cours (converti en euros) est sous le seuil.',
     'help': 'Les titres à quelques centimes ont des variations en pourcentage énormes et un écart achat/vente très coûteux : leurs pentes et leurs replis ne sont pas comparables à ceux des autres.'},
    {'id': 'liquidity_equity', 'label': 'Liquidité minimale des actions', 'kinds': ('equity',), 'unit': '€/jour', 'step': 50_000, 'key': 'min_eur', 'default': 1_000_000.0, 'max': 1e9,
     'reason': 'liquidité', 'role': 'Écarte les actions dont l’échange quotidien moyen (prix × volume moyen sur 3 mois) est sous le seuil.',
     'help': 'Un titre peu échangé est difficile à acheter et à revendre au prix affiché. Le seuil est une valeur en euros échangée par jour, pas un nombre de titres.'},
    {'id': 'liquidity_etf', 'label': 'Liquidité minimale des ETF', 'kinds': ('etf',), 'unit': '€/jour', 'step': 50_000, 'key': 'min_eur', 'default': 250_000.0, 'max': 1e9,
     'reason': 'liquidité', 'role': 'Écarte les ETF dont l’échange quotidien moyen est sous le seuil.',
     'help': 'Un ETF se négocie contre ses teneurs de marché : un seuil plus bas que pour les actions est raisonnable, mais un ETF presque jamais échangé reste risqué (DVDG.DE : ~5 000 €/jour).'},
    {'id': 'unknown_volume', 'label': 'Volume moyen inconnu', 'kinds': ('equity', 'etf'),
     'reason': 'volume moyen inconnu', 'role': 'Écarte les titres pour lesquels Yahoo ne donne pas de volume moyen.',
     'help': 'Sans volume, la liquidité ne peut pas être vérifiée. Désactivez cette règle pour laisser passer ces titres (la règle de liquidité ne s’applique alors pas à eux).'},
)
BY_ID = {r['id']: r for r in RULES}
DEFAULTS = {'min_price_eur': 2.0, 'min_liquidity_eur_equity': 1_000_000.0, 'min_liquidity_eur_etf': 250_000.0}      # ancien format, toujours accepté


def default_config():
    cfg = {}
    for r in RULES:
        cfg[r['id']] = {'enabled': True}
        if 'key' in r:
            cfg[r['id']][r['key']] = r['default']
    return cfg


DEFAULT_CONFIG = default_config()


def normalize(params):
    """Configuration complète et valide. Accepte aussi l'ancien format plat (min_price_eur…). ValueError avec message affichable sinon."""
    cfg = default_config()
    params = params or {}
    if not isinstance(params, dict):
        raise ValueError('Configuration du préfiltre invalide')
    flat = {'min_price_eur': ('price', 'min_eur'), 'min_liquidity_eur_equity': ('liquidity_equity', 'min_eur'), 'min_liquidity_eur_etf': ('liquidity_etf', 'min_eur')}
    params = dict(params)
    for k, (rid, field) in flat.items():
        if k in params:
            params[rid] = dict(params.get(rid) or {}, **{field: params.pop(k)})
    for rid, given in params.items():
        if rid not in BY_ID:
            raise ValueError(f'Règle inconnue : {rid}')
        spec = BY_ID[rid]
        if not isinstance(given, dict):
            raise ValueError(f'Règle « {spec["label"]} » invalide')
        if 'enabled' in given:
            if type(given['enabled']) is not bool:
                raise ValueError(f'Activation de « {spec["label"]} » invalide')
            cfg[rid]['enabled'] = given['enabled']
        if 'key' in spec and spec['key'] in given:
            v = given[spec['key']]
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(f'Seuil de « {spec["label"]} » invalide')
            try:
                v = float(v)
            except ValueError:
                raise ValueError(f'Seuil de « {spec["label"]} » invalide') from None
            if not 0 <= v <= spec['max']:
                raise ValueError(f'Seuil de « {spec["label"]} » : entre 0 et {spec["max"]:,.0f}'.replace(',', ' '))
            cfg[rid][spec['key']] = v
    return cfg


def decide(kind, price, avg_volume, to_eur, params=None):
    """Renvoie ('selected', None) ou ('excluded', motif) ou (None, None) si les données manquent."""
    c = normalize(params)
    if price is None or to_eur is None:
        return None, None
    if c['price']['enabled'] and price * to_eur < c['price']['min_eur']:
        return 'excluded', f'{PREFIX} : cours inférieur à {c["price"]["min_eur"]:g} €'
    if avg_volume is None:
        if c['unknown_volume']['enabled']:
            return 'excluded', f'{PREFIX} : volume moyen inconnu'
        return 'selected', None
    rid = 'liquidity_etf' if kind == 'etf' else 'liquidity_equity'
    liquidity = price * avg_volume * to_eur
    minimum = c[rid]['min_eur']
    if c[rid]['enabled'] and liquidity < minimum:
        return 'excluded', f'{PREFIX} : liquidité {liquidity:,.0f} €/jour < {minimum:,.0f} €'.replace(',', ' ')
    return 'selected', None


def step_of(reason):
    """Étape du préfiltre qui a produit ce motif ('price' | 'liquidity' | 'volume') ; None si ce n'est pas un motif de préfiltre."""
    if not reason or not reason.startswith(PREFIX):
        return None
    if 'cours inférieur' in reason:
        return 'price'
    if 'volume moyen inconnu' in reason:
        return 'volume'
    return 'liquidity'
