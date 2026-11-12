import json

from engine.analytics.admin import service


class Cursor:
    def __init__(self, profiles): self.profiles = profiles
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, args=()): self.args = list(args)
    def fetchall(self): return [dict(listing_id=i, data_json=json.dumps({'category': c})) for i, c in self.profiles.items() if i in self.args]


class Conn:
    def __init__(self, profiles): self.profiles = profiles
    def cursor(self): return Cursor(self.profiles)


def test_filters_scope_full_universe_by_region_and_aum_decile(monkeypatch):
    entries = [
        dict(id=1, instrument_id=101, kind='etf', mic='XPAR', country=None, category=None, status='retained', score=90, net_assets=900, currency='USD', price_currency='USD', symbol='A', name='US ETF', isin=None, group='etf', fails=[]),
        dict(id=2, instrument_id=102, kind='etf', mic='XETR', country=None, category=None, status='retained', score=80, net_assets=100, currency='EUR', price_currency='EUR', symbol='B', name='Europe ETF', isin=None, group='etf', fails=[]),
        dict(id=3, instrument_id=103, kind='etf', mic='XETR', country=None, category=None, status='retained', score=70, net_assets=None, currency='EUR', price_currency='EUR', symbol='C', name='World ETF', isin=None, group='etf', fails=[]),
        dict(id=4, instrument_id=104, kind='equity', mic='XPAR', country='France', category=None, status='retained', score=60, net_assets=None, currency='EUR', price_currency='EUR', symbol='D', name='EU equity', isin=None, group='equity', fails=[]),
        dict(id=5, instrument_id=105, kind='equity', mic='XNAS', country='United States', category=None, status='retained', score=50, net_assets=None, currency='USD', price_currency='USD', symbol='E', name='US equity', isin=None, group='equity', fails=[]),
        dict(id=6, instrument_id=102, kind='etf', mic='XNAS', country=None, category=None, status='retained', score=40, net_assets=120, currency='USD', price_currency='USD', symbol='B.US', name='Europe ETF alternate listing', isin=None, group='etf', fails=[]),
    ]
    monkeypatch.setattr(service, 'cached_verdicts', lambda *args: entries)
    monkeypatch.setattr(service, '_reference_window', lambda *args: 21)
    monkeypatch.setattr(service, 'judge_universe', lambda conn, config, ids: [dict(key=i, rank=i, score=i) for i in ids])
    conn = Conn({1: 'United States Stock', 2: 'Europe Stock', 3: 'World Stock', 6: 'Europe Stock'})
    all_entries, largest, _, _ = service.scoped_entries(conn, {}, {'kind': 'large_etf'}, rates={'USD': 0.9}, aux={})
    assert len(all_entries) == 6
    assert [x['symbol'] for x in largest] == ['A']  # 2 instruments (doublon B / B.US compté une fois) : le premier dixième n'en garde qu'un
    _, us, _, _ = service.scoped_entries(conn, {}, {'kind': 'etf', 'geo_region': 'us'}, rates={'USD': 0.9}, aux={})
    assert [x['symbol'] for x in us] == ['A']  # place Paris sans effet sur zone du fonds
    _, europe, _, _ = service.scoped_entries(conn, {}, {'kind': 'etf', 'geo_region': 'eu'}, rates={'USD': 0.9}, aux={})
    assert [x['symbol'] for x in europe] == ['B', 'B.US']
    _, worldwide, _, _ = service.scoped_entries(conn, {}, {'kind': 'etf', 'geo_region': 'us'}, rates={'USD': 0.9}, aux={})
    assert all(x['symbol'] != 'C' for x in worldwide)
    _, us_equities, _, _ = service.scoped_entries(conn, {}, {'kind': 'equity', 'geo_region': 'us'}, rates={'USD': 0.9}, aux={})
    assert [x['symbol'] for x in us_equities] == ['E']


def test_currency_unknown_does_not_enter_aum_decile(monkeypatch):
    entries = [
        dict(id=1, instrument_id=1, kind='etf', mic='XETR', country=None, category=None, status='retained', score=90, net_assets=1000, currency='EUR', price_currency='EUR', symbol='Known', name='Known AUM', isin=None, group='etf', fails=[]),
        dict(id=2, instrument_id=2, kind='etf', mic='XETR', country=None, category=None, status='retained', score=80, net_assets=999999, currency='XYZ', price_currency='XYZ', symbol='Unknown', name='Unknown FX', isin=None, group='etf', fails=[]),
    ]
    monkeypatch.setattr(service, 'cached_verdicts', lambda *args: entries)
    monkeypatch.setattr(service, '_reference_window', lambda *args: 21)
    monkeypatch.setattr(service, 'judge_universe', lambda conn, config, ids: [dict(key=i, rank=i, score=i) for i in ids])
    _, selected, _, _ = service.scoped_entries(Conn({}), {}, {'kind': 'large_etf'}, rates={}, aux={})
    assert [x['symbol'] for x in selected] == ['Known']


def _etfs(amounts):
    return [dict(id=i, instrument_id=1000 + i, kind='etf', mic='XETR', country=None, category=None, status='retained', score=1, net_assets=a, currency='EUR', price_currency='EUR',
                 symbol=f'E{i}', name=f'ETF {i}', isin=None, group='etf', fails=[]) for i, a in enumerate(amounts, 1)]


def test_large_etf_keeps_only_the_top_tenth_by_aum(monkeypatch):
    entries = _etfs([float(a) for a in range(1, 101)])           # encours 1 … 100
    monkeypatch.setattr(service, 'cached_verdicts', lambda *args: entries)
    monkeypatch.setattr(service, '_reference_window', lambda *args: 21)
    monkeypatch.setattr(service, 'judge_universe', lambda conn, config, ids: [dict(key=i, rank=i, score=i) for i in ids])
    _, selected, _, _ = service.scoped_entries(Conn({}), {}, {'kind': 'large_etf'}, rates={}, aux={})
    assert sorted(x['net_assets'] for x in selected) == [float(a) for a in range(91, 101)]


def test_large_etf_rounds_the_tenth_up_and_keeps_ties(monkeypatch):
    entries = _etfs([5.0, 50.0, 50.0] + [1.0] * 12)               # 15 ETF : 2 au premier dixième, égalité au seuil conservée
    monkeypatch.setattr(service, 'cached_verdicts', lambda *args: entries)
    monkeypatch.setattr(service, '_reference_window', lambda *args: 21)
    monkeypatch.setattr(service, 'judge_universe', lambda conn, config, ids: [dict(key=i, rank=i, score=i) for i in ids])
    _, selected, _, _ = service.scoped_entries(Conn({}), {}, {'kind': 'large_etf'}, rates={}, aux={})
    assert sorted(x['net_assets'] for x in selected) == [50.0, 50.0]


def test_max_fee_keeps_cheap_etfs_and_ignores_equities(monkeypatch):
    entries = _etfs([10.0, 20.0, 30.0]) + [dict(id=9, instrument_id=9, kind='equity', mic='XPAR', country='France', category=None, status='retained', score=1, net_assets=None, currency='EUR',
                                                 price_currency='EUR', symbol='EQ', name='Action', isin=None, group='equity', fails=[])]
    aux = {1: {'fee': 0.07}, 2: {'fee': 0.45}, 3: {}, 9: {}}                     # ETF 3 : frais inconnus
    monkeypatch.setattr(service, 'cached_verdicts', lambda *args: entries)
    monkeypatch.setattr(service, '_reference_window', lambda *args: 21)
    monkeypatch.setattr(service, 'judge_universe', lambda conn, config, ids: [dict(key=i, rank=i, score=i) for i in ids])
    _, selected, _, _ = service.scoped_entries(Conn({}), {}, {'max_fee': '0.3'}, rates={}, aux=aux)
    assert [x['symbol'] for x in selected] == ['E1', 'EQ']
