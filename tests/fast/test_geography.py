from engine.analytics.geography import equity_region, etf_region


def test_equity_regions_use_issuer_country_names():
    assert equity_region('United States') == 'us'
    assert equity_region('France') == 'eu'
    assert equity_region('India') == 'emerging'
    assert equity_region(None) is None
    assert equity_region('Japan') is None


def test_etf_regions_use_explicit_fund_categories_and_leave_global_unknown():
    assert etf_region('Europe Stock') == 'eu'
    assert etf_region('Diversified Emerging Mkts') == 'emerging'
    assert etf_region('United States Stock') == 'us'
    assert etf_region('World Large-Stock Blend') is None
    assert etf_region(None) is None

