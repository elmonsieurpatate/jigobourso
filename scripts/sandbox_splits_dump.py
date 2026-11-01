"""Verdicts de TOUS les profils sur la base d'essai, pour comparer deux versions du code (même base, même instant). Lecture seule. Usage : PYTHONPATH=<copie du code> python sandbox_splits_dump.py sortie.json"""
import datetime
import json
import os
import sys

from engine.analytics import service, strategy
from engine.shared.db import connect

NOW = datetime.datetime.fromisoformat(os.environ['SANDBOX_NOW'])
service.hours.utcnow = lambda: NOW
conn = connect()
with conn.cursor() as cur:
    cur.execute('SET SESSION TRANSACTION READ ONLY')
out = {}
for name in strategy.PRESETS:
    out[name] = {str(v['key']): {'symbol': v['symbol'], 'status': v['status'], 'rank': v['rank'], 'score': None if v['score'] is None else round(v['score'], 6), 'quality': v['row']['quality'],
                                 'criteria': sorted((str(r['period']), r['criterion'], r['result']) for r in v['reasons']),
                                 'missing': sorted((str(r['period']), r['metric']) for r in v['reasons'] if r['criterion'] == 'data')} for v in service.judge_universe(conn, strategy.validate(strategy.preset(name)))}
json.dump(out, open(sys.argv[1], 'w'), sort_keys=True)
print('verdicts écrits :', sum(len(v) for v in out.values()), '(titre × profil)')
