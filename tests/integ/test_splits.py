"""Splits : un saut ressemblant à un split n'est corrigé que si Yahoo déclare ce split ; une vraie chute n'est jamais « corrigée »."""
import datetime
import os

import pytest

from engine.analytics import compute
from engine.market import splits
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=UTC)
START = datetime.date(2026, 8, 3)
SESSIONS = [START + datetime.timedelta(days=i) for i in range(100) if (START + datetime.timedelta(days=i)).weekday() < 5 and START + datetime.timedelta(days=i) <= datetime.date(2026, 10, 27)]
JUMP = datetime.date(2026, 10, 13)


def price(d):
    return 100.0 if d < JUMP else 10.0           # cours divisé par 10 : split 10 pour 1 (ou chute de 90 %)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (1,'isin:DE0001','DE0001','equity','Split SE','Germany'),(2,'isin:DE0002','DE0002','equity','Chute SE','Germany')")
        cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XETR','SPL.DE','EUR','selected',1),(2,2,'XETR','MOVE.DE','EUR','selected',1)")
        for lid in (1, 2):
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, d, price(d)) for d in SESSIONS])
    c.commit()
    compute.compute_all(c, NOW)                   # remplit series_state (break_dates) comme la maintenance
    yield c
    c.close()


def quality(conn, lid):
    with conn.cursor() as cur:
        cur.execute('SELECT quality FROM series_state WHERE listing_id=%s', (lid,))
        return cur.fetchone()['quality']


def test_both_series_start_as_breaks_and_both_jumps_look_like_splits(conn):
    assert quality(conn, 1) == 'break' and quality(conn, 2) == 'break'
    assert splits.detect(conn, NOW) == 2
    assert splits.detect(conn, NOW) == 0                      # déjà noté
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status, ratio FROM split_log ORDER BY listing_id')
        assert [(r['listing_id'], r['status'], float(r['ratio'])) for r in cur.fetchall()] == [(1, 'detected', 10.0), (2, 'detected', 10.0)]


def test_only_the_split_declared_by_yahoo_is_corrected(conn):
    splits.detect(conn, NOW)
    client = FakeYahoo(declared_splits={'SPL.DE': [('2026-10-13', 10.0, 1.0)]})              # Yahoo ne déclare rien pour MOVE.DE
    out = splits.verify(conn, client, NOW)
    assert out == {'confirmed': 1, 'real_move': 1, 'unanswered': 0}
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status FROM split_log ORDER BY listing_id')
        assert [(r['listing_id'], r['status']) for r in cur.fetchall()] == [(1, 'confirmed'), (2, 'real_move')]
        cur.execute('SELECT listing_id, kind, ratio FROM corporate_events')
        assert [(r['listing_id'], r['kind'], float(r['ratio'])) for r in cur.fetchall()] == [(1, 'split', 10.0)]
    compute.compute_all(conn, NOW)
    assert quality(conn, 1) == 'ok'                           # le split est corrigé, sans rupture inexpliquée
    with conn.cursor() as cur:
        cur.execute('SELECT coverage_252, expected_252 FROM series_state WHERE listing_id=1')
        coverage = cur.fetchone()
        assert coverage['coverage_252'] < 1 and coverage['expected_252'] > 100  # couverture annuelle incomplète, affichée à la lecture
    assert quality(conn, 2) == 'break'                        # la chute du titre 2 reste une rupture, non corrigée


def test_declared_split_that_does_not_explain_the_jump_is_ignored(conn):
    splits.detect(conn, NOW)
    client = FakeYahoo(declared_splits={'MOVE.DE': [('2026-10-13', 3.0, 1.0)], 'SPL.DE': [('2026-06-01', 10.0, 1.0)]})     # ratio ou date sans rapport avec le saut
    assert splits.verify(conn, client, NOW) == {'confirmed': 0, 'real_move': 2, 'unanswered': 0}
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM corporate_events')
        assert cur.fetchone()['n'] == 0


def test_no_conclusion_when_yahoo_does_not_answer(conn):
    splits.detect(conn, NOW)

    class Broken(FakeYahoo):
        def splits(self, symbol, range_='2y'):
            raise RuntimeError('réseau')
    assert splits.verify(conn, Broken(), NOW) == {'confirmed': 0, 'real_move': 0, 'unanswered': 2}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM split_log WHERE status='detected'")
        assert cur.fetchone()['n'] == 2                       # rien n'est conclu : nouvel essai au prochain passage


# ───────── revérification bornée des sauts « real_move » (Yahoo peut déclarer un split avec retard) ─────────
DAY = datetime.timedelta(days=1)


def at(days):
    return NOW + days * DAY


def rows(conn, lid=None):
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, status, checks, recheck_after FROM split_log' + (' WHERE listing_id=%s' if lid else '') + ' ORDER BY listing_id', (lid,) if lid else ())
        return cur.fetchall()


def split_calls(client):
    return [c for c in client.calls if c[0] == 'splits']


def verified(conn):
    splits.detect(conn, NOW)
    client = FakeYahoo()                                        # Yahoo ne déclare encore rien
    assert splits.verify(conn, client, NOW) == {'confirmed': 0, 'real_move': 2, 'unanswered': 0}
    return client


def test_a_negative_answer_schedules_one_recheck_and_is_not_final(conn):
    verified(conn)
    assert [(r['status'], r['checks'], r['recheck_after']) for r in rows(conn)] == [('real_move', 1, (NOW + 7 * DAY).date())] * 2


def test_nothing_is_asked_again_before_the_scheduled_date(conn):
    verified(conn)
    client = FakeYahoo()
    assert splits.recheck(conn, client, at(6)) == {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}
    assert split_calls(client) == []


def test_a_late_declaration_is_found_and_corrects_the_series(conn):
    verified(conn)
    late = FakeYahoo(declared_splits={'MOVE.DE': [('2026-10-14', 10.0, 1.0)]})                   # Yahoo publie le split avec retard (date à un jour près)
    out = splits.recheck(conn, late, at(8))
    assert out == {'rechecked': 1, 'confirmed': 1, 'unanswered': 0, 'waiting': 0}
    assert [(r['listing_id'], r['status']) for r in rows(conn)] == [(1, 'real_move'), (2, 'confirmed')]
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, kind, ratio FROM corporate_events')
        assert [(r['listing_id'], r['kind'], float(r['ratio'])) for r in cur.fetchall()] == [(2, 'split', 10.0)]
    compute.compute_all(conn, NOW)                                                               # mêmes clôtures, calculées à la date des données
    assert quality(conn, 2) == 'ok'                                                              # le saut n'est plus une rupture une fois le split déclaré


def test_a_repeated_negative_answer_stops_after_the_maximum_and_never_confirms_by_itself(conn):
    verified(conn)
    client = FakeYahoo()
    assert splits.recheck(conn, client, at(8))['rechecked'] == 2
    assert [(r['status'], r['checks'], r['recheck_after']) for r in rows(conn)] == [('real_move', 2, (at(8) + 14 * DAY).date())] * 2
    assert splits.recheck(conn, client, at(9))['rechecked'] == 0                                 # pas avant la date prévue
    assert splits.recheck(conn, client, at(22))['rechecked'] == 2
    assert [(r['status'], r['checks'], r['recheck_after']) for r in rows(conn)] == [('real_move', 3, None)] * 2
    before = len(split_calls(client))
    assert splits.recheck(conn, client, at(40)) == {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}
    assert len(split_calls(client)) == before                                                    # plus aucune requête : le maximum de réponses est atteint
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM corporate_events')
        assert cur.fetchone()['n'] == 0                                                          # une absence répétée ne confirme rien et n'invente aucun split


def test_an_unanswered_recheck_is_not_counted_and_is_retried_later(conn):
    verified(conn)

    class Down(FakeYahoo):
        def splits(self, symbol, range_='2y'):
            raise RuntimeError('réseau')
    out = splits.recheck(conn, Down(), at(8))
    assert out == {'rechecked': 0, 'confirmed': 0, 'unanswered': 2, 'waiting': 0}
    assert [(r['status'], r['checks'], r['recheck_after']) for r in rows(conn)] == [('real_move', 1, (at(8) + 3 * DAY).date())] * 2      # ni vérification comptée, ni conclusion
    client = FakeYahoo()
    assert splits.recheck(conn, client, at(9))['rechecked'] == 0 and split_calls(client) == []                                         # attend la date de nouvel essai
    assert splits.recheck(conn, client, at(11))['rechecked'] == 2


def test_a_contradictory_declaration_does_not_confirm(conn):
    verified(conn)
    odd = FakeYahoo(declared_splits={'MOVE.DE': [('2026-10-13', 3.0, 1.0)], 'SPL.DE': [('2026-06-01', 10.0, 1.0)]})        # ratio sans rapport / date sans rapport
    assert splits.recheck(conn, odd, at(8)) == {'rechecked': 2, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}
    assert {r['status'] for r in rows(conn)} == {'real_move'}
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM corporate_events')
        assert cur.fetchone()['n'] == 0


def test_old_jumps_are_not_rechecked(conn):
    verified(conn)
    client = FakeYahoo(declared_splits={'MOVE.DE': [('2026-10-13', 10.0, 1.0)]})
    assert splits.recheck(conn, client, at(60)) == {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}         # le saut date de plus de 60 jours : on s'arrête
    assert split_calls(client) == []


def test_legacy_rows_without_a_schedule_are_due_once_and_then_scheduled(conn):
    verified(conn)
    with conn.cursor() as cur:
        cur.execute('UPDATE split_log SET recheck_after=NULL')               # lignes écrites avant la migration
    conn.commit()
    client = FakeYahoo()
    assert splits.recheck(conn, client, at(1))['rechecked'] == 2
    assert all(r['recheck_after'] is not None for r in rows(conn))


def test_one_pass_asks_yahoo_for_a_bounded_number_of_titles(conn):
    verified(conn)
    with conn.cursor() as cur:
        for lid in range(10, 60):
            cur.execute("INSERT INTO instruments(id,group_key,isin,kind,name,country) VALUES (%s,%s,%s,'equity','Titre',%s)", (lid, f'isin:T{lid}', f'T{lid:010d}', 'Germany'))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, f'T{lid}.DE'))
            cur.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at,checked_at,checks,recheck_after) VALUES (%s,'2026-10-13',0.1,10,'real_move',%s,%s,1,NULL)",
                        (lid, NOW.replace(tzinfo=None), NOW.replace(tzinfo=None)))
    conn.commit()
    client = FakeYahoo()
    out = splits.recheck(conn, client, at(8))
    assert len(split_calls(client)) == splits.RECHECK_LIMIT == 30 and out['rechecked'] == 30 and out['waiting'] == 22          # 52 titres dus : 30 interrogés, 22 attendent
    out2 = splits.recheck(conn, client, at(8))
    assert out2['rechecked'] == 22 and out2['waiting'] == 0 and len(split_calls(client)) == 52                                  # la suite au passage suivant, sans repasser sur les 30 premiers
    assert splits.recheck(conn, client, at(8)) == {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}


def test_a_rate_limit_stops_the_pass_but_keeps_the_work_already_done(conn):
    verified(conn)
    from engine.market.yahoo import RateLimited

    class Limited(FakeYahoo):
        def splits(self, symbol, range_='2y'):
            if symbol == 'MOVE.DE':
                raise RateLimited('429')
            return super().splits(symbol, range_)
    with pytest.raises(RateLimited):
        splits.recheck(conn, Limited(), at(8))
    assert [(r['listing_id'], r['checks']) for r in rows(conn)] == [(1, 2), (2, 1)]            # SPL.DE (déjà traité) est conservé, MOVE.DE reste dû


def test_without_the_new_columns_nothing_is_rechecked_and_verification_still_works(conn):
    with conn.cursor() as cur:
        cur.execute('ALTER TABLE split_log DROP COLUMN recheck_after, DROP COLUMN checks')
    conn.commit()
    try:
        splits.detect(conn, NOW)
        client = FakeYahoo(declared_splits={'SPL.DE': [('2026-10-13', 10.0, 1.0)]})
        assert splits.verify(conn, client, NOW) == {'confirmed': 1, 'real_move': 1, 'unanswered': 0}                              # comportement d'avant la migration
        assert splits.recheck(conn, client, at(8)) == {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}
    finally:
        with conn.cursor() as cur:
            cur.execute('ALTER TABLE split_log ADD COLUMN checks TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER checked_at, ADD COLUMN recheck_after DATE NULL AFTER checks')
        conn.commit()
