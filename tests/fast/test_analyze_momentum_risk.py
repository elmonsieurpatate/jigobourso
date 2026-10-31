"""Analyse des pires périodes du Momentum 6-1 : mesures, successions, crises, concentration, rapport pédagogique, deux modes de lecture."""
import csv
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'fast'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', f'{name}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


am = load('analyze_momentum_risk')
eh = load('export_history')


def row(d, pick, universe=0.0, **extra):
    return dict({'date': d, 'pick': pick, 'universe': universe, 'picks_count': 20}, **extra)


def test_drawdown_depth_dates_and_recovery():
    dates = ['2020-01-31', '2020-02-28', '2020-03-31', '2020-04-30', '2020-05-29', '2020-06-30']
    eps = am.drawdown_episodes(dates, [10.0, -20.0, -25.0, 100.0, 10.0, -5.0])
    worst = eps[0]
    assert worst['peak'] == '2020-01-31' and worst['trough'] == '2020-03-31'
    assert round(worst['depth'], 2) == -40.0                       # 0,8 × 0,75 = 0,6
    assert worst['months_down'] == 2 and worst['recovery'] == '2020-04-30' and worst['months_to_recover'] == 3
    assert eps[1]['recovery'] is None and eps[1]['peak'] == '2020-05-29'            # dernière baisse jamais retrouvée


def test_drawdown_when_the_first_period_is_already_a_loss():
    eps = am.drawdown_episodes(['2020-01-31', '2020-02-28'], [-10.0, -10.0])
    assert eps[0]['peak'] == 'début' and round(eps[0]['depth'], 2) == -19.0 and eps[0]['recovery'] is None


def test_loss_streaks_count_runs_and_never_cross_a_gap():
    rows = [row('2020-01-31', -1), row('2020-02-28', -2), row('2020-03-31', 3), row('2020-04-30', -1), row('2020-05-29', -1), row('2020-06-30', -1), row('2020-07-31', -1), row('2020-08-31', 2)]
    st = am.loss_streaks(am.segments(rows), lambda r: r['pick'])
    assert st['counts'] == {1: 0, 2: 1, 3: 0, '4+': 1} and st['longest']['length'] == 4 and st['longest']['start'] == '2020-04-30'
    gap = [row('2020-01-31', -1), row('2020-02-28', -1), row('2020-06-30', -1), row('2020-07-31', -1)]          # trou de 4 mois : deux séries de deux, pas une de quatre
    assert len(am.segments(gap)) == 2
    assert am.loss_streaks(am.segments(gap), lambda r: r['pick'])['counts'][2] == 2


def test_costs_are_a_round_trip_per_period():
    assert am.net_returns([row('2020-01-31', 1.0)], 30) == [1.0 - 0.6]
    assert am.net_returns([row('2020-01-31', 1.0)], 0) == [1.0]


def test_crisis_table_uses_only_the_fixed_windows():
    rows = [row('2008-09-30', -10, -5), row('2008-10-31', -20, -10), row('2010-01-29', 5, 4)]
    table = am.crisis_table(rows, windows=(('Crise', '2007-10-01', '2009-02-28'), ('Vide', '2015-01-01', '2015-12-31')))
    assert table[0]['months'] == 2 and round(table[0]['pick_total'], 1) == -28.0 and round(table[0]['mean_excess'], 1) == -7.5
    assert table[0]['worst_month'] == -20 and table[0]['share_negative_excess'] == 100.0
    assert table[1]['months'] == 0
    assert [c[1] for c in am.CRISES] == sorted(c[1] for c in am.CRISES)                 # fenêtres chronologiques, figées dans le code


def test_concentration_by_group_repeats_and_top_contributors():
    meta = {i: {'category': 'Tech' if i < 15 else 'Santé', 'country': 'US', 'currency': 'USD', 'symbol': f'S{i}'} for i in range(30)}
    a = row('2020-01-31', 0, returns={i: 1.0 for i in range(20)})
    b = row('2020-02-28', 0, returns={i: -1.0 for i in range(10, 30)})
    c = am.concentration([a, b], meta)
    assert c['fields']['category']['top_share_max'] == 75.0 and c['fields']['country']['top_share_mean'] == 100.0
    assert c['repeat_share'] == 50.0 and round(c['top3_contribution_mean'], 1) == 15.0
    far = row('2020-06-30', 0, returns={i: 1.0 for i in range(20)})
    assert am.concentration([a, far], meta)['repeat_share'] is None                       # un trou : pas « le mois suivant »
    assert am.worst_month_detail(row('d', 0, returns={1: -50.0, 2: 3.0, 3: -10.0}), meta, 2) == [('S1', -50.0), ('S3', -10.0)]


def synthetic_json(months=60):
    import datetime
    d, results = datetime.date(2010, 1, 29), []
    by_date = []
    for i in range(months):
        by_date.append({'date': d.isoformat(), 'picks': 20, 'pick': (-8.0 if i % 7 == 0 else 2.0), 'universe': 1.0})
        d += datetime.timedelta(days=30)
    for name in am.SCENARIOS:
        results.append({'period': '2017-2026', 'horizon': 21, 'scenario': name, 'by_date': by_date})
        results.append({'period': '2017-2026', 'horizon': 63, 'scenario': name, 'by_date': by_date[:5]})          # autre horizon : ignoré
    return {'results': results}


def test_json_mode_report_is_pedagogical_without_promises(tmp_path, capsys):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps(synthetic_json()), encoding='utf-8')
    out = tmp_path / 'rapport.md'
    rc = am.main(['--json-in', str(path), '--from', '2010-01-01', '--out', str(out)])
    text = capsys.readouterr().out
    assert rc == 0 and out.read_text(encoding='utf-8').strip() == text.strip()
    for part in ('Comment lire ce rapport', 'Perte maximale', 'Successions de mois perdants', 'Comportement pendant les crises', 'Ce que ces chiffres ne disent pas', 'brut (sans frais)', '30 points de base'):
        assert part in text
    for name in am.SCENARIOS:
        assert f'Scénario « {name} »' in text
    assert 'Concentration des sélections' not in text                                        # le JSON ne contient pas les titres choisis
    low = text.lower()
    assert 'aucune supériorité démontrée' in low and 'rien sur l\'avenir' in low
    assert 'garanti' not in low and 'surperform' not in low


def test_short_scenarios_are_skipped_and_empty_input_fails(tmp_path, capsys):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps(synthetic_json(5)), encoding='utf-8')
    assert am.main(['--json-in', str(path)]) == 3


def test_csv_mode_full_recompute_adds_concentration(tmp_path, capsys):
    from test_backtest_liquidity import business_days, candidate
    days = business_days(1500)
    cands = [candidate(i, days, drift=0.0004, sigma=0.012, volume=60_000 + 900 * i, currency='USD', seed=5, price=100.0) for i in range(180)]
    for c in cands:
        eh.write_history(str(tmp_path), c['key'], [(d, p, a, v) for (d, p, a), v in zip(c['bars'], c['volumes'])])
    eh.write_universe(str(tmp_path), [{'key': c['key'], 'symbol': c['symbol'], 'mic': 'XNYS', 'kind': 'equity', 'country': 'United States', 'currency': 'USD',
                                       'category': 'Tech' if c['key'] % 2 else 'Santé'} for c in cands])
    rc = am.main(['--csv-dir', str(tmp_path), '--from', days[200], '--min-pool', '40', '--min-titles', '0'])
    text = capsys.readouterr().out
    assert rc == 0 and 'Concentration des sélections' in text and 'Par secteur' in text and 'Titres qui ont le plus pesé' in text


def test_update_universe_adds_the_sector_without_touching_history(tmp_path):
    eh.write_universe(str(tmp_path), [{'key': 1, 'symbol': 'A', 'mic': 'X', 'kind': 'equity', 'country': 'FR', 'currency': 'EUR'},
                                     {'key': 2, 'symbol': 'B', 'mic': 'X', 'kind': 'equity', 'country': 'FR', 'currency': 'EUR'}])
    fresh = [{'key': k, 'symbol': s, 'mic': 'X', 'kind': 'equity', 'country': 'FR', 'currency': 'EUR', 'category': 'Industrie'} for k, s in ((1, 'A'), (2, 'B'), (3, 'C'))]
    assert eh.update_universe(fresh, str(tmp_path)) == 2                                     # le titre 3 n'a pas été exporté : absent
    rows = list(csv.DictReader(open(tmp_path / 'universe.csv', encoding='utf-8')))
    assert [r['category'] for r in rows] == ['Industrie', 'Industrie'] and 'category' in eh.UNIVERSE_FIELDS
