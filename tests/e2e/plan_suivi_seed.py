"""Scénarios financiers du Plan de suivi (base jetable uniquement). Lancer depuis la racine : JIGO_TEST_DATABASE=1 JIGO_DB_NAME=jigobourso_it … python -m tests.e2e.plan_suivi_seed
Chaque titre est un scénario chiffré (voir tests/e2e/plan-suivi.cjs). Les séries sont synthétiques, déterministes, bruit ±1,2 % pour une volatilité réaliste."""
import datetime as dt, json, os, subprocess
from engine.shared.db import connect
assert os.environ.get('JIGO_TEST_DATABASE') == '1' and os.environ['JIGO_DB_NAME'] in ('jigobourso_it', 'jigobourso_plan_suivi') and os.environ.get('JIGO_DB_HOST') == '127.0.0.1'
from tests.dbutil import reset_data
c = connect(); reset_data(c)
for t in ('portfolio_transactions', 'portfolios', 'position_levels', 'position_watch', 'position_watch_log', 'lot_origin', 'lot_settings'):
    with c.cursor() as q: q.execute(f'DELETE FROM {t}')
c.commit()
subprocess.run(['php', 'scripts/create_user.php', 'plan_suivi', 'plan-suivi-local-2026', '--admin'], check=True)
today = dt.date.today(); days = []; d = today - dt.timedelta(days=1)
while len(days) < 420:
    if d.weekday() < 5: days.append(d)
    d -= dt.timedelta(days=1)
days.sort(); N = len(days)


def path(points, noise=0.012):
    out = []
    for (i0, p0), (i1, p1) in zip(points, points[1:]):
        for i in range(i0, i1): out.append(p0 * (p1 / p0) ** ((i - i0) / (i1 - i0)) * (1 + (noise if i % 2 else -noise)))
    out.append(points[-1][1]); return out


S = {}
S['RISEUP'] = path([(0, 100), (N - 1, 160)])
S['CORRECT'] = path([(0, 100), (N - 31, 160), (N - 1, 150)])
S['DEEP140'] = path([(0, 100), (N - 61, 160), (N - 1, 140)])
S['DEEP120'] = path([(0, 100), (N - 91, 160), (N - 61, 140), (N - 1, 120)])
S['MULTILOT'] = path([(0, 100), (N - 1, 170)])
S['PERSOSTOP'] = path([(0, 100), (N - 1, 160)])
for k in ('FAST', 'REGULAR', 'CALM', 'REBOUND', 'MOM6', 'MOM12', 'MOMRISK', 'NOSTRAT'):
    S[k] = path([(0, 100), (250, 200), (N - 1, 140)])
S['SHORT'] = path([(0, 100), (39, 112)])
S['CLOSEDX'] = path([(0, 100), (N - 1, 130)])
S['ETFSAFE'] = path([(0, 100), (N - 1, 130)], 0.004)
S['USDPOS'] = path([(0, 100), (N - 1, 200)])
S['LOSS'] = path([(0, 100), (N - 1, 80)])          # position en perte, sans protection perso
S['LOSSPERS'] = path([(0, 100), (N - 1, 82)])      # perte, protection perso (90) au-dessus du cours
S['CROWD'] = path([(0, 100), (N - 1, 103)], 0.002)  # repères très rapprochés : PRU ≈ cours ≈ plus-haut
LEN = {'SHORT': 40}
with c.cursor() as q:
    q.execute("SELECT id FROM users WHERE username='plan_suivi'"); uid = q.fetchone()['id']
    ids = {}
    for i, (sym, ser) in enumerate(S.items(), start=201):
        ids[sym] = i; cur = 'USD' if sym == 'USDPOS' else 'EUR'; kind = 'etf' if sym == 'ETFSAFE' else 'equity'
        q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,%s,%s,'France')", (i, 'ps:' + sym, kind, 'Scénario ' + sym))
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XPAR',%s,%s,'selected',1)", (i, i, sym, cur))
        n = LEN.get(sym, N); dd = days[N - n:]; ss = ser[-n:] if sym in LEN else ser
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(i, day, round(v, 4)) for day, v in zip(dd, ss)])
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m) VALUES (%s,%s,NOW(),'quote',%s,100000)", (i, round(ss[-1], 4), cur))
    for day in days + [today]: q.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',%s,.85)", (day,))
    q.execute("INSERT INTO portfolios(id,user_id,name,is_default,created_at,updated_at) VALUES (1,%s,'Scénarios de suivi',1,NOW(),NOW())", (uid,))

    def tx(sym, side, qty, price, idx, fx=1, fee=0):
        q.execute("INSERT INTO portfolio_transactions(portfolio_id,listing_id,symbol,name,side,quantity,unit_price,currency,fx_to_eur,fees,trade_at,created_at) VALUES (1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
                  (ids[sym], sym, 'Scénario ' + sym, side, qty, price, 'USD' if sym == 'USDPOS' else 'EUR', fx, fee, days[idx].isoformat() + ' 12:00:00'))
        return q.lastrowid
    for sym in ('RISEUP', 'CORRECT', 'DEEP140', 'DEEP120', 'PERSOSTOP', 'FAST', 'REGULAR', 'CALM', 'REBOUND', 'MOM6', 'MOM12', 'MOMRISK', 'NOSTRAT', 'ETFSAFE'): tx(sym, 'buy', 10, 100, 100)
    # multi-achats : trois stratégies d'origine, vente partielle FIFO (8 des 10 premiers titres)
    a = tx('MULTILOT', 'buy', 10, 100, 100); b = tx('MULTILOT', 'buy', 5, 130, 200); cc = tx('MULTILOT', 'buy', 5, 150, 300); tx('MULTILOT', 'sell', 8, 160, 330)
    for t, key in ((a, 'fast'), (b, 'regular'), (cc, 'rebound')):
        q.execute("INSERT INTO lot_origin(transaction_id,strategy_key,status,snapshot,set_by,created_at) VALUES (%s,%s,'official',NULL,'purchase',NOW())", (t, key))
    tx('LOSS', 'buy', 10, 100, 100); tx('LOSSPERS', 'buy', 10, 100, 100); tx('CROWD', 'buy', 10, 103, 100)
    tx('SHORT', 'buy', 10, 110, 410)
    tx('CLOSEDX', 'buy', 10, 100, 100); tx('CLOSEDX', 'sell', 10, 125, 380)
    tx('USDPOS', 'buy', 10, 100, 100, fx=.9)
    q.execute("INSERT INTO position_levels(portfolio_id,listing_id,stop_px,target_px,updated_at) VALUES (1,%s,110,200,NOW())", (ids['PERSOSTOP'],))
    q.execute("INSERT INTO position_levels(portfolio_id,listing_id,stop_px,target_px,updated_at) VALUES (1,%s,90,NULL,NOW())", (ids['LOSSPERS'],))
    for sym, key in (('RISEUP', 'regular'), ('CORRECT', 'regular'), ('DEEP140', 'regular'), ('DEEP120', 'regular'), ('MULTILOT', 'regular'), ('PERSOSTOP', 'fast'), ('FAST', 'fast'), ('REGULAR', 'regular'), ('CALM', 'calm'), ('REBOUND', 'rebound'),
                     ('MOM6', 'mom6'), ('MOM12', 'mom12'), ('MOMRISK', 'momrisk'), ('SHORT', 'regular'), ('ETFSAFE', 'regular'), ('USDPOS', 'regular'), ('LOSS', 'regular'), ('LOSSPERS', 'regular'), ('CROWD', 'calm')):
        q.execute("INSERT INTO position_watch(portfolio_id,listing_id,strategy_key,updated_at) VALUES (1,%s,%s,NOW())", (ids[sym], key))
c.commit(); c.close(); print(json.dumps(ids))
