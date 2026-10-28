import datetime
import os
import pytest
from engine.shared.db import connect
from engine.analytics import compute, service, strategy, tracking
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


def seed(conn):
    reset_data(conn)
    end = datetime.date(2026, 10, 27)
    days = []
    d = end
    while len(days) < 300:
        if d.weekday() < 5:
            days.append(d)
        d -= datetime.timedelta(days=1)
    days.reverse()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'sym:XETR:A.DE','equity','Hausse nette','Germany'),(2,'sym:XETR:B.DE','equity','Plate','Germany'),(3,'sym:XETR:C.DE','etf','Fonds sain',NULL)")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','A.DE','EUR','selected',1),(2,2,'XETR','B.DE','EUR','selected',1),(3,3,'XETR','C.DE','EUR','selected',1)")
        for lid, growth in ((1, 1.004), (2, 1.0), (3, 1.002)):
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                            [(lid, day, round(100 * growth ** i * (1 + (0.0005 if i % 2 else -0.0005) * (lid != 2)), 6)) for i, day in enumerate(days)])
    conn.commit()
    compute.compute_all(conn, NOW)


def test_backfill_then_outcomes_then_summary():
    conn = connect()
    seed(conn)
    assert tracking.backfill(conn, sessions=8) > 0
    assert tracking.update_outcomes(conn) > 0
    s = tracking.summary(conn)
    assert s['days'] == 8 and s['rebuilt_days'] == 8 and s['resolved_days']['1'] >= 5
    stat = s['presets']['*']['groups']['equity']['1']
    assert stat['n'] > 0 and stat['edge'] is not None
    # un instantané vécu n'est pas écrasé par une reconstitution rejouée
    day, rows = tracking.record_snapshot(conn)
    assert day == '2026-10-27' and rows > 0
    tracking.backfill(conn, sessions=8)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM ranking_snapshots WHERE origin='live' AND snap_date='2026-10-27'")
        assert cur.fetchone()['n'] == rows
    # exclu jamais classé : une cotation exclue ne figure dans aucun instantané
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='excluded', excluded_reason='test' WHERE id=1")
    conn.commit()
    tracking.record_snapshot(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM ranking_snapshots WHERE listing_id=1 AND origin='live' AND snap_date='2026-10-27'")
        assert cur.fetchone()['n'] == 0


def test_explorer_cache_is_identical_and_invalidated():
    conn = connect()
    seed(conn)
    request = {'config': 'regular', 'view': {'status': 'all', 'page_size': 10}}
    first = service.explore(conn, request)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM result_cache')
        assert cur.fetchone()['n'] == 1
    assert service.explore(conn, request) == first                      # lecture du cache
    with conn.cursor() as cur:
        cur.execute('DELETE FROM result_cache')
    conn.commit()
    assert service.explore(conn, request) == first                      # recalcul complet : même résultat
    version = service.data_version(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,status,started_at,finished_at) VALUES ('nightly','completed',%s,%s)", (datetime.datetime.utcnow(),) * 2)
    conn.commit()
    assert service.data_version(conn) != version                        # un traitement terminé invalide le cache
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='excluded', excluded_reason='test' WHERE id=1")
    conn.commit()
    after = service.explore(conn, request)
    assert 1 not in [r['id'] for r in after['rows']]                    # exclu : jamais proposé, cache ou pas


def test_explorer_filters_sorts_and_reasons():
    conn = connect()
    seed(conn)
    base = {'config': 'regular'}
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,%s,%s,'daily','EUR')", [(1, 300, NOW), (2, 100, NOW), (3, 150, NOW)])
    conn.commit()

    def run(**view):
        return service.explore(conn, dict(base, view=dict({'status': 'all', 'page_size': 50}, **view)))
    everyone = run()
    assert everyone['total'] == 3 and everyone['ref_sessions'] == 63
    assert {r['symbol'] for r in run(kind='etf')['rows']} == {'C.DE'}
    assert {r['symbol'] for r in run(budget=1)['rows']} == set()                    # budget inférieur à tout prix : rien
    assert {r['symbol'] for r in run(budget=150)['rows']} == {'B.DE', 'C.DE'}          # budget : prix d'une part inférieur ou égal
    by_slope = [r['symbol'] for r in run(sort='slope', dir='desc')['rows']]
    assert by_slope[0] == 'A.DE' and by_slope[-1] == 'B.DE'                          # tri par colonne : la plus forte pente d'abord
    assert run(sort='slope', dir='asc')['rows'][0]['symbol'] == 'B.DE'
    assert [r['symbol'] for r in run(min_score=1)['rows']] and all(r['score'] >= 1 for r in run(min_score=1)['rows'])
    assert [r['symbol'] for r in run(max_volatility=0.0001)['rows']] == ['B.DE']      # seul le titre plat a une volatilité nulle
    assert run(fresh_only=True)['total'] == 3
    r = run()
    assert r['reasons'] and all(k.count('|') == 2 for k in r['reasons'])            # statistiques d'exclusion : 'période|critère|f'
    assert sum(r['scope_counts'].values()) == 3 and 'Germany' in r['facets']['countries']
    assert len(run(export=True)['rows']) == 3


def _custom(**kw):
    c = strategy.preset('regular')
    for p in c['periods']:
        p['enabled'] = False
        for f, _, _ in strategy.CRITERIA:
            p[f] = None
    for pid, vals in kw.items():
        p = next(x for x in c['periods'] if x['id'] == pid)
        p.update(enabled=True, **vals)
    c['name'] = 'custom'
    c['ranking']['mode'] = 'trend'
    return c


def test_custom_criteria_drive_results_not_presets():
    conn = connect()
    seed(conn)
    view = {'status': 'all', 'page_size': 50}
    free = service.explore(conn, {'config': _custom(month={}), 'view': view})                   # aucun seuil : tout titre mesurable est retenu
    assert free['scope_counts']['retained'] == 3
    strict = service.explore(conn, {'config': _custom(month={'min_slope': 0.3}), 'view': view})
    assert {r['symbol'] for r in strict['rows'] if r['status'] == 'retained'} == {'A.DE'}      # seule la forte pente passe
    other = service.explore(conn, {'config': _custom(week={'min_slope': 0.0}), 'view': view})   # autre période : autre résultat
    assert other['config']['periods'][1]['enabled'] and not other['config']['periods'][2]['enabled']
    assert free != strict


def test_rank_is_recomputed_inside_the_filtered_selection_and_pagination_comes_after():
    conn = connect()
    seed(conn)
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,%s,%s,'daily','EUR')", [(1, 300, NOW), (2, 100, NOW), (3, 150, NOW)])
    conn.commit()
    cfg = _custom(month={})
    full = {r['symbol']: r for r in service.explore(conn, {'config': cfg, 'view': {'status': 'retained', 'kind': 'equity'}})['rows']}
    assert full['A.DE']['rank'] == 1 and full['B.DE']['rank'] == 2
    only_b = service.explore(conn, {'config': cfg, 'view': {'status': 'retained', 'kind': 'equity', 'budget': 120}})
    assert [(r['symbol'], r['rank']) for r in only_b['rows']] == [('B.DE', 1)]               # reclassé dans la sélection : rang 1, pas 2
    assert only_b['examined'] == 1 and only_b['universe'] == 3
    p1 = service.explore(conn, {'config': cfg, 'view': {'status': 'all', 'page_size': 2, 'page': 1}})
    p2 = service.explore(conn, {'config': cfg, 'view': {'status': 'all', 'page_size': 2, 'page': 2}})
    ids = [r['id'] for r in p1['rows'] + p2['rows']]
    assert p1['total'] == 3 and len(ids) == 3 and len(set(ids)) == 3 and p1['pages'] == 2     # aucune ligne perdue ni doublée entre les pages


def test_sheet_verdict_matches_explorer_for_the_same_configuration():
    conn = connect()
    seed(conn)
    cfg = _custom(week={'min_slope': 0.0}, month={'min_slope': 0.1})
    rows = {r['id']: r for r in service.explore(conn, {'config': cfg, 'view': {'status': 'all', 'page_size': 50}})['rows']}
    for lid, row in rows.items():
        sheet = service.instrument_sheet(conn, {'config': cfg, 'listing_id': lid, 'source': 'test'})
        assert sheet['verdict']['status'] == row['status'] and sheet['verdict']['rank'] == row['rank'] and sheet['verdict']['score'] == row['score']
        assert [p['id'] for p in sheet['strategy']['periods']] == ['week', 'month'] and sheet['strategy']['source'] == 'test'
    default = service.instrument_sheet(conn, {'config': 'regular', 'listing_id': 1})
    assert [p['id'] for p in default['strategy']['periods']] == ['month', 'quarter']          # la fiche annonce la configuration qu'elle a utilisée


def test_excluded_listing_never_becomes_a_recommendation():
    conn = connect()
    seed(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE listings SET status='excluded', excluded_reason='liquidité insuffisante' WHERE id=1")
    conn.commit()
    for cfg in (_custom(month={}), 'regular'):
        res = service.explore(conn, {'config': cfg, 'view': {'status': 'retained', 'page_size': 50}})
        assert 'A.DE' not in {r['symbol'] for r in res['rows']}
        assert res['universe'] == 2
    sheet = service.instrument_sheet(conn, {'config': _custom(month={}), 'listing_id': 1})
    assert sheet['verdict']['status'] == 'excluded'
