"""Parcours complet voulu : Import FinanceDatabase → Filtrage → Import Yahoo → Filtrage Yahoo → catalogue final → historiques → cron (entretien seulement)."""
import csv
import datetime
import os
import pytest
from engine.shared.db import connect
from engine.shared import settings
from engine.analytics import adminsvc
from engine.catalogue import rules
from engine.jobs import tasks, schedule
from engine.jobs.runner import run_job
from engine.market import collect, hours
from engine.market import intraday as intra
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)          # mardi, Xetra fermée et clôture publiée
FIELDS = ('symbol', 'name', 'mic', 'isin', 'currency', 'delisted', 'sector', 'country')
EQUITIES = [('LIQ.DE', 'Liquide SE', 'XETR', 'DE0000000001', 'EUR', 'False', 'Tech', 'Germany'),
            ('PEN.DE', 'Penny SE', 'XETR', 'DE0000000002', 'EUR', 'False', 'Tech', 'Germany'),
            ('FAR.T', 'Loin KK', 'XTKS', 'JP0000000004', 'JPY', 'False', 'Tech', 'Japan'),
            ('UNK.Q', 'Inconnue SA', 'XQQQ', 'ZZ0000000005', 'EUR', 'False', 'Tech', 'Nowhere')]


def q(price, volume, cur='EUR'):
    return {'price': price, 'price_time': datetime.datetime(2026, 10, 27, 16, 30), 'avg_volume_3m': volume, 'currency': cur, 'market_cap': None, 'quote_type': 'EQUITY'}


def sessions_bars(mic, symbol_days):
    out = []
    for day in symbol_days:
        out += [(t, 100.0 + i * 0.01) for i, t in enumerate(intra.expected_slot_starts(mic, day))]
    return out


@pytest.fixture
def env(tmp_path, monkeypatch):
    c = connect()
    reset_data(c)
    (tmp_path / 'database' / 'equities').mkdir(parents=True)
    (tmp_path / 'database' / 'etfs').mkdir(parents=True)
    with (tmp_path / 'database' / 'equities' / 'a.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        w.writerows(EQUITIES)
    with (tmp_path / 'database' / 'etfs' / 'a.csv').open('w', newline='') as fh:
        csv.writer(fh).writerows([('symbol', 'name', 'mic', 'isin', 'currency', 'delisted', 'category_group'), ('ETF.DE', 'Bon ETF', 'XETR', 'IE0000000006', 'EUR', 'False', 'Equity')])
    monkeypatch.setenv('JIGO_FDB_SOURCE', str(tmp_path))
    days = [datetime.date(2024, 1, 1) + datetime.timedelta(days=i) for i in range(1200)]
    days = [d for d in days if d.weekday() < 5 and d <= datetime.date(2026, 10, 27)][-420:]
    last2 = days[-2:]
    client = FakeYahoo(quotes={'LIQ.DE': q(100.0, 50000), 'PEN.DE': q(0.5, 9_000_000), 'ETF.DE': q(50.0, 10000), 'FAR.T': q(3000.0, 400000, 'JPY'), 'UNK.Q': q(20.0, 100000)},
                       daily={s: ('Europe/Berlin', [(d, 100.0 + i * 0.1) for i, d in enumerate(days)]) for s in ('LIQ.DE', 'ETF.DE', 'PEN.DE')},
                       intraday={s: ('Europe/Berlin', sessions_bars('XETR', last2)) for s in ('LIQ.DE', 'ETF.DE')})
    yield c, client
    c.close()


def go(conn, client, name, now=NOW):
    tasks.precheck(conn, name)
    job = tasks.run_manual(conn, client, name, now)
    with conn.cursor() as cur:
        cur.execute('SELECT status, summary FROM jobs WHERE id=%s', (job,))
        row = cur.fetchone()
    assert row['status'] in ('completed', 'completed_with_errors'), row
    return job


def statuses(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT symbol, status, is_primary FROM listings ORDER BY symbol')
        return {r['symbol']: (r['status'], r['is_primary']) for r in cur.fetchall()}


def test_steps_refuse_to_run_out_of_order(env):
    conn, client = env
    for name in ('fdb_filter', 'yahoo_filter', 'history'):
        with pytest.raises(ValueError):
            tasks.precheck(conn, name)


def test_full_parcours_then_cron_only_maintains(env):
    conn, client = env
    go(conn, client, 'fdb_import')
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        assert cur.fetchone()['n'] == 5 and tasks.history_coverage(conn)['complete'] == 0
    assert statuses(conn) == {}                                         # l'import ne filtre rien et ne crée aucune cotation
    go(conn, client, 'fdb_filter')
    st = statuses(conn)
    assert st['LIQ.DE'][0] == 'candidate' and 'FAR.T' not in st and 'UNK.Q' not in st      # places par défaut seulement
    go(conn, client, 'yahoo_info')
    info = settings.get(conn, 'last_stats')['yahoo_info']
    assert info['requested'] == 3 and info['recovered'] == 3 and info['missing'] == 0
    go(conn, client, 'yahoo_filter')
    st = statuses(conn)
    assert st['LIQ.DE'][0] == 'selected' and st['ETF.DE'][0] == 'selected' and st['PEN.DE'][0] == 'excluded'
    assert len(collect.collection_set(conn)) == 2                         # catalogue final : LIQ.DE + ETF.DE
    # historiques
    go(conn, client, 'history')
    h = settings.get(conn, 'last_stats')['history']
    assert h['daily']['added'] > 0 and h['intraday']['added'] == 2 * 2 * hours.expected_slots('XETR')
    assert h['coverage']['complete'] == 2 and h['coverage']['absent'] == 0
    # deuxième passage : rien n'est retéléchargé, aucun doublon
    calls = len(client.calls)
    go(conn, client, 'history', NOW + datetime.timedelta(minutes=5))
    assert [c for c in client.calls[calls:] if c[0] == 'spark'] == []
    h2 = settings.get(conn, 'last_stats')['history']
    assert h2['daily']['added'] == 0 and h2['intraday']['added'] == 0 and h2['daily']['up_to_date'] == 2
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM daily_prices WHERE listing_id IN (SELECT id FROM listings WHERE symbol=%s)', ('LIQ.DE',))
        assert cur.fetchone()['n'] >= 400
    # cron : entretien seulement, jamais de catalogue ni de filtre
    before = statuses(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        raw = cur.fetchone()['n']
    later = NOW + datetime.timedelta(days=1, hours=1)                      # mercredi : clôture de la veille déjà collectée → maintenance + rien d'autre
    done = tasks.tick(conn, client, later, 'cron')
    assert {k for k, _, _ in done} <= {'daily', 'intraday', 'maintenance'}
    assert statuses(conn) == before
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT job_type FROM jobs WHERE trigger_by=%s', ('cron',))
        assert all(r['job_type'].split(':')[0] in ('daily', 'intraday', 'maintenance') for r in cur.fetchall())
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        assert cur.fetchone()['n'] == raw
    assert schedule.state(conn, later.replace(tzinfo=None))['cron']['observed'] is True


def test_free_places_flow_through_the_whole_pipeline(env):
    conn, client = env
    go(conn, client, 'fdb_import')
    cfg = settings.catalogue_rules(conn)
    cfg['markets']['values'] = sorted(set(cfg['markets']['values']) | {'XTKS', 'XQQQ'})      # places absentes du code, ajoutées sans le modifier
    adminsvc.rules_save(conn, 'catalogue', cfg)
    go(conn, client, 'fdb_filter')
    st = statuses(conn)
    assert st['FAR.T'][0] == 'candidate' and st['UNK.Q'][0] == 'candidate'
    go(conn, client, 'yahoo_info')
    go(conn, client, 'yahoo_filter')
    assert statuses(conn)['UNK.Q'][0] == 'selected'
    titles = adminsvc.titles(conn, {'q': 'Inconnue'})
    row = titles['rows'][0]
    assert row['in_final'] and row['fdb_state'] == 'kept' and row['y_state'] == 'kept' and row['d_state'] == 'absent' and row['intraday_state'] == 'na'
    out = adminsvc.titles(conn, {'fdb': 'removed'})
    assert all(r['reason']['stage'] == 'FinanceDatabase' for r in out['rows'])
    # la place sans horaires connus : clôtures seulement, aucune erreur
    client.daily['UNK.Q'] = ('UTC', [(datetime.date(2026, 10, 26), 20.0)])
    go(conn, client, 'history')
    assert settings.get(conn, 'last_stats')['history']['intraday']['unknown_hours'] >= 1


def test_titles_page_explains_every_exclusion(env):
    conn, client = env
    go(conn, client, 'fdb_import')
    go(conn, client, 'fdb_filter')
    go(conn, client, 'yahoo_info')
    go(conn, client, 'yahoo_filter')
    rows = {r['symbol']: r for r in adminsvc.titles(conn, {})['rows']}
    assert rows['FAR.T']['reason']['stage'] == 'FinanceDatabase' and rows['FAR.T']['in_final'] is False
    assert rows['PEN.DE']['reason']['stage'] == 'Yahoo Finance' and 'cours' in rows['PEN.DE']['reason']['detail']
    assert rows['LIQ.DE']['reason'] is None and rows['LIQ.DE']['in_final'] is True
