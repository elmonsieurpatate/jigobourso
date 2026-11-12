"""Motif affiché quand une mesure manque : une rupture de cours est présentée comme telle (jamais comme un « calendrier indisponible »), sans changer le moindre statut, rang ou score."""
import datetime
import math
import os

import pytest

from engine.analytics.series import compute
from engine.analytics.admin import service
from engine.analytics.explorer import strategy
from engine.shared.db import connect
from tests.dbutil import reset_data

pytestmark = pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):
    pytest.skip('base jetable non configurée', allow_module_level=True)

NOW = datetime.datetime(2026, 10, 28, 2, 10, tzinfo=datetime.timezone.utc)


@pytest.fixture(autouse=True)
def fixed_market_clock(monkeypatch):
    monkeypatch.setattr(service.hours, 'utcnow', lambda: NOW)


def sessions(n):
    import exchange_calendars as xc
    cal = xc.get_calendar('XETR', start='2025-01-02', end='2026-12-31')
    return [d.date() for d in cal.sessions if d.date() <= datetime.date(2026, 10, 27)][-n:]


def path(n, daily, jump_at=None, factor=0.5):
    out = [100 * math.exp(daily * i) for i in range(n)]
    if jump_at is not None:
        out = [c * (factor if i >= jump_at else 1.0) for i, c in enumerate(out)]
    return out


UNIVERSE = (   # id, symbole, nombre de séances, cours
    (1, 'CALM.DE', 360, path(360, 0.0010)),
    (2, 'RECENT.DE', 360, path(360, 0.0010, 330)),        # saut de ÷2 il y a 29 séances : traverse les fenêtres de 63, 126 et 252 séances, pas celle de 21
    (3, 'OLD.DE', 360, path(360, 0.0010, 150)),           # saut il y a 209 séances : traverse la seule fenêtre de 252 séances
    (4, 'YOUNG.DE', 100, path(100, 0.0010)),               # historique trop court pour 126 et 252 séances
    (5, 'IPO.DE', 100, path(100, 0.0010, 60)),             # historique trop court ET saut récent (introduction en bourse agitée) : le motif est l'historique, pas le calendrier ni la rupture
)


@pytest.fixture
def conn():
    c = connect()
    reset_data(c)
    with c.cursor() as cur:
        for lid, symbol, n, closes in UNIVERSE:
            cur.execute('INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,%s,%s,%s)', (lid, f'sym:XETR:{symbol}', 'equity', symbol.split('.')[0].title(), 'Germany'))
            cur.execute("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,'XETR',%s,'EUR','selected',1)", (lid, lid, symbol))
            days = sessions(360)[-n:]
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(lid, d, round(x, 6)) for d, x in zip(days, closes)])
            cur.execute("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,quote_at) VALUES (%s,%s,%s,'quote','EUR',500000,%s)",
                        (lid, round(closes[-1], 6), datetime.datetime(2026, 10, 27, 16, 30), datetime.datetime(2026, 10, 27, 20, 0)))
    c.commit()
    compute.compute_all(c, NOW)
    yield c
    c.close()


def verdicts(conn, name):
    return {v['symbol']: v for v in service.judge_universe(conn, strategy.validate(strategy.preset(name)))}


def data_reasons(v):
    return [(r['period'], r['metric']) for r in v['reasons'] if r['criterion'] == 'data']


def test_missing_reason_distinguishes_history_break_calendar_and_coverage():
    f = service._missing_reason
    assert f(50, 126, None, None) == 'history'                       # moins de 127 clôtures
    assert f(50, 126, None, 10) == 'history'                         # l'historique court passe avant tout
    assert f(300, 126, None, 40) == 'break'                          # rupture plus récente que la fenêtre
    assert f(300, 126, None, 126) == 'calendar'                      # rupture plus ancienne que la fenêtre : elle ne la traverse pas
    assert f(300, 126, None, None) == 'calendar'                     # aucune rupture : le calendrier est bien la cause
    assert f(300, 126, {'slope': 1.0}, 40) == 'coverage'             # mesure présente mais incomplète


def test_momentum_names_the_break_not_the_calendar(conn):
    for name, windows in (('momentum', {'RECENT.DE'}), ('momentum12', {'RECENT.DE', 'OLD.DE'})):
        v = verdicts(conn, name)
        for symbol in windows:
            assert v[symbol]['status'] == 'unknown' and v[symbol]['rank'] is None, (name, symbol)
            reasons = data_reasons(v[symbol])
            assert reasons and all(metric == 'break' for _, metric in reasons), (name, symbol, reasons)       # période ET motif général disent « rupture »
        assert not any(metric == 'break' for _, metric in data_reasons(v['CALM.DE'])) and v['CALM.DE']['status'] == 'retained'
    assert verdicts(conn, 'momentum')['OLD.DE']['status'] == 'retained'                                         # la rupture d'il y a 209 séances ne touche pas la fenêtre de 126 séances
    young = verdicts(conn, 'momentum')['YOUNG.DE']
    assert young['status'] == 'unknown' and not any(metric == 'break' for _, metric in data_reasons(young))     # historique court : jamais présenté comme une rupture


def test_filtering_profiles_name_the_break_only_for_the_window_it_crosses(conn):
    v = verdicts(conn, 'regular')['RECENT.DE']                         # fenêtres de 21 et 63 séances ; saut il y a 29 séances
    assert v['status'] == 'unknown'
    assert sorted(data_reasons(v)) == [('quarter', 'break')]           # le mois n'est pas traversé : aucun motif pour lui
    assert verdicts(conn, 'regular')['OLD.DE']['status'] != 'unknown'


def test_status_rank_and_score_are_untouched_by_the_new_reasons(conn):
    expected = {'momentum': {'CALM.DE': 'retained', 'RECENT.DE': 'unknown', 'OLD.DE': 'retained', 'YOUNG.DE': 'unknown', 'IPO.DE': 'unknown'},
                'momentum12': {'CALM.DE': 'retained', 'RECENT.DE': 'unknown', 'OLD.DE': 'unknown', 'YOUNG.DE': 'unknown', 'IPO.DE': 'unknown'}}
    for name, statuses in expected.items():
        v = verdicts(conn, name)
        assert {s: x['status'] for s, x in v.items()} == statuses
        assert [x['rank'] for s, x in sorted(v.items()) if x['status'] != 'retained'] == [None] * sum(1 for x in statuses.values() if x != 'retained')
    res = service.explore(conn, {'config': 'momentum', 'view': {'status': 'unknown', 'kind': 'equity', 'page_size': 50}})
    by = {r['symbol']: r for r in res['rows']}
    assert by['RECENT.DE']['quality'] == 'break' and 'RECENT.DE' in by and 'CALM.DE' not in by
    assert any(r['metric'] == 'break' for r in by['RECENT.DE']['reasons'])


def test_a_short_history_is_never_explained_as_calendar_or_break(conn):
    for name in ('momentum', 'momentum12'):
        ipo = verdicts(conn, name)['IPO.DE']
        assert ipo['status'] == 'unknown'
        metrics = {metric for _, metric in data_reasons(ipo)}
        assert 'calendar' not in metrics and 'break' not in metrics, (name, metrics)           # « momentum » (mesure absente) ou « history », jamais « calendrier »
