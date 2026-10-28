import pytest
from engine.catalogue import rules
from engine.market import prefilter
from engine.jobs import schedule


def test_catalogue_defaults_keep_current_behaviour():
    cfg = rules.normalize({})
    assert rules.evaluate('equity', {'mic': 'XETR', 'symbol': 'A', 'name': 'X Warrants', 'delisted': ''}, cfg)[0] == 'warrants'
    assert rules.evaluate('etf', {'mic': 'XETR', 'symbol': 'A', 'name': 'Ultra Short Dax', 'delisted': ''}, cfg)[0] == 'leveraged'
    assert rules.evaluate('equity', {'mic': 'XETR', 'symbol': 'A', 'name': 'Ok SE', 'delisted': ''}, cfg) == (None, None)


def test_catalogue_rule_can_be_disabled_and_validation():
    cfg = rules.normalize({'delisted': {'enabled': False}, 'types': {'etf': False}})
    assert rules.evaluate('equity', {'mic': 'XETR', 'symbol': 'A', 'name': 'N', 'delisted': 'True'}, cfg) == (None, None)
    assert rules.evaluate('etf', {'mic': 'XETR', 'symbol': 'E', 'name': 'N'}, cfg)[0] == 'types'
    for bad in ({'nope': {}}, {'markets': {'values': ['bad mic!']}}, {'markets': {'values': []}}, {'types': {'equity': False, 'etf': False}}):
        with pytest.raises(ValueError):
            rules.normalize(bad)


def test_prefilter_flags_and_old_format():
    assert prefilter.decide('equity', 1.0, 10, 1.0, {})[0] == 'excluded'
    assert prefilter.decide('equity', 1.0, 10, 1.0, {'price': {'enabled': False}, 'liquidity_equity': {'enabled': False}}) == ('selected', None)
    assert prefilter.decide('equity', 50.0, None, 1.0, {'unknown_volume': {'enabled': False}}) == ('selected', None)
    assert prefilter.normalize({'min_price_eur': 5})['price']['min_eur'] == 5.0
    with pytest.raises(ValueError):
        prefilter.normalize({'price': {'min_eur': -3}})


def test_schedule_validation():
    assert schedule.normalize({'intraday': {'interval_minutes': 30}})['intraday']['interval_minutes'] == 30
    assert set(schedule.normalize({})) == {'cron_interval_minutes', 'daily', 'intraday'}       # le cron ne planifie ni catalogue ni filtrage
    for bad in ({'intraday': {'interval_minutes': 1}}, {'ghost': {}}, {'cron_interval_minutes': 0}):
        with pytest.raises(ValueError):
            schedule.normalize(bad)


def test_places_are_free_and_any_mic_is_accepted():
    cfg = rules.normalize({'markets': {'values': ['XTKS', 'XQQQ']}})
    assert rules.evaluate('equity', {'mic': 'XTKS', 'symbol': 'A', 'name': 'N'}, cfg) == (None, None)
    assert rules.evaluate('equity', {'mic': 'XPAR', 'symbol': 'A', 'name': 'N'}, cfg)[0] == 'markets'
    off = rules.normalize({'markets': {'enabled': False}})
    assert rules.evaluate('equity', {'mic': 'XZZZ', 'symbol': 'A', 'name': 'N'}, off) == (None, None)


def test_categories_filter_is_optional():
    assert rules.evaluate('equity', {'mic': 'XETR', 'symbol': 'A', 'name': 'N', 'category': 'Financials'}, rules.normalize({})) == (None, None)
    cfg = rules.normalize({'categories': {'enabled': True, 'values': ['Financials']}})
    assert rules.evaluate('equity', {'mic': 'XETR', 'symbol': 'A', 'name': 'N', 'category': 'Financials'}, cfg)[0] == 'categories'


def test_stale_quote_rule_is_optional_and_adjustable():
    assert prefilter.decide('etf', 30.0, 100000, 1.0, None, age_days=3) == ('selected', None)
    status, reason = prefilter.decide('etf', 30.0, 100000, 1.0, None, age_days=1800)           # titre mort : cours figé depuis 2021, il passait prix et liquidité
    assert status == 'excluded' and prefilter.step_of(reason) == 'stale'
    assert prefilter.decide('etf', 30.0, 100000, 1.0, {'stale': {'max_days': 3000}}, age_days=1800)[0] == 'selected'            # seuil modifiable
    assert prefilter.decide('etf', 30.0, 100000, 1.0, {'stale': {'enabled': False}}, age_days=1800)[0] == 'selected'             # désactivable
    assert prefilter.decide('etf', 30.0, 100000, 1.0, None, age_days=None)[0] == 'selected'                                      # âge inconnu : pas de décision sur ce critère
    assert prefilter.default_config()['stale'] == {'enabled': True, 'max_days': 10}
