"""Tableau du classement : toutes les lignes avec scores V4, rangs, valeurs des filtres et groupes ; rien n'est inventé."""
import os

import pytest

from engine.analytics import ranking_table as R
from engine.shared.db import connect
from tests.dbutil import reset_data
from tests.integ.test_scores_admin import seed

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)


def test_table_has_scores_ranks_groups_and_unknowns_stay_none():
    conn = connect()
    reset_data(conn)
    assert R.table(conn, {})['rows'] == []
    seed(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE instruments SET category='Technology' WHERE id=1")
        cur.execute("UPDATE latest_prices SET analyst_rating='1.6 - Buy' WHERE listing_id=1")      # texte de Yahoo, pas un nombre
    conn.commit()
    t = R.table(conn, {})
    rows = {r['symbol']: r for r in t['rows']}
    assert t['universe'] == 2 and set(rows) == {'UP.DE', 'ZIG.DE'}
    up = rows['UP.DE']
    assert up['analyst'] == '1.6 - Buy'
    assert up['simple'] is not None and up['rank_simple'] == 1 and up['rank_complex'] in (1, 2)
    assert up['group'] == {'country': 'country:europe', 'market': 'market:europe', 'sector': 'sector:technology', 'asset': 'asset:equity'}
    assert rows['ZIG.DE']['group']['sector'] == 'unknown'                           # secteur non renseigné : inconnu, pas « autres »
    assert up['price_eur'] == pytest.approx(250.0) and up['curve'] and set(up['perf']) == {'week', 'month', 'quarter'}
    assert up['avg_volume'] == 300000 and up['extra']['up_fraction'] is not None
    assert set(up['periods']) >= {'5', '21', '63'} and up['periods']['21']['slope'] is not None
    assert 'freshness' not in up['extra'] and 'secondary' not in up                  # fraîcheur : non fournie, jamais zéro


def test_sheet_carries_the_same_v4_scores_as_the_ranking():
    from engine.analytics import service
    conn = connect()
    reset_data(conn)
    seed(conn)
    t = {r['symbol']: r for r in R.table(conn, {})['rows']}
    sheet = service.instrument_sheet(conn, {'listing_id': 1, 'config': 'regular'})
    v4 = sheet['scores_v4']
    assert v4['simple']['score'] == pytest.approx(t['UP.DE']['simple'], abs=1e-3) and v4['complex']['score'] == pytest.approx(t['UP.DE']['complex'], abs=1e-3)
    assert v4['ranks']['simple']['rank'] == t['UP.DE']['rank_simple']
