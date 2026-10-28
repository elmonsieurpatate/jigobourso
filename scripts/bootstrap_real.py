"""Amorçage de la base LOCALE avec de vraies données Yahoo (lecture seule côté Yahoo) : Quote, préfiltre, clôtures 2 ans, mesures.
Usage : JIGO_DB_*=… python scripts/bootstrap_real.py   (base jetable uniquement)"""
import sys, time
sys.path.insert(0, '.')
from engine.shared.db import connect
from engine.market import collect, hours
from engine.market.yahoo import YahooClient
from engine.catalogue import loader
from engine.analytics import compute

conn, client, now = connect(), YahooClient(), hours.utcnow()
t0 = time.time()
with conn.cursor() as cur:
    cur.execute("SELECT id AS listing_id, mic, symbol FROM listings WHERE status='candidate' AND is_primary=1")
    rows = cur.fetchall()
print('quotes', len(rows), flush=True)
ok, err = collect.refresh_quotes(conn, client, rows, now)
print('quotes ok/err', ok, err, round(time.time() - t0), 's', flush=True)
print('fx', collect.refresh_fx(conn, client, now), flush=True)
print('prefilter', collect.apply_prefilter(conn), flush=True)
print('primaries', loader.assign_primaries(conn), flush=True)
rows = collect.collection_set(conn)
print('collection set', len(rows), flush=True)
ok, lines, err = collect.collect_daily(conn, client, rows, now, range_='2y')
print('daily ok/lines/err', ok, lines, err, round(time.time() - t0), 's', flush=True)
print('prune', collect.prune_daily(conn, now), flush=True)
print('compute', compute.compute_all(conn, now), round(time.time() - t0), 's', flush=True)
