import os,datetime as dt,json
assert os.environ.get('JIGO_TEST_DATABASE')=='1' and os.environ['JIGO_DB_NAME']=='jigobourso_it'
from engine.shared.db import connect
from tests.dbutil import reset_data
from engine.analytics.compute import compute_all
con=connect();reset_data(con)
dates=[];d=dt.date(2026,10,28)
while len(dates)<400:
    if d.weekday()<5:dates.append(d)
    d-=dt.timedelta(days=1)
dates.reverse()
with con.cursor() as c:
    c.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (1,'audit:1','equity','Action de test','France'),(2,'audit:2','equity','Action exclue de test','France')")
    c.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary,excluded_reason) VALUES (1,1,'XPAR','TEST.PA','EUR','selected',1,NULL),(2,2,'XPAR','EXCL.PA','EUR','excluded',0,'liquidité insuffisante')")
    c.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (1,149,NOW(),'quote','EUR',100000)")
    c.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px) VALUES (%s,%s,%s,%s)',[(1,d,100*1.001**i,100*1.001**i) for i,d in enumerate(dates)])
con.commit();compute_all(con,dt.datetime.now(dt.timezone.utc));con.close()
