"""Classification géographique prudente, fondée sur les pays d'émetteur et les catégories de fonds.

Les libellés mondiaux, internationaux et ambigus restent inconnus. Aucune zone ETF
ne dépend du domicile ou de la place de cotation.
"""
import re
import unicodedata


def _norm(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


EUROPE = frozenset(_norm(x.strip()) for x in '''Albania|Andorra|Austria|Belarus|Belgium|Bosnia and Herzegovina|Bulgaria|Croatia|Cyprus|Czech Republic|Denmark|Estonia|Finland|France|Germany|Greece|Hungary|Iceland|Ireland|Italy|Kosovo|Latvia|Liechtenstein|Lithuania|Luxembourg|Malta|Moldova|Monaco|Montenegro|Netherlands|North Macedonia|Norway|Poland|Portugal|Romania|Russia|San Marino|Serbia|Slovakia|Slovenia|Spain|Sweden|Switzerland|Turkey|Ukraine|United Kingdom|Vatican|Czechia|Türkiye'''.split('|'))
EMERGING = frozenset(_norm(x.strip()) for x in '''Afghanistan|Algeria|Angola|Argentina|Armenia|Azerbaijan|Bahrain|Bangladesh|Benin|Bhutan|Bolivia|Botswana|Brazil|Brunei|Burkina Faso|Burundi|Cambodia|Cameroon|Cape Verde|Central African Republic|Chad|Chile|China|Colombia|Comoros|Congo|Costa Rica|Cote d'Ivoire|Ivory Coast|Cuba|Democratic Republic of the Congo|Djibouti|Dominican Republic|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Eswatini|Ethiopia|Fiji|Gabon|Gambia|Georgia|Ghana|Guatemala|Guinea|Guinea Bissau|Guyana|Haiti|Honduras|India|Indonesia|Iran|Iraq|Jamaica|Jordan|Kazakhstan|Kenya|Kuwait|Kyrgyzstan|Laos|Lebanon|Lesotho|Liberia|Libya|Madagascar|Malawi|Malaysia|Maldives|Mali|Mauritania|Mauritius|Mexico|Mongolia|Morocco|Mozambique|Myanmar|Namibia|Nepal|Nicaragua|Niger|Nigeria|Oman|Pakistan|Panama|Papua New Guinea|Paraguay|Peru|Philippines|Qatar|Rwanda|Saudi Arabia|Senegal|Seychelles|Sierra Leone|Singapore|Somalia|South Africa|South Korea|Sri Lanka|Sudan|Suriname|Syria|Taiwan|Tajikistan|Tanzania|Thailand|Togo|Trinidad and Tobago|Tunisia|Turkmenistan|Uganda|Ukraine|United Arab Emirates|Uruguay|Uzbekistan|Venezuela|Vietnam|Yemen|Zambia|Zimbabwe|Hong Kong|Macau|Türkiye'''.split('|'))

US_LABELS_NORMALIZED = frozenset(_norm(x) for x in ('United States Stock', 'US Stock', 'Large Blend', 'Large Growth', 'Large Value',
                                    'Mid Cap Blend', 'Mid Cap Growth', 'Mid Cap Value', 'Small Blend', 'Small Growth', 'Small Value'))


def equity_region(country):
    """Pays du rattachement de l'entreprise, jamais pays de cotation."""
    name = _norm(country)
    if name in {'united states', 'united states of america', 'usa', 'us', 'u s a'}:
        return 'us'
    if name in EUROPE:
        return 'eu'
    if name in EMERGING:
        return 'emerging'
    return None


def etf_region(category):
    """Catégorie Morningstar/Yahoo uniquement; refuse explicitement les familles globales."""
    text = _norm(category)
    if not text:
        return None
    if text in US_LABELS_NORMALIZED:
        return 'us'
    if any(token in text for token in ('world', 'global', 'international', 'foreign', 'allocation')):
        return None
    if 'diversified emerging' in text:
        return 'emerging'
    if any(token in text for token in ('emerging', 'frontier market', 'latin america stock', 'india equity', 'china region')):
        return 'emerging'
    if any(token in text for token in ('europe stock', 'europe equity', 'european equity')):
        return 'eu'
    return None
