"""Étape 9 : mesure des requêtes SQL par appel d'API (recherche de N+1). Les plafonds ci-dessous sont les mesures du 14/11 avec une marge ; ils
décrivent le contrat actuel (docs/DATA_CONTRACT.md) et signalent toute dérive."""
import os

import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('disposable DB only', allow_module_level=True)

from engine.shared.db import connect
from tests.integ.test_api import login, server, world  # noqa: F401
from tests.integ.test_portfolio_audit import add

pytestmark = pytest.mark.integration


def questions():
    conn = connect()
    with conn.cursor() as q:
        q.execute("SHOW GLOBAL STATUS LIKE 'Questions'")
        n = int(q.fetchone()['Value'])
    conn.close()
    return n


def cost(client, route, params=''):
    before = questions()
    status, _ = client.call(route, params=params)
    assert status == 200
    return questions() - before - 2                          # les deux lectures de mesure elles-mêmes


def test_portfolio_list_grows_linearly_and_detail_is_bounded(world):
    a = login(world, 'alice', 'alice-secret-1234')
    ids = []
    for i in range(3):
        pf = a.call('portfolio/create', {'name': f'Mesure {i}'})[1]['id']
        add(a, pf, qty=1 + i)
        ids.append(pf)
    one = cost(a, 'portfolios')
    a.call('portfolio/create', {'name': 'Mesure 3'})
    two = cost(a, 'portfolios')
    per_portfolio = two - one
    print(f'portefeuilles : {one} requêtes ; +1 portefeuille = +{per_portfolio}')
    assert 0 < per_portfolio <= 12                          # coût fixe par portefeuille (valorisation) : linéaire, connu
    cost(a, 'portfolio', f'&id={ids[0]}')                    # appel d'échauffement : le premier appel d'une session coûte davantage (43 contre 33 requêtes)
    detail = cost(a, 'portfolio', f'&id={ids[0]}')
    print(f'détail d’un portefeuille : {detail} requêtes')
    assert detail <= 60
    # le détail ne dépend pas du nombre de transactions
    for _ in range(5):
        add(a, ids[0], qty=1)
    cost(a, 'portfolio', f'&id={ids[0]}')
    assert abs(cost(a, 'portfolio', f'&id={ids[0]}') - detail) <= 3
