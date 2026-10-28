from engine.catalogue.rules import exclusion_reason
from engine.catalogue.primary import choose_primary


def row(**kw):
    base = {'symbol': 'ABC.DE', 'name': 'Abc SE', 'mic': 'XETR', 'delisted': 'False'}
    base.update(kw)
    return base


def test_exclusions():
    assert exclusion_reason('equity', row()) is None
    assert exclusion_reason('equity', row(mic='XTKS')) == 'place non retenue'
    assert exclusion_reason('equity', row(delisted='True')) == 'titre radié'
    assert exclusion_reason('equity', row(name='Foo Acquisition Corp II')) == 'société vide (SPAC)'
    assert exclusion_reason('equity', row(name='Foo Corp Warrants')) is not None
    assert exclusion_reason('equity', row(symbol='FOO-WT', name='Foo Corp')) is not None
    assert exclusion_reason('etf', row(name='Leverage Shares 3x Tesla')) == 'ETF à effet de levier ou inverse'
    assert exclusion_reason('etf', row(name='iShares Core MSCI World')) is None
    assert exclusion_reason('equity', row(name='Unity Software')) is None      # « unit » ne doit pas matcher « Unity »


def test_sap_goes_to_xetra():
    ls = [{'id': 1, 'mic': 'XNYS', 'symbol': 'SAP', 'currency': 'USD'}, {'id': 2, 'mic': 'XETR', 'symbol': 'SAP.DE', 'currency': 'EUR'},
          {'id': 3, 'mic': 'XPAR', 'symbol': 'SAP.PA', 'currency': 'EUR'}]
    assert choose_primary(ls, 'Germany', {1: 9e9, 2: 1e6}) == (2, 'home_market')


def test_unknown_home_uses_liquidity_then_euro():
    ls = [{'id': 1, 'mic': 'XETR', 'symbol': 'A', 'currency': 'EUR'}, {'id': 2, 'mic': 'XPAR', 'symbol': 'A', 'currency': 'EUR'}]
    assert choose_primary(ls, None, {1: 5, 2: 9}) == (2, 'liquidity')
    assert choose_primary(ls, None, {1: 5, 2: 5})[0] == 1                       # égalité : ordre alphabétique des places
    mixed = [{'id': 1, 'mic': 'XNYS', 'symbol': 'A', 'currency': 'USD'}, {'id': 2, 'mic': 'XETR', 'symbol': 'A', 'currency': 'EUR'}]
    assert choose_primary(mixed, None, {1: 5, 2: 5}) == (2, 'liquidity')        # euro préféré à égalité


def test_us_issuer_picks_us_listing_over_german_copy():
    ls = [{'id': 1, 'mic': 'XNAS', 'symbol': 'AAPL', 'currency': 'USD'}, {'id': 2, 'mic': 'XETR', 'symbol': 'APC.DE', 'currency': 'EUR'}]
    assert choose_primary(ls, 'United States', {1: 1, 2: 9})[0] == 1


def test_no_liquidity_fallback_is_deterministic_and_single():
    ls = [{'id': 1, 'mic': 'XETR', 'symbol': 'A', 'currency': 'EUR'}, {'id': 2, 'mic': 'XNAS', 'symbol': 'A', 'currency': 'USD'}]
    assert choose_primary(ls)[1] == 'default'
    assert choose_primary([ls[0]]) == (1, 'single')
