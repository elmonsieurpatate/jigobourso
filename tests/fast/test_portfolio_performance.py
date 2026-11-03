"""Exercise the actual JavaScript performance function with independent cash-flow examples."""
import json
from pathlib import Path
import subprocess

import pytest


def perf(gain, values, purchases, start, end):
    source = (Path(__file__).resolve().parents[2] / 'app/public/assets/portefeuilles.js').read_text()
    function = source[source.index('  function perf('):source.index('  const PER_LABEL')]
    code = function + '\nconsole.log(JSON.stringify(perf(...JSON.parse(process.argv[1]))));'
    out = subprocess.run(['node', '-e', code, json.dumps([gain, values, purchases, start, end])],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_total_percentage_uses_purchases_not_net_cash_after_full_sale():
    assert perf([0, 20], [100, 0], [100, 100], 0, 1) == {'eur': 20, 'pct': 20}
    result = perf([0, 233.4], [100, 2900.4], [100, 3942], 0, 1)
    assert result['pct'] == pytest.approx(100 * 233.4 / 3942)


def test_period_includes_new_purchases_but_does_not_subtract_sales():
    # Start value 1000, purchase 500, net sale 300, final value 1300 => gain 100.
    assert perf([0, 0, 100], [0, 1000, 1300], [0, 1000, 1500], 1, 2) == {'eur': 100, 'pct': 100 / 15}


def test_unknown_value_is_not_zero_and_small_capital_has_a_percentage():
    assert perf([None, None], [None, None], [10, 10], 0, 1) == {'eur': None, 'pct': None}
    assert perf([0, .1], [.1, .2], [.1, .1], 0, 1) == {'eur': .1, 'pct': 100}
