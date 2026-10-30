"""Résumé du profil : appréciation descriptive, période sur les pastilles, filtres de niveau (masquage seul, sans effet sur rang ni score)."""
import pathlib

from engine.analytics import service, signals

ROOT = pathlib.Path(__file__).resolve().parents[2]


def measures(week=(1.0, 0.9, 6.0), month=(0.5, 0.9, 12.0), quarter=(0.3, 0.9, 25.0), year=(0.15, 0.9, 40.0)):
    return {n: {'slope': v[0], 'r2': v[1], 'perf': v[2]} for n, v in ((5, week), (21, month), (63, quarter), (252, year)) if v}


def pills(r2=0.9, vol=1.0, dd=10.0, daily=10_000_000.0, ref=21, quality='ok'):
    return [signals.regularity(r2, ref), signals.risk(vol, dd, ref), signals.liquidity(daily, 'equity', None, 1), signals.data_quality(quality, None, False)]


def test_pills_name_the_period_they_really_measure():
    reg, risk, liq, _ = pills()
    assert (reg['period'], risk['period']) == ('1 mois', '1 mois')
    assert liq['period'] == '3 mois'                                  # volume moyen 3 mois, quelle que soit la période de la stratégie
    assert signals.regularity(0.9, 63)['period'] == '3 mois' and signals.risk(1, 1, 252)['period'] == '1 an'
    assert signals.regularity(None, 21)['period'] == '1 mois'         # même inconnue, la pastille dit sa période


def test_a_strong_rise_with_everything_favourable_is_very_favourable():
    a = signals.assessment(measures(), 21, pills())
    assert (a['code'], a['label'], a['level']) == ('very_favorable', 'Très favorable', 'ok')
    assert 'montée très régulière' in a['strengths'] and any('forte hausse sur 1 mois' in x for x in a['strengths'])
    assert a['nothing_flagged'] and 'tendance peut s’arrêter' in a['closing']


def test_a_strong_rise_is_never_favourable_when_a_risk_is_important():
    for bad in (dict(vol=6.0, dd=60.0), dict(r2=0.2), dict(daily=1_000.0)):          # volatilité forte, hausse irrégulière, négociabilité limitée
        a = signals.assessment(measures(), 21, pills(**bad))
        assert a['code'] == 'mixed' and 'risque important' in a['reason'], bad
    a = signals.assessment(measures(), 21, pills(vol=6.0, dd=60.0, r2=0.2))
    assert a['code'] == 'mixed' and '2 risques importants' in a['reason']
    a = signals.assessment(measures(), 21, pills(vol=6.0, dd=60.0, r2=0.2, daily=1_000.0))
    assert a['code'] == 'unfavorable'


def test_one_vigilance_point_keeps_favourable_but_two_make_it_mixed():
    one = signals.assessment(measures(), 21, pills(vol=2.0))                                 # volatilité modérée
    assert one['code'] == 'favorable' and any('volatilité modérée' in c for c in one['cautions'])
    two = signals.assessment(measures(), 21, pills(vol=2.0, daily=2_000_000.0))              # + négociabilité à surveiller
    assert two['code'] == 'mixed' and '2 points de vigilance' in two['reason']


def test_texts_keep_their_units_and_never_give_advice():
    a = signals.assessment(measures(), 21, pills(daily=2_300_000.0))
    assert any('2,3 M€' in c for c in a['cautions'])                                         # « M€ » jamais mis en minuscules
    text = ' '.join([a['label'], a['reason'], a['closing']] + a['strengths'] + a['cautions']).lower()
    assert 'acheter' not in text.replace('conseil d’achat', '') and 'vendre' not in text.replace('de vente', '')


def test_a_falling_curve_is_unfavourable_and_missing_data_is_undetermined():
    assert signals.assessment(measures(month=(-0.2, 0.9, -8.0)), 21, pills())['code'] == 'unfavorable'
    assert signals.assessment({}, 21, pills())['code'] == 'undetermined'
    short = signals.assessment(measures(), 21, pills(quality='insufficient'))
    assert short['code'] == 'undetermined' and 'historique court' in short['reason']
    broke = signals.assessment(measures(), 21, pills(quality='break'))
    assert broke['code'] == 'mixed' and 'rupture de cours' in broke['cautions']                  # période mesurée : la rupture est un risque important, pas un motif d'ignorer la mesure
    unknown = signals.assessment(measures(), 21, [signals.regularity(None, 21), signals.risk(None, None, 21), signals.liquidity(1e7, 'equity', None, 1)])
    assert unknown['code'] == 'undetermined'                                                  # deux indicateurs inconnus : rien n'est supposé


def test_one_unknown_indicator_never_gives_very_favourable_and_stays_listed_as_unknown():
    a = signals.assessment(measures(), 21, [signals.regularity(0.9, 21), signals.risk(1, 10, 21), signals.liquidity(None, 'equity')])
    assert a['code'] == 'favorable' and a['unknowns'] == ['négociabilité'] and not a['nothing_flagged']


def test_a_recent_drop_contradicting_the_background_trend_is_reported_and_caps_the_rating():
    m = measures(week=(-1.0, 0.5, -7.0), month=(0.3, 0.8, 6.0), quarter=(0.3, 0.9, 25.0), year=(0.2, 0.9, 60.0))
    a = signals.assessment(m, 63, pills(ref=63))
    assert a['contradiction']['kind'] == 'drop' and 'Repli récent' in a['contradiction']['text']
    assert a['code'] == 'mixed' and any('repli récent' in c for c in a['cautions'])
    rebound = signals.contradiction(measures(week=(1, 1, 3), month=(1, 1, 14.0), quarter=(1, 1, 5.0), year=(-0.2, 0.5, -30.0)))
    assert rebound['kind'] == 'rise'
    assert signals.contradiction(measures(year=None, quarter=None)) is None                  # sans mesure de fond, rien n'est affirmé


def test_an_extreme_rise_is_flagged_and_cannot_be_very_favourable():
    a = signals.assessment(measures(month=(3.0, 0.95, 150.0)), 21, pills())
    assert a['code'] == 'favorable' and any('peut se retourner vite' in c for c in a['cautions'])


def test_the_assessment_follows_the_strategy_period():
    m = measures(month=(0.5, 0.9, 12.0), quarter=(-0.1, 0.4, -3.0))
    assert signals.assessment(m, 21, pills())['code'] == 'very_favorable'
    a = signals.assessment(m, 63, pills(ref=63))
    assert a['code'] == 'unfavorable' and a['period'] == '3 mois' and '3 mois' in a['reason']


def rows(n=6):
    return [{'id': i, 'symbol': f'S{i}', 'isin': None, 'kind': 'equity', 'rank': i + 1, 'score': 100 - i} for i in range(n)]


def aux_for(levels):
    ok = {'r2': 0.9, 'volatility': 1.0, 'drawdown': 5.0, 'price_eur': 10.0, 'volume': 1_000_000, 'quote_age_days': 1}
    bad_r2 = dict(ok, r2=0.1)
    return {i: (bad_r2 if lv == 'bad' else ok) for i, lv in enumerate(levels)}


def test_level_filters_only_hide_and_never_change_rank_score_or_order():
    levels = ['ok', 'bad', 'ok', 'bad', 'ok', 'ok']
    base = rows()
    kept, counts = service.level_filtered_rows(base, aux_for(levels), 21, None, {'regularity': {'ok'}})
    assert [e['id'] for e in kept] == [0, 2, 4, 5] and [(e['rank'], e['score']) for e in kept] == [(1, 100), (3, 98), (5, 96), (6, 95)]
    assert counts['regularity'] == {'ok': 4, 'bad': 2}
    allrows, _ = service.level_filtered_rows(base, aux_for(levels), 21, None, {})
    assert allrows == base                                                                    # aucun choix : rien n'est masqué
    both, _ = service.level_filtered_rows(base, aux_for(levels), 21, None, {'regularity': {'ok'}, 'liquidity': {'bad'}})
    assert both == []                                                                         # les filtres se cumulent
    exact, _ = service.level_filtered_rows(base, aux_for(levels), 21, None, {'regularity': {'ok'}}, query='s1')
    assert 1 in [e['id'] for e in exact]                                                      # un titre retrouvé par son symbole exact n'est jamais masqué


def test_the_interface_exposes_the_three_multi_choice_filters_and_the_summary():
    html, js = (ROOT / 'app/public/index.html').read_text(), (ROOT / 'app/public/assets/explorer.js').read_text()
    for key in ('regularity', 'risk', 'liquidity'):
        assert f'id="{key}"' in html and f"{key}: JMulti(el('{key}'))" in js
    assert "'regularity', 'risk', 'liquidity'" in (ROOT / 'app/routes/explore.php').read_text()
    assert 'JEtf.assessment(s.assessment)' in (ROOT / 'app/public/assets/titre.js').read_text()
    assert 's.period' in (ROOT / 'app/public/assets/etf.js').read_text()
