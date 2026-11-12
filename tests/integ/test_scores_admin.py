"""Administration des scores sur une vraie base : simulation, suivi et profils, avec des séries enregistrées (aucune donnée d'exemple dans le produit)."""
import datetime
import os

import pytest

from engine.analytics.series import compute
from engine.analytics.admin import scores_admin as A
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


def seed(conn):
    import exchange_calendars as xc
    calendar = xc.get_calendar('XETR', start='2026-01-05', end='2027-01-31')
    days = [d.date() for d in calendar.sessions if d.date() >= datetime.date(2026, 1, 5)][:260]
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:UP.DE','equity','Monte SE','Germany'),(2,'sym:XETR:ZIG.DE','equity','Zigzag AG','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','UP.DE','EUR','selected',1),(2,2,'XETR','ZIG.DE','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                        [(1, d, round(100 * 1.004 ** i, 6)) for i, d in enumerate(days)] + [(2, d, round(100 * 1.0015 ** i * (1.04 if i % 3 == 0 else 0.97), 6)) for i, d in enumerate(days)])
        cur.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (%s,%s,%s,'daily','EUR',%s)", [(1, 250.0, NOW, 300000), (2, 120.0, NOW, 50000)])
    conn.commit()
    compute.compute_all(conn, NOW)


def test_simulation_monitor_and_profiles_use_real_data_and_stay_independent_of_conformity():
    conn = connect()
    reset_data(conn)
    empty = A.simulate(conn, {'strategy': 'growth_v4'})
    assert empty['empty'] and 'Aucun titre noté' in empty['reason']                    # sans données : jamais d'exemple fictif
    assert A.monitor(conn)['rated'] == 0
    seed(conn)
    mon = A.monitor(conn)
    assert mon['rated'] == 2 and mon['liquidity']['universe'] == 2 and mon['freshness']['last_close'] is not None
    sim = A.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE'})
    assert sim['title']['symbol'] == 'UP.DE' and [p['id'] for p in sim['periods']] == ['week', 'month']
    simple, complex_ = sim['result']['simple'], sim['result']['complex']
    assert simple['score'] is not None and 0 < simple['score'] <= 100 and complex_['score'] is not None
    assert sum(sim['result']['weights'].values()) == pytest.approx(1)
    assert A.simulate(conn, {'strategy': 'growth_v4', 'q': 'introuvable'}).get('not_found')
    # régulier mieux noté que le titre en dents de scie (score simple)
    zig = A.simulate(conn, {'strategy': 'growth_v4', 'q': 'ZIG.DE'})['result']['simple']['score']
    assert zig is None or zig < simple['score']
    # les seuils de conformité ne changent aucune note
    p = A.profile_of(A.base_config('growth_v4'))
    for x in p['periods'].values():
        x.pop('sessions')
    p['periods']['week']['min_slope'] = 0.9
    p['periods']['month']['min_r2'] = 0.95
    A.save(conn, {'profile': dict(p, name='growth_v4')})
    again = A.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE'})['result']
    assert again['simple']['score'] == simple['score'] and again['complex']['score'] == complex_['score']
    # une granularité de plus change les notes ; le brouillon non enregistré permet de simuler sans enregistrer
    p['periods']['quarter']['enabled'] = True
    draft = A.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE', 'draft': {'profile': dict(p, name='growth_v4')}})
    assert [x['id'] for x in draft['periods']] == ['week', 'month', 'quarter']
    assert [x['id'] for x in A.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE'})['periods']] == ['week', 'month']
    A.save(conn, {'reset': 'all'})
    assert not [s for s in A.state(conn)['strategies'] if s['name'] == 'growth_v4'][0]['customised']


def test_general_ranking_rates_every_evaluable_title_and_filters_remove_none():
    from engine.analytics.admin import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    r = A.ranking(conn, {'strategy': 'growth_v4'})
    s = r['summary']
    assert s['universe'] == 2 and s['simple']['ranked'] == 2 and s['complex']['ranked'] == 2 and s['simple']['unavailable'] == 0      # tous notés, aucun quota
    assert sum(s['simple']['distribution']['histogram']) == 2 and [x['symbol'] for x in r['top']['simple']][0] == 'UP.DE'
    assert abs(sum(w['weight'] for w in r['weights']) - 1) < 1e-9 and r['compared'] is None
    # classement par catégorie : courbes réelles, rang général inchangé, granularité = période active la plus longue
    lst = r['listing']
    assert r['granularity']['sessions'] == 21 and lst['which'] == 'simple' and lst['total'] == 2 and [x['rank'] for x in lst['rows']] == [1, 2]
    assert all(len(x['curve']) <= 22 for x in lst['rows']) and sum(c['count'] for c in lst['categories']) == 2
    sub = A.ranking(conn, {'strategy': 'growth_v4', 'which': 'complex', 'category': None})['listing']
    assert sub['which'] == 'complex'
    sim0 = A.simulate(conn, {'strategy': 'growth_v4', 'q': 'UP.DE'})
    assert sim0['ranks']['simple']['rank'] == 1 and sim0['granularity'] == 21 and isinstance(sim0['curve'], list) and sim0['suggestions'][0]['rank'] == 1
    # seuils extrêmes SANS activer les filtres : ni notes ni classement ne bougent, et l'Explorer ne retire aucun titre
    p = A.profile_of(A.base_config('growth_v4'))
    for x in p['periods'].values():
        x.pop('sessions')
    p['periods']['week']['min_slope'] = 50
    p['periods']['month']['min_r2'] = 0.999
    A.save(conn, {'profile': dict(p, name='growth_v4')})
    assert A.ranking(conn, {'strategy': 'growth_v4'})['summary'] == s
    cfg = A.build_config(conn, 'growth_v4')
    verdicts = service.judge_universe(conn, cfg)
    assert {v['status'] for v in verdicts} == {'retained'}
    # filtres activés : le verdict peut écarter, mais le classement général garde les deux titres
    p['filters'] = {'enabled': True}
    A.save(conn, {'profile': dict(p, name='growth_v4')})
    assert {v['status'] for v in service.judge_universe(conn, A.build_config(conn, 'growth_v4'))} == {'rejected'}
    assert A.ranking(conn, {'strategy': 'growth_v4'})['summary'] == s
    # effet d'un changement de poids : comparaison avec le réglage enregistré
    p['weights_mode'], p['weights'] = 'custom', {'week': 90, 'month': 10}
    moved = A.ranking(conn, {'strategy': 'growth_v4', 'draft': {'profile': dict(p, name='growth_v4')}})
    assert moved['compared']['simple']['compared'] == 2 and moved['weights'][0]['weight'] == pytest.approx(0.9)
    A.save(conn, {'reset': 'all'})


def test_per_strategy_normalisations_persist_change_only_their_strategy_and_the_cache_key():
    from engine.analytics.scoring import score_service as S
    conn = connect()
    reset_data(conn)
    seed(conn)
    from engine.analytics.admin import service
    ver = service.data_version(conn)
    before = {n: {e['id']: (e['simple'], e['complex']) for e in S.score_book(conn, A.build_config(conn, n), ver).values()} for n in ('growth_v4', 'rebound')}
    key_before = S._key(A.build_config(conn, 'rebound'), ver)
    p = A.clean_profile(A.profile_of(A.base_config('rebound')))
    p['tuning'] = dict(p['tuning'], sat_a=40.0, accel_ref=1.5, vol_mode='relative')
    A.save(conn, {'profile': dict(p, name='rebound')})
    st = {s['name']: s for s in A.state(conn)['strategies']}
    assert st['rebound']['current']['tuning'] == {'sat_a': 40.0, 'accel_ref': 1.5, 'vol_mode': 'relative', 'momentum_horizon': '6m'}      # persisté et relu
    assert st['growth_v4']['current']['tuning']['sat_a'] == 17.0                                                                          # autre stratégie : inchangée
    assert S._key(A.build_config(conn, 'rebound'), ver) != key_before                  # les nouveaux paramètres font partie de la clé de cache
    assert S._key(A.build_config(conn, 'growth_v4'), ver) == S._key(A.base_config('growth_v4'), ver)
    after = {n: {e['id']: (e['simple'], e['complex']) for e in S.score_book(conn, A.build_config(conn, n), ver).values()} for n in ('growth_v4', 'rebound')}
    assert after['growth_v4'] == before['growth_v4'] and after['rebound'] != before['rebound']
    sim = A.simulate(conn, {'strategy': 'rebound', 'q': 'UP.DE'})
    assert sim['tuning'] == {'sat_a': 40.0, 'accel_ref': 1.5, 'vol_mode': 'relative', 'momentum_horizon': '6m'}                           # la simulation affiche ce que le calcul utilise
    A.save(conn, {'reset': 'profile', 'name': 'rebound'})
    assert A.build_config(conn, 'rebound')['scoring']['sat_a'] == 17.0 and A.build_config(conn, 'rebound')['scoring']['accel_ref'] == 0.25     # retour aux valeurs par défaut de la stratégie
    with pytest.raises(ValueError):
        A.save(conn, {'profile': dict(p, name='rebound', tuning=dict(p['tuning'], sat_a=1.0))})


def test_stored_profile_without_new_fields_is_still_valid_and_momentum_strategies_use_series_state():
    from engine.analytics.scoring import score_service as S
    from engine.analytics.admin import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    old = A.clean_profile(A.profile_of(A.base_config('growth_v4')))
    old.pop('tuning', None)
    old['complex_weights'].pop('momentum')                                           # profil enregistré avant l'ajout du momentum (huit poids)
    A.save(conn, {'profile': dict(old, name='growth_v4')})
    cfg = A.build_config(conn, 'growth_v4')
    assert cfg['scoring']['sat_a'] == 17.0 and S.params_for(cfg, 'equity')['complex_weights']['momentum'] == 0
    with conn.cursor() as cur:
        cur.execute('UPDATE series_state SET momentum_6m=45, momentum_12m=80 WHERE listing_id=1')
        cur.execute('UPDATE series_state SET momentum_6m=-10, momentum_12m=-20 WHERE listing_id=2')
    conn.commit()
    ver = service.data_version(conn)
    book = S.score_book(conn, A.build_config(conn, 'momentum_6m'), ver)
    assert book[1]['complex'] is not None and book[1]['complex'] > book[2]['complex']
    det = S.details(conn, A.build_config(conn, 'momentum_6m'), [1])[1]['complex']['contributions']['momentum']
    assert det['value'] == pytest.approx(75.0) and det['weight'] == pytest.approx(0.5)                # 45 % / 60 % de saturation


def test_global_settings_never_override_profile_complex_weights():
    from engine.analytics.scoring import score_service as S
    from engine.shared import settings
    conn = connect()
    reset_data(conn)
    settings.put(conn, S.SETTING, {'kappa': 0.7, 'threshold': 0.75, 'complex_weights': {'dynamics': 90, 'liquidity': 10}})      # ancien réglage global résiduel
    conn.commit()
    assert S.params_for(A.build_config(conn, 'growth_v4'), 'equity')['complex_weights'] == {k: float(v) for k, v in __import__('engine.analytics.scoring.scores', fromlist=['x']).COMPLEX_WEIGHTS.items()}
