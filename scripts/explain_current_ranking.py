"""SELECT-only snapshot for the requested week/month configuration, no ranking changes."""
import json,math,sys,importlib.util
from engine.shared.db import connect
from engine.analytics import service,strategy
c=connect()
with c.cursor() as cur:
 cur.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
 cur.execute('START TRANSACTION READ ONLY')
cfg=strategy.preset('regular')
for p in cfg['periods']:
 p['enabled']=p['id'] in ('week','month')
 for k in ('min_r2','min_er','min_return','max_return','max_volatility','max_drawdown'):p[k]=None
 p['min_slope']=strategy.SLOPE_LEVELS['very_strong'] if p['enabled'] else None
cfg['ranking']={'mode':'performance','weights':{}}
rows=service.judge_universe(c,cfg);kept=[r for r in rows if r['status']=='retained' and r['group']=='equity']
result=[]
for r in rows:
 if r['symbol'] not in ('CXM','AR','DOW'):continue
 peers={n:strategy._percentiles({v['key']:v['measures'][n]['perf'] for v in kept}) for n in (5,21)}
 result.append({'symbol':r['symbol'],'name':r['row']['name'],'mic':r['row']['mic'],'status':r['status'],'rank':r['rank'],'score':r['score'],'last_close':str(r['row']['last_close_date']),'metrics':r['measures'],'percentiles':{n:peers[n].get(r['key']) for n in (5,21)}})
print(json.dumps({'config':cfg,'retained_equities':len(kept),'at_data_max':max(str(r['row']['last_close_date']) for r in rows if r['row']['last_close_date']),'titles':result},default=str))
c.rollback();c.close()
