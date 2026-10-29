import datetime
import os

import pytest

from engine.market import collect
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.fakes import FakeYahoo

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 27, 18, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES ('USD','2026-10-27',0.90),('CHF','2026-10-27',1.05)")
    c.commit()
    yield c
    c.close()


def test_history_is_added_without_overwriting_and_not_asked_twice(conn):
    days = [datetime.date(2026, 4, 1) + datetime.timedelta(days=i) for i in range(0, 200, 7)]
    client = FakeYahoo(daily={'USDEUR=X': ('UTC', [(d, 0.92) for d in days] + [(datetime.date(2026, 10, 27), 0.91)])})
    added = collect.backfill_fx(conn, client, NOW)
    assert added == len(days)                                  # le taux du 27/10 existait déjà : conservé tel quel, pas écrasé
    with conn.cursor() as cur:
        cur.execute("SELECT to_eur FROM fx_rates WHERE currency='USD' AND rate_date='2026-10-27'")
        assert float(cur.fetchone()['to_eur']) == 0.90
        cur.execute("SELECT MIN(rate_date) d FROM fx_rates WHERE currency='USD'")
        assert cur.fetchone()['d'] == days[0]
    calls = len(client.calls)
    assert collect.backfill_fx(conn, client, NOW) == 0 and len(client.calls) == calls     # USD n'est plus redemandée ; CHF (sans réponse) attend une semaine
