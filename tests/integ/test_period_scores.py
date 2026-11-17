"""Fenêtres V4 longues sur la base jetable, sans cours antérieurs à cinq ans."""

import datetime
import os

import pytest

from engine.analytics.scoring import score_service, scores_profiles
from engine.analytics.series import compute
from engine.market.calendar import session_dates
from engine.shared import settings
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


def test_three_and_five_year_scores_use_only_1261_closes():
    conn = connect()
    reset_data(conn)
    profile = scores_profiles.profile_of(scores_profiles.base_config('growth_v4'))
    for p in profile['periods'].values():
        p['enabled'] = False
    profile['periods']['three_year']['enabled'] = True
    profile['periods']['five_year']['enabled'] = True
    profile['weights_mode'] = 'custom'
    profile['weights'] = {'three_year': 40, 'five_year': 60}
    profile['complex_weights'].update(dynamics=10, acceleration=10, momentum=10, recovery=10)
    settings.put(conn, 'scores_profiles', {'growth_v4': scores_profiles.clean_profile(profile)})
    days = session_dates('XETR', '2026-10-27', 1261)
    assert days and len(days) == 1261
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:LONG.DE','equity','Long SE','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','LONG.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (1,%s,%s,100000)', [(d, round(100 * 1.0002**i, 6)) for i, d in enumerate(days)])
        cur.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (1,130,%s,'daily','EUR',100000)", (datetime.datetime(2026, 10, 27, 18),))
    conn.commit()
    cfg = scores_profiles.build_config(conn, 'growth_v4')
    assert score_service.params_for(cfg, 'equity')['periods'] == [{'id': 'three_year', 'sessions': 756, 'weight': 40.0}, {'id': 'five_year', 'sessions': 1260, 'weight': 60.0}]
    assert 1260 in compute.wanted_windows(conn)
    compute.compute_all(conn, datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc))
    result = score_service.details(conn, cfg, [1])[1]
    assert result['simple']['status'] == 'ok'
    assert result['complex']['status'] == 'ok'
    assert result['weights'] == {'three_year': 0.4, 'five_year': 0.6}
    for period in result['periods'].values():
        assert period['momentum'] is not None
        assert period['acceleration'] is not None
        assert period['recovery'] == 0
        assert period['liquidity'] is not None
    with conn.cursor() as cur:
        cur.execute('SELECT MAX(sessions) AS longest FROM strategy_metrics')
        assert cur.fetchone()['longest'] == 1260
