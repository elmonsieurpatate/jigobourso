"""Offline comparison on synthetic or exported market snapshots, no DB/network.

python -m scripts.compare_growth_v4 [--snapshot file.json] [--json]
V1 means audited trajectory gates only, not its universe/news/volumes/ranking.
"""
import argparse
import json
from pathlib import Path
from engine.analytics import growth as G, strategy as S, explorer_config as C
from engine.market.calendar import window_calendars, session_dates
from scripts.preview_growth_v4 import fixtures


def evaluate(snapshot):
    if snapshot.get('schema')!=1:raise ValueError('Snapshot de schéma 1 attendu')
    config=C.validate(snapshot['config']) if snapshot.get('config',{}).get('growth') else G.preset()
    windows=window_calendars(snapshot['mic'],snapshot['expected_last_date'],S.required_sessions(config))
    bars=[bar for bar in snapshot['bars'] if bar[0]<=snapshot['expected_last_date']]
    candidate=dict(bars=bars,split_dates=snapshot.get('split_dates',[]),session_windows=windows,
                   technical_sessions=session_dates(snapshot['mic'],snapshot['expected_last_date'],205),
                   expected_last_date=snapshot['expected_last_date'])
    v=S.evaluate_one(config,candidate);v.update(key=1,symbol=snapshot.get('symbol','SNAPSHOT'),group='equity');S.rank(config,[v])
    measures=v['measures'];checks=[]
    for n,field,threshold,operator in [(1,'perf',0,'>'),(5,'perf',3,'>='),(21,'perf',8,'>='),(21,'r2',.6,'>='),(21,'log_net_share',45,'<=')]:
        value=(measures.get(n) or {}).get(field)
        checks.append(dict(sessions=n,metric=field,value=value,threshold=threshold,operator=operator,
                           status='unknown' if value is None else 'pass' if (value>threshold if operator=='>' else value>=threshold if operator=='>=' else value<=threshold) else 'fail'))
    legacy=S.judge(S.preset('fast'),measures,v['technical'],{})
    return dict(symbol=v['symbol'],v4_status=v['status'],scores=v['scores'],reasons=v['reasons'],measures=measures,
                future_closes_ignored=len(snapshot['bars'])-len(bars),
                v3_fast_status=legacy['status'],v1_trajectory_checks=checks,
                limitation='V1 : contrôles de trajectoire comparés, pas reproduction du scanner ou de son classement réel')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot');parser.add_argument('--json',action='store_true');args=parser.parse_args()
    if args.snapshot:snapshots=[json.loads(Path(args.snapshot).read_text())]
    else:
        from engine.market.calendar import session_dates
        ds=session_dates('XPAR','2026-10-27',64)
        snapshots=[dict(schema=1,symbol=name,mic='XPAR',expected_last_date=ds[-1],bars=[[d,p,None] for d,p in zip(ds,prices)]) for name,prices in fixtures().items()]
    results=[evaluate(s) for s in snapshots]
    if args.json:print(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False))
    else:
        print('Titre | V4 | Simple /100 | Complexe /100 | V3 fast')
        for r in results:print(f"{r['symbol']} | {r['v4_status']} | {r['scores']['simple']} | {r['scores']['complex']} | {r['v3_fast_status']}")
        print('Comparaison pédagogique, aucun classement réel V1 revendiqué. Utiliser --json pour le détail.')


if __name__=='__main__':main()
