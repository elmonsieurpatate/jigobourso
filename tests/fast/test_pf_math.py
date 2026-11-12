"""Le Portefeuille calcule résultats, contributions et courbes dans le navigateur (pf-math.js) à partir de l'historique du moteur : les règles d'additivité
(résultat du portefeuille = somme des positions, flux neutralisés) et le traitement des données manquantes sont vérifiés ici sur un historique réel du moteur."""
import datetime as dt, json, shutil, subprocess, pathlib
import pytest
from engine.analytics.series import history

ROOT = pathlib.Path(__file__).resolve().parents[2]
node = shutil.which('node')
pytestmark = pytest.mark.skipif(node is None, reason='node absent')


def make_history():
    start = dt.date(2026, 1, 5)
    days = [start + dt.timedelta(days=i) for i in range(0, 120) if (start + dt.timedelta(days=i)).weekday() < 5]
    bars = {1: [(d.isoformat(), 100 + 0.2 * i + (3 if i % 7 == 0 else 0), None) for i, d in enumerate(days)],
            2: [(d.isoformat(), 50 - 0.1 * i, None) for i, d in enumerate(days) if not (30 <= i < 34)]}     # titre 2 : quatre séances sans cours
    unit = {1: 'EUR', 2: 'EUR'}
    meta = {1: {'currency': 'EUR', 'symbol': 'AAA', 'name': 'Alpha', 'price': None, 'price_time': None}, 2: {'currency': 'EUR', 'symbol': 'BBB', 'name': 'Beta', 'price': None, 'price_time': None}}
    tx = [dict(id=1, listing_id=1, symbol='AAA', name='Alpha', side='buy', quantity=10, unit_price=100.4, currency='EUR', fx_to_eur=1, fees=1, trade_at=days[1].isoformat() + ' 12:00:00'),
          dict(id=2, listing_id=2, symbol='BBB', name='Beta', side='buy', quantity=20, unit_price=49.9, currency='EUR', fx_to_eur=1, fees=1, trade_at=days[10].isoformat() + ' 12:00:00'),
          dict(id=3, listing_id=1, symbol='AAA', name='Alpha', side='buy', quantity=5, unit_price=105, currency='EUR', fx_to_eur=1, fees=1, trade_at=days[40].isoformat() + ' 12:00:00'),
          dict(id=4, listing_id=1, symbol='AAA', name='Alpha', side='sell', quantity=8, unit_price=120, currency='EUR', fx_to_eur=1, fees=1, trade_at=days[60].isoformat() + ' 12:00:00')]
    return history.build(tx, bars, {}, unit, {}, meta, today=days[-1])


SCRIPT = r'''
const PFM = require(process.argv[1]); const H = JSON.parse(require('fs').readFileSync(0, 'utf8')); const out = {};
const near = (a, b) => Math.abs(a - b) < 0.011;
const res = {};
for (const per of ['all', '1m', '3m', '1d']) {
  const w = PFM.resolveWindow(H, per), pf = PFM.portfolio(H, w);
  const parts = H.lines.map(l => PFM.position(H, l, w).result).filter(v => v !== null);
  res[per] = { result: pf.result, sum: parts.reduce((a, b) => a + b, 0), pct: pf.pct, base: pf.base, i0: w.i0, i1: w.i1, clipped: w.clipped, reason: pf.pctReason };
}
// série : le dernier point du résultat cumulé = résultat de période ; pas de courbe avant le premier achat
const w = PFM.resolveWindow(H, 'all');
const sPf = PFM.series(H, w, 'pf', 'result'), sB = PFM.series(H, w, H.lines.find(l => l.symbol === 'BBB').key, 'result');
res.series = { last: sPf.y[sPf.y.length - 1], fullGain: H.gain[H.gain.length - 1], bFirstNonNull: sB.y.findIndex(v => v !== null), bFirstBuyIdx: PFM.firstActive(H.lines.find(l => l.symbol === 'BBB')), bNulls: sB.y.filter(v => v === null).length };
const sPerf = PFM.series(H, w, 'pf', 'perf'); res.perf = { n: sPerf.y.length, nulls: sPerf.y.filter(v => v === null).length, note: sPerf.note, last: sPerf.y[sPerf.y.length - 1] };
res.titles = PFM.countTitles(H.lines.map(l => ({ key: l.key })).concat(H.lines.map(l => ({ key: l.key }))));
console.log(JSON.stringify(res));
'''


def run():
    h = make_history()
    p = subprocess.run([node, '-e', SCRIPT, str(ROOT / 'app/public/assets/pf-math.js')], input=json.dumps(h, default=str), capture_output=True, text=True, check=True)
    return h, json.loads(p.stdout)


def test_period_results_are_additive_and_flow_neutral():
    h, r = run()
    assert r['all']['i0'] == -1 and abs(r['all']['result'] - h['gain'][-1]) < 0.011
    for per in ('all', '1m', '3m', '1d'):
        assert abs(r[per]['result'] - r[per]['sum']) < 0.02, per                      # somme des positions = portefeuille
    # le résultat ne contient ni les achats ni la vente : il vaut valeur − apports nets
    assert abs(h['gain'][-1] - (h['value'][-1] - h['net_in'][-1])) < 0.011


def test_series_end_on_the_period_result_and_start_at_first_purchase():
    h, r = run()
    assert abs(r['series']['last'] - r['series']['fullGain']) < 0.011
    assert r['series']['bFirstNonNull'] >= r['series']['bFirstBuyIdx'] - 1               # aucune courbe avant l'achat
    assert r['titles'] == 2                                                              # titres distincts, jamais des lots


def test_missing_factor_interrupts_flow_neutral_performance_without_inventing_it():
    h = make_history()
    k = next(i for i, f in enumerate(h['performance']['factors']) if f is not None and i > 20)
    h['performance']['factors'][k] = None                                               # facteur non calculable (cours manquant)
    p = subprocess.run([node, '-e', SCRIPT, str(ROOT / 'app/public/assets/pf-math.js')], input=json.dumps(h, default=str), capture_output=True, text=True, check=True)
    r = json.loads(p.stdout)
    assert r['perf']['nulls'] >= 1 and r['perf']['note']


def test_adding_money_is_not_counted_as_performance():
    """Investir 200, valeur 210, ajouter 200 : la performance reste +5 %, jamais +95 %."""
    start = dt.date(2026, 1, 5)
    days = [start + dt.timedelta(days=i) for i in range(0, 10) if (start + dt.timedelta(days=i)).weekday() < 5]
    bars = {1: [(d.isoformat(), 20.0 if i < 3 else 21.0, None) for i, d in enumerate(days)]}
    meta = {1: {'currency': 'EUR', 'symbol': 'AAA', 'name': 'Alpha', 'price': None, 'price_time': None}}
    tx = [dict(id=1, listing_id=1, symbol='AAA', name='Alpha', side='buy', quantity=10, unit_price=20, currency='EUR', fx_to_eur=1, fees=0, trade_at=days[0].isoformat() + ' 12:00:00'),
          dict(id=2, listing_id=1, symbol='AAA', name='Alpha', side='buy', quantity=10, unit_price=21, currency='EUR', fx_to_eur=1, fees=0, trade_at=days[4].isoformat() + ' 12:00:00')]
    h = history.build(tx, bars, {}, {1: 'EUR'}, {}, meta, today=days[-1])
    script = "const P=require(process.argv[1]);const H=JSON.parse(require('fs').readFileSync(0,'utf8'));const s=P.series(H,P.resolveWindow(H,'all'),'pf','perf');console.log(JSON.stringify(s.y))"
    p = subprocess.run([node, '-e', script, str(ROOT / 'app/public/assets/pf-math.js')], input=json.dumps(h, default=str), capture_output=True, text=True, check=True)
    last = [v for v in json.loads(p.stdout) if v is not None][-1]
    assert 4.0 < last < 6.0, last
