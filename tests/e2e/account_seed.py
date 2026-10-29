import os,runpy,datetime as dt
assert os.environ.get('JIGO_TEST_DATABASE')=='1' and os.environ.get('JIGO_DB_NAME')=='jigobourso_it'
runpy.run_path('tests/e2e/financial_seed.py')
from engine.shared.db import connect
from engine.analytics.compute import compute_all
c=connect()
with c.cursor() as q:
 for i in range(3,46):
  q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'France')",(i,f'e2e:{i}',f'Test action {i:02d}'))
  q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)",(i,i,f'TEST{i:02d}.PA'))
  q.execute("INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px) SELECT %s,price_date,close_px,adj_close_px FROM daily_prices WHERE listing_id=1",(i,))
  q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,149,NOW(),'quote','EUR')",(i,))
c.commit();compute_all(c,dt.datetime.now(dt.timezone.utc));c.close()
