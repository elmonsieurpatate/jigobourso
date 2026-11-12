"""Barre de risque d'un achat : trois signaux notés, niveaux, cas non évaluables, réglages personnels."""

from engine.analytics.portfolio import risk


def path(n, daily, start=100.0, wobble=0.0):
    out, c = [], start
    for i in range(n):
        c *= 1 + daily + (wobble if i % 2 else -wobble)
        out.append(c)
    return out


def test_a_steady_climb_is_ok_for_every_strategy():
    closes = path(300, 0.0012, wobble=0.002)
    for name in ('fast', 'regular', 'momentum', 'low_volatility', 'recovery', 'custom'):
        r = risk.assess(name, closes, 1.0)
        assert r['level'] == 'ok' and r['score'] == 0, (name, r)


def test_a_slowing_trend_and_a_big_drop_turn_the_bar_to_act():
    closes = path(250, 0.002, wobble=0.004) + path(60, -0.012, start=130.0, wobble=0.004)
    high_drop = 100 * (1 - closes[-1] / max(closes))
    r = risk.assess('fast', closes, high_drop)
    assert r['level'] == 'act' and any(s['kind'] == 'drop' and s['points'] == 2 for s in r['signals'])


def test_the_drop_threshold_is_tighter_for_fast_strategies_than_for_long_ones():
    closes = path(300, 0.001, wobble=0.01)
    fast, regular, mom = (risk.assess(n, closes, 0.0)['drop_threshold'] for n in ('fast', 'regular', 'momentum'))
    assert fast < regular < mom or (fast <= regular <= mom and fast < mom)
    assert risk.DROP_MIN <= fast and mom <= risk.DROP_MAX


def test_a_personal_threshold_replaces_the_default_and_is_said():
    closes = path(300, 0.001, wobble=0.004)
    r = risk.assess('regular', closes, 9.0, drop_override=8)
    assert r['drop_threshold'] == 8 and r['level'] == 'act'
    assert 'réglé par vous' in [s for s in r['signals'] if s['kind'] == 'drop'][0]['message']


def test_drop_at_the_threshold_is_act_even_if_the_trend_is_fine():
    closes = path(300, 0.002, wobble=0.003)
    r = risk.assess('regular', closes, 50.0)
    assert r['level'] == 'act'


def test_a_price_break_or_a_short_history_is_not_evaluated_instead_of_alerting():
    closes = path(300, 0.001)
    closes[-20] *= 0.3
    r = risk.assess('regular', closes, 5.0)
    assert r['level'] == 'na' and r['reason'] == 'break' and r['score'] is None
    short = risk.assess('regular', path(50, 0.001), 5.0)
    assert short['level'] == 'na' and short['reason'] == 'history'


def test_the_prudent_strategy_has_no_bar():
    assert risk.assess('prudent', path(300, 0.001), 1.0) is None


def test_extended_price_is_information_only_and_never_scored():
    closes = path(300, 0.001, wobble=0.002)
    base = risk.assess('regular', closes, 1.0)
    r = risk.assess('regular', closes, 1.0, ma50=closes[-1] / 1.4)
    assert 'Information' in r['info'] and r['score'] == base['score'] and 'info' not in base


def test_every_signal_explains_itself_with_numbers():
    r = risk.assess('regular', path(300, 0.001, wobble=0.004), 3.0)
    assert [s['kind'] for s in r['signals']] == ['slope', 'drop', 'stability']
    assert all(s['message'] and any(ch.isdigit() for ch in s['message']) for s in r['signals'])
    assert all(isinstance(s['points'], int) and 0 <= s['points'] <= 2 for s in r['signals'])
