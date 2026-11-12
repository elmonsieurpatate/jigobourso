"""Répartition par zone et écart à la cible (stratégie prudente)."""
import pytest

from engine.analytics.portfolio import allocation as al

CTX = {1: ('etf', None, {'category': 'United States Stock'}), 2: ('etf', None, {'category': 'Europe Stock'}), 3: ('etf', None, {'category': 'Diversified Emerging Mkts'}),
       4: ('etf', None, {'category': 'World Large-Cap Blend'}), 5: ('equity', 'France', None), 6: ('equity', 'United States', None)}


def test_validate_target():
    assert al.validate_target({'us': 50, 'eu': '25', 'emerging': 25.0}) == {'us': 50.0, 'eu': 25.0, 'emerging': 25.0}
    for bad in ({'us': 60, 'eu': 25, 'emerging': 25}, {'us': -1, 'eu': 51, 'emerging': 50}, {'us': 'x', 'eu': 50, 'emerging': 50}, None):
        with pytest.raises(ValueError):
            al.validate_target(bad)


def test_zones_never_guess_world_funds():
    assert al.zone_of('etf', None, {'category': 'World Large-Cap Blend'}) == 'other'
    assert al.zone_of('etf', None, None) == 'other'
    assert al.zone_of('equity', 'France', None) == 'eu' and al.zone_of('equity', 'Narnia', None) == 'other'


def test_summary_against_prudent_target():
    pos = [{'listing_id': 1, 'value': 600}, {'listing_id': 2, 'value': 200}, {'listing_id': 3, 'value': 100}, {'listing_id': 4, 'value': 100}, {'listing_id': 5, 'value': None}]
    s = al.summarize(pos, CTX, al.PRUDENT)
    rows = {r['zone']: r for r in s['rows']}
    assert s['total_eur'] == 1000 and s['unpriced'] == 1
    assert rows['us']['current_pct'] == 60 and rows['us']['gap_eur'] == -100 and rows['us']['off_target']
    assert rows['eu']['gap_eur'] == 50 and rows['eu']['off_target']                # 20 % contre 25 % : 5 points, le seuil compte
    assert rows['emerging']['gap_eur'] == 150 and rows['other']['gap_eur'] == -100
    assert s['rebalance_suggested'] and s['zones'][4] == 'other'


def test_summary_without_target_or_value():
    s = al.summarize([{'listing_id': 6, 'value': 10}], CTX, None)
    assert s['target'] is None and not s['rebalance_suggested'] and {r['zone']: r['current_pct'] for r in s['rows']}['us'] == 100
    assert al.summarize([], CTX, al.PRUDENT)['rows'][0]['current_pct'] is None
