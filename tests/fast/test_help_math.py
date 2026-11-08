"""L'aide interactive recalcule mesures et scores en JavaScript (help-math.js) sur des exemples fictifs : ces calculs doivent rester identiques à ceux du moteur Python."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from engine.analytics import measures as M, score_inputs as SI, scores as S

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node absent')


def make_series(n, total, amp, cycles, noise=0.0):
    b = math.log(1 + total / 100) / n
    return [100 * math.exp(b * t + amp * math.sin(2 * math.pi * cycles * t / n)) for t in range(n + 1)]


CASES = [make_series(300, 60, 0.0, 1), make_series(300, 60, 0.15, 7), make_series(300, 25, 0.05, 3), make_series(300, -20, 0.08, 5), make_series(300, 130, 0.02, 2)]
IDS = {'a': ['week', 'month'], 'b': ['month', 'quarter'], 'c': ['week', 'month', 'quarter', 'half']}
SESS = {'week': 5, 'month': 21, 'quarter': 63, 'half': 126}


def python_eval(closes, ids, liquidity, anchor=0.5):
    inputs = {}
    for i in ids:
        n = SESS[i]; w = closes[-1 - n:]
        m = M.window_metrics(w); m.update(SI.path_inputs(w)); m.update(accel=None, r2_prev=None); inputs[n] = m
    periods = [{'id': i, 'sessions': SESS[i]} for i in ids]
    r = S.score_title(inputs, {'turnover_eur': liquidity, 'source': 'daily'}, periods, kappa=0.7, anchor=anchor)
    return {'simple': r['simple']['score'], 'complex': r['complex']['score'], 'weights': r['weights'],
            'slope': {i: inputs[SESS[i]]['slope'] for i in ids}, 'r2': {i: inputs[SESS[i]]['r2'] for i in ids}, 'vol': {i: inputs[SESS[i]]['volatility'] for i in ids}, 'dd': {i: inputs[SESS[i]]['drawdown'] for i in ids}}


def test_javascript_matches_python_engine():
    cases = [{'closes': c, 'ids': IDS[k], 'liq': liq, 'anchor': a} for c in CASES for k in IDS for liq, a in ((20e6, 0.5), (3e6, 0.0), (80e6, 1.0))]
    code = "const HM=require(%s);const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(cases.map(c=>{const r=HM.evaluate({closes:c.closes,liquidity:c.liq},c.ids,{anchor:c.anchor});const o={simple:r.simple.score,complex:r.complex.score,weights:r.weights,slope:{},r2:{},vol:{},dd:{}};r.periods.forEach(p=>{o.slope[p.id]=p.m.slope;o.r2[p.id]=p.m.r2;o.vol[p.id]=p.m.volatility;o.dd[p.id]=p.m.drawdown});return o;})))" % json.dumps(str(ROOT / 'app/public/assets/help-math.js'))
    out = subprocess.run(['node', '-e', code], input=json.dumps(cases), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    for c, g in zip(cases, got):
        want = python_eval(c['closes'], c['ids'], c['liq'], c['anchor'])
        for k in ('simple', 'complex'):
            assert g[k] == pytest.approx(want[k], abs=1e-6), (k, c['ids'], c['liq'], g[k], want[k])
        for i in c['ids']:
            assert g['weights'][i] == pytest.approx(want['weights'][i], abs=1e-9)
            for k in ('slope', 'r2', 'vol', 'dd'):
                assert g[k][i] == pytest.approx(want[k][i], abs=1e-6)


def test_fifo_and_dietz_examples():
    code = "const HM=require(%s);console.log(JSON.stringify([HM.fifo([{qty:10,price:5},{qty:10,price:8}],[{qty:10,price:10}]),HM.dietz(1000,2300,[{amount:1000,t:0.5}])]))" % json.dumps(str(ROOT / 'app/public/assets/help-math.js'))
    f, d = json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=30).stdout)
    assert f['realized'] == 50 and f['qty'] == 10 and f['cost'] == 80 and f['avg'] == 8
    assert d['gain'] == 300 and d['den'] == 1500 and d['perf'] == pytest.approx(20.0)
