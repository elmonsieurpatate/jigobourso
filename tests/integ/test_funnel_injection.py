"""Entonnoir de l'administration : `funnel.items` reçoit des paramètres venus du navigateur ; aucun ne doit atteindre le SQL autrement que lié ou validé."""
import os
import pytest
from engine.analytics.explorer import funnel
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

PAYLOADS = ["' OR '1'='1", "'; DROP TABLE catalogue_raw; --", '" OR ""="', "%' UNION SELECT 1,2,3,4,5,6,7,8,9,10 -- ", '\\', "x') OR 1=1 -- ", 'a_b%c']


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        cur.execute("INSERT INTO catalogue_raw(group_key,kind,mic,symbol,isin,name,country,category,currency) VALUES ('isin:FR0000000001','equity','XPAR','AIR.PA','FR0000000001','Airbus','France','Industrials','EUR')")
    c.commit()
    yield c
    reset_data(c)
    c.close()


def raw_count(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        return cur.fetchone()['n']


@pytest.mark.parametrize('payload', PAYLOADS)
@pytest.mark.parametrize('field', ('q', 'kind', 'mic'))
def test_text_filters_are_bound_not_interpolated(conn, payload, field):
    for stage, step in (('catalogue', 'raw'), ('catalogue', 'kept'), ('yahoo', 'asked')):
        out = funnel.items(conn, stage, step, **{field: payload})
        assert out['total'] == 0 and not out['rows']          # l'injection n'élargit jamais la sélection
    assert raw_count(conn) == 1                                  # et ne détruit rien


def test_search_text_still_finds_the_row(conn):
    assert funnel.items(conn, 'catalogue', 'raw', q='airb')['total'] == 1
    assert funnel.items(conn, 'catalogue', 'raw', kind='equity', mic='XPAR')['total'] == 1
    assert funnel.items(conn, 'catalogue', 'raw', kind='equity', mic='XETR')['total'] == 0


@pytest.mark.parametrize('payload', PAYLOADS)
def test_unknown_step_is_refused_before_any_query(conn, payload):
    for stage in ('catalogue', 'yahoo'):
        with pytest.raises(ValueError):
            funnel.items(conn, stage, payload)
    assert raw_count(conn) == 1


@pytest.mark.parametrize('payload', PAYLOADS)
def test_quality_never_reaches_the_sql(conn, payload):
    # `history` n'est pas une étape de YAHOO_WHERE : la branche `quality` est aujourd'hui inatteignable (code mort à retirer à l'Étape 3).
    assert funnel.items(conn, 'yahoo', 'asked', quality=payload)['total'] == 0
    with pytest.raises(ValueError):
        funnel.items(conn, 'yahoo', 'history', quality=payload)


def test_wildcards_only_search_is_an_empty_filter(conn):
    assert funnel.items(conn, 'catalogue', 'raw', q='%%')['total'] == 1


@pytest.mark.parametrize('page', ('1; DROP TABLE catalogue_raw', "1 OR 1=1", '', None, 'abc'))
def test_page_must_be_an_integer(conn, page):
    with pytest.raises((ValueError, TypeError)):
        funnel.items(conn, 'catalogue', 'raw', page=page)
    assert raw_count(conn) == 1


def test_page_is_clamped_to_first_page(conn):
    assert funnel.items(conn, 'catalogue', 'raw', page=-5)['page'] == 1
    assert funnel.items(conn, 'catalogue', 'raw', page='2')['page'] == 2
