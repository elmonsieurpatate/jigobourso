"""Faits de marché communs : éligibilité PEA, dernière collecte, dernière clôture attendue, classes de capitalisation, lecture des recommandations d'analystes."""
from engine.market import hours
from engine.market.collect import effective_expected_close, to_eur_factor


# PEA : actions d'une société dont le siège est dans l'UE ou l'EEE (Islande, Liechtenstein et Norvège compris ; pas le Royaume-Uni ni la Suisse),
# achetées sur une place européenne (c'est ce que les courtiers acceptent dans un PEA). Une action américaine d'une société irlandaise n'est donc
# pas « PEA probable ». Les ETF dépendent de leur indice et de leur domicile : toujours « à vérifier ».
PEA_COUNTRIES = {'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece',
                 'Hungary', 'Iceland', 'Ireland', 'Italy', 'Latvia', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta', 'Netherlands', 'Norway', 'Poland',
                 'Portugal', 'Romania', 'Slovakia', 'Slovenia', 'Spain', 'Sweden'}


PEA_MICS = {'XPAR', 'XAMS', 'XBRU', 'XLIS', 'XETR', 'XFRA', 'XSTU', 'XBER', 'XDUS', 'XHAM', 'XMUN', 'XHAN', 'XMIL', 'XMAD', 'XSTO', 'XOSL', 'XHEL', 'XCSE',
            'XWBO', 'XDUB', 'XATH', 'XWAR', 'XPRA', 'XBUD', 'XBSE', 'XICE', 'XLUX'}


def pea_status(kind, country, mic):
    """'probable' (action d'un pays éligible cotée en Europe) | 'a_verifier' (ETF) | 'non'."""
    if kind == 'etf':
        return 'a_verifier'
    return 'probable' if country in PEA_COUNTRIES and mic in PEA_MICS else 'non'


def last_collection(conn, mic):
    """Fin de la dernière collecte de 15 minutes réussie de la place (UTC naïf), ou None : c'est elle qui dit si NOS données sont à jour pendant la séance."""
    now = hours.utcnow()
    memo = conn.__dict__.setdefault('_jigo_collected', {})
    key = (mic, now.replace(second=0, microsecond=0))
    if key not in memo:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(finished_at) f FROM jobs WHERE job_type=%s AND status IN ('completed','completed_with_errors')", ('intraday:' + mic,))
            memo[key] = cur.fetchone()['f']
    return memo[key]


def expected_close(conn, mic):
    """Dernière clôture due pour la place, jours fériés déduits des données (mémorisée par connexion et par minute)."""
    now = hours.utcnow()
    memo = conn.__dict__.setdefault('_jigo_expected', {})
    key = (mic, now.replace(second=0, microsecond=0))
    if key not in memo:
        memo[key] = effective_expected_close(conn, mic, now)
    return memo[key]


_ANALYST_FR = {'strong buy': 'Achat fort', 'buy': 'Achat', 'hold': 'Conserver', 'underperform': 'Sous-performance', 'sell': 'Vente', 'strong sell': 'Vente forte'}


def analyst_view(raw):
    """Consensus des analystes tel que Yahoo le donne (« 1.8 - Buy »), mis en français pour l'affichage. Information externe : ni score, ni filtre, ni critère de Jigobourso.
    Une absence n'est jamais un défaut du titre ; un libellé inconnu n'est pas traduit (la note seule est affichée)."""
    if not raw or ' - ' not in raw:
        return None
    note, _, label = raw.partition(' - ')
    try:
        score = float(note)
    except ValueError:
        return None
    fr = _ANALYST_FR.get(label.strip().casefold())
    return {'score': score, 'label': fr, 'raw': raw, 'text': ('%s (%s)' % (fr, ('%.1f' % score).replace('.', ','))) if fr else 'Note ' + ('%.1f' % score).replace('.', ',')}


_SIZE_KEYS = ((300e6, 'micro'), (2e9, 'small'), (10e9, 'mid'), (200e9, 'large'), (float('inf'), 'mega'))     # clés du filtre « Capitalisation » de l'Explorer (mêmes seuils que les libellés ci-dessous)


_SIZE_CLASSES = ((300e6, 'micro-capitalisation'), (2e9, 'petite capitalisation'), (10e9, 'capitalisation moyenne'), (200e9, 'grande capitalisation'), (float('inf'), 'très grande capitalisation'))


def size_class(market_cap, currency, rates):
    """Catégorie de taille d'une action, en euros ; inconnue si la devise n'est pas une devise ordinaire (par exemple les pence)."""
    if not market_cap or currency in (None, 'GBp', 'ZAc', 'ILA'):
        return None
    f = to_eur_factor(currency, rates)
    if not f:
        return None
    eur = float(market_cap) * f
    return next(label for limit, label in _SIZE_CLASSES if eur < limit)


def size_key(market_cap, currency, rates):
    """Clé de taille (micro, small, mid, large, mega) en euros ; None si inconnue (ETF, devise non ordinaire, capitalisation absente)."""
    if not market_cap or currency in (None, 'GBp', 'ZAc', 'ILA'):
        return None
    f = to_eur_factor(currency, rates)
    if not f:
        return None
    eur = float(market_cap) * f
    return next(key for limit, key in _SIZE_KEYS if eur < limit)
