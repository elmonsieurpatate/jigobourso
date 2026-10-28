import math
import pytest
from engine.analytics import strategy as S


def bars(rate, n=300, noise=0.0, start=100.0):
    out, price = [], start
    for i in range(n):
        out.append((f'2026-{1 + i // 28:02d}-{1 + i % 28:02d}' if False else f'd{i:04d}', price, None))
        price *= 1 + rate + (noise if i % 2 else -noise)
    return out


def cand(key, rate, group='equity', noise=0.0, n=300):
    return {'key': key, 'symbol': f'S{key}', 'group': group, 'bars': bars(rate, n, noise)}


def test_presets_validate():
    for name in S.PRESETS:
        assert S.validate(S.preset(name))['name'] == name


def test_validate_rejects_bad_config():
    c = S.preset('regular')
    c['periods'][2]['sessions'] = 300
    with pytest.raises(ValueError):
        S.validate(c)
    c = S.preset('regular')
    for p in c['periods']:
        p['enabled'] = False
    with pytest.raises(ValueError):
        S.validate(c)
    with pytest.raises(ValueError):
        S.validate({'version': 2})


def test_regular_retains_steady_rise_and_rejects_flat_and_noisy():
    r = S.evaluate(S.preset('regular'), [cand(1, 0.003), cand(2, 0.0), cand(3, 0.003, noise=0.05)])
    by = {v['key']: v for v in r}
    assert by[1]['status'] == 'retained'
    assert by[2]['status'] == 'rejected'
    assert by[3]['status'] == 'rejected'          # hausse bruitée : R² insuffisant


def test_insufficient_history_is_unknown_not_rejected():
    r = S.evaluate(S.preset('regular'), [cand(1, 0.003, n=30)])
    assert r[0]['status'] == 'unknown'
    assert any(x['result'] == 'missing' for x in r[0]['reasons'])


def test_failure_wins_over_missing():
    c = S.preset('regular')
    c['periods'][3]['enabled'] = True
    c['periods'][3].update(min_slope=0.0)       # trimestre: manque (n=40) ; mois: échoue (plat)
    r = S.evaluate(c, [cand(1, 0.0, n=40)])
    assert r[0]['status'] == 'rejected'


def test_break_window_not_evaluated():
    data = bars(0.003, 100)
    data = data[:80] + [(d, p / 2, a) for d, p, a in data[80:]]   # saut -50 % non expliqué
    r = S.evaluate(S.preset('regular'), [{'key': 1, 'symbol': 'X', 'group': 'equity', 'bars': data}])
    assert r[0]['status'] == 'unknown' and r[0]['breaks']


def test_stale_series_is_unknown():
    c = cand(1, 0.003)
    c['expected_last_date'] = 'd9999'
    assert S.evaluate(S.preset('regular'), [c])[0]['status'] == 'unknown'


def test_ranking_separate_groups_and_order():
    cs = [cand(1, 0.006), cand(2, 0.007), cand(3, 0.008), cand(4, 0.007, group='etf')]
    cfg = S.preset('fast')
    cfg['periods'][0]['enabled'] = False
    r = {v['key']: v for v in S.evaluate(cfg, cs)}
    assert [r[k]['rank'] for k in (3, 2, 1)] == [1, 2, 3]
    assert r[4]['rank'] == 1 and r[4]['score'] == 50.0      # seul ETF : classé dans son groupe


def test_only_given_candidates_are_ranked():
    """Le moteur ne classe que ce qu'on lui donne : l'exclusion se fait en amont (v_recommendable)."""
    r = S.evaluate(S.preset('fast'), [cand(1, 0.008)])
    assert len(r) == 1


def test_technical_filter():
    c = S.preset('fast')
    c['technical']['above_ma50'] = True
    assert S.evaluate(c, [cand(1, 0.008)])[0]['status'] == 'retained'
    down = bars(0.006, 250) + [(f'x{i}', 100.0 * 0.9 ** (i + 1) * 3, None) for i in range(1)]
    r = S.evaluate(c, [{'key': 2, 'symbol': 'D', 'group': 'equity', 'bars': down}])
    assert r[0]['status'] in ('rejected', 'unknown')
