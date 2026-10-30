"""Regroupement des ETF quasi identiques sur toute une page : lien direct avec le chef (jamais de chaînage), couverture de change respectée, rien de masqué."""
from engine.analytics import etf


def etf_entry(name, near=(), fee=None, currency='EUR'):
    return {'meta': {'name': name, 'currency': currency}, 'near': [{'id': i, 'coefficient': c, 'stable': True} for i, c in near], 'profile': {'expense_ratio': fee}}


def test_variant_reads_hedge_distribution_and_index_from_the_name():
    v = etf.variant('iShares Edge S&P 500 Minimum Volatility UCITS ETF USD (Acc)')
    assert v['hedge'] is None and v['dist'] == 'Acc' and v['index'] == 's&p 500 minimum volatility'
    assert etf.variant('iShares Core S&P 500 UCITS ETF EUR Hedged (Dist)') == {'hedge': 'EUR', 'dist': 'Dist', 'index': 's&p 500'} or etf.variant('iShares Core S&P 500 UCITS ETF EUR Hedged (Dist)')['hedge'] == 'EUR'
    assert etf.variant('Xtrackers MSCI World UCITS ETF 1C')['index'] == 'msci world'
    assert etf.variant(None) == {'hedge': None, 'dist': None, 'index': None, 'flags': frozenset()}


def test_members_must_be_linked_to_the_leader_not_through_a_chain():
    cached = {1: etf_entry('A S&P 500 UCITS ETF', near=[(2, .99)]), 2: etf_entry('B S&P 500 UCITS ETF', near=[(1, .99), (3, .98)]), 3: etf_entry('C S&P 500 UCITS ETF', near=[(2, .98)])}
    groups = etf.page_groups(cached, [1, 2, 3])
    assert len(groups) == 1 and groups[0]['leader'] == 1 and groups[0]['members'] == [2]          # 3 n'est lié qu'à 2 : pas de chaînage


def test_hedged_and_unhedged_variants_are_never_mixed_and_nothing_is_dropped():
    cached = {1: etf_entry('iShares MSCI World UCITS ETF USD (Acc)', near=[(2, .98), (3, .99)]), 2: etf_entry('iShares MSCI World UCITS ETF EUR Hedged (Acc)', near=[(1, .98)]),
              3: etf_entry('Xtrackers MSCI World UCITS ETF USD (Dist)', near=[(1, .99)], fee=.12, currency='USD')}
    groups = etf.page_groups(cached, [1, 2, 3])
    assert groups[0]['members'] == [3] and 2 not in groups[0]['members']
    row = groups[0]['rows'][0]
    assert any('même indice' in w for w in row['why']) and any('distribue' in d for d in row['diff']) and any('USD' in d for d in row['diff'])


def test_unknown_data_gives_no_group():
    assert etf.page_groups({1: etf_entry('A ETF'), 2: etf_entry('B ETF')}, [1, 2]) == []
    assert etf.page_groups({}, [1, 2]) == []


def test_correlation_alone_needs_099_and_strategy_products_are_never_grouped_with_plain_ones():
    cached = {1: etf_entry('Innovator S&P 500 Buffer ETF - August', near=[(2, .98), (3, .995)]), 2: etf_entry('PGIM S&P 500 Buffer 12 ETF - June'),
              3: etf_entry('Roundhill Gold WeeklyPay ETF'), 4: etf_entry('iShares Gold ETF', near=[(5, .98), (6, .995)]), 5: etf_entry('iShares Other ETF'), 6: etf_entry('Xtrackers Physical Gold ETC')}
    assert etf.page_groups(cached, [1, 2, 3]) == []                         # 0,98 sans indice commun : non ; produit « weeklypay » : jamais avec un fonds classique
    groups = etf.page_groups(cached, [4, 5, 6])
    assert [g['members'] for g in groups] == [[6]]                         # 0,98 refusé, 0,995 accepté
    assert etf.variant('Innovator S&P 500 Buffer ETF - August')['flags'] == frozenset({'buffer'})
    assert etf.variant('Amundi Index Solutions - Amundi Index MSCI World')['index'] == etf.variant('iShares Core MSCI World UCITS ETF USD (Acc)')['index'] == 'msci world'
