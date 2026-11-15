"""Étape 9 : mesure des requêtes SQL par appel d'API (recherche de N+1). Les plafonds ci-dessous sont les mesures du 14/11 avec une marge ; ils
décrivent le contrat actuel (docs/DATA_CONTRACT.md) et signalent toute dérive."""

import os

import pytest

if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('disposable DB only', allow_module_level=True)

from engine.shared.db import connect
from tests.integ.test_api import login, server as api_server, world  # noqa: F401
from tests.integ.test_portfolio_audit import add

pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def query_meter():
    """Compte un utilisateur réservé à cette sonde, jamais les healthchecks du serveur.

    USER_STATISTICS est spécifique à MariaDB (cible du projet). La configuration
    et le compte temporaire sont restaurés même si une assertion échoue.
    """
    conn = connect()
    user = 'jigo_query_probe'
    with conn.cursor() as q:
        q.execute('SELECT @@GLOBAL.userstat AS enabled')
        enabled = q.fetchone()['enabled']
        q.execute("CREATE USER %s@'%%' IDENTIFIED BY %s", (user, 'probe-local-only'))
        database = os.environ['JIGO_DB_NAME'].replace('`', '``')
        q.execute(f"GRANT ALL ON `{database}`.* TO %s@'%%'", (user,))
        q.execute('SET GLOBAL userstat=1')
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv('JIGO_DB_USER', user)
            patch.setenv('JIGO_DB_PASSWORD', 'probe-local-only')
            yield conn, user
    finally:
        with conn.cursor() as q:
            q.execute("DROP USER %s@'%%'", (user,))
            q.execute('SET GLOBAL userstat=%s', (enabled,))
        conn.close()


@pytest.fixture(scope='module')
def server(query_meter):
    yield from api_server.__wrapped__()


def questions(meter):
    conn, user = meter
    with conn.cursor() as q:
        q.execute('SELECT SELECT_COMMANDS + UPDATE_COMMANDS + OTHER_COMMANDS AS n FROM information_schema.USER_STATISTICS WHERE USER=%s', (user,))
        row = q.fetchone()
    return row['n'] if row else 0


def cost(client, route, meter, params=''):
    before = questions(meter)
    status, _ = client.call(route, params=params)
    assert status == 200
    return questions(meter) - before


def test_query_meter_ignores_other_database_clients(query_meter):
    before = questions(query_meter)
    with query_meter[0].cursor() as q:
        for _ in range(20):
            q.execute('SELECT 1')  # même bruit que les sondes de santé MariaDB
    assert questions(query_meter) == before


def test_portfolio_list_grows_linearly_and_detail_is_bounded(world, query_meter):
    a = login(world, 'alice', 'alice-secret-1234')
    ids = []
    for i in range(3):
        pf = a.call('portfolio/create', {'name': f'Mesure {i}'})[1]['id']
        add(a, pf, qty=1 + i)
        ids.append(pf)
    one = cost(a, 'portfolios', query_meter)
    a.call('portfolio/create', {'name': 'Mesure 3'})
    two = cost(a, 'portfolios', query_meter)
    per_portfolio = two - one
    print(f'portefeuilles : {one} requêtes ; +1 portefeuille = +{per_portfolio}')
    assert 0 < per_portfolio <= 12  # coût fixe par portefeuille (valorisation) : linéaire, connu
    cost(a, 'portfolio', query_meter, f'&id={ids[0]}')  # appel d'échauffement : le premier appel d'une session coûte davantage
    detail = cost(a, 'portfolio', query_meter, f'&id={ids[0]}')
    print(f'détail d’un portefeuille : {detail} requêtes')
    assert detail <= 60
    # le détail ne dépend pas du nombre de transactions
    for _ in range(5):
        add(a, ids[0], qty=1)
    cost(a, 'portfolio', query_meter, f'&id={ids[0]}')
    assert abs(cost(a, 'portfolio', query_meter, f'&id={ids[0]}') - detail) <= 3


def test_engine_route_reports_its_timing_breakdown(world):
    """Une lenteur doit être attribuable : attente d'emplacement, moteur Python, décodage, total (en-tête Server-Timing)."""
    import re
    import urllib.request

    a = login(world, 'alice', 'alice-secret-1234')
    req = urllib.request.Request(f'{world}/api.php?r=strategy/presets')
    resp = a.opener.open(req, timeout=60)
    timing = resp.headers['Server-Timing']
    assert re.fullmatch(r'app;dur=\d+, slot;dur=\d+, engine;dur=\d+, decode;dur=\d+', timing), timing
