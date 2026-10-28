from engine.analytics import strategy
from engine.migration.legacy import convert_config

OLD = {"version": 2, "strategy": "regular", "ranking": {"mode": "regularity", "k": 2, "weights": {"week": 2}},
       "technical_filters": {"price_above_ma50": {"enabled": True}, "ma50_ascending": {"enabled": False},
                             "max_daily_change": {"enabled": True, "value": 8.0}, "max_gap_to_ma20": {"enabled": False, "value": 15.0}},
       "periods": {"day": {"enabled": False, "sessions": 1, "min_slope": 0.27, "min_r2": None, "min_er": None, "min_return": None, "max_volatility": None, "max_drawdown": None, "min_acceleration": None},
                   "week": {"enabled": True, "sessions": 5, "min_slope": 0.3, "min_r2": 0.75, "min_er": None, "min_return": 1.0, "max_volatility": None, "max_drawdown": None, "min_acceleration": 0.0},
                   "month": {"enabled": True, "sessions": 21, "min_slope": 0.27, "min_r2": 0.75, "min_er": 0.188, "min_return": None, "max_volatility": 2.0, "max_drawdown": 12, "min_acceleration": None},
                   "quarter": {"enabled": False, "sessions": 63, "min_slope": 0.27}, "half": {"enabled": False, "sessions": 126, "min_slope": 0.27}, "year": {"enabled": False, "sessions": 252, "min_slope": 0.27}}}


def test_user_thresholds_preserved_and_result_valid():
    c = convert_config(OLD)
    assert c and strategy.validate(c)
    wk = next(p for p in c['periods'] if p['id'] == 'week')
    assert wk['enabled'] and wk['min_slope'] == 0.3 and wk['min_r2'] == 0.75 and wk['min_return'] == 1.0
    mo = next(p for p in c['periods'] if p['id'] == 'month')
    assert mo['max_volatility'] == 2.0 and mo['max_drawdown'] == 12 and mo['min_er'] == 0.188
    assert c['technical'] == {'above_ma50': True, 'ma50_rising': False, 'max_daily_change': 8.0, 'max_gap_ma20': None}
    assert c['ranking'] == {'mode': 'regularity', 'weights': {'week': 2}}


def test_garbage_is_dropped_not_crashing():
    assert convert_config('pas du json') is None
    assert convert_config({'periods': 3}) is None
    assert convert_config(None) is None
