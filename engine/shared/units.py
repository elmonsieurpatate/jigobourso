"""Unités de prix : devise principale + diviseur. Source unique côté Python ; la règle miroir PHP est eur_factor() (app/services/ledger.php),
leur parité est testée (tests/fast/test_units_parity.py) et la table est documentée dans docs/FINANCIAL_INTEGRITY.md.

Un prix peut être coté dans une sous-unité : pence (GBp/GBX), cents du rand (ZAc/ZAC), agorot (ILA). Le taux de change est toujours enregistré
pour la devise principale (GBP, ZAR, ILS) ; le facteur vers l'euro d'une unité est donc taux / diviseur."""

# Code (sensible à la casse quand il l'est : GBp pence ≠ GBP livre) -> (devise principale, diviseur).
SUBUNITS = {'GBp': ('GBP', 100), 'GBX': ('GBP', 100), 'ZAc': ('ZAR', 100), 'ZAC': ('ZAR', 100), 'ILA': ('ILS', 100)}


def split_unit(unit):
    """(devise principale en majuscules, diviseur) d'une unité de prix ; ('', 1) si absente."""
    if not unit:
        return '', 1
    sub = SUBUNITS.get(unit) or SUBUNITS.get(unit.upper())
    return sub if sub else (unit.upper(), 1)


def is_subunit(unit):
    return bool(unit) and (unit in SUBUNITS or unit.upper() in SUBUNITS)


def to_eur_factor(unit, rates):
    """Facteur de conversion vers l'euro d'une unité de prix ; None si l'unité ou son taux est inconnu. `rates` : devise principale -> euros."""
    base, divisor = split_unit(unit)
    if not base:
        return None
    if base == 'EUR':
        return 1.0
    r = rates.get(base)
    return r / divisor if r else None
