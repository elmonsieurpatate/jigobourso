"""Quatre ETF synthétiques, seulement dans la base jetable du runner."""
import datetime as dt
import json
import math
import os
assert os.environ.get('JIGO_TEST_DATABASE') == '1' and os.environ.get('JIGO_DB_NAME') == 'jigobourso_it'
from engine.shared.db import connect
from engine.analytics import etf
c = connect()
with c.cursor() as q:
    q.execute('SELECT price_date,close_px FROM daily_prices WHERE listing_id=1 ORDER BY price_date')
    bars = q.fetchall()
    for lid in range(1001, 1005):
        q.execute("INSERT INTO instruments(id,group_key,kind,name,category) VALUES (%s,%s,'etf',%s,%s)", (lid, 'browser:' + str(lid), 'ETF test ' + str(lid), 'Energy' if lid < 1004 else 'Commodities'))
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,'EUR','selected',1)", (lid, lid, 'ETF' + str(lid) + '.PA'))
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, b['price_date'], float(b['close_px']) * (1 + .003 * math.sin(i))) for i, b in enumerate(bars)])
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,149,NOW(),'quote','EUR')", (lid,))
    profile = {'family': 'Test synthétique', 'holdings': [{'name': 'Entreprise test', 'weight': None}], 'stock_position': 100, 'sectors': {'Énergie': 100}, 'expense_ratio': None}
    q.execute("INSERT INTO etf_profiles VALUES (1001,NOW(),2,'ok',%s)", (json.dumps(profile),))
    q.execute("SELECT id FROM users WHERE username='review_user'")
    uid = q.fetchone()['id']
    q.execute("INSERT INTO portfolios(user_id,name,is_default,created_at,updated_at) VALUES (%s,'Test diversification',1,NOW(),NOW())", (uid,))
    pid = q.lastrowid
    for lid in (1001, 1002):
        q.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,side,quantity,unit_price,currency,fx_to_eur,trade_at,created_at) VALUES (%s,%s,%s,'buy',1,100,'EUR',1,'2026-10-28',NOW())", (pid, lid, 'ETF' + str(lid) + '.PA'))
c.commit()
etf.build(c, dt.datetime.utcnow())
c.close()
