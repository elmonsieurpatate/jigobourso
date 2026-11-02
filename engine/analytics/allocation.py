"""Répartition d'un portefeuille par zone (États-Unis, Europe, émergents) comparée à une répartition cible (stratégie prudente).

Valeurs ACTUELLES en euros, fournies par le registre PHP. Zone d'une action : pays de rattachement de l'entreprise (FinanceDatabase) ;
zone d'un ETF : catégorie géographique explicite du fonds (Yahoo/Morningstar). Un ETF « Monde » ou sans catégorie reste « autre » : rien n'est deviné.
Le calcul est descriptif : il dit combien il faudrait acheter ou vendre par zone pour revenir à la cible, il ne passe aucun ordre.
"""
from . import geography

ZONES = ('us', 'eu', 'emerging')
LABELS = {'us': 'États-Unis', 'eu': 'Europe', 'emerging': 'Émergents', 'other': 'Autre ou inconnue'}
PRUDENT = {'us': 50.0, 'eu': 25.0, 'emerging': 25.0}
TOLERANCE = 5.0                  # points d'écart à partir desquels un rééquilibrage est suggéré


def _number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def validate_target(target):
    """{'us','eu','emerging'} en %, chacun entre 0 et 100, total 100 (± 0,01). ValueError sinon."""
    if not isinstance(target, dict):
        raise ValueError('répartition cible invalide')
    out = {}
    for z in ZONES:
        x = _number(target.get(z))
        if x is None or x < 0 or x > 100:
            raise ValueError(f'part {LABELS[z]} invalide (0 à 100 %)')
        out[z] = round(x, 2)
    if abs(sum(out.values()) - 100) > 0.01:
        raise ValueError('les trois parts doivent faire 100 %')
    return out


def zone_of(kind, country, profile_data):
    if kind == 'equity':
        return geography.equity_region(country) or 'other'
    data = profile_data or {}
    return data.get('geography_region') or geography.etf_region(data.get('category')) or 'other'


def _context(conn, ids):
    """{listing_id: (kind, country, données du profil ETF)} en lecture seule."""
    from . import etf
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute('SELECT l.id, i.kind, i.country FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE l.id IN (%s)' % ','.join(['%s'] * len(ids)), list(ids))
        rows = cur.fetchall()
        cur.execute("SELECT listing_id, data_json FROM etf_profiles WHERE state='ok' AND listing_id IN (%s)" % ','.join(['%s'] * len(ids)), list(ids))
        profiles = {r['listing_id']: etf.decode(r['data_json']) if isinstance(r['data_json'], (str, bytes, type(None))) else r['data_json'] for r in cur.fetchall()}
    return {r['id']: (r['kind'], r['country'], profiles.get(r['id'])) for r in rows}


def summarize(positions, context, target=None):
    """positions : [{listing_id, value}] (valeur en EUR, None si inconnue). context : {listing_id: (kind, country, profil)}."""
    values = {z: 0.0 for z in ZONES + ('other',)}
    zones_by_listing, unpriced = {}, 0
    for p in positions:
        lid = int(p.get('listing_id') or 0)
        value = _number(p.get('value'))
        kind, country, prof = context.get(lid, (p.get('kind'), None, None))
        z = zone_of(kind, country, prof) if lid else 'other'
        zones_by_listing[lid] = z
        if value is None:
            unpriced += 1
            continue
        values[z] += max(0.0, value)
    total = sum(values.values())
    rows = []
    for z in ZONES + ('other',):
        current = 100 * values[z] / total if total else None
        goal = (target or {}).get(z, 0.0) if target else None
        gap = None if goal is None or not total else goal * total / 100 - values[z]
        rows.append({'zone': z, 'label': LABELS[z], 'value_eur': values[z], 'current_pct': current, 'target_pct': goal, 'gap_eur': gap,
                     'off_target': goal is not None and current is not None and abs(current - goal) >= TOLERANCE})
    return {'total_eur': total, 'unpriced': unpriced, 'target': target, 'rows': rows, 'zones': zones_by_listing,
            'rebalance_suggested': any(r['off_target'] for r in rows) if target else False, 'tolerance': TOLERANCE}


def portfolio_allocation(conn, request):
    positions = list(request.get('positions', []))          # un titre saisi sans cotation reconnue compte en « autre »
    target = validate_target(request['target']) if request.get('target') else None
    return summarize(positions, _context(conn, {int(p['listing_id']) for p in positions if p.get('listing_id')}), target)
