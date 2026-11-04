"""Contrats du banc de proposition ; ne valent pas validation des coefficients."""
import pytest

from scripts.preview_growth_v4 import compare, fixtures, proposal


def test_equal_total_return_does_not_hide_recent_dynamics():
    series = fixtures()
    assert series['acceleration'][-1] == pytest.approx(series['stable'][-1])
    assert series['ralentissement'][-1] == pytest.approx(series['stable'][-1])
    scores = [proposal(series[name]) for name in ('acceleration', 'stable', 'ralentissement')]
    assert all(s['status'] == 'admis' for s in scores)
    assert scores[0]['simple'] > scores[1]['simple'] > scores[2]['simple']
    assert all(0 <= s['simple'] <= 100 and 0 <= s['complexe'] <= 100 for s in scores)


def test_plateau_and_jump_are_not_rewarded_as_smooth_acceleration():
    result = compare()
    assert result['plateau']['v4_proposition']['status'] == 'non_admis'
    assert result['plat']['v4_proposition']['status'] == 'non_admis'
    jump = result['pic_unique']['v4_proposition']
    assert jump['status'] == 'non_admis' and jump['simple'] is None
    assert jump['components']['evolution'] == pytest.approx(50)


def test_disabled_week_does_not_reject_a_plateau_or_become_fake_zero():
    result = proposal(fixtures()['plateau'], periods=(21, 63))
    assert result['status'] == 'admis'
    assert 5 not in result['mesures']
    one = proposal(fixtures()['stable'], periods=(21,))
    assert one['components']['evolution'] is None
    assert one['simple'] == pytest.approx((one['components']['force'] + one['components']['regularite']) / 2)


def test_unavailable_is_never_zero_or_favourably_renormalized():
    prices = fixtures()['stable'][:]
    prices[-3] = None
    missing = proposal(prices)
    assert missing['status'] == 'indisponible'
    assert missing['simple'] is None and missing['complexe'] is None
    assert missing['mesures'][5]['observations'] == 5
    assert missing['mesures'][5]['coverage'] == pytest.approx(5 / 6)


def test_each_score_is_the_sum_of_its_effective_contributions():
    for periods in [(5, 21, 63), (21,)]:
        p = proposal(fixtures()['stable'], periods=periods)
        for name in ('simple', 'complexe'):
            assert sum(x['contribution'] for x in p['decomposition'][name]) == pytest.approx(p[name])
            assert sum(x['poids_effectif'] for x in p['decomposition'][name]) == pytest.approx(1)
    assert p['mesures'][21]['avg_volume'] is None  # Volume absent, pas une entrée de ces scores.
