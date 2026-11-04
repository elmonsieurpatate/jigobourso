"""Additional path/liquidity measures from stored closes only (no collection).

A missing session makes path statistics unavailable. Split-adjusted prices are used
for returns; raw historical prices and dated FX for traded euro amounts.
"""
import math
import datetime
from bisect import bisect_right
from collections import defaultdict
from .series import prepare_series
from engine.market.calendar import window_calendars
from engine.market.collect import SUBUNITS, to_eur_factor


def path_metrics(prices,volumes=None,turnovers=None):
    if len(prices)<2 or any(p is None or p<=0 or not math.isfinite(p) for p in prices):return {}
    logs=[math.log(p) for p in prices];steps=[b-a for a,b in zip(logs,logs[1:])];positive=[x for x in steps if x>1e-12]
    daily=[100*math.expm1(x) for x in steps];total=100*math.expm1(logs[-1]-logs[0])
    out={'up_days':len(positive),'up_fraction':len(positive)/len(steps),
         'gain_share':100*max(positive)/sum(positive) if positive else 0.0,
         'largest_day':max(daily),'worst_day':min(daily),
         'gain_net_share':100*max(0,max(daily))/total if total>0 else None,
         'current_drawdown':100*(1-prices[-1]/max(prices))}
    for field,values in [('avg_volume',volumes),('turnover_eur',turnovers)]:
        valid = [v for v in (values or ()) if v is not None and math.isfinite(v) and v >= 0]
        complete = values is not None and len(values) == len(steps) and len(valid) == len(steps)
        out[field] = sum(valid) / len(steps) if complete else None
        prefix = 'volume' if field == 'avg_volume' else 'turnover'
        out.update({prefix + '_source': 'daily_prices.volume' if field == 'avg_volume' else 'raw_close*historical_volume*dated_fx',
                    prefix + '_observations': len(valid), prefix + '_expected': len(steps),
                    prefix + '_coverage': min(1.0, len(valid) / len(steps))})
    return out


def load(conn,universe,windows,expected_close):
    out=defaultdict(dict);meta={u['id']:u for u in universe};ids=list(meta)
    calendars={m:window_calendars(m,expected_close(conn,m),windows) for m in {u['mic'] for u in universe}}
    starts=[d[0] for group in calendars.values() for d in group.values() if d]
    if not starts:return out
    since=min(starts)
    with conn.cursor() as q:
        q.execute('SELECT currency,rate_date,to_eur FROM fx_rates WHERE rate_date>=%s ORDER BY currency,rate_date',(str(datetime.date.fromisoformat(since)-datetime.timedelta(days=7)),))
        fx=defaultdict(list)
        for r in q.fetchall():fx[r['currency']].append((str(r['rate_date']),float(r['to_eur'])))
        for start in range(0,len(ids),500):
            part=ids[start:start+500];marks=','.join(['%s']*len(part));bars=defaultdict(list);volume={};raw={};splits=defaultdict(list)
            q.execute(f'SELECT listing_id,price_date,close_px,adj_close_px,volume FROM daily_prices WHERE listing_id IN ({marks}) AND price_date>=%s ORDER BY listing_id,price_date',part+[since])
            for r in q.fetchall():
                lid=r['listing_id'];day=str(r['price_date']);bars[lid].append((day,float(r['close_px']),float(r['adj_close_px']) if r['adj_close_px'] is not None else None))
                volume[lid,day]=None if r['volume'] is None else float(r['volume']);raw[lid,day]=float(r['close_px'])
            q.execute(f"SELECT listing_id,event_date,ratio FROM corporate_events WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split') ORDER BY event_date",part)
            for r in q.fetchall():splits[r['listing_id']].append((str(r['event_date']),float(r['ratio']) if r['ratio'] is not None else None))
            for lid in part:
                u=meta[lid];dates,prices,_,breaks=prepare_series(bars[lid],splits[lid]);observations=dict(zip(dates,prices))
                currency=u.get('price_currency') or u.get('currency')
                subunit = SUBUNITS.get(currency) or SUBUNITS.get((currency or '').upper())
                base = subunit[0] if subunit else (currency or '').upper()
                for n,ds in calendars[u['mic']].items():
                    if not ds or any(ds[0]<dates[b]<=ds[-1] for b in breaks):continue
                    vs=[volume.get((lid,d)) for d in ds[1:]];amounts=[]
                    for d,v in zip(ds[1:],vs):
                        rates=fx.get(base,[]);index=bisect_right(rates,(d,float('inf')))-1
                        rate=rates[index] if index>=0 else None
                        factor=1.0 if currency=='EUR' else None
                        if rate and (datetime.date.fromisoformat(d)-datetime.date.fromisoformat(rate[0])).days<=7:factor=to_eur_factor(currency,{base:rate[1]})
                        amounts.append(raw[lid,d]*v*factor if (lid,d) in raw and v is not None and factor is not None else None)
                    out[lid][n]=path_metrics([observations.get(d) for d in ds],vs,amounts)
    return out
