import pytest

from engine.market.splits import split_ratio


@pytest.mark.parametrize('price_ratio,expected', [
    (0.5, 2.0), (0.4999, 2.0), (0.52, 2.0), (1 / 3, 3.0), (0.1, 10.0), (0.098, 10.0), (2 / 3, 1.5), (0.25, 4.0),
    (2.0, 0.5), (10.0, 0.1), (20.0, 0.05), (1.5, 1 / 1.5)])
def test_usual_split_and_reverse_split_ratios_are_recognised(price_ratio, expected):
    assert split_ratio(price_ratio) == pytest.approx(expected)


@pytest.mark.parametrize('price_ratio', [0.8, 0.85, 0.9, 1.0, 1.2, 1.7, 2.3, 3.6, 0.0, -1.0, None])
def test_ordinary_moves_and_odd_ratios_are_not_taken_for_splits(price_ratio):
    assert split_ratio(price_ratio) is None


def test_recheck_schedule_is_bounded():
    import datetime
    from engine.market import splits
    day = datetime.date(2026, 11, 2)
    assert splits.next_recheck(1, day) == day + datetime.timedelta(days=7)
    assert splits.next_recheck(2, day) == day + datetime.timedelta(days=14)
    assert splits.next_recheck(splits.RECHECK_MAX_CHECKS, day) is None
    assert splits.RECHECK_MAX_CHECKS == 3 and splits.RECHECK_LIMIT <= 50 and splits.RECHECK_WINDOW_DAYS <= 90
