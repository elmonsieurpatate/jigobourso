"""Règle R1 : choix de la cotation principale d'un produit coté sur plusieurs places.

1. place d'origine du produit (pays de l'émetteur) si le produit y est coté ;
2. sinon cotation la plus liquide (prix × volume moyen 3 mois, en EUR) ;
3. départage : devise euro, puis ordre alphabétique de (place, symbole).
Sans liquidité connue (chargement initial), le produit n'a pas d'origine reconnue : la plus haute priorité de place fait foi,
et le choix est recalculé dès que les liquidités sont connues.
"""
HOME_MARKET = {'Germany': 'XETR', 'France': 'XPAR', 'Netherlands': 'XAMS', 'United Kingdom': 'XLON', 'Italy': 'XMIL',
               'Spain': 'XMAD', 'Sweden': 'XSTO', 'Norway': 'XOSL', 'Switzerland': 'XSWX', 'Belgium': 'XBRU', 'Portugal': 'XLIS', 'Finland': 'XHEL',
               'Denmark': 'XCSE', 'Austria': 'XWBO', 'Ireland': 'XDUB', 'Poland': 'XWAR', 'Greece': 'XATH', 'Canada': 'XTSE', 'Japan': 'XTKS',
               'Hong Kong': 'XHKG', 'Australia': 'XASX', 'Singapore': 'XSES', 'South Korea': 'XKRX', 'India': 'XNSE', 'Brazil': 'BVMF'}
US_COUNTRY = 'United States'
US_MICS = ('XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS')
FALLBACK_ORDER = ('XNAS', 'XNYS', 'XETR', 'XPAR', 'XAMS', 'XLON', 'XMIL', 'XMAD', 'XSTO', 'XOSL', 'XSWX', 'XASE', 'ARCX', 'BATS')


def _sort_key(item, liquidity):
    return (-(liquidity.get(item['id']) or 0), 0 if item.get('currency') == 'EUR' else 1, item['mic'], item['symbol'])


def choose_primary(listings, country=None, liquidity=None):
    """listings : [{'id','mic','symbol','currency'}] (non exclues). liquidity : {id: valeur EUR}. Renvoie (id, raison)."""
    liquidity = liquidity or {}
    if len(listings) == 1:
        return listings[0]['id'], 'single'
    home = HOME_MARKET.get(country)
    candidates = [l for l in listings if l['mic'] == home] if home else (
        [l for l in listings if l['mic'] in US_MICS] if country == US_COUNTRY else [])
    if candidates:
        return min(candidates, key=lambda l: _sort_key(l, liquidity))['id'], 'home_market'
    if any(liquidity.get(l['id']) for l in listings):
        return min(listings, key=lambda l: _sort_key(l, liquidity))['id'], 'liquidity'
    rank = {m: i for i, m in enumerate(FALLBACK_ORDER)}
    return min(listings, key=lambda l: (rank.get(l['mic'], 99), l['symbol']))['id'], 'default'
