"""F12 : unités de prix — mêmes facteurs vers l'euro en Python (engine/shared/units.py) et en PHP (eur_factor)."""

import json
import os
import shutil
import subprocess

import pytest

from engine.shared.units import is_subunit, split_unit, to_eur_factor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RATES = {'GBP': 1.2, 'ZAR': 0.05, 'ILS': 0.25, 'USD': 0.9, 'EUR': 1.0}
UNITS = ['EUR', 'eur', 'USD', 'usd', 'GBP', 'gbp', 'GBp', 'GBX', 'gbx', 'ZAc', 'ZAC', 'zac', 'ILA', 'ila', 'ILS', 'ZAR', 'CHF', 'XXX', '', None]
EXPECTED = {'GBP': 1.2, 'GBp': 0.012, 'GBX': 0.012, 'ZAc': 0.0005, 'ZAC': 0.0005, 'ILA': 0.0025, 'ILS': 0.25, 'EUR': 1.0, 'USD': 0.9}


@pytest.mark.parametrize('unit,factor', EXPECTED.items())
def test_python_factors(unit, factor):
    assert to_eur_factor(unit, RATES) == pytest.approx(factor)


def test_unknown_or_missing_unit_is_none():
    assert to_eur_factor('CHF', RATES) is None and to_eur_factor('', RATES) is None and to_eur_factor(None, RATES) is None


def test_pound_is_not_pence_and_subunit_detection():
    assert split_unit('GBP') == ('GBP', 1) and split_unit('GBp') == ('GBP', 100)
    assert is_subunit('ILA') and is_subunit('GBX') and not is_subunit('GBP') and not is_subunit(None)


@pytest.mark.skipif(not shutil.which('php'), reason='php absent')
def test_php_matches_python():
    code = (
        "require " + json.dumps(ROOT + '/app/services/ledger.php') + "; $r = json_decode('" + json.dumps(RATES) + "', true); $out = [];"
        "foreach (json_decode('" + json.dumps(UNITS) + "', true) as $u) $out[] = eur_factor($u, $r); echo json_encode($out);"
    )
    out = subprocess.run(['php', '-r', code], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [to_eur_factor(u, RATES) for u in UNITS]


@pytest.mark.skipif(not shutil.which('php'), reason='php absent')
def test_unreadable_split_events_are_unavailable_not_empty():
    """F01 : base injoignable = 503 explicite, jamais une liste vide qui ferait calculer des quantités sans split."""
    code = (
        "require " + json.dumps(ROOT + '/app/services/ledger.php') + ";"
        "try { echo json_encode(['ok' => split_events([1, 2])]); } catch (ApiError $e) { echo json_encode(['status' => $e->status]); }"
        " echo '|', json_encode(split_events([]));"
    )
    env = dict(os.environ, JIGO_DB_HOST='127.0.0.1', JIGO_DB_NAME='x', JIGO_DB_USER='x', JIGO_DB_PASSWORD='x', JIGO_DB_SOCKET='/nonexistent/mysql.sock')
    out = subprocess.run(['php', '-r', code], capture_output=True, text=True, timeout=30, env=env)
    assert out.returncode == 0, out.stderr
    unreadable, empty = out.stdout.split('|')
    assert json.loads(unreadable) == {'status': 503}
    assert json.loads(empty) == []  # aucun titre demandé : vide légitime, sans lecture
