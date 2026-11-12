"""Classement par catégorie et courbes (administration des scores V4) : rang général inchangé par la catégorie, courbes réelles seulement."""
import json
import os

from engine.analytics.scoring import score_categories
from engine.analytics.admin import scores_admin as A

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Cur:
    def __init__(self, conn): self.c = conn
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, args=()):
        self.c.sql = sql
        if 'corporate_events' in sql:
            self.rows = []
        elif 'daily_prices' in sql:
            ids = [a for a in args if isinstance(a, int)]
            import datetime
            self.rows = [{'listing_id': i, 'price_date': datetime.date(2026, 9, 1) + datetime.timedelta(days=k), 'close_px': 100 + k, 'adj_close_px': 100 + k} for i in ids for k in range(self.c.points)]
        else:
            ids = list(args)
            self.rows = [{'id': i, 'symbol': 'S%d' % i, 'mic': 'XPAR', 'name': 'N%d' % i, 'kind': 'equity', 'isin': None} for i in ids]
    def fetchall(self): return self.rows


class Conn:
    points = 40
    def cursor(self): return Cur(self)


def book(values):
    return {i: dict(id=i, simple=v, complex=None if v is None else v / 2, simple_status='ok', complex_status='ok', simple_coverage=1, complex_coverage=1)
            for i, v in enumerate(values, 1)}


def cats():
    d = json.load(open(os.path.join(ROOT, 'app/config/explorer_secondary_filters.json')))
    return score_categories.measure(d, 'simple')[0]


def test_series_keeps_last_sessions_plus_one_and_never_invents():
    out = A.series(Conn(), [1, 2], 21)
    assert len(out[1]) == 22 and out[1][-1] == 139
    short = Conn(); short.points = 3
    assert len(A.series(short, [1], 21)[1]) == 3
    assert A.series(Conn(), [], 21) == {} and A.series(Conn(), [1], 0) == {1: []}


def test_listing_category_keeps_general_rank_and_counts():
    b = book([90, 20, 3, 0.5, None, 12])
    c = cats()
    allr = A._listing(Conn(), b, 'simple', None, 0, 25, c, 21)
    assert [r['id'] for r in allr['rows']] == [1, 2, 6, 3, 4] and allr['total'] == 5
    assert sum(x['count'] for x in allr['categories']) == 5
    cid = score_categories.assign(3, c)
    sub = A._listing(Conn(), b, 'simple', cid, 0, 25, c, 21)
    assert [r['id'] for r in sub['rows']] == [3] and sub['rows'][0]['rank'] == 4
    assert all(r['curve'] for r in sub['rows'])


def test_listing_paginates_without_changing_ranks():
    b = book(list(range(50, 0, -1)))
    p2 = A._listing(Conn(), b, 'simple', None, 10, 5, cats(), 5)
    assert [r['rank'] for r in p2['rows']] == [11, 12, 13, 14, 15] and p2['total'] == 50


def test_rank_of_and_suggestions_carry_scores_and_curve():
    b = book([10, 30, 20])
    assert A._rank_of(b, 2)['simple'] == {'rank': 1, 'of': 3}
    s = A._suggestions(Conn(), b, n=2, sessions=5)
    assert [x['id'] for x in s] == [2, 3] and s[0]['rank'] == 1 and s[0]['complex'] == 15 and len(s[0]['curve']) == 6


def test_dated_series_has_iso_dates_and_prices():
    import datetime
    class C2(Conn):
        def cursor(self):
            c = Cur(self)
            orig = c.execute
            def ex(sql, args=()):
                orig(sql, args)
                if 'daily_prices' in sql:
                    c.rows = [{'listing_id': 1, 'price_date': datetime.date(2026, 10, 1) + datetime.timedelta(days=k), 'close_px': 100 + k, 'adj_close_px': 100 + k} for k in range(30)]
            c.execute = ex
            return c
    out = A.dated_series(C2(), 1, 21)
    assert len(out) == 22 and out[-1] == {'d': '2026-10-30', 'p': 129.0} and out[0]['d'] == '2026-10-09'
    assert A.dated_series(C2(), 1, 0) == []
