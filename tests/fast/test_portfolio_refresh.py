import datetime as dt
from engine.analytics.series import history_refresh as r

class Cursor:
 def __init__(self,rows):self.rows=rows
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def execute(self,*args):pass
 def fetchone(self):return {'ok':1}
 def fetchall(self):return self.rows
class Conn:
 def __init__(self,rows):self.rows=rows
 def cursor(self):return Cursor(self.rows)

def test_explicit_refresh_reuses_collectors_for_exactly_one_listing(monkeypatch):
 calls=[];conn=Conn([{'listing_id':3,'mic':'XPAR','symbol':'A','held':1}]);client=object()
 monkeypatch.setattr(r.settings,'get',lambda *a:0);monkeypatch.setattr(r.settings,'put',lambda *a:None)
 def collect(c,cl,rows,now):calls.append((cl,rows));return {'added':2}
 monkeypatch.setattr(r,'fetch_daily',collect);monkeypatch.setattr(r,'fetch_intraday',collect)
 out=r.refresh(conn,3,client,dt.datetime.now(dt.timezone.utc))
 assert len(calls)==2 and all(len(rows)==1 and rows[0]['listing_id']==3 for _,rows in calls)
 assert out['daily']['added']==2

def test_cooldown_does_not_call_collectors(monkeypatch):
 import time
 monkeypatch.setattr(r.settings,'get',lambda *a:time.time())
 monkeypatch.setattr(r,'fetch_daily',lambda *a:(_ for _ in ()).throw(AssertionError('unwanted collection')))
 assert r.refresh(Conn([]),3,object())['cooldown'] is True
