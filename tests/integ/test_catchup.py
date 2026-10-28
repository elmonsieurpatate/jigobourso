"""Rattrapage autonome : après une panne de Yahoo ou un cron arrêté, tout ce qui manque est redemandé sans intervention, sans marteler Yahoo,
et ce qui ne peut pas être récupéré est signalé au lieu d'être présenté comme à jour."""
import datetime
import os
import pytest
from engine.jobs import tasks
from engine.market import catchup, collect, hours, intraday
from engine.market.yahoo import RateLimited
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
N = 20
SYMS = [f'T{i}.DE' for i in range(1, N + 1)]


def at(day, hh, mm=0):
    return datetime.datetime(2026, 10, day, hh, mm, tzinfo=UTC)


class Yahoo(FakeYahoo):
    """Faux Yahoo avec pannes : down=True lève une erreur réseau, limited=True un 429."""
    down = False
    limited = False

    def spark(self, symbols, range_, interval):
        if self.limited:
            raise RateLimited(60)
        if self.down:
            raise OSError('Yahoo indisponible')
        return super().spark(symbols, range_, interval)


class Ranged(Yahoo):
    """Comme le vrai Yahoo : la plage '1d' ne renvoie que la séance du jour (28), seule la plage '5d' remonte aux séances précédentes."""

    def spark(self, symbols, range_, interval):
        out = super().spark(symbols, range_, interval)
        if range_ == '1d' and interval == '15m':
            day = int(datetime.datetime(2026, 10, 28, tzinfo=UTC).timestamp())
            out = {k: dict(v, bars=[b for b in v['bars'] if b[0] >= day]) for k, v in out.items()}
        return out


def full_day(day):
    return [(t, 10.0 + (t.minute % 7)) for t in intraday.expected_slot_starts('XETR', datetime.date(2026, 10, day))]


def yahoo(days=(26, 27), **kw):
    y = Yahoo(intraday={s: ('UTC', [b for d in days for b in full_day(d)]) for s in SYMS},
              daily={s: ('UTC', [(datetime.date(2026, 10, d), 10.0) for d in (23, 26, 27, 28)]) for s in SYMS})
    for k, v in kw.items():
        setattr(y, k, v)
    return y


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


def seed(conn, day, bars=True, closes=True):
    with conn.cursor() as cur:
        if bars:
            cur.executemany('INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (%s,%s,10,1)',
                            [(i, t) for i in range(1, N + 1) for t in intraday.expected_slot_starts('XETR', datetime.date(2026, 10, day))])
        if closes:
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,10)', [(i, datetime.date(2026, 10, day)) for i in range(1, N + 1)])
    conn.commit()


def count(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchone().values())[0]


def bars_of(conn, day):
    return count(conn, 'SELECT COUNT(*) FROM intraday_prices WHERE slot_start >= %s AND slot_start < %s', datetime.datetime(2026, 10, day), datetime.datetime(2026, 10, day + 1))


def closes_of(conn, day):
    return count(conn, 'SELECT COUNT(*) FROM daily_prices WHERE price_date=%s', datetime.date(2026, 10, day))


def jobs(conn, kind):
    return count(conn, "SELECT COUNT(*) FROM jobs WHERE job_type LIKE %s", kind + '%')


def test_outage_then_restart_catches_up_by_itself_without_hammering_yahoo(conn):
    seed(conn, 26)                                                          # la veille est complète
    down = yahoo(down=True)
    for hh in (9, 12, 15, 17):                                               # mardi 27 : Yahoo est tombé toute la journée, le cron tourne
        tasks.tick(conn, down, at(27, hh, 5), 'cron')
    assert bars_of(conn, 27) == 0 and closes_of(conn, 27) == 0
    # le cron s'arrête toute la nuit puis revient mercredi 28, Yahoo toujours indisponible : rien de récupérable, mais tout est retenu et signalé
    tasks.tick(conn, down, at(28, 10, 5), 'cron')
    st = catchup.status(conn, at(28, 10, 5))
    assert st['open'] and st['daily']['waiting'] == N
    assert bars_of(conn, 27) == 0
    catch_before, daily_before = jobs(conn, 'catchup'), jobs(conn, 'daily:XETR')
    tasks.tick(conn, down, at(28, 10, 10), 'cron')                            # 5 min plus tard : le délai de nouvelle tentative n'est pas écoulé
    assert jobs(conn, 'catchup') == catch_before and jobs(conn, 'daily:XETR') == daily_before      # pas de rafale sur un Yahoo en panne
    # Yahoo revient : au premier passage suivant, tout est rattrapé (clôtures puis barres) sans aucune intervention
    back = yahoo()
    tasks.tick(conn, back, at(28, 11, 0), 'cron')
    tasks.tick(conn, back, at(28, 11, 5), 'cron')
    assert closes_of(conn, 27) == N
    assert bars_of(conn, 27) == N * 34
    st = catchup.status(conn, at(28, 11, 5))
    assert st['open'] == [] and st['daily']['waiting'] == 0 and st['unrecoverable'] == []
    assert count(conn, "SELECT COUNT(*) FROM price_gaps WHERE state='to_repair'") == 0
    assert count(conn, "SELECT COUNT(*) FROM jobs WHERE job_type='catchup' AND trigger_by='cron'") >= 1


def test_rate_limit_pauses_catchup_and_resumes(conn):
    seed(conn, 26); seed(conn, 27, bars=False)                                 # le 27 a ses clôtures mais aucune barre
    limited = yahoo(limited=True)
    tasks.tick(conn, limited, at(28, 9, 0), 'cron')
    assert catchup.status(conn, at(28, 9, 0))['cooldown_until']
    assert catchup.plan_intraday(conn, at(28, 9, 5)) == []                    # pause après un 429
    tasks.tick(conn, yahoo(), at(28, 9, 20), 'cron')                          # pause écoulée
    assert bars_of(conn, 27) == N * 34


def test_normal_collection_stays_first_and_catchup_never_touches_catalogue_or_portfolios(conn):
    seed(conn, 26); seed(conn, 27, bars=False)
    before = count(conn, "SELECT COUNT(*) FROM listings WHERE status='selected'")
    y = Ranged(intraday=yahoo().intraday, daily=yahoo().daily)
    tasks.tick(conn, y, at(28, 9, 30), 'cron')
    assert bars_of(conn, 27) == N * 34
    assert count(conn, "SELECT COUNT(*) FROM listings WHERE status='selected'") == before
    with conn.cursor() as cur:
        cur.execute("SELECT job_type FROM jobs ORDER BY id")
        order = [r['job_type'] for r in cur.fetchall()]
    assert order.index('intraday:XETR') < order.index('catchup')               # collecte normale d'abord, rattrapage ensuite
    assert all(t.split(':')[0] in ('intraday', 'daily', 'maintenance', 'catchup') for t in order)


def test_data_yahoo_never_provides_is_reported_not_hidden(conn):
    seed(conn, 26, bars=False); seed(conn, 27, bars=False)                     # clôtures présentes, barres jamais fournies par Yahoo
    empty = Yahoo(daily=yahoo().daily)                                         # répond, mais sans aucune barre de 15 min
    for hh, mm in ((18, 0), (18, 10), (18, 30), (19, 10), (20, 30), (22, 0)):
        tasks.tick(conn, empty, at(27, hh, mm), 'cron')
    st = catchup.status(conn, at(27, 22, 0))
    assert len(st['open']) == 2 and all(o['tries'] >= 2 for o in st['open'])
    assert all(o['next_try'] for o in st['open'])                              # les nouvelles tentatives continuent, espacées
    tasks.tick(conn, empty, at(29, 18, 0), 'cron')                             # deux jours plus tard : ces séances ne sont plus conservées
    st = catchup.status(conn, at(29, 18, 0))
    lost = {(u['mic'], u['session']) for u in st['unrecoverable']}
    assert ('XETR', '2026-10-26') in lost and ('XETR', '2026-10-27') in lost
    assert all('Yahoo' in u['why'] for u in st['unrecoverable'])
    assert count(conn, "SELECT COUNT(*) FROM price_gaps WHERE state='unrecoverable'") >= 2


def test_thin_titles_without_trades_do_not_trigger_any_catchup(conn):
    pct = lambda j: 92 if j < 3 or j >= 31 else 38                           # profil en U : peu d'échanges en milieu de séance
    with conn.cursor() as cur:
        for day in (22, 23, 26, 27):
            rows = [(i, t) for i in range(1, N + 1) for j, t in enumerate(intraday.expected_slot_starts('XETR', datetime.date(2026, 10, day)))
                    if (i * 31 + j * 17 + day * 13) % 100 < pct(j)]
            cur.executemany('INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (%s,%s,10,1)', rows)
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,10)', [(i, datetime.date(2026, 10, day)) for i in range(1, N + 1)])
    conn.commit()
    assert catchup.plan_intraday(conn, at(28, 9, 0)) == []
