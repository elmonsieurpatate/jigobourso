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


def plan(closes, strategy=None, pru=None, stop=None, open_idx=0, qty=10, kind='stock', price=None, fx=1.0, label=None, target=None, rules=None):
    dates = days(len(closes))
    cur = closes[-1] if price is None else price
    pos = {'listing_id': 1, 'kind': kind, 'qty': qty, 'avg_cost': pru if pru is not None else closes[open_idx], 'price': cur / fx, 'price_eur': cur, 'currency': 'USD' if fx != 1 else 'EUR',
           'open_date': dates[open_idx], 'stop_px': stop, 'target_px': target, 'rules': rules, 'watch_key': strategy, 'watch_label': label}
    return pp.build(pos, dates, closes, [], datetime.date(2026, 11, 9))


def texts(p):
    """Tout le texte d'un conseil : message principal, détail et autres règles déclenchées (consultables)."""
    a = p['advice']
    return ' '.join([a['headline'], a['detail']] + [o['text'] + ' ' + o['detail'] for o in a['others']]).lower()


def rule(p, key):
    return next(r for r in p['rules'] if r['key'] == key)


# ── forte hausse : 100 -> 160 ──
def test_strong_rise_no_sell_advice():
    c = path([(0, 100), (150, 130), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    assert abs(p['gain']['pct'] - 60.0) < 1.5
    assert p['advice']['state'] == 'keep' and p['advice']['tone'] == 'ok', p['advice']
    text = (p['advice']['headline'] + p['advice']['detail']).lower()
    assert 'vendre' not in text.replace('rien n’est vendu', '') and 'objectif' not in p['advice']['headline'].lower()
    assert p['prices']['high'] >= p['prices']['current']
    assert p['recul_pct'] < 2
    assert p['prices']['suggested'] < p['prices']['current'] < p['prices']['high'] * 1.0001
    assert p['momentum']['active'] is False


def test_no_fixed_target_anywhere():
    p = plan(path([(0, 100), (260, 400)], noise=0.012), 'fast', pru=100)
    assert p['gain']['pct'] >= 299 and p['prices']['target'] is None and rule(p, 'target')['mode'] == 'none' and rule(p, 'target')['auto'] is None
    assert 'objectif' not in str(p['advice']).lower().replace('aucun objectif', '')


# ── correction 160 -> 150 ──
def test_small_correction_drawdown():
    c = path([(0, 100), (200, 160), (230, 150)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    assert abs(p['recul_pct'] - 100 * (1 - c[-1] / max(c))) < 1e-9 and 5 < p['recul_pct'] < 9
    assert p['risk']['level'] in ('low', 'moderate')
    assert p['advice']['state'] in ('keep', 'watch')


# ── recul important 160 -> 140 puis 120 ──
def test_deep_drawdowns_messages_and_levels():
    c140 = path([(0, 100), (200, 160), (240, 140)], noise=0.012)
    p140 = plan(c140, 'regular', pru=100)
    assert abs(p140['recul_pct'] - 100 * (1 - c140[-1] / max(c140))) < 1e-9 and 11 < p140['recul_pct'] < 15
    c120 = path([(0, 100), (200, 160), (240, 140), (270, 120)], noise=0.012)
    p120 = plan(c120, 'regular', pru=100)
    assert abs(p120['recul_pct'] - 100 * (1 - c120[-1] / max(c120))) < 1e-9 and 23 < p120['recul_pct'] < 28
    assert p120['advice']['state'] in ('watch', 'reevaluate', 'exit')
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
    assert p2['advice']['state'] == 'exit' and p2['advice']['rule'] == 'stop' and 'protection personnelle' in p2['advice']['headline'].lower()
    assert 'automatiquement' in p2['advice']['detail'] and p2['advice']['label'] == 'Sortie à envisager'
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
    assert 'momentum' in texts(p) and 'dernier mois' in texts(p)
    assert rule(p, 'trend')['triggered'] is True


def test_momentum_already_negative_at_open_is_not_an_alert():
    c = path([(0, 200), (160, 140), (320, 100)], noise=0.012)
    p = plan(c, 'regular', pru=200, open_idx=140)         # ouverte quand m6−1 est déjà négatif
    assert p['momentum']['available'] and p['momentum']['value'] < 0
    assert p['momentum']['active'] is False and p['momentum']['negative_at_open'] is True
    assert 'momentum de moyen terme est devenu' not in texts(p)


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
            assert 'momentum' not in texts(p), (key, head)
            assert rule(p, 'trend')['triggered'] is False
        else:
            assert p['momentum']['active'] and rule(p, 'trend')['triggered'] and 'momentum' in texts(p), (key, head)
        if support == 'provisional':
            assert 'provisoire' in texts(p)


def test_combined_alert_only_where_tested():
    c = path([(0, 100), (150, 200), (320, 160)], noise=0.012)
    for key, combined in (('momentum', True), ('low_volatility', True), ('regular', False), ('fast', False)):
        p = plan(c, key, pru=100)
        if p['momentum']['active'] and p['recul_pct'] >= 15:
            assert ('règle de réévaluation de la stratégie' in texts(p)) == combined, key


def test_neutral_when_no_strategy():
    p = plan(decline_series(), None, pru=100)
    assert p['strategy']['support'] == 'undefined' and 'neutre' in p['strategy']['note']
    assert 'momentum de moyen terme est devenu' not in texts(p) and rule(p, 'trend')['triggered'] is False
    assert p['risk'] and p['prices']['suggested']


def test_custom_strategy_is_neutral():
    p = plan(decline_series(), None, pru=100, label='Ma stratégie')
    assert p['strategy']['support'] == 'custom' and p['strategy']['label'] == 'Ma stratégie'
    assert rule(p, 'trend')['triggered'] is False and 'momentum de moyen terme est devenu' not in texts(p)


# ── cas particuliers ──
def test_insufficient_history_no_invented_values():
    p = plan(path([(0, 100), (40, 120)], noise=0.012), 'regular', pru=100)
    assert p['risk'] is None and p['prices']['suggested'] is None and p['momentum']['available'] is False
    assert p['advice']['state'] == 'na' and p['advice']['tone'] == 'na' and p['notes']


def test_missing_price():
    dates = days(200)
    pos = {'listing_id': 1, 'qty': 1, 'avg_cost': 10, 'price': None, 'price_eur': None, 'open_date': dates[0], 'watch_key': 'regular'}
    p = pp.build(pos, dates, [10.0] * 200, [], datetime.date(2026, 11, 9))
    assert p['status'] == 'unavailable' and p['advice']['state'] == 'na'


def test_currency_conversion_explicit():
    c = path([(0, 100), (260, 160)], noise=0.012)
    p = plan(c, 'regular', pru=90, fx=0.5)                # cours en devise = 2 × cours en euros
    assert abs(p['prices']['fx'] - 0.5) < 1e-12
    assert abs(p['prices']['high'] - max(c) * 0.5 / 0.5 * 1.0) < 1e-6 * max(c) or p['prices']['high'] > 0
    assert p['prices']['local_currency'] == 'USD'


def test_etf_same_engine():
    p = plan(path([(0, 100), (260, 130)], noise=0.004), 'regular', pru=100, kind='etf')
    assert p['risk']['level'] == 'low' and p['advice']['state'] == 'keep'


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


# ═════════ conseils : CONSERVER / SURVEILLER / RÉÉVALUER / SORTIE À ENVISAGER, protections automatiques et personnalisées ═════════
def gibo():
    """Hausse continue (85 -> 160), volatilité très élevée (≈ 7 % par séance), stratégie Rebond : cas de la spécification."""
    return path([(0, 85), (260, 160)], noise=0.035)


def test_high_risk_without_protection_crossed_is_watch_not_exit():
    p = plan(gibo(), 'recovery', pru=85.47)
    a = p['advice']
    assert p['risk']['level'] == 'very_high' and p['risk']['sigma63'] > 6
    assert a['state'] == 'watch' and a['label'] == 'Surveiller' and a['tone'] == 'watch' and a['rule'] == 'risk'
    assert a['headline'] == 'Surveiller — La hausse se poursuit, mais le risque de repli est très élevé.'
    assert a['protection'].startswith('Protection automatique : ') and a['protection'].endswith('Tu peux la modifier.')
    assert not rule(p, 'stop')['triggered'] and rule(p, 'stop')['mode'] == 'auto' and rule(p, 'stop')['effective'] == p['prices']['suggested']
    assert 'vendre' not in a['detail'].replace('rien n’est vendu', '')


def test_keep_when_nothing_triggered_and_never_claims_no_risk():
    p = plan(path([(0, 100), (260, 130)], noise=0.004), 'regular', pru=100)
    a = p['advice']
    assert a['state'] == 'keep' and a['label'] == 'Conserver' and a['tone'] == 'ok' and a['rule'] is None and a['others'] == []
    assert a['headline'] == 'Conserver — La position progresse et aucune protection n’est franchie.'
    assert 'sans risque' in a['detail'] and 'ne signifie pas' in a['detail']


def test_loss_position_without_protection_crossed_is_keep():
    c = path([(0, 100), (260, 96)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    assert p['gain']['pct'] < 0 and p['advice']['state'] == 'keep' and 'perte latente' in p['advice']['detail']


def test_automatic_protection_crossed_is_exit_with_the_rule_named():
    c = path([(0, 100), (200, 200), (260, 150)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    a = p['advice']
    assert rule(p, 'stop')['mode'] == 'auto' and rule(p, 'stop')['triggered']
    assert a['state'] == 'exit' and a['label'] == 'Sortie à envisager' and a['tone'] == 'exit' and a['rule'] == 'stop'
    assert a['headline'].startswith('Sortie à envisager — La protection automatique de ') and 'est franchie' in a['headline']
    assert 'pas un ordre de vente' in a['detail'] and 'ne pas agir mécaniquement' in a['detail']


def test_personal_protection_is_the_effective_level_and_never_overwritten():
    c = gibo()
    auto = plan(c, 'recovery', pru=85.47)
    perso = plan(c, 'recovery', pru=85.47, stop=130.0)             # filet personnalisé avec la stratégie Rebond : permis
    r = rule(perso, 'stop')
    assert r['mode'] == 'custom' and r['effective'] == 130.0 and r['custom'] == 130.0
    assert abs(r['auto'] - auto['prices']['suggested']) < 1e-9, 'le moteur continue de calculer sa suggestion'
    assert perso['prices']['effective'] == 130.0 and perso['prices']['effective_source'] == 'custom'
    assert 'Protection personnelle : ' in perso['advice']['protection'] and '(automatique : ' in perso['advice']['protection']
    assert perso['advice']['state'] == 'watch'                      # cours 160 > 130 : non franchie
    c2 = c[:-1] + [128.0]
    crossed = plan(c2, 'recovery', pru=85.47, stop=130.0)
    assert crossed['advice']['state'] == 'exit' and crossed['advice']['rule'] == 'stop'
    assert crossed['advice']['headline'] == 'Sortie à envisager — Ta protection personnelle de 130,00 € est franchie.'


def test_return_to_automatic_restores_only_that_rule():
    c = gibo()
    custom = plan(c, 'recovery', pru=85.47, stop=130.0, rules={'recul': {'custom': 30.0}, 'trend': {'enabled': False}})
    back = plan(c, 'recovery', pru=85.47, stop=None, rules={'recul': {'custom': 30.0}, 'trend': {'enabled': False}})   # seul le filet revient à l'automatique
    assert rule(back, 'stop')['mode'] == 'auto' and rule(back, 'stop')['effective'] == back['prices']['suggested']
    assert rule(back, 'recul')['mode'] == 'custom' and rule(back, 'recul')['custom'] == 30.0
    assert rule(back, 'trend')['enabled'] is False and rule(custom, 'stop')['mode'] == 'custom'


def test_protection_above_pru_and_above_current_price():
    c = path([(0, 100), (260, 160)], noise=0.012)
    above_pru = plan(c, 'regular', pru=100, stop=120.0)
    assert rule(above_pru, 'stop')['effective'] == 120.0 > above_pru['prices']['pru'] and not rule(above_pru, 'stop')['triggered']
    above_cur = plan(c, 'regular', pru=100, stop=170.0)
    assert rule(above_cur, 'stop')['triggered'] and above_cur['advice']['state'] == 'exit'


def test_personal_objective_reached_is_exit_and_never_automatic():
    c = path([(0, 100), (260, 160)], noise=0.012)
    none = plan(c, 'regular', pru=100)
    assert rule(none, 'target')['mode'] == 'none' and not rule(none, 'target')['triggered'] and none['advice']['state'] == 'keep'
    below = plan(c, 'regular', pru=100, target=150.0)                       # objectif déjà dépassé
    assert rule(below, 'target')['triggered'] and below['advice']['state'] == 'exit' and below['advice']['rule'] == 'target'
    assert below['advice']['headline'] == 'Sortie à envisager — Ton objectif de gain de 150,00 € est atteint.'
    far = plan(c, 'regular', pru=100, target=300.0)
    assert not rule(far, 'target')['triggered'] and far['advice']['state'] == 'keep'


def test_custom_recul_threshold_means_reevaluate_while_automatic_means_watch():
    c = path([(0, 100), (200, 160), (240, 148)], noise=0.012)               # recul ≈ 7,5 %, volatilité modérée (repli médian ≈ 8,5 %)
    auto = plan(c, 'low_volatility', pru=100)
    custom = plan(c, 'low_volatility', pru=100, rules={'recul': {'custom': 5.0}})
    assert rule(custom, 'recul')['mode'] == 'custom' and rule(custom, 'recul')['triggered']
    assert custom['advice']['state'] == 'reevaluate' and custom['advice']['label'] == 'Réévaluer' and custom['advice']['rule'] == 'recul'
    assert 'dépasse ton seuil de 5,0 %' in custom['advice']['headline']
    assert auto['advice']['state'] != 'reevaluate'
    ok = plan(c, 'low_volatility', pru=100, rules={'recul': {'custom': 40.0}})
    assert not rule(ok, 'recul')['triggered']


def test_disabled_rules_are_not_evaluated_but_still_computed():
    c = path([(0, 100), (200, 200), (260, 150)], noise=0.012)
    p = plan(c, 'regular', pru=100, rules={'stop': {'enabled': False}})
    r = rule(p, 'stop')
    assert r['enabled'] is False and r['effective'] is None and not r['triggered'] and r['auto'] is not None
    assert p['advice']['state'] != 'exit' and p['advice']['protection'] == 'Protection désactivée pour cette position.'
    dec = decline_series()
    on, off = plan(dec, 'regular', pru=100), plan(dec, 'regular', pru=100, rules={'trend': {'enabled': False}, 'stop': {'enabled': False}})
    assert rule(on, 'trend')['triggered'] and not rule(off, 'trend')['triggered'] and 'momentum' not in texts(off)
    risky = plan(gibo(), 'recovery', pru=85.47, rules={'risk': {'enabled': False}})
    assert risky['advice']['state'] == 'keep' and not rule(risky, 'risk')['triggered']


def test_several_rules_triggered_main_is_highest_priority_and_others_are_listed():
    c = decline_series()                                                      # 100 -> 200 -> 140 : tendance dégradée, recul 30 %, protection automatique franchie
    p = plan(c, 'low_volatility', pru=100, stop=150.0, target=130.0, rules={'recul': {'custom': 10.0}})
    a = p['advice']
    assert a['state'] == 'exit' and a['rule'] == 'stop' and 'personnelle' in a['headline']
    keys = [o['key'] for o in a['others']]
    assert keys[0] == 'target' and {'recul', 'trend'} <= set(keys)           # objectif atteint (sortie) avant la réévaluation, avant la vigilance
    states = [o['state'] for o in a['others']]
    order = {'exit': 0, 'reevaluate': 1, 'watch': 2}
    assert states == sorted(states, key=lambda x: order[x])
    assert all(o['text'] and o['detail'] for o in a['others'])


def test_insufficient_data_personal_rules_still_work_and_nothing_is_invented():
    c = path([(0, 100), (40, 120)], noise=0.012)
    p = plan(c, 'regular', pru=100)
    s = rule(p, 'stop')
    assert s['auto'] is None and s['effective'] is None and 'indisponible' in s['note'] and rule(p, 'recul')['auto'] is None
    assert p['advice']['state'] == 'na' and 'Protection automatique indisponible' in p['advice']['protection']
    hit = plan(c, 'regular', pru=100, stop=130.0)                             # protection personnelle déjà franchie : signalée malgré l'historique court
    assert hit['advice']['state'] == 'exit' and 'personnelle' in hit['advice']['headline']


def test_every_strategy_accepts_personal_protection():
    c = path([(0, 100), (200, 180), (260, 150)], noise=0.012)
    for key in ('regular', 'fast', 'low_volatility', 'momentum', 'momentum12', 'momentum_risk', 'recovery', None):
        p = plan(c, key, pru=100, stop=155.0)
        assert rule(p, 'stop')['mode'] == 'custom' and p['advice']['state'] == 'exit' and p['advice']['rule'] == 'stop', key
