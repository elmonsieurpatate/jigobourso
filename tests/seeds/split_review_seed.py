"""Jeu local pour la page de revue ; refuse toute base non jetable."""
import datetime
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from engine.shared.db import connect
from tests.dbutil import reset_data

assert os.environ.get('JIGO_TEST_DATABASE')=='1' and os.environ.get('JIGO_DB_NAME')=='jigobourso_it'
c=connect();reset_data(c)
day=datetime.date(2026,10,27)
with c.cursor() as q:
 q.execute("INSERT INTO instruments(id,group_key,isin,kind,name) VALUES (1,'isin:LU1230136894','LU1230136894','etf','Amundi Overnight GBP — test'),(2,'sym:ODD',NULL,'equity','Cas à examiner — test')")
 q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (1,1,'XLON','CSH2.L','GBP','selected',1),(2,2,'XETR','ODD.DE','EUR','selected',1)")
 q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',[(1,day-datetime.timedelta(days=1),1250),(1,day,5),(2,day-datetime.timedelta(days=1),1470),(2,day,10)])
 q.executemany("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (%s,%s,%s,%s,'detected',UTC_TIMESTAMP())",[(1,day,.004,250),(2,day,1/147,147)])
c.commit();c.close()
