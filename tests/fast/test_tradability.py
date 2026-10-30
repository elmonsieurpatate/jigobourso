"""Filtre « Titres facilement négociables » : un seul calcul (engine.analytics.signals.liquidity) pour le filtre, la pastille et la fiche."""
import pytest

from engine.analytics import service, signals

CFG = {'liquidity_equity': {'min_eur': 1_000_000}, 'liquidity_etf': {'min_eur': 250_000}}


@pytest.mark.parametrize('kind,value,level', [
    ('equity', 6_300_000, 'ok'), ('equity', 4_000_000, 'ok'), ('equity', 3_000_000, 'warn'), ('equity', 2_000_000, 'warn'), ('equity', 1_999_999, 'bad'),
    ('etf', 1_000_000, 'ok'), ('etf', 700_000, 'warn'), ('etf', 500_000, 'warn'), ('etf', 495_000, 'bad'), ('etf', 256_000, 'bad')])
def test_levels_follow_the_explainable_floor_and_comfort(kind, value, level):
    assert signals.liquidity(value, kind, CFG)['level'] == level


def test_missing_or_stale_data_is_never_called_limited():
    assert signals.liquidity(None, 'etf', CFG)['level'] == 'unknown'
    stale = signals.liquidity(100_000, 'etf', CFG, quote_age_days=30)           # volume bas MAIS périmé : aucune preuve
    assert stale['level'] == 'unknown' and stale['reason'] == 'stale'
    assert signals.liquidity(100_000, 'etf', CFG, quote_age_days=2)['level'] == 'bad'


def test_floor_follows_the_prefilter_minimum():
    assert signals.liquidity_levels('equity', CFG) == (2_000_000, 4_000_000)
    assert signals.liquidity_levels('etf', {'liquidity_etf': {'min_eur': 400_000}}) == (800_000, 1_600_000)


def entry(symbol='CFFI', isin=None, kind='equity'):
    return {'symbol': symbol, 'isin': isin, 'kind': kind}


def test_mask_only_hides_limited_titles_and_never_an_exact_search_hit():
    low = {'price_eur': 100.0, 'volume': 5_000, 'quote_age_days': 0.1}              # 500 k€ / jour : limitée pour une action
    assert service.masked_by_tradability(entry(), low, CFG) is True
    assert service.masked_by_tradability(entry(), low, CFG, 'cffi') is False         # recherche par symbole exact
    assert service.masked_by_tradability(entry(isin='IE00B78JSG98'), low, CFG, 'ie00b78jsg98') is False
    assert service.masked_by_tradability(entry(), low, CFG, 'cf') is True            # une recherche partielle ne lève pas le masque
    assert service.masked_by_tradability(entry(), {'price_eur': 100.0, 'volume': None}, CFG) is False        # inconnu : visible
    assert service.masked_by_tradability(entry(), {'price_eur': 100.0, 'volume': 5_000, 'quote_age_days': 40}, CFG) is False
    assert service.masked_by_tradability(entry(), {'price_eur': 100.0, 'volume': 60_000, 'quote_age_days': 0.1}, CFG) is False


def test_a_held_title_is_masked_like_any_other_except_in_the_held_view():
    rows = [{'id': 1, 'symbol': 'UBU5.DE', 'isin': None, 'kind': 'etf'}, {'id': 2, 'symbol': 'GOOD', 'isin': None, 'kind': 'etf'}]
    aux = {1: {'price_eur': 100.0, 'volume': 4_500, 'quote_age_days': 0.1}, 2: {'price_eur': 100.0, 'volume': 50_000, 'quote_age_days': 0.1}}      # 450 k€ et 5 M€ par jour
    assert [e['id'] for e in service.tradable_rows(rows, aux, CFG)] == [2]                       # détenu ou non : masqué
    assert [e['id'] for e in service.tradable_rows(rows, aux, CFG, '', {1})] == [1, 2]           # vue « Titres détenus » : complète
