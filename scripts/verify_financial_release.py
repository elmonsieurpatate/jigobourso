"""Read-only verification against actual production series; no Yahoo or portfolio write."""
import datetime as dt
import json
from engine.shared.db import connect
from engine.analytics.series import analyze_series
from engine.market import hours
from engine.market.collect import to_eur_factor


def run():
    conn = connect()
    with conn.cursor() as c:
        c.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        c.execute('START TRANSACTION READ ONLY')
    with conn.cursor() as c:
        c.execute("SELECT l.id,l.symbol,l.mic FROM listings l WHERE l.symbol IN ('BOX','BBSI','VOO','UBU5.DE') AND l.is_primary=1")
        listings=c.fetchall()
    checks=[]
    for listing in listings:
        with conn.cursor() as c:
            c.execute('SELECT price_date,close_px,adj_close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date',(listing['id'],))
            bars=[(r['price_date'].isoformat(),float(r['close_px']),None if r['adj_close_px'] is None else float(r['adj_close_px'])) for r in c.fetchall()]
            c.execute("SELECT event_date,ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')",(listing['id'],))
            splits=[(r['event_date'].isoformat(),float(r['ratio']) if r['ratio'] else None) for r in c.fetchall()]
            c.execute('SELECT * FROM strategy_metrics WHERE listing_id=%s',(listing['id'],))
            stored={r['sessions']:r for r in c.fetchall()}
        windows=[1,5,21,63,126,252]
        dates,closes,basis,breaks,metrics,missing,tech=analyze_series(bars,windows,splits)
        compared=0
        for n,m in metrics.items():
            if m is None:
                assert n not in stored or stored[n]['perf'] is None,(listing['symbol'],n,'unsafe stored metric')
                continue
            for key in ('slope','r2','perf','volatility','drawdown','er'):
                if m[key] is None:
                    assert stored[n][key] is None
                else:
                    assert abs(float(stored[n][key])-m[key])<=.000051,(listing['symbol'],n,key)
            compared+=1
        checks.append({'symbol':listing['symbol'],'daily_closes':len(bars),'last_close':dates[-1] if dates else None,'basis':basis,'windows_verified':compared,'expected_close':hours.expected_last_close(listing['mic'],dt.datetime.now(dt.timezone.utc))})
    assert {x['symbol'] for x in checks}=={'BOX','BBSI','VOO','UBU5.DE'}
    conn.rollback();conn.close()
    assert abs(to_eur_factor('GBX',{'GBP':1.2})-.012)<1e-12
    print(json.dumps({'ok':True,'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'actual_series_checks':checks},ensure_ascii=False))

if __name__=='__main__':run()
