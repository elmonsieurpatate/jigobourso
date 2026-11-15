"""Fournisseur de la fiche d'un ETF (Yahoo quoteSummary) : lecture et extraction brute uniquement.
La normalisation et la présentation (profile_data, région géographique) sont dans analytics/market_views/etf.py : ce module ne dépend d'aucune analyse."""

import json
import urllib.parse

VERSION = 4
MODULES = 'fundProfile,topHoldings,summaryDetail,defaultKeyStatistics'
SECTOR_NAMES = {
    'realestate': 'Immobilier',
    'consumer_cyclical': 'Consommation cyclique',
    'basic_materials': 'Matériaux',
    'consumer_defensive': 'Consommation de base',
    'technology': 'Technologie',
    'communication_services': 'Communication',
    'financial_services': 'Finance',
    'utilities': 'Services publics',
    'industrials': 'Industrie',
    'energy': 'Énergie',
    'healthcare': 'Santé',
}


def _raw(v):
    return v.get('raw') if isinstance(v, dict) else v


def parse_raw_profile(payload):
    """Renvoie les champs extraits (non normalisés), ou None si Yahoo ne décrit pas ce produit comme un fonds."""
    try:
        r = payload['quoteSummary']['result'][0]
    except (KeyError, IndexError, TypeError):
        return None
    fund, top, summary, stats = r.get('fundProfile') or {}, r.get('topHoldings') or {}, r.get('summaryDetail') or {}, r.get('defaultKeyStatistics') or {}
    if not fund and not top and not summary and not stats:
        return None
    fees = fund.get('feesExpensesInvestment') or {}
    sectors = {}
    for item in top.get('sectorWeightings') or []:
        for key, val in item.items():
            if _raw(val) is not None:
                sectors[SECTOR_NAMES.get(key, key)] = round(_raw(val) * 100, 2)
    holdings = [
        {'symbol': h.get('symbol'), 'name': h.get('holdingName'), 'weight': None if _raw(h.get('holdingPercent')) is None else round(_raw(h.get('holdingPercent')) * 100, 4)}
        for h in (top.get('holdings') or [])[:10]
    ]
    out = {
        'family': fund.get('family'),
        'category': fund.get('categoryName'),
        'legal_type': fund.get('legalType'),
        'expense_ratio': None if _raw(fees.get('annualReportExpenseRatio')) is None else round(_raw(fees['annualReportExpenseRatio']) * 100, 3),
        'yield': None if _raw(summary.get('yield')) is None else round(_raw(summary['yield']) * 100, 2),
        'total_assets': _raw(summary.get('totalAssets')) if _raw(summary.get('totalAssets')) is not None else _raw(stats.get('totalAssets')),
        'total_assets_currency': summary.get('currency') if isinstance(summary.get('currency'), str) else None,
        'geography_region': None,
        'holdings': holdings,
        'sectors': dict(sorted(sectors.items(), key=lambda kv: -kv[1])),
        'top10_weight': round(sum(h['weight'] for h in holdings), 1) if len(holdings) == 10 and all(h['weight'] is not None for h in holdings) else None,
        'stock_position': None if _raw(top.get('stockPosition')) is None else round(_raw(top['stockPosition']) * 100, 1),
        'bond_position': None if _raw(top.get('bondPosition')) is None else round(_raw(top['bondPosition']) * 100, 1),
    }
    return out


def fetch_payload(transport, symbol):
    """Interroge Yahoo (crumb inclus par le transport) ; renvoie la réponse JSON décodée."""
    params = {'modules': MODULES}
    text = transport.get('/v10/finance/quoteSummary/' + urllib.parse.quote(symbol), params)
    return json.loads(text)
