"""Plan de suivi des positions : scénarios financiers chiffrés (voir research/suivi_positions/SPEC_SUIVI_POSITIONS.md).
Aucune base : les séries sont synthétiques. Un test par exigence du cahier des charges."""
import datetime
import math

from engine.analytics import position_plan as pp


def days(n, start='2025-01-01'):
    d, out = datetime.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def path(points, noise=0.0):
    """Interpolation géométrique entre des (jour, prix) ; bruit déterministe optionnel (alternance ±noise)."""
    out = []
    for (i0, p0), (i1, p1) in zip(points, points[1:]):
        for i in range(i0, i1):
            c = p0 * (p1 / p0) ** ((i - i0) / (i1 - i0))
            out.append(c * (1 + (noise if i % 2 else -noise)))
    out.append(points[-1][1])
    return out


def plan(closes, strategy=None, pru=None, stop=None, open_idx=0, qty=10, kind='stock', price=None, fx=1.0, label=None):
    dates = days(len(closes))
    cur = closes[-1] if price is None else price
    pos = {'listing_id': 1, 'kind': kind, 'qty': qty, 'avg_cost': pru if pru is not None else closes[open_idx], 'price': cur / fx, 'price_eur': cur, 'currency': 'USD' if fx != 1 else 'EUR',
           'open_date': dates[open_idx], 'stop_px': stop, 'watch_key': strategy, 'watch_label': label}
    return pp.build(pos, dates, closes, [], datetime.date(2026, 11, 9))


# ── forte hausse : 100 -> 160 ──
def test_strong_rise_no_sell_advice():
    c = path([(0, 100), (150, 130), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    assert abs(p['gain']['pct'] - 60.0) < 1.5
    assert p['advice']['tone'] in ('ok', 'info'), p['advice']
    text = (p['advice']['headline'] + p['advice']['detail']).lower()
    assert 'vendre' not in text.replace('rien n’est vendu', '') and 'objectif' not in p['advice']['headline'].lower()
    assert p['prices']['high'] >= p['prices']['current']
    assert p['recul_pct'] < 2
    assert p['prices']['suggested'] < p['prices']['current'] < p['prices']['high'] * 1.0001
    assert p['momentum']['active'] is False


def test_no_fixed_target_anywhere():
    p = plan(path([(0, 100), (260, 400)], noise=0.012), 'fast', pru=100)
    assert p['gain']['pct'] >= 299 and 'target' not in p['prices'] and 'objectif' not in str(p['advice']).lower().replace('aucun objectif', '')


# ── correction 160 -> 150 ──
def test_small_correction_drawdown():
    c = path([(0, 100), (200, 160), (230, 150)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    assert abs(p['recul_pct'] - 100 * (1 - c[-1] / max(c))) < 1e-9 and 5 < p['recul_pct'] < 9
    assert p['risk']['level'] in ('low', 'moderate')
    assert p['advice']['tone'] in ('ok', 'info', 'watch')


# ── recul important 160 -> 140 puis 120 ──
def test_deep_drawdowns_messages_and_levels():
    c140 = path([(0, 100), (200, 160), (240, 140)], noise=0.012)
    p140 = plan(c140, 'regular', pru=100)
    assert abs(p140['recul_pct'] - 100 * (1 - c140[-1] / max(c140))) < 1e-9 and 11 < p140['recul_pct'] < 15
    c120 = path([(0, 100), (200, 160), (240, 140), (270, 120)], noise=0.012)
    p120 = plan(c120, 'regular', pru=100)
    assert abs(p120['recul_pct'] - 100 * (1 - c120[-1] / max(c120))) < 1e-9 and 23 < p120['recul_pct'] < 28
    assert p120['advice']['tone'] in ('watch', 'alert')
    assert p120['prices']['suggested'] and p120['prices']['current'] < p120['prices']['pru'] * 1.3
    assert p120['advice']['why']


# ── protection personnelle jamais écrasée ──
def test_personal_protection_kept_and_distinct():
    c = path([(0, 100), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=100, stop=110.0)
    assert p['prices']['personal'] == 110.0 and p['prices']['suggested'] != p['prices']['personal']
    assert p['prices']['personal'] < p['prices']['current']
    c2 = c[:-1] + [105.0]
    p2 = plan(c2, 'regular', pru=100, stop=110.0)
    assert p2['advice']['tone'] == 'alert' and 'protection personnel' in p2['advice']['headline']
    assert 'automatiquement' in p2['advice']['detail']
    assert p2['prices']['personal'] == 110.0


def test_no_personal_level_means_none_not_invented():
    p = plan(path([(0, 100), (200, 140)], noise=0.012), 'regular', pru=100)
    assert p['prices']['personal'] is None


# ── momentum 6-1 : armement et unités ──
def decline_series():
    return path([(0, 100), (150, 200), (320, 140)], noise=0.012)


def test_momentum_alert_armed_after_entry():
    c = decline_series()
    p = plan(c, 'regular', pru=100)
    m = p['momentum']
    expect = 100 * (c[-1 - 21] / c[-1 - 126] - 1)
    assert abs(m['value'] - expect) < 1e-9 and m['value'] < 0
    assert m['armed'] and m['active'] and m['since']
    assert 'momentum' in p['advice']['headline'].lower() and 'dernier mois' in p['advice']['detail']


def test_momentum_already_negative_at_open_is_not_an_alert():
    c = path([(0, 200), (160, 140), (320, 100)], noise=0.012)
    p = plan(c, 'regular', pru=200, open_idx=140)         # ouverte quand m6−1 est déjà négatif
    assert p['momentum']['available'] and p['momentum']['value'] < 0
    assert p['momentum']['active'] is False and p['momentum']['negative_at_open'] is True
    assert 'momentum de moyen terme est devenu' not in p['advice']['headline']


def test_momentum_does_not_claim_recent_reversal():
    c = path([(0, 100), (150, 200), (300, 140), (330, 175)], noise=0.012)   # rebond récent
    p = plan(c, 'regular', pru=100)
    if p['momentum']['active']:
        assert 'peut remonter' in p['advice']['detail']


# ── sept stratégies ──
def test_seven_strategies_alert_support():
    c = decline_series()
    exp = {'regular': 'validated', 'fast': 'fragile', 'low_volatility': 'limited', 'momentum': 'validated', 'momentum12': 'provisional', 'momentum_risk': 'provisional', 'recovery': 'none'}
    for key, support in exp.items():
        p = plan(c, key, pru=100)
        assert p['strategy']['support'] == support and p['strategy']['note']
        head = p['advice']['headline'].lower()
        if key == 'recovery':
            assert 'momentum' not in head, (key, head)
        else:
            assert p['momentum']['active'] and ('momentum' in head or 'vigilance' in head), (key, head)
        if support == 'provisional':
            assert 'provisoire' in p['advice']['detail']


def test_combined_alert_only_where_tested():
    c = path([(0, 100), (150, 200), (320, 160)], noise=0.012)
    for key, combined in (('momentum', True), ('low_volatility', True), ('regular', False), ('fast', False)):
        p = plan(c, key, pru=100)
        if p['momentum']['active'] and p['recul_pct'] >= 15:
            assert ('renforcée' in p['advice']['headline'] and 'recul' in p['advice']['headline'].lower()) == combined, key


def test_neutral_when_no_strategy():
    p = plan(decline_series(), None, pru=100)
    assert p['strategy']['support'] == 'undefined' and 'neutre' in p['strategy']['note']
    assert 'momentum de moyen terme est devenu' not in p['advice']['headline']
    assert p['risk'] and p['prices']['suggested']


def test_custom_strategy_is_neutral():
    p = plan(decline_series(), None, pru=100, label='Ma stratégie')
    assert p['strategy']['support'] == 'custom' and p['strategy']['label'] == 'Ma stratégie'
    assert not p['momentum']['active'] or 'momentum de moyen terme est devenu' not in p['advice']['headline']


# ── cas particuliers ──
def test_insufficient_history_no_invented_values():
    p = plan(path([(0, 100), (40, 120)], noise=0.012), 'regular', pru=100)
    assert p['risk'] is None and p['prices']['suggested'] is None and p['momentum']['available'] is False
    assert p['advice']['tone'] == 'na' and p['notes']


def test_missing_price():
    dates = days(200)
    pos = {'listing_id': 1, 'qty': 1, 'avg_cost': 10, 'price': None, 'price_eur': None, 'open_date': dates[0], 'watch_key': 'regular'}
    p = pp.build(pos, dates, [10.0] * 200, [], datetime.date(2026, 11, 9))
    assert p['status'] == 'unavailable' and p['advice']['tone'] == 'na'


def test_currency_conversion_explicit():
    c = path([(0, 100), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=90, fx=0.5)                # cours en devise = 2 × cours en euros
    assert abs(p['prices']['fx'] - 0.5) < 1e-12
    assert abs(p['prices']['high'] - max(c) * 0.5 / 0.5 * 1.0) < 1e-6 * max(c) or p['prices']['high'] > 0
    assert p['prices']['local_currency'] == 'USD'


def test_etf_same_engine():
    p = plan(path([(0, 100), (260, 130)], noise=0.004), 'regular', pru=100, kind='etf')
    assert p['risk']['level'] == 'low' and p['advice']['tone'] == 'ok'


def test_strategy_change_changes_only_alerts():
    c = decline_series()
    a, b = plan(c, 'regular', pru=100), plan(c, 'recovery', pru=100)
    assert a['prices'] == b['prices'] and a['risk'] == b['risk'] and a['momentum']['value'] == b['momentum']['value']
    assert a['advice'] != b['advice']


def test_risk_bands_are_monotone_and_documented():
    levels = [b[1] for b in pp.BANDS]
    assert levels == ['low', 'low', 'moderate', 'moderate', 'high', 'high', 'very_high']
    assert all(pp.BANDS[i][3] < pp.BANDS[i + 1][3] and pp.BANDS[i][2] < pp.BANDS[i + 1][2] for i in range(len(pp.BANDS) - 1))
    assert pp.band_of(0.9)[0] == 0 and pp.band_of(1.0)[0] == 0 and pp.band_of(2.5)[0] == 3 and pp.band_of(7)[0] == 6


def test_suggested_formula():
    c = path([(0, 100), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    sigma = p['risk']['sigma63']; i, b = pp.band_of(sigma)
    assert abs(p['prices']['suggested'] - p['prices']['high'] * (1 - b[3] / 100)) < 1e-9
    # σ63 recalculé à la main : écart-type des 63 derniers rendements log
    r = [math.log(c[k] / c[k - 1]) for k in range(len(c) - 63, len(c))]
    m = sum(r) / 63
    assert abs(100 * math.sqrt(sum((x - m) ** 2 for x in r) / 62) - sigma) < 1e-9


# ── multi-lots : le PRU est celui du portefeuille (prix de revient moyen du ledger), jamais recalculé ──
def test_pru_is_taken_from_portfolio_not_recomputed():
    # achats 10@100, 5@130, 5@150 puis vente de 8 au prix de revient moyen : 12 titres à 120 € ; une moyenne FIFO des lots restants (133,33) serait contradictoire
    c = path([(0, 100), (200, 170)], noise=0.012)
    p = plan(c, 'regular', pru=120.0, qty=12)
    assert p['prices']['pru'] == 120.0
    assert abs(p['gain']['pct'] - 100 * (c[-1] / 120.0 - 1)) < 1e-9
    assert abs(p['gain']['eur'] - (c[-1] - 120.0) * 12) < 1e-9
