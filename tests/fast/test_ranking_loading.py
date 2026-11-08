"""Le chargement léger garde les notes/statuts et ne lit pas les historiques invisibles."""
from contextlib import contextmanager

import pytest
from engine.analytics import ranking_table as R


class Connection:
    @contextmanager
    def cursor(self):
        yield self

    def execute(self, *args):
        pass

    def fetchone(self):
        return {'n': 3}


@pytest.fixture
def ranking(monkeypatch):
    book = {i: dict(id=i, simple=s, complex=s, simple_status='ok', complex_status='ok') for i, s in [(1, 80), (2, 60), (3, None)]}
    monkeypatch.setattr(R, '_base', lambda conn, req: ('growth_v4', {}, book))
    fetched, curves = [], []
    def fetch(conn, ids):
        fetched.append(ids)
        return {i: {'symbol': str(i), 'name': str(i), 'mic': 'XPAR', 'kind': 'equity', 'currency': 'EUR',
                    'price': 100, 'avg_volume_3m': 1000, 'm': {21: {'slope': 0.2 if i == 1 else 0.1, 'r2': 0.8}}} for i in ids}
    def series(conn, ids, sessions):
        curves.append(ids)
        return {i: [100, 101] for i in ids}
    monkeypatch.setattr(R, '_fetch', fetch)
    monkeypatch.setattr(R.scores_admin, 'series', series)
    monkeypatch.setattr(R, 'latest_rates', lambda conn: {})
    return Connection(), fetched, curves


def test_light_table_keeps_scores_and_applies_draft_without_loading_curves(ranking):
    conn, fetched, curves = ranking
    spec = {'periods': {'month': {'enabled': True, 'slope': 0.15, 'r2': 0}}, 'extra': []}
    light = R.table(conn, {'ct_id': 'fast', 'spec': spec, 'include_curves': False})
    assert curves == [] and fetched == [[1, 2]]  # les titres sans note ne sont pas chargés
    full = R.table(conn, {'ct_id': 'fast', 'spec': spec})
    assert [{k: v for k, v in r.items() if k != 'curve'} for r in light['rows']] == [{k: v for k, v in r.items() if k != 'curve'} for r in full['rows']]
    assert [r['status'] for r in light['rows']] == ['retained', 'excluded']
    assert light['counts'] == full['counts'] == {'retained': 1, 'excluded': 1, 'undetermined': 0, 'all': 2}
    assert curves == [[1, 2]]


def test_page_curves_do_not_read_scores_or_other_titles(ranking, monkeypatch):
    conn, fetched, curves = ranking
    monkeypatch.setattr(R, '_base', lambda *args: pytest.fail('Les courbes ne doivent pas charger les scores'))
    assert R.curves(conn, {'ids': [2, 2, 1]}) == {'curves': {2: [100, 101], 1: [100, 101]}}
    assert curves == [[2, 1]] and fetched == []
    assert R.curves(conn, {'ids': []}) == {'curves': {}}


@pytest.mark.parametrize('ids', [None, '1', [True], [-1], ['1'], list(range(1, 102))])
def test_page_curves_reject_unbounded_or_invalid_ids(ids):
    with pytest.raises(ValueError):
        R.curves(None, {'ids': ids})
