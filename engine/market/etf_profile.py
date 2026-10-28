"""Fiche pédagogique d'un ETF : éditeur, frais, principales lignes, répartition par secteur (Yahoo quoteSummary)."""
import json
import urllib.parse

VERSION = 1
MODULES = 'fundProfile,topHoldings,summaryDetail'
SECTOR_NAMES = {'realestate': 'Immobilier', 'consumer_cyclical': 'Consommation cyclique', 'basic_materials': 'Matériaux', 'consumer_defensive': 'Consommation de base',
                'technology': 'Technologie', 'communication_services': 'Communication', 'financial_services': 'Finance', 'utilities': 'Services publics',
                'industrials': 'Industrie', 'energy': 'Énergie', 'healthcare': 'Santé'}


def _raw(v):
    return v.get('raw') if isinstance(v, dict) else v


def parse_profile(payload):
    """Renvoie un dict stable pour l'interface, ou None si Yahoo ne décrit pas ce produit comme un fonds."""
    try:
        r = payload['quoteSummary']['result'][0]
    except (KeyError, IndexError, TypeError):
        return None
    fund, top, summary = r.get('fundProfile') or {}, r.get('topHoldings') or {}, r.get('summaryDetail') or {}
    if not fund and not top:
        return None
    fees = fund.get('feesExpensesInvestment') or {}
    sectors = {}
    for item in top.get('sectorWeightings') or []:
        for key, val in item.items():
            if _raw(val) is not None:
                sectors[SECTOR_NAMES.get(key, key)] = round(_raw(val) * 100, 2)
    holdings = [{'symbol': h.get('symbol'), 'name': h.get('holdingName'), 'weight': round((_raw(h.get('holdingPercent')) or 0) * 100, 2)}
                for h in (top.get('holdings') or [])[:10]]
    out = {'family': fund.get('family'), 'category': fund.get('categoryName'), 'legal_type': fund.get('legalType'),
           'expense_ratio': None if _raw(fees.get('annualReportExpenseRatio')) is None else round(_raw(fees['annualReportExpenseRatio']) * 100, 3),
           'yield': None if _raw(summary.get('yield')) is None else round(_raw(summary['yield']) * 100, 2),
           'holdings': holdings, 'sectors': dict(sorted(sectors.items(), key=lambda kv: -kv[1])),
           'top10_weight': round(sum(h['weight'] for h in holdings), 1) if holdings else None,
           'stock_position': None if _raw(top.get('stockPosition')) is None else round(_raw(top['stockPosition']) * 100, 1),
           'bond_position': None if _raw(top.get('bondPosition')) is None else round(_raw(top['bondPosition']) * 100, 1)}
    return out if any(out[k] for k in ('holdings', 'sectors', 'expense_ratio', 'family')) else None


def fetch_profile(transport, symbol):
    """Interroge Yahoo (crumb inclus par le transport) ; None si aucune donnée de fonds."""
    params = {'modules': MODULES}
    text = transport.get('/v10/finance/quoteSummary/' + urllib.parse.quote(symbol), params)
    return parse_profile(json.loads(text))
