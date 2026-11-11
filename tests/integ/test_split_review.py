"""Décisions explicites de splits sur une base jetable : audit, cohérence et refus durable."""
import datetime
import os

import pytest

from engine.market import split_review as R, splits
from engine.shared import settings
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

DAY = datetime.date(2026, 10, 27)
NOW = datetime.datetime(2026, 11, 11, 12, tzinfo=datetime.timezone.utc)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as q:
        q.execute("INSERT INTO instruments(id,group_key,isin,kind,name) VALUES (1,'isin:LU1230136894','LU1230136894','etf','CSH2 fixture'),(2,'sym:ODD',NULL,'equity','Ratio inhabituel')")
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XLON','CSH2.L','GBP','selected',1),(2,2,'XETR','ODD.DE','EUR','selected',1)")
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(1,DAY-datetime.timedelta(days=1),1250),(1,DAY,5),(2,DAY-datetime.timedelta(days=1),1470),(2,DAY,10)])
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (1,%s,0.004,250,'detected',%s)", (DAY,NOW.replace(tzinfo=None)))
        q.execute("INSERT INTO series_state(listing_id,computed_at,closes_count,quality,break_dates) VALUES (2,%s,2,'break',%s)", (NOW.replace(tzinfo=None),DAY.isoformat()))
    c.commit()
    yield c
    c.close()


def action(conn, decision='applied', **kw):
    return R.decide(conn, dict(listing_id=1,event_date=DAY.isoformat(),actor_id=7,revision=0,decision=decision,old_shares=1,new_shares=250,note='Avis officiel Amundi vérifié',source_url='https://example.com/issuer-notice',**kw))


def test_apply_is_audited_and_idempotent_without_changing_original_trades(conn):
    with conn.cursor() as q:
        q.execute("INSERT INTO users(id,username,pass_hash,is_admin,created_at) VALUES (7,'review-test','unused-test-hash',1,UTC_TIMESTAMP())")
        q.execute("INSERT INTO portfolios(id,user_id,name,created_at,updated_at) VALUES (1,7,'Split test',UTC_TIMESTAMP(),UTC_TIMESTAMP())")
        q.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (1,1,'CSH2.L','buy',2,1250,'GBP',1.2,0,'2026-10-26 10:00:00',UTC_TIMESTAMP())")
    conn.commit()
    with conn.cursor() as q:
        q.execute('SELECT * FROM portfolio_transactions'); before=q.fetchall()
    assert len(before)==1
    assert action(conn)['changed']
    assert action(conn)['changed'] is False
    with conn.cursor() as q:
        q.execute('SELECT * FROM corporate_events'); events=q.fetchall()
        q.execute('SELECT * FROM split_review_history'); history=q.fetchall()
        q.execute('SELECT * FROM portfolio_transactions'); assert q.fetchall()==before
    assert len(events)==1 and float(events[0]['ratio'])==250
    assert len(history)==1 and history[0]['actor_id']==7 and history[0]['source_url']=='https://example.com/issuer-notice'
    d=R.state(conn,{'state':'applied','q':'LU1230136894'})
    assert d['total']==1 and d['rows'][0]['state']=='applied' and d['rows'][0]['revision']==1
    assert float(d['rows'][0]['price_before'])==1250 and float(d['rows'][0]['price_after'])==5
    assert settings.get(conn,'split_metrics_pending') is True


@pytest.mark.parametrize('override',[{'new_shares':2.5},{'new_shares':0},{'old_shares':0},{'new_shares':'NaN'},{'new_shares':'inf'},{'source_url':'javascript:alert(1)'},{'note':'','source_url':''}])
def test_invalid_ratio_and_source_never_change_events(conn,override):
    payload=dict(listing_id=1,event_date=DAY.isoformat(),actor_id=7,revision=0,decision='applied',old_shares=1,new_shares=250,note='Justification',source_url='https://example.com/notice')
    payload.update(override)
    with pytest.raises(ValueError): R.decide(conn,payload)
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) AS n FROM corporate_events');assert q.fetchone()['n']==0
        q.execute('SELECT COUNT(*) AS n FROM split_review_history');assert q.fetchone()['n']==0
    assert not settings.get(conn,'split_metrics_pending',False)


def test_rejection_survives_yahoo_confirmation_and_can_be_reopened(conn):
    action(conn,'rejected')
    client=FakeYahoo(declared_splits={'CSH2.L':[(DAY.isoformat(),250.,1.)]})
    splits.verify(conn,client,NOW)
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) AS n FROM corporate_events');assert q.fetchone()['n']==0
        q.execute("UPDATE split_log SET status='real_move',recheck_after=NULL WHERE listing_id=1")
    conn.commit()
    splits.recheck(conn,client,NOW)
    assert R.state(conn,{'state':'rejected'})['total']==1
    R.decide(conn,dict(listing_id=1,event_date=DAY.isoformat(),actor_id=7,revision=1,decision='pending'))
    splits.recheck(conn,client,NOW)
    assert R.state(conn,{'state':'confirmed'})['total']==1
    assert len(R.state(conn,{'state':'all'})['rows'][0]['history'])==2


def test_stale_decision_cannot_overwrite_another_review(conn):
    action(conn,'rejected')
    with pytest.raises(ValueError,match='changé'): action(conn)
    assert R.state(conn,{'state':'rejected'})['total']==1


def test_nonstandard_ratios_are_detected_for_human_review(conn):
    assert splits.detect(conn,NOW)==1
    d=R.state(conn,{'q':'ODD.DE'})
    assert d['total']==1 and float(d['rows'][0]['proposed_ratio'])==pytest.approx(147)
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) AS n FROM corporate_events'); assert q.fetchone()['n']==0


def test_scan_listing_and_counts_do_not_apply_any_split(conn):
    assert R.scan(conn,{})['detected']==1
    d=R.state(conn,{'state':'all'})
    assert d['total']==2 and d['counts']['pending']==2 and not d['recompute_pending']


def test_computation_lock_prevents_a_partial_update(conn):
    other=connect()
    try:
        with other.cursor() as q:
            q.execute("SELECT GET_LOCK('jigo:job:compute',0) AS got");assert q.fetchone()['got']
        with pytest.raises(ValueError,match='calcul est en cours'):action(conn)
        assert R.state(conn,{})['rows'][0]['state']=='pending'
    finally:
        other.close()


def test_successful_recomputation_clears_the_persistent_request(conn,monkeypatch):
    from engine.jobs import tasks
    action(conn)
    assert settings.get(conn,'split_metrics_pending') is True
    monkeypatch.setattr(tasks.compute,'compute_all',lambda c,now:(2,10))
    tasks._recompute(conn,NOW,lambda *a:None,'metrics')
    assert settings.get(conn,'split_metrics_pending') is False


def test_zero_price_does_not_crash_detection_or_create_a_split(conn):
    with conn.cursor() as q:
        q.execute('UPDATE daily_prices SET close_px=0 WHERE listing_id=2 AND price_date=%s',(DAY,))
    conn.commit()
    assert splits.detect(conn,NOW)==0


def test_amplitude_sort_and_filter_cover_all_pages_and_reverse_splits(conn):
    with conn.cursor() as q:
        q.executemany("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (2,%s,0.5,2,'detected',UTC_TIMESTAMP())",
                      [(DAY-datetime.timedelta(days=i),) for i in range(1,46)])
        q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (2,%s,1000,0.001,'detected',UTC_TIMESTAMP())",(DAY-datetime.timedelta(days=50),))
    conn.commit()
    d=R.state(conn,{})
    assert d['total']==47 and len(d['rows'])==40 and d['pages']==2
    assert float(d['rows'][0]['proposed_ratio'])==pytest.approx(.001)  # regroupement 1 pour 1000 en tête, même ancien
    assert float(d['rows'][1]['proposed_ratio'])==250
    filtered=R.state(conn,{'min_ratio':'100'})
    assert filtered['total']==2 and filtered['counts']['pending']==2
    assert [float(r['proposed_ratio']) for r in filtered['rows']]==[.001,250]
    recent=R.state(conn,{'sort':'recent'})
    assert recent['rows'][0]['listing_id']==1
    smallest=R.state(conn,{'sort':'magnitude_asc'})
    assert float(smallest['rows'][0]['proposed_ratio'])==2
    assert R.state(conn,{'q':'CSH2','min_ratio':'100'})['total']==1


@pytest.mark.parametrize('payload',[{'sort':'bogus'},{'min_ratio':'NaN'},{'min_ratio':'inf'},{'min_ratio':'-1'},{'min_ratio':'oops'}])
def test_invalid_sort_or_amplitude_is_rejected(payload):
    with pytest.raises(ValueError):R.state(None,payload)
