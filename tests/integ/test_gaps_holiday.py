"""Jours fériés et trous de barres 15 min : une absence de données n'est pas un jour sans séance ; un titre peu échangé n'a pas de trou."""
import datetime
import os
import pytest
from engine.shared.db import connect
from engine.market import collect, hours, intraday
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)             # mardi 27 : Xetra fermée depuis 16:30 UTC
D = lambda d: datetime.date(2026, 10, d)
N = 20


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.executemany("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (%s,%s,%s,'equity',%s,'Germany')", [(i, f'isin:T{i}', f'T{i:010d}', f'T{i}') for i in range(1, N + 1)])
        cur.executemany("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", [(i, i, f'T{i}.DE') for i in range(1, N + 1)])
    c.commit()
    yield c
    c.close()


def bars(conn, day, keep=lambda i, j: True):
    rows = [(i, t, 10.0, 1) for i in range(1, N + 1) for j, t in enumerate(intraday.expected_slot_starts('XETR', day)) if keep(i, j)]
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (%s,%s,%s,%s)', rows)
    conn.commit()


def closes(conn, day):
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,10)', [(i, day) for i in range(1, N + 1)])
    conn.commit()


def daily_job_after(conn, when):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at,finished_at) VALUES ('daily:XETR','cron','completed',%s,%s)", (when, when))
    conn.commit()


def plan(conn):
    return collect.intraday_plan(conn, collect.collection_set(conn, 'XETR'), NOW)


def test_missing_bars_with_closes_is_not_a_holiday(conn):
    closes(conn, D(26)); bars(conn, D(27)); closes(conn, D(27))
    daily_job_after(conn, datetime.datetime(2026, 10, 27, 17, 30))
    p, summary = plan(conn)
    assert len(p.get('5d', [])) == N and summary['holiday'] == 0       # la séance du 26 sera redemandée


def test_real_holiday_is_still_recognised(conn):
    bars(conn, D(27)); closes(conn, D(27))                             # le 26 : ni barre ni clôture, une collecte quotidienne est passée
    daily_job_after(conn, datetime.datetime(2026, 10, 27, 17, 30))
    p, summary = plan(conn)
    assert summary['holiday'] == 1 and not p.get('5d')


def test_no_conclusion_before_the_daily_close_was_searched(conn):
    bars(conn, D(27))                                                  # ni clôture du 26 ni collecte quotidienne passée : on ne dit pas « férié »
    p, summary = plan(conn)
    assert summary['holiday'] == 0 and len(p.get('5d', [])) == N


def test_thin_titles_are_not_gaps_but_an_outage_and_an_empty_session_are(conn):
    thin = lambda i, j: (i + j) % 3 != 0                               # 2 créneaux sur 3 : titres peu échangés, aucun trou réel
    bars(conn, D(24), thin)
    bars(conn, D(26), lambda i, j: thin(i, j) and not 10 <= j <= 15)  # panne : 6 créneaux sans aucune donnée
    closes(conn, D(23))                                                # le 23 : clôtures présentes mais aucune barre
    gaps = collect.session_gaps(conn, 'XETR', NOW)
    assert D(24) not in gaps and D(22) not in gaps
    assert D(26) in gaps and '6 créneaux' in gaps[D(26)]
    assert D(23) in gaps and 'clôtures' in gaps[D(23)]
    assert collect.detect_gaps(conn, 'XETR', NOW) == 2


def test_repair_closes_gaps_that_the_new_rule_no_longer_sees(conn):
    thin = lambda i, j: (i + j) % 3 != 0
    bars(conn, D(24), thin); bars(conn, D(26), thin)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO price_gaps(mic,session_date,state,detected_at,note) VALUES ('XETR',%s,'to_repair',%s,'ancienne médiane 20/34 créneaux')", (D(26), NOW.replace(tzinfo=None)))
    conn.commit()

    class NoCall:
        def spark(self, *a, **k):
            raise AssertionError('aucune redemande à Yahoo pour une fausse alerte')
    assert collect.repair_gaps(conn, NoCall(), NOW) == 0
    with conn.cursor() as cur:
        cur.execute("SELECT state FROM price_gaps WHERE session_date=%s", (D(26),))
        assert cur.fetchone()['state'] == 'repaired'


def test_daily_close_is_fetched_after_its_publication_not_before(conn):
    """Une collecte quotidienne de l'après-midi (qui récupérait la veille) ne dispense pas de chercher la clôture de New York le soir même."""
    from engine.jobs import tasks
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at,finished_at) VALUES ('daily:XNYS','cron','completed','2026-10-28 17:05:00','2026-10-28 17:05:30')")
    conn.commit()
    assert not tasks._daily_done(conn, 'XNYS', D(28))                  # fermeture 20:00 UTC + règlement : la collecte de 17:05 ne compte pas
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at,finished_at) VALUES ('daily:XNYS','cron','completed','2026-10-28 20:35:00','2026-10-28 20:35:30')")
    conn.commit()
    assert tasks._daily_done(conn, 'XNYS', D(28))
