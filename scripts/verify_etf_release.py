"""Rapport SELECT uniquement : couverture et exemples publics, aucune donnée utilisateur."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.shared.db import connect
from engine.analytics import etf

conn = connect()
try:
    with conn.cursor() as c:
        c.execute('START TRANSACTION READ ONLY')
    result = {'coverage': etf.coverage(conn)}
    with conn.cursor() as c:
        c.execute("SELECT l.id,l.symbol FROM listings l WHERE l.symbol IN ('QDVF.DE','ZPDE.DE','XUEN.DE','ESIE.DE','USL')")
        rows = c.fetchall()
    cache = etf.load(conn, [r['id'] for r in rows])
    result['examples'] = {r['symbol']: cache.get(r['id']) for r in rows}
    print(json.dumps(result, ensure_ascii=False, default=str, allow_nan=False))
finally:
    conn.rollback()
    conn.close()
