"""Moteur unique de décision des critères de recherche : retenue / exclue / indéterminée, unités, indépendance des scores."""
from engine.analytics import criteria as CR


def spec(**periods):
    return {'periods': {k: {'enabled': True, 'slope': v[0], 'r2': v[1]} for k, v in periods.items()}, 'extra': [], 'join': 'and'}


def metrics(**by):
    sessions = CR.PERIODS
    return {'m': {sessions[k]: {'slope': v[0], 'r2': v[1], 'perf': v[2] if len(v) > 2 else None, 'volatility': None, 'drawdown': None} for k, v in by.items()}}


def status(sp, m):
    return CR.evaluate(CR.normalize(sp), m)['status']


def test_retained_when_every_active_criterion_passes():
    assert status(spec(month=(0.07, 0.5)), metrics(month=(0.1, 0.6))) == CR.RETAINED


def test_excluded_when_one_criterion_fails():
    ev = CR.evaluate(CR.normalize(spec(month=(0.07, 0.5))), metrics(month=(0.1, 0.4)))
    assert ev['status'] == CR.EXCLUDED
    fails = [c for c in ev['checks'] if c['result'] == 'fail']
    assert [(c['metric'], c['period']) for c in fails] == [('r2', 'month')] and fails[0]['value'] == 0.4 and fails[0]['threshold'] == 0.5


def test_missing_measure_is_undetermined_never_excluded():
    assert status(spec(month=(0.07, 0.5)), {'m': {}}) == CR.UNDETERMINED
    assert status(spec(month=(0.07, 0.5)), metrics(month=(0.1, None))) == CR.UNDETERMINED


def test_a_proven_failure_wins_over_missing_data():
    assert status(spec(week=(0.5, 0), month=(0.07, 0)), metrics(month=(0.01, 0.9))) == CR.EXCLUDED


def test_no_active_criterion_is_retained_but_flagged_free():
    norm = CR.normalize(spec(month=(0, 0)))
    assert norm is not None and CR.evaluate(norm, metrics(month=(-5, 0)))['active'] == 0
    assert CR.evaluate(norm, metrics())['status'] == CR.RETAINED


def test_missing_context_is_undetermined_never_retained():
    assert CR.normalize(None) is None and CR.normalize({}) is None
    assert CR.evaluate(None, metrics(month=(9, 1)))['status'] == CR.UNDETERMINED


def test_disabled_period_is_ignored():
    sp = spec(month=(0.07, 0.5))
    sp['periods']['month']['enabled'] = False
    assert status(sp, metrics(month=(-1, 0))) == CR.RETAINED


def test_extra_rules_and_or():
    sp = spec(month=(0, 0))
    sp['extra'] = [{'metric': 'return', 'period': 'quarter', 'op': '>=', 'value': 5}, {'metric': 'return', 'period': 'month', 'op': '>=', 'value': 5}]
    m = metrics(quarter=(0, 0, 6), month=(0, 0, 1))
    assert status(sp, m) == CR.EXCLUDED
    assert status(dict(sp, join='or'), m) == CR.RETAINED


def test_slope_unit_is_percent_per_session_in_checks():
    ev = CR.evaluate(CR.normalize(spec(month=(0.07, 0))), metrics(month=(0.2, 0.9)))
    assert ev['checks'][0]['unit'] == '% par séance' and ev['checks'][0]['op'] == '>='


def test_counts_cover_every_title():
    assert CR.counts([CR.RETAINED, CR.EXCLUDED, CR.UNDETERMINED, CR.RETAINED]) == {'retained': 2, 'excluded': 1, 'undetermined': 1, 'all': 4}
