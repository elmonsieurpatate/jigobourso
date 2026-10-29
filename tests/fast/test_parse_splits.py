import datetime

from engine.market import splits
from engine.market.yahoo import parse_splits

# Réponse réelle de l'API Chart (events=split) pour DHY, regroupement 1 pour 10 le 2 janvier 2026 (09:30 à New York = 14:30 UTC).
TS = int(datetime.datetime(2026, 1, 2, 14, 30, tzinfo=datetime.timezone.utc).timestamp())
PAYLOAD = {'chart': {'result': [{'meta': {'exchangeTimezoneName': 'America/New_York'},
                                 'events': {'splits': {str(TS): {'date': TS, 'numerator': 1.0, 'denominator': 10.0, 'splitRatio': '1:10'}}}}]}}


def test_declared_split_is_read_with_its_local_session_date():
    assert parse_splits(PAYLOAD) == [('2026-01-02', 1.0, 10.0)]


def test_missing_or_garbage_answers_give_no_split():
    assert parse_splits(None) == [] and parse_splits({}) == [] and parse_splits({'chart': {'result': None}}) == []
    bad = {'chart': {'result': [{'meta': {}, 'events': {'splits': {'1': {'date': 'x', 'numerator': 0, 'denominator': 10}}}}]}}
    assert parse_splits(bad) == []


def test_matching_requires_close_date_and_a_ratio_that_explains_the_jump():
    jump = datetime.date(2026, 1, 2)
    assert splits.match_declared([('2026-01-02', 1.0, 10.0)], jump, 10.05) == (0.1, '2026-01-02')       # ×10 : regroupement 1 pour 10
    assert splits.match_declared([('2026-01-05', 1.0, 10.0)], jump, 10.05) is not None                  # 3 jours d'écart : toléré
    assert splits.match_declared([('2026-01-20', 1.0, 10.0)], jump, 10.05) is None                      # trop loin dans le temps
    assert splits.match_declared([('2026-01-02', 1.0, 3.0)], jump, 10.05) is None                       # ratio sans rapport avec le saut
    # notation inversée de Yahoo : cours divisé par 10 (split 10 pour 1) mais déclaré « 1:10 » (cas réel TACK) -> on suit le sens que le saut confirme
    assert splits.match_declared([('2026-04-20', 1.0, 10.0)], datetime.date(2026, 4, 20), 0.09975) == (10.0, '2026-04-20')
    assert splits.match_declared([('2026-01-02', 4.0, 1.0)], datetime.date(2026, 1, 2), 0.2505) == (4.0, '2026-01-02')   # split 4 pour 1 : le cours est divisé par 4
    assert splits.match_declared([], jump, 10.05) is None
