"""Fixtures shared by the three requested regressions, isolated local DB only."""
import datetime as dt
import runpy
runpy.run_path('tests/e2e/explorer-editor-seed.py')
from engine.shared.db import connect
from engine.analytics.series.compute import compute_all
c=connect()
today=dt.date.today();days=[];d=today-dt.timedelta(days=1)
while len(days)<3:
    if d.weekday()<5: days.append(d)
    d-=dt.timedelta(days=1)
days.reverse()
with c.cursor() as q:
    q.execute("UPDATE listings SET symbol='ZNEAR' WHERE id=2")
    q.execute("UPDATE listings SET symbol='AFAR' WHERE id=4")
    q.execute('SELECT MAX(price_date) d FROM daily_prices WHERE listing_id=4');last=q.fetchone()['d']
    q.execute('UPDATE daily_prices SET close_px=close_px*.97/.98 WHERE listing_id=4 AND price_date=%s',(last,))
    q.execute('UPDATE latest_prices SET price=price*.97/.98 WHERE listing_id=4')
    for lid,name in [(10,'Premier investissement'),(11,'Achat complémentaire')]:
        q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'France')",(lid,'neutral:'+str(lid),name))
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)",(lid,lid,'NEUT'+str(lid)))
        prices=[100,105,105] if lid==10 else [100,100,100]
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',[(lid,d,p) for d,p in zip(days,prices)])
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,quote_at) VALUES (%s,%s,NOW(),'quote','EUR',100000,NOW())",(lid,prices[-1]))
    q.execute("SELECT id FROM users WHERE username='editor_test'");uid=q.fetchone()['id']
    q.execute("INSERT INTO portfolios(id,user_id,name,is_default,created_at,updated_at) VALUES (900,%s,'200 euros + 5 pour cent puis 200 euros',1,NOW(),NOW())",(uid,))
    for lid,day in [(10,days[0]),(11,days[2])]:
        q.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,name,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (900,%s,%s,%s,'buy',2,100,'EUR',1,0,%s,NOW())",(lid,'NEUT'+str(lid),'Investissement '+str(lid),str(day)+' 12:00:00'))
c.commit();compute_all(c,dt.datetime.now(dt.timezone.utc));c.close()
