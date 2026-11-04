"""Disposable local fixtures: equity/ETF, strong month/week, rising/falling last close."""
import datetime as dt
import os
import subprocess
assert os.environ.get('JIGO_TEST_DATABASE') == '1'
assert os.environ.get('JIGO_DB_HOST') == '127.0.0.1'
assert os.environ.get('JIGO_DB_NAME') == 'jigobourso_portfolio_audit'
from engine.shared.db import connect
from engine.analytics.compute import compute_all
from tests.dbutil import reset_data
c=connect();reset_data(c)
subprocess.run(['php','scripts/create_user.php','editor_test','editor-local-only-password','--admin'],check=True)
dates=[];d=dt.date.today()-dt.timedelta(days=1)
while len(dates)<400:
    if d.weekday()<5:dates.append(d)
    d-=dt.timedelta(days=1)
dates.reverse()
with c.cursor() as q:
    for lid,kind,fall in [(1,'equity',False),(2,'equity',True),(3,'etf',False),(4,'etf',True)]:
        q.execute('INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,%s,%s,%s)',(lid,'editor:'+str(lid),kind,'Titre '+str(lid),'France'))
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)",(lid,lid,'EDIT'+str(lid)))
        values=[(lid,day,round(10*1.01**i*(.98 if fall and i==len(dates)-1 else 1),8)) for i,day in enumerate(dates)]
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',values)
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,quote_at) VALUES (%s,%s,NOW(),'quote','EUR',100000,NOW())",(lid,values[-1][2]))
c.commit();compute_all(c,dt.datetime.now(dt.timezone.utc));c.close()
