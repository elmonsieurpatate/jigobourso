"""CPU benchmark only: 9,611 synthetic instruments, six windows and 24 score parts.

No database, provider, historical data or production writes. This is not a
full-universe SQL/Hostinger latency claim.
"""
import os
import sys
import time
import json
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.analytics.explorer import explorer_config as C
from engine.analytics.explorer import strategy as S
from engine.analytics.admin.service import packed

c=C.empty()
for p in c['periods']:p['enabled']=True
c['asset_rules']={'etf':{'periods':{'month':{'min_r2':.6}}}}
c['ranking']['components']=[dict(id=pid+'-'+metric,metric=metric,period=pid,kind='all',enabled=True,weight=1,direction='higher',normalization='percentile',transform='identity',min=0,max=100,exponent=1) for pid in C.PERIODS for metric in ('slope','perf','drawdown','up_fraction')]
c=C.validate(c);rows=[]
for i in range(9611):
    rows.append(dict(key=i,symbol='SYN'+str(i),group='equity' if i%2 else 'etf',status='retained',reasons=[],technical={},measures={n:dict(slope=i*.00001,perf=i*.001,r2=.6+i*.00003,up_fraction=.5+i*.00003,drawdown=i*.0001) for n in C.SESSIONS.values()}))
start=time.perf_counter();S.rank(c,rows);elapsed=time.perf_counter()-start
assert all(abs(v['score']-sum(p['contribution'] for p in v['score_parts']))<1e-8 for v in rows)
print(json.dumps(dict(instruments=len(rows),components=len(c['ranking']['components']),ranking_seconds=round(elapsed,3),compressed_result_bytes=len(packed(rows)),scope='CPU synthetic only; excludes SQL and Hostinger')))
