"""Règles d'admission au catalogue (niveau 1 : FinanceDatabase). Une cotation écartée ici reçoit status='excluded' et un motif lisible ;
elle n'est jamais collectée (sauf si détenue) ni recommandée.

Les règles sont des données : un registre ordonné (`RULES`) décrit chacune (rôle, types concernés, paramètres, explication), la
configuration enregistrée dans `settings['catalogue_rules']` les active, les désactive ou règle leurs paramètres. Les valeurs par
défaut (`DEFAULT_CONFIG`) sont le point de départ et ce à quoi « restaurer les valeurs par défaut » revient.
Les trois niveaux restent séparés : ce module ne connaît ni les cours Yahoo (niveau 2, `market/prefilter.py`) ni les stratégies (niveau 3).
"""
import re

# Places proposées par défaut (point de départ). Le choix est LIBRE : toute place présente dans les données importées peut être ajoutée ou retirée
# depuis l'administration, sans modifier le code. Les noms ci-dessous servent seulement à l'affichage.
DEFAULT_MARKETS = ('XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS', 'XPAR', 'XAMS', 'XETR', 'XLON', 'XMIL', 'XMAD', 'XSTO', 'XOSL', 'XSWX')
MARKET_NAMES = {
    'XNAS': 'Nasdaq', 'XNYS': 'NYSE', 'XASE': 'NYSE American', 'ARCX': 'NYSE Arca', 'BATS': 'Cboe BZX',
    'XPAR': 'Euronext Paris', 'XAMS': 'Euronext Amsterdam', 'XETR': 'Xetra', 'XLON': 'Bourse de Londres',
    'XMIL': 'Borsa Italiana', 'XMAD': 'Bourse de Madrid', 'XSTO': 'Nasdaq Stockholm', 'XOSL': 'Oslo Børs', 'XSWX': 'SIX Swiss Exchange',
    'XBRU': 'Euronext Bruxelles', 'XLIS': 'Euronext Lisbonne', 'XHEL': 'Nasdaq Helsinki', 'XCSE': 'Nasdaq Copenhague', 'XWBO': 'Bourse de Vienne', 'XDUB': 'Euronext Dublin',
    'XATH': 'Bourse d’Athènes', 'XWAR': 'Bourse de Varsovie', 'XPRA': 'Bourse de Prague', 'XBUD': 'Bourse de Budapest', 'XIST': 'Borsa Istanbul', 'XFRA': 'Francfort',
    'XTSE': 'Bourse de Toronto', 'XTSX': 'TSX Venture', 'XTKS': 'Bourse de Tokyo', 'XHKG': 'Hong Kong', 'XSHG': 'Shanghai', 'XSHE': 'Shenzhen', 'XKRX': 'Bourse de Corée',
    'XASX': 'ASX Sydney', 'XSES': 'Singapour', 'XBOM': 'BSE Inde', 'XNSE': 'NSE Inde', 'XTAI': 'Taïwan', 'XJSE': 'Johannesburg', 'BVMF': 'B3 São Paulo', 'XMEX': 'Bourse du Mexique',
}
MARKETS = MARKET_NAMES       # compatibilité d'affichage (noms) : ne limite plus rien
US_MICS = ('XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS')
MIC_FORMAT = re.compile(r'^[A-Z0-9]{3,6}$')

# Bons de souscription, droits, unités : détectés par le nom ou le suffixe du symbole. « units » et « rights » seuls ne suffisent pas :
# « Multi Units Luxembourg - Lyxor … » (toute une gamme d'ETF) ou « Human Rights » ne sont pas des dérivés. Pour une action, ces mots ne comptent
# qu'en fin de nom (« Foo Acquisition Corp Units », « Foo Corp Rights ») ; pour un ETF, seuls « warrant(s) » et « subscription receipt(s) » comptent.
_WARRANT = re.compile(r'\b(warrants?|subscription receipts?)\b', re.I)
_EQUITY_DERIVATIVE_END = re.compile(r'\b(rights?|units?)\s*$', re.I)
_SYMBOL_DERIVATIVE = re.compile(r'[-.](W|WS|WT|WTS|R|RT|U|UN)$')
# ETF à effet de levier ou inverses. Marqueurs forts : toujours exclus. Marqueurs faibles (« short », « ultra ») : exclus sauf si le nom décrit un fonds
# obligataire / monétaire à courte durée (« Short Duration », « Ultra Short Income », « Short Treasury Bond »…), ou à une stratégie sans levier
# (« Ultra Buffer », « Long/Short Equity », « Short-Term REIT »), qui n'a rien de spéculatif.
_LEVERAGED_STRONG = re.compile(r'(\b[2-9]x\b|\bx[2-9]\b|\bleverag|\bultra[- ]?(short|pro)\b(?![- ]*(term|duration|bond|income|municipal|muni|treasur|credit|maturity|dated))|\bdaily (short|inverse)|\binverse\b|\bshort\s+\d|\bbear\b|\blevered\b|\b-[1-9]x\b)', re.I)
_LEVERAGED_WEAK = re.compile(r'\b(short|ultra)\b', re.I)
_FIXED_INCOME = re.compile(r'\b(bonds?|income|treasur\w*|municipal|muni|duration|dur|maturity|dated|credit|money market|cash|government|govt|corporate|clean energy|buffer|box|reit)\b|\bultra[- ]small\b|\blong/short\b|\bshort[- ]term\s+(fund|etf)\b', re.I)
_SPAC = re.compile(r'\b(acquisition (corp|corporation|co)|blank check|spac)\b', re.I)

# Ordre réel d'application. 'perimeter' : la ligne écartée n'est pas enregistrée comme cotation (hors périmètre) ;
# sinon la cotation existe, avec le statut « exclue » et son motif.
RULES = (
    {'id': 'incomplete', 'label': 'Ligne sans place ou sans symbole', 'perimeter': True, 'locked': True, 'kinds': ('equity', 'etf'),
     'reason': 'ligne incomplète', 'role': 'Écarte les lignes qui ne permettent pas d’identifier une cotation.',
     'help': 'Sans place de cotation ni symbole, Yahoo Finance ne peut pas être interrogé : la ligne est inutilisable. Règle technique, non modifiable.'},
    {'id': 'duplicates', 'label': 'Doublons place + symbole', 'perimeter': True, 'locked': True, 'kinds': ('equity', 'etf'),
     'reason': 'doublon', 'role': 'Garde une seule ligne par couple (place, symbole).',
     'help': 'FinanceDatabase répète parfois la même cotation. La première ligne rencontrée est conservée, les suivantes sont ignorées. Règle technique, non modifiable.'},
    {'id': 'types', 'label': 'Types de produits retenus', 'perimeter': True, 'kinds': ('equity', 'etf'), 'reason': 'type non retenu', 'group': 'products',
     'role': 'Choisit les familles de produits analysées : actions, ETF.',
     'help': 'Décochez « ETF » pour ne travailler que sur des actions (ou l’inverse). Les produits d’un type retiré sont écartés du catalogue, sans être supprimés : vos positions restent suivies.'},
    {'id': 'markets', 'label': 'Places de cotation retenues', 'perimeter': True, 'kinds': ('equity', 'etf'), 'reason': 'place non retenue', 'group': 'markets',
     'role': 'Ne garde que les places choisies. Toutes les places présentes dans FinanceDatabase sont proposées.',
     'help': 'Seules les places cochées sont transmises à Yahoo Finance. Retirer une place écarte toutes ses cotations ; en ajouter une les réintègre au prochain filtrage, sans retélécharger FinanceDatabase. Règle désactivée = toutes les places.'},
    {'id': 'categories', 'label': 'Catégories exclues', 'kinds': ('equity', 'etf'), 'reason': 'catégorie exclue', 'group': 'products', 'default_enabled': False,
     'role': 'Écarte les secteurs (actions) ou catégories (ETF) cochés.',
     'help': 'Utile pour retirer un secteur entier (ex. « Financials ») ou une famille d’ETF. Les catégories proposées sont celles des données importées.'},
    {'id': 'delisted', 'group': 'quality', 'label': 'Titres radiés', 'kinds': ('equity', 'etf'), 'reason': 'titre radié',
     'role': 'Écarte les titres marqués comme radiés de la cote.',
     'help': 'Un titre radié ne cote plus : ses derniers cours sont figés et trompeurs. Désactiver cette règle les laisse entrer dans la collecte (déconseillé).'},
    {'id': 'nameless', 'group': 'quality', 'label': 'Identité incomplète (nom absent)', 'kinds': ('equity', 'etf'), 'reason': 'identité incomplète',
     'role': 'Écarte les lignes sans nom.',
     'help': 'Sans nom, impossible de présenter le titre ni de repérer les produits dérivés. Ces lignes sont rares et presque toujours des fiches vides.'},
    {'id': 'warrants', 'group': 'quality', 'label': 'Bons de souscription, droits et unités', 'kinds': ('equity', 'etf'), 'reason': 'bon de souscription, droit ou unité',
     'role': 'Écarte les instruments dérivés d’une action (bons, droits, unités).',
     'help': 'Détectés par le nom (« Warrants », « Rights », « Units ») ou le suffixe du symbole (-WT, .U…). Ce ne sont pas des actions ordinaires et leur cours se comporte très différemment.'},
    {'id': 'spac', 'group': 'quality', 'label': 'Sociétés vides (SPAC)', 'kinds': ('equity',), 'reason': 'société vide (SPAC)',
     'role': 'Écarte les sociétés d’acquisition sans activité.',
     'help': 'Un SPAC est une coquille cotée qui lève de l’argent pour racheter une société. Son cours est quasi plat puis très volatil à l’annonce : il fausse les classements de tendance.'},
    {'id': 'leveraged', 'group': 'quality', 'label': 'ETF à levier ou inverses', 'kinds': ('etf',), 'reason': 'ETF à effet de levier ou inverse',
     'role': 'Écarte les ETF qui amplifient ou inversent l’indice.',
     'help': 'Détectés par le nom (« 3x », « Ultra », « Short », « Inverse »…). Leur performance dérive de celle de l’indice sur la durée : ils ne se comparent pas aux ETF classiques.'},
)
RULE_IDS = tuple(r['id'] for r in RULES)
BY_ID = {r['id']: r for r in RULES}


def default_config():
    cfg = {r['id']: {'enabled': r.get('default_enabled', True)} for r in RULES}
    cfg['types'].update({'equity': True, 'etf': True})
    cfg['markets']['values'] = sorted(DEFAULT_MARKETS)
    cfg['categories']['values'] = []
    return cfg


DEFAULT_CONFIG = default_config()


def normalize(config):
    """Configuration complète et valide issue de `config` (même partielle) ; ValueError avec un message affichable sinon."""
    cfg = default_config()
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError('Configuration des règles invalide')
    for rid, given in config.items():
        if rid not in BY_ID:
            raise ValueError(f'Règle inconnue : {rid}')
        if not isinstance(given, dict):
            raise ValueError(f'Règle « {rid} » invalide')
        spec = BY_ID[rid]
        if spec.get('locked'):
            continue                                    # règles techniques : jamais modifiables
        if 'enabled' in given:
            if type(given['enabled']) is not bool:
                raise ValueError(f'Activation de « {spec["label"]} » invalide')
            cfg[rid]['enabled'] = given['enabled']
        if rid == 'types':
            for k in ('equity', 'etf'):
                if k in given:
                    if type(given[k]) is not bool:
                        raise ValueError('Types retenus invalides')
                    cfg['types'][k] = given[k]
            if cfg['types']['enabled'] and not (cfg['types']['equity'] or cfg['types']['etf']):
                raise ValueError('Gardez au moins un type de produit (ou désactivez la règle)')
        if rid == 'markets' and 'values' in given:
            values = given['values']
            if not isinstance(values, list) or any(not isinstance(v, str) or not MIC_FORMAT.match(v) for v in values):
                raise ValueError('Place invalide dans la liste des places retenues')
            if not values and cfg['markets']['enabled']:
                raise ValueError('Gardez au moins une place (ou désactivez la règle pour accepter toutes les places)')
            cfg['markets']['values'] = sorted(set(values))
        if rid == 'categories' and 'values' in given:
            values = given['values']
            if not isinstance(values, list) or any(not isinstance(v, str) or not 0 < len(v) <= 80 for v in values):
                raise ValueError('Catégories invalides')
            cfg['categories']['values'] = sorted(set(values))
    return cfg


def is_leveraged_name(name):
    """ETF à levier ou inverse d'après son nom (voir _LEVERAGED_STRONG / _LEVERAGED_WEAK)."""
    if _LEVERAGED_STRONG.search(name):
        return True
    return bool(_LEVERAGED_WEAK.search(name)) and not _FIXED_INCOME.search(name)


def evaluate(kind, row, config=None):
    """Premier motif d'exclusion rencontré, dans l'ordre réel des règles : (id de règle, motif) ou (None, None).
    `row` : dict avec symbol, name, mic, delisted. Les doublons sont traités par l'appelant (ils dépendent des autres lignes)."""
    cfg = config or DEFAULT_CONFIG
    mic, symbol, name = (row.get('mic') or '').strip(), (row.get('symbol') or '').strip(), row.get('name') or ''
    if not mic or not symbol:
        return 'incomplete', BY_ID['incomplete']['reason']
    t = cfg['types']
    if t['enabled'] and not t.get(kind, True):
        return 'types', BY_ID['types']['reason']
    if cfg['markets']['enabled'] and mic not in cfg['markets']['values']:
        return 'markets', BY_ID['markets']['reason']
    if cfg['categories']['enabled'] and (row.get('category') or '') in cfg['categories']['values']:
        return 'categories', BY_ID['categories']['reason']
    if cfg['delisted']['enabled'] and str(row.get('delisted', '')).strip().lower() in ('true', '1'):
        return 'delisted', BY_ID['delisted']['reason']
    if cfg['nameless']['enabled'] and not name:
        return 'nameless', BY_ID['nameless']['reason']
    if cfg['warrants']['enabled'] and (_WARRANT.search(name) or (kind == 'equity' and _EQUITY_DERIVATIVE_END.search(name)) or _SYMBOL_DERIVATIVE.search(symbol)):
        return 'warrants', BY_ID['warrants']['reason']
    if cfg['spac']['enabled'] and kind == 'equity' and _SPAC.search(name):
        return 'spac', BY_ID['spac']['reason']
    if cfg['leveraged']['enabled'] and kind == 'etf' and is_leveraged_name(name):
        return 'leveraged', BY_ID['leveraged']['reason']
    return None, None


def exclusion_reason(kind, row, config=None):
    """Motif d'exclusion (texte court) ou None (compatibilité : même signature qu'avant)."""
    return evaluate(kind, row, config)[1]


def rule_text(rid, config):
    """Description lisible de la règle avec sa valeur actuelle (affichée dans l'entonnoir)."""
    c = config[rid]
    if not c['enabled'] and not BY_ID[rid].get('locked'):
        return 'Règle désactivée : n’écarte rien'
    if rid == 'types':
        return 'Types retenus : ' + ', '.join(n for k, n in (('equity', 'actions'), ('etf', 'ETF')) if c[k])
    if rid == 'markets':
        return f'{len(c["values"])} places retenues : ' + ', '.join(c['values'])
    if rid == 'categories':
        return f'{len(c["values"])} catégories exclues' + (' : ' + ', '.join(c['values'][:6]) + (' …' if len(c['values']) > 6 else '') if c['values'] else '')
    return BY_ID[rid]['role']
