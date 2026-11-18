"""Démonstration et recette de la matrice : données synthétiques, jamais production."""

import math
import os
import subprocess
from engine.shared.db import connect
from engine.market import hours
from engine.market.calendar import session_dates
from tests.integ.test_api import Client

assert os.environ.get('JIGO_TEST_DATABASE') == '1'
assert os.environ.get('JIGO_DB_NAME') == 'jigobourso_it'
subprocess.run(['php', 'scripts/create_user.php', 'matrix_demo', 'matrix-local-test-2026'], check=True)
now = hours.utcnow()
days = session_dates('XNYS', str(hours.latest_settled('XNYS', now)), 2200)
c = connect()
prices = {}
with c.cursor() as q:
    for i, symbol in enumerate(['VFC', 'ASO', 'BOX', 'FIGS', 'IBE', 'GIBO', 'DXC'], 1001):
        q.execute("INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,'equity',%s,'United States')", (i, 'matrix:' + symbol, 'Démonstration ' + symbol))
        currency = 'USD' if symbol == 'BOX' else 'EUR'
        q.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XNYS',%s,%s,'selected',1)", (i, i, symbol, currency))
        price, bars = 35.0, []
        for j, day in enumerate(days):
            rate = 0.0002 + (i - 1003) * 0.00011 + 0.0025 * math.sin(j / (11 + i % 7))
            price *= 1 + rate
            bars.append((i, day, price, price))
        # BOX volontairement court : les horizons longs doivent afficher —.
        if symbol == 'BOX':
            bars = bars[-500:]
        q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px) VALUES (%s,%s,%s,%s)', bars)
        q.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,%s,NOW(),'quote',%s)", (i, price, currency))
        prices[i] = price
    q.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD',CURDATE(),.92) ON DUPLICATE KEY UPDATE to_eur=.92")
c.commit()
c.close()
a = Client(os.environ.get('BASE', 'http://127.0.0.1:18089'))
assert a.call('auth/login', {'username': 'matrix_demo', 'password': 'matrix-local-test-2026'})[0] == 200
pf = a.call('portfolio/create', {'name': 'Démo synthétique — matrice', 'kind': 'virtual', 'initial_capital': 10000, 'start_date': '2025-01-01'})[1]['id']
legacy = a.call('portfolio/create', {'name': 'Démo legacy — matrice'})[1]['id']
for portfolio in [pf, legacy]:
    for lid, price in prices.items():
        b = dict(
            portfolio_id=portfolio,
            listing_id=lid,
            side='buy',
            quantity=2,
            unit_price=price * 0.9,
            fees=1,
            currency='USD' if lid == 1003 else 'EUR',
            fx_to_eur=0.92 if lid == 1003 else 1,
            trade_at='2025-06-02',
        )
        assert a.call('tx/add', b)[0] == 200
        if lid >= 1006:
            assert a.call('tx/add', b | dict(side='sell', unit_price=price, trade_at='2025-06-03'))[0] == 200
# Deuxième achat puis vente partielle, gardant uniquement le latent restant.
assert a.call('tx/add', dict(portfolio_id=pf, listing_id=1001, side='buy', quantity=1, unit_price=prices[1001] * 0.95, fees=1, trade_at='2025-06-04'))[0] == 200
assert a.call('tx/add', dict(portfolio_id=pf, listing_id=1001, side='sell', quantity=1, unit_price=prices[1001], fees=1, trade_at='2025-06-05'))[0] == 200
print(f'Matrice synthétique prête : portefeuille {pf}, legacy {legacy}')
