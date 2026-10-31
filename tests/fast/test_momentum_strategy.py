"""Stratégie expérimentale « Momentum 6 mois » : mesure entre J−126 et J−21 séances, jugement, classement, et garantie que les quatre profils existants ne changent pas."""
import datetime
import hashlib
import importlib.util
import json
import math
import os

from engine.analytics import strategy as S
from engine.analytics import tracking
from engine.analytics.series import momentum_6_1, MOMENTUM_LONG, MOMENTUM_SKIP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def days(n, start=datetime.date(2025, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


# ───────── les quatre profils existants ne bougent pas ─────────
FINGERPRINTS = {   # empreintes calculées sur le code AVANT l'ajout du cinquième profil
    'regular': '14d71cdecf74c5da1409c037f4b6ea94bb4980fd40a0496cc6241a8c5e78252b',
    'fast': 'c4e174a632cc8be3ac601b0e515977e276340c68a59acdd66759d734573058f7',
    'recovery': '93c46cf20bb7b15c1a1492130a454720525729c2fe205096b4db4dc478031451',
    'low_volatility': '15913494b48bd8dbd1c0cea0033f308c26c1a8cd7af6251e57ae54b5b1fa0201',
}


def test_the_four_existing_strategies_are_byte_for_byte_unchanged():
    for name, expected in FINGERPRINTS.items():
        assert hashlib.sha256(json.dumps(S.preset(name), sort_keys=True).encode()).hexdigest() == expected, name
    assert S.PRESETS[:4] == ('regular', 'fast', 'recovery', 'low_volatility') and S.PRESETS[4] == 'momentum'
    assert S.EXPERIMENTAL == ('momentum',) and S.RANK_MODES[:4] == ('trend', 'performance', 'regularity', 'stability')


def test_momentum_preset_is_valid_and_has_no_threshold():
    cfg = S.validate(S.preset('momentum'))
    assert cfg['name'] == 'momentum' and cfg['ranking']['mode'] == 'momentum'
    enabled = [p for p in cfg['periods'] if p['enabled']]
    assert [p['id'] for p in enabled] == ['half'] and all(p[f] is None for p in enabled for f, _, _ in S.CRITERIA)      # aucun seuil : seul le rang compte
    assert all(not v for v in cfg['technical'].values())


# ───────── la mesure : J−126 → J−21 ─────────
def growth(n, rate=0.01):
    return [100 * (1 + rate) ** i for i in range(n)]


def test_momentum_is_the_change_between_126_and_21_sessions_ago():
    closes = growth(200)
    expected = 100 * ((1.01) ** (MOMENTUM_LONG - MOMENTUM_SKIP) - 1)
    assert abs(momentum_6_1(days(200), closes, []) - expected) < 1e-9
    assert (MOMENTUM_LONG, MOMENTUM_SKIP) == (126, 21)


def test_the_last_month_is_ignored():
    steady = growth(200, 0.002)
    crash = steady[:-21] + [steady[-22] * 0.5 ** ((i + 1) / 21) for i in range(21)]        # le dernier mois s'effondre
    surge = steady[:-21] + [steady[-22] * 2 ** ((i + 1) / 21) for i in range(21)]          # ou explose
    d = days(200)
    assert momentum_6_1(d, crash, []) == momentum_6_1(d, steady, []) == momentum_6_1(d, surge, [])


def test_dated_window_uses_the_market_calendar_and_never_estimates():
    d, closes = days(200), growth(200)
    expected_dates = d[-127:]
    assert abs(momentum_6_1(d, closes, [], expected_dates) - momentum_6_1(d, closes, [])) < 1e-9       # même résultat quand aucune séance ne manque
    assert momentum_6_1(d[:-22] + d[-21:], closes[:-22] + closes[-21:], [], expected_dates) is None     # la clôture de J−21 manque : non évaluable, jamais interpolé
    assert momentum_6_1(d, closes, [], expected_dates[:100]) is None                                    # calendrier trop court


def test_short_history_and_price_breaks_make_the_measure_unavailable():
    assert momentum_6_1(days(120), growth(120), []) is None                                # moins de 127 clôtures
    d, closes = days(200), growth(200)
    first = 199 - MOMENTUM_LONG
    assert momentum_6_1(d, closes, [first + 5]) is None                                    # rupture après J−126 : la fenêtre ne se mesure pas
    assert momentum_6_1(d, closes, [first - 5]) is not None                                # rupture antérieure à la fenêtre : sans effet


def test_same_definition_as_the_backtest_signal_mom_6_1():
    spec = importlib.util.spec_from_file_location('backtest_walkforward', os.path.join(ROOT, 'scripts', 'backtest_walkforward.py'))
    bw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bw)
    closes = [100 * math.exp(0.0004 * i + 0.03 * math.sin(i / 7)) for i in range(220)]
    assert abs(momentum_6_1(days(220), closes, []) - 100 * bw.SIGNALS['mom_6_1'][0](closes)) < 1e-9        # ce qui a été testé est ce qui est calculé


# ───────── jugement et classement ─────────
def measures_ok():
    return {126: {'sessions': 126, 'perf': 10.0, 'slope': 0.05, 'r2': 0.8, 'volatility': 1.0, 'drawdown': 5.0, 'er': 0.3}}


def test_judge_marks_unknown_when_momentum_is_missing():
    cfg = S.validate(S.preset('momentum'))
    unknown = S.judge(cfg, measures_ok(), {}, {})
    retained = S.judge(cfg, measures_ok(), {}, {}, momentum=12.5)
    assert unknown['status'] == 'unknown' and any(r['metric'] == 'momentum' and r['result'] == 'missing' for r in unknown['reasons'])
    assert retained['status'] == 'retained' and retained['momentum'] == 12.5
    other = S.judge(S.validate(S.preset('regular')), {63: {'perf': 1.0, 'slope': 0.1, 'r2': 0.9, 'volatility': 1.0, 'drawdown': 2.0, 'er': 0.3}, 21: {'perf': 1.0, 'slope': 0.1, 'r2': 0.9, 'volatility': 1.0, 'drawdown': 2.0, 'er': 0.3}}, {}, {})
    assert 'momentum' not in {r['metric'] for r in other['reasons']}                       # les autres profils ignorent le momentum


def verdict(key, group, momentum, status='retained'):
    return {'key': key, 'group': group, 'symbol': f'S{key}', 'status': status, 'measures': measures_ok(), 'momentum': momentum}


def test_rank_orders_by_momentum_within_each_group_only():
    cfg = S.validate(S.preset('momentum'))
    vs = S.rank(cfg, [verdict(1, 'equity', 5.0), verdict(2, 'equity', 30.0), verdict(3, 'equity', -10.0), verdict(4, 'etf', 1.0), verdict(5, 'etf', 2.0),
                      verdict(6, 'equity', 99.0, status='rejected'), verdict(7, 'equity', None)])
    by = {v['key']: v for v in vs}
    assert [by[k]['rank'] for k in (2, 1, 3)] == [1, 2, 3] and by[5]['rank'] == 1 and by[4]['rank'] == 2           # les ETF sont classés à part des actions
    assert by[6]['rank'] is None and by[6]['score'] is None and by[7]['rank'] is None                              # écarté ou sans momentum : pas de rang
    assert by[2]['score'] == 100.0 and by[3]['score'] == 0.0 and all(0 <= v['score'] <= 100 for v in vs if v['score'] is not None)


def test_end_to_end_ranking_from_prices_ignores_the_last_month():
    d = days(200)

    def bars(path):
        return [(day, c, None) for day, c in zip(d, path)]
    steady = growth(200, 0.004)
    winner_then_crash = steady[:-21] + [steady[-22] * 0.6 ** ((i + 1) / 21) for i in range(21)]
    flat_then_surge = [100.0] * 179 + [100.0 * 1.5 ** ((i + 1) / 21) for i in range(21)]
    laggard = [100 * (0.999) ** i for i in range(200)]
    cands = [{'key': k, 'group': 'equity', 'symbol': s, 'bars': bars(p)} for k, s, p in ((1, 'WIN', winner_then_crash), (2, 'SURGE', flat_then_surge), (3, 'LAG', laggard))]
    out = {v['symbol']: v for v in S.evaluate(S.preset('momentum'), cands)}
    assert out['WIN']['rank'] == 1 and out['LAG']['rank'] == 3 and out['SURGE']['rank'] == 2
    assert out['WIN']['momentum'] > 0 > out['LAG']['momentum'] and abs(out['SURGE']['momentum']) < 1e-9          # la flambée du dernier mois ne compte pas


# ───────── suivi à 21 et 63 séances ─────────
def test_tracking_horizons_include_21_and_63_sessions():
    assert tracking.HORIZONS[:3] == (1, 3, 5) and 21 in tracking.HORIZONS and 63 in tracking.HORIZONS
    d = days(100)
    closes = growth(100, 0.01)
    full = tracking.forward_returns([(x, c, None) for x, c in zip(d, closes)], d[10], (21, 63))
    assert abs(full[21] - 100 * (1.01 ** 21 - 1)) < 1e-9 and abs(full[63] - 100 * (1.01 ** 63 - 1)) < 1e-9
    assert 63 not in tracking.forward_returns([(x, c, None) for x, c in zip(d, closes)], d[60], (21, 63))        # horizon pas encore écoulé : aucun résultat inventé
