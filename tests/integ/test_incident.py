"""Incident de référence (Londres, 26 et 27 octobre) rejoué sur le mécanisme commun : cron absent pendant des séances, puis retour.
Détecté même sans aucune barre, récupéré avec la plage Yahoo qui remonte assez loin, suivi jusqu'à la résolution ; verrous, budget et erreurs sans blocage."""
import datetime
import os
import time
import pytest
from engine.jobs import tasks
from engine.market import catchup, collect, intraday
from engine.market.yahoo import RateLimited
from tests.integ.test_catchup import N, SYMS, Empty, Yahoo, at, bars_of, closes_of, conn, count, full_day, seed  # noqa: F401

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

D = lambda d: datetime.date(2026, 10, d)
WEEKDAYS = [d for d in range(12, 29) if datetime.date(2026, 10, d).weekday() < 5]      # 12-16, 19-23, 26-28
CUTOFF = {'5d': datetime.datetime(2026, 10, 22), '1mo': datetime.datetime(2026, 9, 28), '60d': datetime.datetime(2026, 8, 1)}


class Depth(Yahoo):
    """Comme le vrai Yahoo : chaque plage ne remonte qu'à sa profondeur ; les plages demandées sont conservées."""
    def __init__(self, days, **kw):
        super().__init__(intraday={s: ('UTC', [b for d in days for b in full_day(d)]) for s in SYMS},
                         daily={s: ('UTC', [(D(d), 10.0) for d in WEEKDAYS]) for s in SYMS}, **kw)
        self.ranges = []

    def spark(self, symbols, range_, interval):
        out = super().spark(symbols, range_, interval)
        if interval == '15m':
            self.ranges.append(range_)
            cut = int(CUTOFF[range_].replace(tzinfo=datetime.timezone.utc).timestamp())
            out = {k: dict(v, bars=[b for b in v['bars'] if b[0] >= cut]) for k, v in out.items()}
        return out


def states(conn, mic='XETR'):
    with conn.cursor() as cur:
        cur.execute('SELECT session_date, state FROM price_gaps WHERE mic=%s', (mic,))
        return {r['session_date']: r['state'] for r in cur.fetchall()}


def test_reference_incident_is_detected_without_any_bar_recovered_and_resolved(conn):
    for d in WEEKDAYS:                                                      # les clôtures quotidiennes sont là pour toutes les séances (historique)
        seed(conn, d, bars=False)
    for d in (12, 13, 14, 15, 19, 20, 21, 22):                              # 16 (ancienne), 23, 26 et 27 : AUCUNE barre n'a jamais été enregistrée (cron absent)
        seed(conn, d, closes=False)
    y = Depth(WEEKDAYS)
    gaps = collect.session_gaps(conn, 'XETR', at(28, 18, 0))
    assert set(gaps) == {D(16), D(23), D(26), D(27), D(28)}                         # détectées sans qu'aucune barre n'ait jamais existé, y compris la plus ancienne
    tasks.tick(conn, y, at(28, 18, 0), 'cron')                               # un seul passage du cron
    assert {states(conn)[D(d)] for d in (23, 26, 27, 28)} == {'repaired'}
    assert [bars_of(conn, d) for d in (23, 26, 27, 28)] == [N * 34] * 4          # données insérées
    assert set(y.ranges) >= {'1mo'} and all(r in ('5d', '1mo') for r in y.ranges)      # la séance du 16 a exigé une plage plus longue que 5 jours
    assert states(conn)[D(16)] == 'repaired' and bars_of(conn, 16) == N * 34
    assert collect.session_gaps(conn, 'XETR', at(28, 18, 0)) == {}           # plus aucun trou
    assert catchup.status(conn, at(28, 18, 0))['open'] == []


def test_what_yahoo_no_longer_provides_is_concluded_from_its_own_answers(conn):
    """Rétention de 60 séances : les plus anciennes sont au bord de ce que Yahoo fournit. Il est interrogé (60d), répond pour tous les titres sans ces barres :
    après plusieurs réponses complètes, la séance est « non récupérable » avec les chiffres de la réponse, et les autres séances proches sont bien récupérées."""
    conn.cursor().execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('intraday_retention_sessions','60',NOW())")
    conn.commit()
    now = at(28, 18, 0)
    old = collect.recent_sessions('XETR', now, 60)
    with conn.cursor() as cur:
        for d in old:
            cur.execute('INSERT INTO daily_prices(listing_id,price_date,close_px) SELECT id,%s,10 FROM listings', (d,))
    conn.commit()
    edge = datetime.datetime.combine(old[-5], datetime.time())               # Yahoo ne remonte pas jusqu'aux 4 plus anciennes séances conservées

    class Edge(Yahoo):
        asked = []

        def spark(self, symbols, range_, interval):
            if interval != '15m':
                return {}
            self.asked.append(range_)
            cut = int(edge.replace(tzinfo=datetime.timezone.utc).timestamp())
            return {s: {'currency': 'EUR', 'timezone': 'UTC', 'bars': [b for d in old if d >= edge.date() for b in [(int(t.replace(tzinfo=datetime.timezone.utc).timestamp()), 10.0) for t in intraday.expected_slot_starts('XETR', d)] if b[0] >= cut]} for s in symbols}
    y = Edge()
    for k in range(12):
        tasks.tick(conn, y, now + datetime.timedelta(minutes=40 * k), 'cron')
    st = states(conn)
    beyond = [d for d in old if d < edge.date()]
    assert beyond and all(st[d] == 'unrecoverable' for d in beyond)
    assert all(st[d] == 'repaired' for d in old if d >= edge.date())
    why = {u['session']: u['why'] for u in catchup.status(conn, now)['unrecoverable']}
    assert all(f'Yahoo a répondu pour les {N} titres' in why[d.isoformat()] for d in beyond) and set(Edge.asked) == {'60d'}


def test_budget_interruption_resumes_exactly_where_it_stopped(conn, monkeypatch):
    seed(conn, 26); seed(conn, 27, bars=False)
    monkeypatch.setattr(collect, 'SPARK_BATCH', 5)
    monkeypatch.setattr(catchup, 'BUDGET_SECONDS', 0.05)

    class Slow(Depth):
        def spark(self, *a, **k):
            if a[2] == '15m':
                time.sleep(0.08)
            return super().spark(*a, **k)
    y = Slow((26, 27))
    seen = []
    for i in range(8):
        tasks.tick(conn, y, at(28, 18, i * 5), 'cron')
        seen.append(bars_of(conn, 27))
        if states(conn).get(D(27)) == 'repaired':
            break
    assert 0 < seen[0] < N * 34 and seen == sorted(seen) and seen[-1] == N * 34      # progrès par lots, jamais refait depuis le début, jamais déclaré fini trop tôt
    assert states(conn)[D(27)] == 'repaired'


def test_rate_limit_mid_way_keeps_the_rest_to_do(conn, monkeypatch):
    seed(conn, 26); seed(conn, 27, bars=False)
    monkeypatch.setattr(collect, 'SPARK_BATCH', 5)

    class Limited(Depth):
        n = 0

        def spark(self, *a, **k):
            if a[2] == '15m':
                self.n += 1
                if self.n == 2:
                    raise RateLimited(30)
            return super().spark(*a, **k)
    y = Limited((26, 27))
    tasks.tick(conn, y, at(28, 18, 0), 'cron')
    half = bars_of(conn, 27)
    assert 0 < half < N * 34 and catchup.status(conn, at(28, 18, 0))['cooldown_until']
    assert catchup.load(conn)['intraday']['XETR|2026-10-27']['ids']          # les titres restants sont retenus
    tasks.tick(conn, y, at(28, 18, 5), 'cron')
    assert bars_of(conn, 27) == half                                          # pause de 15 minutes respectée
    tasks.tick(conn, y, at(28, 18, 30), 'cron')
    assert bars_of(conn, 27) == N * 34 and states(conn)[D(27)] == 'repaired'


def test_a_dead_lock_from_a_killed_process_does_not_block_the_catchup(conn):
    seed(conn, 26); seed(conn, 27, bars=False)
    with conn.cursor() as cur:                                                # un rattrapage tué il y a 40 minutes, et une collecte tuée il y a 2 h
        cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at) VALUES ('catchup','cron','running',%s),('intraday:XETR','cron','running',%s)",
                    (datetime.datetime(2026, 10, 28, 17, 20), datetime.datetime(2026, 10, 28, 16, 0)))
    conn.commit()
    tasks.tick(conn, Depth((26, 27)), at(28, 18, 0), 'cron')
    assert bars_of(conn, 27) == N * 34
    assert count(conn, "SELECT COUNT(*) FROM jobs WHERE status='interrupted'") == 2 and count(conn, "SELECT COUNT(*) FROM jobs WHERE status='running'") == 0


def test_a_failing_place_never_blocks_the_others(conn):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (101,'isin:P1','P00000000001','equity','P1','France')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (101,101,'XPAR','P1.PA','EUR','selected',1)")
        cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (101,%s,10)', [(D(23),), (D(26),), (D(27),)])
    conn.commit()
    seed(conn, 26); seed(conn, 27, bars=False)

    class Broken(Depth):
        def spark(self, symbols, range_, interval):
            if interval == '15m' and any(s.endswith('.DE') for s in symbols):
                raise OSError('Yahoo : erreur réseau')
            return super().spark(symbols, range_, interval)
    y = Broken((26, 27))
    y.intraday['P1.PA'] = ('UTC', [b for d in (23, 26, 27) for b in [(t, 10.0) for t in intraday.expected_slot_starts('XPAR', D(d))]])
    tasks.tick(conn, y, at(28, 18, 0), 'cron')                               # aucune exception, XPAR est traitée
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM intraday_prices WHERE listing_id=101")
        assert cur.fetchone()['n'] > 0
    assert states(conn, 'XPAR').get(D(27)) == 'repaired'
    assert states(conn).get(D(27)) == 'to_repair'                             # XETR reste suivie, à réessayer plus tard
    assert catchup.load(conn)['intraday']['XETR|2026-10-27']['tries'] >= 1


def test_closes_retries_do_not_retrigger_the_heavy_maintenance(conn):
    seed(conn, 26); seed(conn, 27)
    y = Depth((26, 27))
    del y.daily['T1.DE']                                                       # un titre dont Yahoo ne donne plus de clôture (titre mort)
    for mm in (0, 15, 45, 90):
        tasks.tick(conn, y, at(28, 18, 0) + datetime.timedelta(minutes=mm), 'cron')
    assert count(conn, "SELECT COUNT(*) FROM jobs WHERE job_type='maintenance'") <= 1
    assert count(conn, "SELECT COUNT(*) FROM jobs WHERE job_type='daily:XETR'") >= 2      # les clôtures manquantes sont bien redemandées, espacées
