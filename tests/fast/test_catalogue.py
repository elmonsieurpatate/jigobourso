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


# ── Faux positifs constatés sur le catalogue réel (audit du 29/10/2026) ──
import pytest as _pytest  # noqa: E402
from engine.catalogue import rules as _rules  # noqa: E402


@_pytest.mark.parametrize('name', [
    'AB Short Duration High Yield ETF', 'AB Ultra Short Income ETF', 'Allspring Short-Term High Income Fund ETF', 'iShares Short Treasury Bond ETF',
    'Vanguard Short-Term Bond ETF', 'iShares € Ultrashort Bond UCITS ETF EUR (Dist)', 'JPM USD Ultra-Short Income ETF USD Acc', 'JH US Short Dur HY ETF',
    'Innovator S&P 500 Ultra Buffer ETF - April New', 'Convergence Long/Short Equity ETF', 'Nuveen Short-Term REIT ETF', 'EA Bridgeway Ultra-Small Company Market ETF',
    'Multi Units Luxembourg - Lyxor DAX (DR) UCITS ETF'])
def test_funds_without_leverage_are_not_excluded_as_leveraged(name):
    assert not _rules.is_leveraged_name(name)
    assert _rules.evaluate('etf', {'mic': 'XPAR', 'symbol': 'ABCD.PA', 'name': name}, _rules.default_config()) == (None, None)


@_pytest.mark.parametrize('name', [
    'ProShares UltraShort QQQ', 'ProShares Ultra QQQ', 'ProShares UltraPro Short QQQ', 'Direxion Daily S&P 500 Bull 3X Shares', 'ProShares Short S&P500',
    'ProShares Short 20+ Year Treasury', 'ProShares Short High Yield', 'Leverage Shares 3x Tesla', 'GraniteShares 2x Long NVDA', 'Ultra Short Dax',
    'Xtrackers FTSE 100 Short Daily Swap UCITS ETF 1C', 'ComStage EURO STOXX 50 Daily Short UCITS ETF', 'Xtrackers S&P 500 Inverse Daily', 'ProShares Short VIX Short-Term Futures ETF'])
def test_real_leveraged_and_inverse_funds_stay_excluded(name):
    assert _rules.is_leveraged_name(name)


@_pytest.mark.parametrize('kind,name,expected', [
    ('etf', 'Multi Units Luxembourg - Lyxor MSCI ACWI Gold UCITS ETF', None),
    ('etf', 'Global X Human Rights ETF', None),
    ('equity', 'Smith Unit Holdings', None),
    ('equity', 'Launch Two Acquisition Corp. Unit', 'warrants'),
    ('equity', 'Range Capital Acquisition Corp. Units', 'warrants'),
    ('equity', 'Foo Corp Rights', 'warrants'),
    ('equity', 'Foo Corp Warrants', 'warrants'),
    ('etf', 'Foo Warrants ETF', 'warrants')])
def test_derivative_detection_does_not_hit_etf_names_with_units(kind, name, expected):
    assert _rules.evaluate(kind, {'mic': 'XNAS', 'symbol': 'ABCD', 'name': name}, _rules.default_config())[0] == expected
