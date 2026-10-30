"""Frais courants et volume 10 jours lus dans la réponse de cotation Yahoo (aucune requête de plus) ; l'inconnu reste inconnu."""
from engine.market import yahoo


def quote(**extra):
    return yahoo.parse_quotes({'quoteResponse': {'result': [dict({'symbol': 'MVUS.L', 'regularMarketPrice': 9146.0, 'currency': 'GBp'}, **extra)]}})['MVUS.L']


def test_fee_and_ten_day_volume_are_read_when_present():
    q = quote(netExpenseRatio=0.2, averageDailyVolume10Day=6906)
    assert q['expense_ratio'] == 0.2 and q['avg_volume_10d'] == 6906


def test_missing_or_absurd_fee_stays_unknown():
    assert quote()['expense_ratio'] is None and quote()['avg_volume_10d'] is None
    assert quote(netExpenseRatio=250)['expense_ratio'] is None and quote(netExpenseRatio=-1)['expense_ratio'] is None


def test_the_requested_fields_include_them():
    assert 'netExpenseRatio' in yahoo.QUOTE_FIELDS and 'averageDailyVolume10Day' in yahoo.QUOTE_FIELDS
