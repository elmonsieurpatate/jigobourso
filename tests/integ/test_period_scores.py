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


def test_risk_adjusted_return_is_stored_per_long_window_and_weight_zero_changes_no_score():
    from engine.analytics.scoring import scores as SC
    from engine.analytics.scoring.score_inputs import mrar_input

    conn = connect()
    reset_data(conn)
    profile = scores_profiles.profile_of(scores_profiles.base_config('growth_v4'))
    for p in profile['periods'].values():
        p['enabled'] = False
    for pid in ('quarter', 'three_year', 'five_year'):
        profile['periods'][pid]['enabled'] = True
    profile['weights_mode'] = 'custom'
    profile['weights'] = {'quarter': 20, 'three_year': 40, 'five_year': 40}
    settings.put(conn, 'scores_profiles', {'growth_v4': scores_profiles.clean_profile(profile)})
    days = session_dates('XETR', '2026-10-27', 1261)
    closes = [round(100 * 1.0002**i * (1.03 if (i // 21) % 2 else 0.97), 6) for i, _ in enumerate(days)]  # tendance + alternance mensuelle
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:LONG.DE','equity','Long SE','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','LONG.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (1,%s,%s,100000)', list(zip(days, closes)))
        cur.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (1,130,%s,'daily','EUR',100000)", (datetime.datetime(2026, 10, 27, 18),))
    conn.commit()
    compute.compute_all(conn, datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc))
    with conn.cursor() as cur:
        cur.execute('SELECT sessions, mrar FROM score_inputs WHERE listing_id=1')
        stored = {r['sessions']: r['mrar'] for r in cur.fetchall()}
    assert stored[63] is None  # période trop courte : aucune valeur artificielle
    assert stored[756] is not None and stored[1260] is not None
    assert float(stored[756]) == pytest.approx(mrar_input(days[-757:], closes[-757:]), abs=1e-3)
    assert float(stored[1260]) == pytest.approx(mrar_input(days[-1261:], closes[-1261:]), abs=1e-3)

    cfg = scores_profiles.build_config(conn, 'growth_v4')
    before = score_service.details(conn, cfg, [1])[1]
    assert 'risk_adjusted' not in {k for k, v in before['complex']['contributions'].items() if not v.get('unavailable')}  # poids 0 : composante absente du calcul
    with conn.cursor() as cur:
        cur.execute('UPDATE score_inputs SET mrar=NULL')
    conn.commit()
    after = score_service.details(conn, cfg, [1])[1]
    assert (before['simple']['score'], before['complex']['score']) == (after['simple']['score'], after['complex']['score'])  # poids 0 : aucune note ne bouge, mesure présente ou non

    compute.compute_all(conn, datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc), full=True)  # `score_inputs.mrar` vidé à la main ci-dessus : recalcul complet explicite
    weighted = scores_profiles.profile_of(scores_profiles.base_config('growth_v4'))
    weighted.update(profile)
    weighted['complex_weights'] = dict(SC.COMPLEX_WEIGHTS, dynamics=30, risk_adjusted=10)  # total 100 : 30 + 10 + 60 de base
    settings.put(conn, 'scores_profiles', {'growth_v4': scores_profiles.clean_profile(weighted)})
    result = score_service.details(conn, scores_profiles.build_config(conn, 'growth_v4'), [1])[1]
    part = result['complex']['contributions']['risk_adjusted']
    assert not part.get('unavailable') and part['value'] is not None
    periods = result['periods']
    assert periods['quarter']['risk_adjusted'] is None  # 63 séances : jamais mesuré
    assert periods['three_year']['risk_adjusted'] == pytest.approx(SC.period_risk_adjusted_note(float(stored[756]), 756))
    assert periods['five_year']['risk_adjusted'] == pytest.approx(SC.period_risk_adjusted_note(float(stored[1260]), 1260))
    assert result['simple']['score'] == before['simple']['score']  # le Score 1 ne change jamais
