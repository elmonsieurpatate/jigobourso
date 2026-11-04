"""Synthetic, isolated Explorer fixtures. Never usable against production."""
import datetime as dt
import os
import subprocess
assert os.environ.get('JIGO_TEST_DATABASE')=='1'
assert os.environ.get('JIGO_DB_HOST')=='127.0.0.1'
assert os.environ.get('JIGO_DB_NAME') in ('jigobourso_explorer_review','jigobourso_it')
from engine.shared.db import connect
from engine.analytics.compute import compute_all
from engine.market.calendar import session_dates
from engine.market.hours import expected_last_close, utcnow
from tests.dbutil import reset_data
c=connect();reset_data(c)
subprocess.run(['php','scripts/create_user.php','explorer_review','synthetic-local-password','--admin'],check=True)
dates=session_dates('XPAR',expected_last_close('XPAR',utcnow()),400)
with c.cursor() as q:
    for lid in range(1,9):
        kind='etf' if lid>4 else 'equity';growth=1+.0005*lid
        q.execute('INSERT INTO instruments(id,group_key,kind,name,country,category) VALUES (%s,%s,%s,%s,%s,%s)',(lid,'explorer-synthetic:'+str(lid),kind,'Titre synthétique '+str(lid),'France','Technology'))
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)",(lid,lid,'SYN'+str(lid)))
        values=[(lid,day,round(10*growth**i*(.97 if lid in (2,6) and i==len(dates)-1 else 1),8),10000*lid) for i,day in enumerate(dates)]
        if lid==8:values=values[-8:]
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (%s,%s,%s,%s)',values)
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,net_assets,expense_ratio) VALUES (%s,%s,NOW(),'daily','EUR',%s,10000000,.002)",(lid,values[-1][2],10000*lid))
        if lid==7:q.execute('UPDATE daily_prices SET volume=NULL WHERE listing_id=7')
    q.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',CURDATE(),.92)")
c.commit();print(compute_all(c,utcnow()));c.close()
