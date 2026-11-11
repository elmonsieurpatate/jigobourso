#!/bin/bash
# LECTURE SEULE : diagnostic des cours d'un ISIN (cotations, sauts de cours, journal des splits, événements, série récente).
# Usage : bash diag_isin.sh LU1230136894
ISIN="${1:?ISIN}"
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
set -a; . "$SITE/private/env"; set +a
ISIN="$ISIN" PYTHONPATH="$SITE" "$SITE/.venv/bin/python" - <<'PY' 2>&1 | grep -v "Warning\|align"
import os
from engine.shared.db import connect
isin = os.environ['ISIN']
c = connect()
with c.cursor() as cur:
    cur.execute('SET SESSION TRANSACTION READ ONLY')
    cur.execute("SELECT l.id, l.mic, l.symbol, l.currency, l.status, l.is_primary, i.name, i.kind FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE i.isin=%s", (isin,))
    ls = cur.fetchall()
    print('COTATIONS :', len(ls))
    for l in ls: print(' ', l)
    for l in ls:
        lid = l['id']; print('\n=== listing', lid, l['mic'], l['symbol'], l['currency'])
        cur.execute("SELECT price_date, close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date", (lid,))
        rows = [(r['price_date'], float(r['close_px'])) for r in cur.fetchall()]
        print('séances :', len(rows), '· du', rows[0][0] if rows else '-', 'au', rows[-1][0] if rows else '-')
        print('SAUTS (rapport entre deux séances > ×1,25 ou < ÷1,25) :')
        n = 0
        for (d0, p0), (d1, p1) in zip(rows, rows[1:]):
            if p0 > 0 and (p1 / p0 > 1.25 or p1 / p0 < 0.8):
                print('  ', d0, p0, '->', d1, p1, 'ratio', round(p1 / p0, 4)); n += 1
        if not n: print('   aucun')
        print('Extrêmes : min', min(p for _, p in rows) if rows else '-', 'max', max(p for _, p in rows) if rows else '-')
        print('15 premières séances :', [(str(d), p) for d, p in rows[:15]])
        print('15 dernières séances :', [(str(d), p) for d, p in rows[-15:]])
        cur.execute("SELECT * FROM split_log WHERE listing_id=%s ORDER BY event_date", (lid,))
        print('split_log :'); [print('  ', r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM corporate_events WHERE listing_id=%s ORDER BY event_date", (lid,))
        print('corporate_events :'); [print('  ', r) for r in cur.fetchall()]
        cur.execute("SELECT quality, break_age, last_close_date FROM series_state WHERE listing_id=%s", (lid,))
        print('series_state :', cur.fetchall())
PY
