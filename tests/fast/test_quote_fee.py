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


def test_analyst_rating_and_fund_assets_are_read_and_validated():
    q = quote(averageAnalystRating='1.8 - Buy', netAssets=766672700.0)
    assert q['analyst_rating'] == '1.8 - Buy' and q['net_assets'] == 766672700
    for bad in ('n/a', '', '9.9 - Buy', None, 3):
        assert quote(averageAnalystRating=bad)['analyst_rating'] is None
    assert quote(netAssets=0)['net_assets'] is None and quote()['net_assets'] is None


def test_analyst_consensus_is_translated_without_inventing_anything():
    from engine.analytics.service import analyst_view
    assert analyst_view('1.8 - Buy')['text'] == 'Achat (1,8)'
    assert analyst_view('2.7 - Hold')['text'] == 'Conserver (2,7)'
    assert analyst_view('1.3 - Strong Buy')['text'] == 'Achat fort (1,3)'
    assert analyst_view('4.2 - Underperform')['text'] == 'Sous-performance (4,2)'
    assert analyst_view('2.5 - Mystère')['text'] == 'Note 2,5'            # libellé inconnu : la note seule
    assert analyst_view(None) is None and analyst_view('') is None and analyst_view('abc') is None


def test_size_class_uses_euros_and_ignores_pence():
    from engine.analytics.service import _size_class
    rates = {'EUR': 1.0, 'USD': 0.9}
    assert _size_class(180e6, 'USD', rates) == 'micro-capitalisation'
    assert _size_class(5e9, 'EUR', rates) == 'capitalisation moyenne'
    assert _size_class(300e9, 'EUR', rates) == 'très grande capitalisation'
    assert _size_class(5e9, 'GBp', rates) is None and _size_class(None, 'EUR', rates) is None


def test_activity_note_explains_without_touching_thresholds():
    from engine.analytics.service import _activity_note
    assert _activity_note({'avg_volume_3m': 100, 'avg_volume_10d': 110}) == []
    assert _activity_note({'avg_volume_3m': None, 'avg_volume_10d': 5}) == []
    note = _activity_note({'avg_volume_3m': 191393, 'avg_volume_10d': 487130})[0]
    assert '×2,5' in note and 'plus actif' in note and 'liquidité durable' in note
    assert 'moins actif' in _activity_note({'avg_volume_3m': 619, 'avg_volume_10d': 0})[0]
