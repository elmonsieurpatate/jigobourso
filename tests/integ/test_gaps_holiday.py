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
    assert set(gaps) == {D(23), D(26)}                                 # toute la rétention est surveillée (20 séances), pas seulement les deux dernières


def test_stale_gap_rows_follow_the_data_without_asking_yahoo(conn):
    from engine.market import catchup
    thin = lambda i, j: (i + j) % 3 != 0
    bars(conn, D(23), thin); bars(conn, D(26), thin)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO price_gaps(mic,session_date,state,detected_at,note) VALUES ('XETR',%s,'to_repair',%s,'ancienne médiane 20/34 créneaux'),('XETR',%s,'unrecoverable',%s,'conclu à tort')",
                    (D(26), NOW.replace(tzinfo=None), D(23), NOW.replace(tzinfo=None)))
    conn.commit()
    assert catchup.plan_intraday(conn, NOW) == []                      # aucune redemande à Yahoo pour une fausse alerte
    with conn.cursor() as cur:
        cur.execute("SELECT session_date, state FROM price_gaps")
        assert {r['session_date']: r['state'] for r in cur.fetchall()} == {D(26): 'repaired', D(23): 'repaired'}      # « non récupérable » aussi est revérifié


def test_partial_collection_is_a_gap_even_when_every_slot_is_still_covered(conn):
    """Une collecte interrompue qui a rempli la moitié des titres sur tous les créneaux est détectée par le nombre de titres couverts."""
    for d in (22, 23, 24, 26):
        bars(conn, D(d))
    bars(conn, D(27), lambda i, j: i <= N // 2)
    gaps = collect.session_gaps(conn, 'XETR', NOW)
    assert set(gaps) == {D(27)} and 'titres' in gaps[D(27)]


def test_yahoo_range_matches_its_real_depth_and_retention():
    assert [collect.intraday_range(n) for n in (1, 5, 6, 22, 23, 60, 64, 65)] == ['5d', '5d', '1mo', '1mo', '60d', '60d', '60d', None]
