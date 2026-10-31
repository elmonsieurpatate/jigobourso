"""Relecture du test de liquidité (scripts/summarize_liquidity.py) : restriction de dates, dates communes, arithmétique des frais, intervalle."""
import importlib.util
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('summarize_liquidity', os.path.join(ROOT, 'scripts', 'summarize_liquidity.py'))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


def entry(scenario, period, horizon, rows):
    return {'scenario': scenario, 'period': period, 'horizon': horizon, 'by_date': [{'date': d, 'picks': 20, 'pick': p, 'universe': u} for d, p, u in rows]}


def sample():
    wide = [(f'1990-0{m}-15', 3.0, 1.0) for m in (1, 2, 3)] + [(f'1995-{m:02d}-15', 2.0, 1.0) for m in range(1, 7)]      # 3 dates anciennes + 6 dates
    strict = [(f'1995-{m:02d}-15', 1.5, 1.0) for m in range(2, 7)]                                                          # le scénario strict en écarte aussi (janvier 1995)
    return {'results': [entry('aucun', 'P', 21, wide), entry('strict', 'P', 21, strict)]}


def test_from_date_restricts_every_scenario():
    groups = sl.collect(sample(), start='1993-01-01')
    assert set(groups[('P', 21)]['aucun']) == {f'1995-{m:02d}-15' for m in range(1, 7)}       # les dates de 1990 disparaissent
    assert len(sl.collect(sample())[('P', 21)]['aucun']) == 9


def test_common_dates_compare_scenarios_on_the_same_days():
    text = sl.render(sample(), start='1993-01-01')
    assert 'DATES COMMUNES à tous les scénarios (5 dates)' in text                              # 6 dates larges ∩ 5 dates strictes
    own, common = text.split('DATES COMMUNES')
    assert 'aucun' in own and 'aucun' in common


def test_costs_t_stat_and_interval_arithmetic():
    rows = [(f'2000-{m:02d}-01', 2.0 + (m % 3) * 0.5, 1.0) for m in range(1, 10)]           # excès de 1,0 / 1,5 / 2,0
    a = sl.analyse(rows, 21)
    gross = sum(p - u for _, p, u in rows) / 9
    assert abs(a['gross'] - gross) < 1e-12 and a['dates'] == 9 and a['indep'] == 9
    for cost in sl.COSTS_BPS:
        assert abs(a['net'][cost] - (gross - 2 * cost / 100)) < 1e-12
    nets = [p - u - 0.2 for _, p, u in rows]
    mean = sum(nets) / 9
    sd = math.sqrt(sum((x - mean) ** 2 for x in nets) / 8)
    assert abs(a['t'] - mean / (sd / 3)) < 1e-9
    assert a['low'] <= mean <= a['high']
    assert sl.analyse(rows, 21) == sl.analyse(rows, 21)                                      # graine fixée : résultat reproductible


def test_long_horizon_uses_one_date_in_three_for_inference():
    rows = [(f'2000-{m:02d}-01', 1.0 + m, 1.0) for m in range(1, 10)]
    a = sl.analyse(rows, 63)
    assert a['dates'] == 9 and a['indep'] == 3                                                # 63 séances = 3 pas de 21 : chevauchement écarté


def test_cli_reads_the_json_file(tmp_path, capsys):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps(sample()), encoding='utf-8')
    assert sl.main(['--json', str(path), '--from', '1993-01-01', '--to', '1995-12-31']) == 0
    out = capsys.readouterr().out
    assert 'dates ≥ 1993-01-01' in out and 'IC95%' in out and 'strict' in out


def two_periods():
    old = [(f'1995-{m:02d}-15', 2.0, 1.0) for m in range(1, 7)]
    old_strict = [(f'1995-{m:02d}-15', 1.5, 1.0) for m in range(2, 7)]                     # janvier 1995 absent du scénario strict
    new = [(f'2020-{m:02d}-15', 3.0, 1.0) for m in range(1, 5)]
    return {'results': [entry('aucun', 'ancienne', 21, old), entry('strict', 'ancienne', 21, old_strict), entry('aucun', 'recente', 21, new), entry('strict', 'recente', 21, new)]}


def test_pooled_tables_put_the_common_dates_of_each_period_end_to_end():
    text = sl.render(two_periods(), pooled_only=True)
    assert 'TOUTES PÉRIODES ENSEMBLE · 21 séances' in text and '(9 dates)' in text            # 5 dates communes (ancienne) + 4 (récente)
    assert 'ancienne' not in text and 'Comparaisons multiples' in text                         # seulement le tableau combiné
    groups = sl.collect(two_periods())
    lines = sl.pooled_tables(groups)
    aucun = [l for l in lines if l.startswith('aucun')][0]
    assert ' 9 ' in aucun                                                                      # 9 dates, une estimation unique


def test_cli_pooled_flag(tmp_path, capsys):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps(two_periods()), encoding='utf-8')
    assert sl.main(['--json', str(path), '--pooled']) == 0
    out = capsys.readouterr().out
    assert 'dates propres à chaque scénario' in out and 'TOUTES PÉRIODES ENSEMBLE' in out
