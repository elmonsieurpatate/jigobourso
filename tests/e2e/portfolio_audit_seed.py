"""Synthetic portfolio audit fixtures. Run from repo root, isolated local DB only."""
import datetime as dt,json,os
from engine.shared.db import connect
assert os.environ.get('JIGO_TEST_DATABASE') == '1'
assert os.environ['JIGO_DB_NAME'] in ('jigobourso_it', 'jigobourso_portfolio_audit')
assert os.environ.get('JIGO_DB_HOST') == '127.0.0.1'
from tests.dbutil import reset_data
import subprocess
c=connect(); reset_data(c)
subprocess.run(['php', 'scripts/create_user.php', 'audit_portfolio', 'audit-local-validation-2026', '--admin'], check=True)
today=dt.date.today(); days=[];d=today-dt.timedelta(days=1)
while len(days)<420:
 if d.weekday()<5: days.append(d)
 d-=dt.timedelta(days=1)
days.sort()
with c.cursor() as q:
 q.execute("SELECT id FROM users WHERE username='audit_portfolio'"); user_id=q.fetchone()['id']
 for i,sym,cur,price in [(1,'ALPHA','EUR',155),(2,'DOLLAR','USD',110),(3,'SPLIT','EUR',60),(4,'PENCE','GBp',120),(5,'NOQUOTE','EUR',None)]:
  q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'France')",(i,'audit:'+sym,'Audit '+sym))
  q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,%s,'selected',1)",(i,i,sym,cur))
  if price is not None:
   q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (%s,%s,NOW(),'quote',%s,100000)",(i,price,cur))
   vals=[]
   for day in days:
    if i==1: val=100 if day<dt.date(2026,9,1) else 200 if day<dt.date(2026,10,1) else 220 if day<dt.date(2026,10,10) else 160
    elif i==2:val=100
    elif i==3:val=100 if day<dt.date(2026,10,1) else 60
    else:val=100
    vals.append((i,day,val))
   q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',vals)
   q.execute("INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma50,momentum_6m,quality) VALUES (%s,NOW(),%s,420,%s,%s,%s,'ok')",(i,days[-1],vals[-1][-1],180 if i==1 else vals[-1][-1],-0.1 if i==1 else .1))
   q.executemany("INSERT INTO intraday_prices(listing_id,slot_start,close_px) VALUES (%s,%s,%s)",[(i,dt.datetime.combine(today,dt.time(9,0))+dt.timedelta(minutes=15*k),price*(.98+.01*k)) for k in range(3)])
   for window in (5,21,63,126,252):
    perf=-27.27 if i==1 and window in (5,21) else 60 if i==1 else 20 if i==4 else 0
    q.execute('INSERT INTO strategy_metrics(listing_id,sessions,slope,perf,volatility) VALUES (%s,%s,%s,%s,%s)',(i,window, -.1 if perf<0 else .1,perf,1.5 if i==1 else .4))
 for day in days+[today]:
  q.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',%s,.85),('GBP',%s,1.2)",(day,day))
 q.execute("INSERT INTO corporate_events VALUES (3,'2026-10-01','split',2)")
 q.execute("INSERT INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at,checked_at) VALUES (3,'2026-10-01',.5,2,'confirmed',NOW(),NOW())")
 for pid,name in [(1,'Multi-achats et devises'),(2,'Split sans vente'),(3,'Position soldée'),(4,'Sans cours'),(5,'Portefeuille vide'),(6,'Arrondis'),(7,'Partiellement valorisable'),(8,'Repères intraday')]:
  q.execute('INSERT INTO portfolios(id,user_id,name,is_default,created_at,updated_at) VALUES (%s,%s,%s,%s,NOW(),NOW())',(pid,user_id,name,pid==1))
 def tx(p,l,side,qty,price,day,fee=0,fx=1):
  sym,cur={1:('ALPHA','EUR'),2:('DOLLAR','USD'),3:('SPLIT','EUR'),4:('PENCE','GBp'),5:('NOQUOTE','EUR')}[l]
  q.execute('INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,name,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())',(p,l,sym,'Audit '+sym,side,qty,price,cur,fx,fee,day+' 12:00:00'))
  return q.lastrowid
 a=tx(1,1,'buy',10,100,'2025-09-01',10); b=tx(1,1,'buy',10,200,'2026-09-15',10);tx(1,1,'sell',5,180,'2026-10-15',5)
 tx(1,2,'buy',10,100,'2026-09-01',10,.9);tx(1,2,'sell',4,120,'2026-10-15',4,.8)
 tx(1,4,'buy',10,100,'2026-09-01',0,.012)
 tx(2,3,'buy',10,100,'2026-09-01');tx(3,1,'buy',1,100,'2026-09-01');tx(3,1,'sell',1,120,'2026-10-01')
 tx(7,1,'buy',1,100,'2026-09-01');tx(7,5,'buy',2,10,'2026-09-01')
 tx(4,5,'buy',2,10,'2026-09-01');tx(6,1,'buy',.12345678,123.456789,'2026-09-01',.013)
 q.execute("INSERT INTO lot_settings(transaction_id,strategy,alert_days,alert_drop_pct,updated_at) VALUES (%s,'momentum',30,20,NOW()),(%s,'fast',30,10,NOW())",(a,b))
 t=tx(8,1,'buy',1,100,today.isoformat(),1)
 q.execute('UPDATE portfolio_transactions SET trade_at=%s WHERE id=%s',(dt.datetime.combine(today,dt.time(9,15)),t))
 # Six held positions, two pairs of identical market paths: six legends, four geometries.
 q.execute("INSERT INTO portfolios(id,user_id,name,is_default,created_at,updated_at) VALUES (9,%s,'Six positions superposées',0,NOW(),NOW())",(user_id,))
 for lid,sym,end in [(11,'TTAN',110),(12,'ASO',105),(13,'BOX',110),(14,'FIGS',105),(15,'VFC',120),(16,'DXC',80)]:
  q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'France')",(lid,'six:'+sym,'Six '+sym))
  q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)",(lid,lid,sym))
  q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,%s,NOW(),'quote','EUR')",(lid,end))
  prices=[(lid,day,100+(end-100)*max(0,min(1,(day-dt.date(2026,10,20)).days/max(1,(today-dt.date(2026,10,20)).days)))) for day in days+[today]]
  q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',prices)
  q.execute("INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma50,momentum_6m,quality) VALUES (%s,NOW(),%s,420,%s,100,%s,'ok')",(lid,today,end,-.1 if sym=='DXC' else .1))
  for window in (5,21,63,126,252):
   q.execute('INSERT INTO strategy_metrics(listing_id,sessions,slope,perf,volatility) VALUES (%s,%s,.1,%s,.5)',(lid,window,end-100))
  for date,qty,price,fee in [('2026-10-20',1,100,1)]+([('2026-10-28',.2,105,.1)] if sym in ('TTAN','BOX') else []):
   q.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,name,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (9,%s,%s,%s,'buy',%s,%s,'EUR',1,%s,%s,NOW())",(lid,sym,'Six '+sym,qty,price,fee,date+' 12:00:00'))
   if sym=='DXC':q.execute("INSERT INTO lot_settings(transaction_id,strategy,alert_drop_pct,updated_at) VALUES (%s,'regular',10,NOW())",(q.lastrowid,))
c.commit();c.close();print('9 portefeuilles synthétiques, 11 titres, base isolée prête')
