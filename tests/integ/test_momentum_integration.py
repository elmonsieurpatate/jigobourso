"""Momentum 6 mois et 12 mois sur une vraie base : colonne et migration, calcul nocturne, classement de l'Explorer avec le filtre de négociabilité, fiche, suivi à 21 et 63 séances."""
import datetime
import math
import os
import pytest
from engine.shared.db import connect
from engine.analytics import compute, service, strategy, tracking
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def fixed_market_clock(monkeypatch):
    monkeypatch.setattr(service.hours, 'utcnow', lambda: NOW)


def sessions(n):
    import exchange_calendars as xc
    cal = xc.get_calendar('XETR', start='2025-01-02', end='2026-12-31')
    return [d.date() for d in cal.sessions if d.date() <= datetime.date(2026, 10, 27)][-n:]


def path(n, daily, last_month=None):
    """Cours en croissance régulière ; `last_month` : facteur appliqué progressivement sur les 21 dernières séances (effondrement ou flambée)."""
    out = [100 * math.exp(daily * i) for i in range(n)]
    if last_month:
        base = out[n - 22]
        for k in range(21):
            out[n - 21 + k] = base * last_month ** ((k + 1) / 21)
    return out


UNIVERSE = (   # id, symbole, type, nombre de séances, cours, volume moyen
    (1, 'STAR.DE', 'equity', 360, path(360, 0.0040), 500_000),
    (2, 'CRASH.DE', 'equity', 360, path(360, 0.0030, 0.6), 500_000),         # monte fort puis s'effondre le dernier mois : le dernier mois est ignoré
    (3, 'SURGE.DE', 'equity', 360, path(360, 0.0000, 1.8), 500_000),          # plat puis flambée le dernier mois : ne compte pas
    (4, 'LAG.DE', 'equity', 360, path(360, -0.0010), 500_000),
    (5, 'ILLIQ.DE', 'equity', 360, path(360, 0.0050), 50),                    # très fort momentum mais quasi aucun échange : masqué par le filtre de négociabilité
    (6, 'YOUNG.DE', 'equity', 100, path(100, 0.0100), 500_000),               # historique trop court : « non évaluable »
    (7, 'ETFA.DE', 'etf', 360, path(360, 0.0010), 500_000),
)


def seed(conn, only=None):
    reset_data(conn)
    with conn.cursor() as cur:
        for lid, symbol, kind, n, closes, volume in UNIVERSE:
            if only is not None and lid not in only:
                continue
            cur.execute('INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,%s,%s,%s)', (lid, f'sym:XETR:{symbol}', kind, symbol.split('.')[0].title(), 'Germany'))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, symbol))
            days = sessions(360)[-n:]
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, d, round(c, 6)) for d, c in zip(days, closes)])
            cur.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,quote_at) VALUES (%s,%s,%s,'quote','EUR',%s,%s)",
                        (lid, round(closes[-1], 6), datetime.datetime(2026, 10, 27, 16, 30), volume, datetime.datetime(2026, 10, 27, 20, 0)))
    conn.commit()
    compute.compute_all(conn, NOW)


def expected_momentum(closes):
    return 100 * (closes[-1 - 21] / closes[-1 - 126] - 1)


def expected_momentum12(closes):
    return 100 * (closes[-1 - 21] / closes[-1 - 252] - 1)


def test_nightly_compute_stores_the_momentum_and_leaves_short_histories_unknown():
    conn = connect()
    seed(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, momentum_6m, momentum_12m FROM series_state')
        rows = cur.fetchall()
    stored = {r['listing_id']: r['momentum_6m'] for r in rows}
    stored12 = {r['listing_id']: r['momentum_12m'] for r in rows}
    for lid, symbol, kind, n, closes, volume in UNIVERSE:
        if n >= 253:
            assert abs(float(stored[lid]) - expected_momentum(closes)) < 1e-4, symbol
            assert abs(float(stored12[lid]) - expected_momentum12(closes)) < 1e-4, symbol
    assert stored[6] is None and stored12[6] is None               # 100 séances : ni 127 ni 253, jamais estimé
    assert abs(float(stored12[3])) < 1e-4 and float(stored12[2]) > float(stored12[4])
    assert abs(float(stored[3])) < 1e-4 and float(stored[2]) > float(stored[4])    # le dernier mois n'entre pas dans la mesure


def test_migrations_add_both_columns_without_touching_data():
    conn = connect()
    seed(conn)
    from scripts import migrate
    for column, name in (('momentum_6m', '20261031_momentum_6m.sql'), ('momentum_12m', '20261101_momentum_12m.sql')):
        sql = open(os.path.join(ROOT, 'db', 'migrations', name), encoding='utf-8').read()
        migrate.check(sql, name)                                   # admissible : ajout seulement
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) n FROM series_state')
            before = cur.fetchone()['n']
            cur.execute(f'ALTER TABLE series_state DROP COLUMN {column}')
            for statement in migrate.statements(sql):
                cur.execute(statement)
            cur.execute('SELECT COUNT(*) n FROM series_state')
            assert cur.fetchone()['n'] == before                   # les lignes existantes sont conservées
            cur.execute(f'SELECT {column} FROM series_state LIMIT 1')
            assert cur.fetchone()[column] is None                  # NULL jusqu'au prochain calcul : l'inconnu reste inconnu
        conn.commit()
    compute.compute_all(conn, NOW)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM series_state WHERE momentum_6m IS NOT NULL')
        assert cur.fetchone()['n'] >= 5
        cur.execute('SELECT COUNT(*) n FROM series_state WHERE momentum_12m IS NOT NULL')
        assert cur.fetchone()['n'] >= 5


def test_explorer_ranks_by_momentum_and_keeps_the_tradability_filter():
    conn = connect()
    seed(conn)
    res = service.explore(conn, {'config': 'momentum', 'view': {'status': 'retained', 'kind': 'equity', 'page_size': 50}})
    symbols = [r['symbol'] for r in res['rows']]
    assert 'ILLIQ.DE' not in symbols and res['tradable']['on'] and res['tradable']['masked'] >= 1       # filtre de négociabilité conservé
    assert symbols == ['STAR.DE', 'CRASH.DE', 'SURGE.DE', 'LAG.DE']                                       # classés par progression entre J−126 et J−21
    assert [r['rank'] for r in res['rows']] == [2, 3, 4, 5]                                               # rang d'origine du catalogue conservé : le titre masqué (ILLIQ.DE) reste n° 1, rien n'est recalculé
    assert abs(res['rows'][0]['momentum'] - expected_momentum(UNIVERSE[0][4])) < 1e-4
    assert 'YOUNG.DE' not in symbols                                                                       # historique trop court : pas « retenu »
    unfiltered = service.explore(conn, {'config': 'momentum', 'view': {'status': 'retained', 'kind': 'equity', 'tradable': False, 'page_size': 50}})
    assert [r['symbol'] for r in unfiltered['rows']][0] == 'ILLIQ.DE'                                      # sans filtre, le plus fort momentum passe devant
    unknown = service.explore(conn, {'config': 'momentum', 'view': {'status': 'unknown', 'kind': 'equity', 'page_size': 50}})
    assert 'YOUNG.DE' in [r['symbol'] for r in unknown['rows']]
    for name in ('regular', 'fast', 'recovery', 'low_volatility'):                                         # les quatre autres profils fonctionnent toujours
        assert service.explore(conn, {'config': name, 'view': {'page_size': 5}})['config']['name'] == name


def test_fiche_exposes_the_momentum_and_the_experimental_flag():
    conn = connect()
    seed(conn)
    sheet = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'momentum'})
    assert abs(sheet['state']['momentum_6m'] - expected_momentum(UNIVERSE[0][4])) < 1e-4
    assert sheet['strategy']['experimental'] is True and sheet['verdict']['status'] == 'retained'
    assert sheet['verdict']['rank'] == 2 and sheet['verdict']['of'] == 5                                    # n° 2 du catalogue sur 5 actions retenues (le n° 1, très peu négociable, est masqué dans l'Explorer)
    assert service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular'})['strategy']['experimental'] is False


def test_tracking_records_both_strategies_at_21_and_63_sessions():
    conn = connect()
    seed(conn, only={1, 4})                                        # deux actions suffisent : le rejeu du suivi est le test le plus long
    day, rows = tracking.record_snapshot(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT preset, COUNT(*) n FROM ranking_snapshots WHERE snap_date=%s GROUP BY preset", (day,))
        by_preset = {r['preset']: r['n'] for r in cur.fetchall()}
    assert by_preset.get('momentum', 0) >= 1 and by_preset.get('momentum12', 0) >= 1
    assert tracking.backfill(conn, sessions=70) > 0
    assert tracking.update_outcomes(conn) > 0
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT horizon FROM ranking_outcomes WHERE preset='momentum' ORDER BY horizon")
        horizons = [r['horizon'] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT horizon FROM ranking_outcomes WHERE preset='momentum12' ORDER BY horizon")
        horizons12 = [r['horizon'] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT horizon FROM universe_outcomes ORDER BY horizon")
        universe_horizons = [r['horizon'] for r in cur.fetchall()]
    assert 21 in horizons and 63 in horizons and {21, 63} <= set(universe_horizons) and 21 in horizons12 and 63 in horizons12
    summary = tracking.summary(conn)
    assert summary['horizons'] == [1, 3, 5, 21, 63] and 'momentum' in summary['presets']
    stat = summary['presets']['momentum']['groups']['equity']['21']
    assert stat is not None and stat['n'] > 0 and stat['days'] > 0
    assert 'momentum12' in summary['presets'] and summary['presets']['momentum12']['groups']['equity']['63']['n'] > 0


def test_explorer_ranks_by_momentum_12_and_keeps_the_tradability_filter():
    conn = connect()
    seed(conn)
    res = service.explore(conn, {'config': 'momentum12', 'view': {'status': 'retained', 'kind': 'equity', 'page_size': 50}})
    symbols = [r['symbol'] for r in res['rows']]
    assert res['config']['name'] == 'momentum12' and 'ILLIQ.DE' not in symbols and res['tradable']['on'] and res['tradable']['masked'] >= 1
    assert symbols == ['STAR.DE', 'CRASH.DE', 'SURGE.DE', 'LAG.DE'] and [r['rank'] for r in res['rows']] == [2, 3, 4, 5]
    assert abs(res['rows'][0]['momentum'] - expected_momentum12(UNIVERSE[0][4])) < 1e-4                    # la valeur affichée est celle de J−252 → J−21
    assert 'YOUNG.DE' not in symbols
    unknown = service.explore(conn, {'config': 'momentum12', 'view': {'status': 'unknown', 'kind': 'equity', 'page_size': 50}})
    assert 'YOUNG.DE' in [r['symbol'] for r in unknown['rows']]
    six = service.explore(conn, {'config': 'momentum', 'view': {'status': 'retained', 'kind': 'equity', 'page_size': 50}})
    assert abs(six['rows'][0]['momentum'] - res['rows'][0]['momentum']) > 1e-3                              # deux stratégies distinctes, deux mesures


def test_fiche_exposes_both_momentums_and_the_flag():
    conn = connect()
    seed(conn)
    sheet = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'momentum12'})
    assert abs(sheet['state']['momentum_12m'] - expected_momentum12(UNIVERSE[0][4])) < 1e-4 and abs(sheet['state']['momentum_6m'] - expected_momentum(UNIVERSE[0][4])) < 1e-4
    assert sheet['strategy']['experimental'] is True and sheet['strategy']['ranking'] == 'momentum12' and sheet['verdict']['status'] == 'retained'
    assert sheet['verdict']['rank'] == 2 and sheet['verdict']['of'] == 5


def test_explorer_capitalisation_filter_uses_the_size_classes():
    conn = connect()
    seed(conn)
    with conn.cursor() as cur:
        for lid, cap in ((1, 5_000_000_000), (2, 500_000_000), (3, 100_000_000), (7, 40_000_000_000)):
            cur.execute('UPDATE latest_prices SET market_cap=%s WHERE listing_id=%s', (cap, lid))
    conn.commit()

    def symbols(cap):
        res = service.explore(conn, {'config': 'momentum', 'view': {'status': 'all', 'tradable': False, 'cap': cap, 'page_size': 50}})
        return sorted(r['symbol'] for r in res['rows'])
    assert symbols('mid') == ['STAR.DE']                                                    # 2 à 10 Md€
    assert symbols('micro|small') == ['CRASH.DE', 'SURGE.DE']                               # plusieurs choix possibles
    assert symbols('large') == []                                                           # un ETF (ici 40 Md€) n'a pas de classe de taille d'actions : jamais classé « grande capitalisation »
    assert 'LAG.DE' not in symbols('mid|small|micro|large|mega')                            # capitalisation inconnue : exclue dès qu'un filtre de taille est posé
    assert len(symbols('')) >= 6                                                            # sans filtre : tout l'univers
    assert symbols('inconnue') == symbols('')                                               # une valeur inconnue est ignorée, jamais une exclusion silencieuse
