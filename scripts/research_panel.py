"""Panel de recherche : pour chaque (titre, date de décision), les indicateurs connus CE JOUR-LÀ et les rendements futurs à plusieurs horizons, plus le classement des profils de l'application.

LECTURE SEULE : aucun appel réseau, aucune base, aucune modification de l'application ni des stratégies. Réutilise backtest_walkforward.py (moteur de l'application rejoué point par point),
backtest_liquidity.py (liquidité sur les 63 séances précédentes, splits non ajustés, devises) et les historiques de scripts/export_history.py.

Règles (research/PROTOCOLE.md) : à la date t, seules les clôtures et volumes connus à t servent aux indicateurs ; les rendements futurs ne servent qu'à mesurer. Deux rendements futurs par horizon :
  f{h} : entrée à la clôture de t (comparable aux travaux précédents) ;  g{h} : entrée à la clôture de t+1 (décalage d'exécution d'une séance).

Deux étapes, REPRENABLES (un lot déjà calculé n'est pas refait) :
  python3 scripts/research_panel.py build --csv-dir ~/tmp-history-long --out ~/tmp-backtest/research/out/panel [--sample 0] [--batch 100] [--start 1993-01-01]
  python3 scripts/research_panel.py merge --out ~/tmp-backtest/research/out/panel      -> panel.pkl.gz (colonnes + classements des profils de l'application)
"""
import argparse
import bisect
import datetime
import glob
import gzip
import math
import os
import pickle
import statistics
import sys
import time
from array import array
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import backtest_liquidity as bl                                   # noqa: E402
import backtest_walkforward as bw                                 # noqa: E402
from engine.analytics import strategy                             # noqa: E402
from engine.analytics.measures import window_metrics              # noqa: E402

FEATURES = ('m61', 'm121', 'm31', 'm1', 'vol126', 'slope', 'r2', 'hi', 'mdd252', 'ma200', 'ma50', 'vtr', 'liq')
HORIZONS = (5, 10, 21, 42, 63, 126)
PRESETS = ('regular', 'fast', 'recovery', 'low_volatility')
CURRENCIES = ('USD', 'EUR', 'GBP', 'CHF', 'SEK', 'NOK', 'DKK', 'JPY', 'CAD', 'AUD', 'autre', 'inconnue')
STATUSES = ('ok', 'history', 'coverage', 'split')
GROUPS = ('equity', 'etf')
NAN = float('nan')
FORWARD_COLUMNS = tuple(f'{p}{h}' for p in ('f', 'g') for h in HORIZONS)
COLUMNS = ('ti', 'key', 'grp', 'status', 'ccy') + FEATURES + FORWARD_COLUMNS


def _num(x):
    return NAN if x is None or not math.isfinite(x) else float(x)


def indicators(c):
    """Indicateurs à partir des clôtures ajustées VISIBLES (jamais une clôture postérieure à t, et seulement après la dernière rupture de cours). Valeurs en fractions (0,10 = +10 %)."""
    n = len(c)
    out = dict.fromkeys(('m61', 'm121', 'm31', 'm1', 'vol126', 'slope', 'r2', 'hi', 'mdd252', 'ma200', 'ma50'), NAN)
    if n > 126:
        out['m61'] = c[-22] / c[-127] - 1
        logs = [math.log(c[i] / c[i - 1]) for i in range(n - 126, n)]
        out['vol126'] = statistics.pstdev(logs)
        w = window_metrics(c[-127:])
        if w:
            out['slope'], out['r2'] = _num(w.get('slope')), _num(w.get('r2'))
    if n > 252:
        out['m121'] = c[-22] / c[-253] - 1
    if n > 63:
        out['m31'] = c[-22] / c[-64] - 1
    if n > 21:
        out['m1'] = c[-1] / c[-22] - 1
    if n >= 252:
        top = max(c[-252:])
        out['hi'] = c[-1] / top - 1
        peak, worst = c[-252], 0.0
        for x in c[-252:]:
            peak = max(peak, x)
            worst = min(worst, x / peak - 1)
        out['mdd252'] = worst
    if n >= 200:
        out['ma200'] = c[-1] / statistics.fmean(c[-200:]) - 1
    if n >= 50:
        out['ma50'] = c[-1] / statistics.fmean(c[-50:]) - 1
    return out


def volume_trend(dv, i):
    """Médiane de la valeur échangée des 21 dernières séances (t exclu) ÷ médiane des 63 précédentes ; NaN si trop de trous."""
    if i < 85:
        return NAN
    recent = [x for x in dv[i - 21:i] if x is not None]
    before = [x for x in dv[i - 84:i - 21] if x is not None]
    if len(recent) < 15 or len(before) < 40:
        return NAN
    base = statistics.median(before)
    return statistics.median(recent) / base if base > 0 else NAN


def forward(full, t, h, lag):
    """Rendement (%) sur h séances avec entrée `lag` séance(s) après t. None si l'historique s'arrête, si la base est trop ancienne ou si une rupture non expliquée est traversée."""
    dates, closes, _, breaks = full
    base = bisect.bisect_right(dates, t) - 1
    if base < 0 or (datetime.date.fromisoformat(t) - datetime.date.fromisoformat(dates[base])).days > bw.MAX_STALE_DAYS:
        return None
    start, end = base + lag, base + lag + h
    if end >= len(closes) or any(base < b <= end for b in breaks):
        return None
    return 100 * (closes[end] / closes[start] - 1)


def slim(verdict, key, group, symbol, sessions):
    return {'status': 'retained', 'key': key, 'group': group, 'symbol': symbol,
            'measures': {s: {k: (verdict['measures'][s] or {}).get(k) for k in ('slope', 'perf', 'r2', 'volatility')} for s in sessions if verdict['measures'].get(s)}}


class PanelBuilder:
    def __init__(self, calendar, dates, presets=PRESETS):
        self.calendar, self.dates = tuple(calendar), tuple(dates)
        self.date_index = {d: i for i, d in enumerate(self.dates)}
        self.liq = bl.LiquidityStudy(calendar, dates, horizons=(21,))
        self.configs = {name: strategy.validate(strategy.preset(name)) for name in presets}
        self.windows = sorted({n for cfg in self.configs.values() for n in strategy.required_sessions(cfg)})
        self.active = {name: [p['sessions'] for p in cfg['periods'] if p['enabled']] for name, cfg in self.configs.items()}
        self.cols = {name: array('d') if name not in ('ti', 'key', 'grp', 'status', 'ccy') else array('l') for name in COLUMNS}
        self.retained = defaultdict(list)

    def add(self, candidates):
        for raw in candidates:
            c = bw.prepare(raw)
            key = int(c['key'])
            dv, prefix = self.liq._aligned(c)
            ccy = c.get('currency') or 'inconnue'
            ccy_code = CURRENCIES.index(ccy) if ccy in CURRENCIES else CURRENCIES.index('autre')
            group = 0 if c['group'] == 'equity' else 1
            for t in self.dates:
                n = bisect.bisect_right(c['dates'], t)
                if n < bw.MIN_CLOSES or (datetime.date.fromisoformat(t) - datetime.date.fromisoformat(c['dates'][n - 1])).days > bw.MAX_STALE_DAYS:
                    continue
                i = self.liq.index[t]
                status, value = bl.LiquidityStudy.liquidity(i, dv, prefix)
                visible = c['bars'][max(0, n - bw.DECISION_BARS):n]                          # jamais une clôture postérieure à t
                vdates, closes, _, breaks, measures, missing, tech = bw.analyze_series(visible, self.windows, c.get('split_dates') or ())
                usable = closes[breaks[-1]:] if breaks else closes
                ind = indicators(usable)
                ind['vtr'] = volume_trend(dv, i)
                ind['liq'] = NAN if value is None else float(value)
                row = {'ti': self.date_index[t], 'key': key, 'grp': group, 'status': STATUSES.index(status), 'ccy': ccy_code}
                row.update(ind)
                for lag, prefix_name in ((0, 'f'), (1, 'g')):
                    for h in HORIZONS:
                        r = forward(c['full'], t, h, lag)
                        row[f'{prefix_name}{h}'] = NAN if r is None else r
                for name in COLUMNS:
                    self.cols[name].append(row[name])
                for name, cfg in self.configs.items():
                    v = strategy.judge(cfg, measures, tech, missing, vdates[-1], None)
                    if v['status'] == 'retained':
                        self.retained[(t, name)].append(slim(v, key, c['group'], c['symbol'], self.active[name]))

    def dump(self, path):
        tmp = path + '.part'
        with gzip.open(tmp, 'wb') as fh:
            pickle.dump({'cols': self.cols, 'retained': dict(self.retained), 'dates': self.dates, 'split_titles': sorted(self.liq.split_titles, key=str)}, fh, protocol=4)
        os.replace(tmp, path)


def merge(parts):
    """Concatène les lots, calcule le classement des profils de l'application date par date (percentiles sur TOUS les titres retenus, par groupe) et garde TOUS les titres classés (ordre du rang)."""
    cols, retained, dates, splits = None, defaultdict(list), None, set()
    for path in parts:
        with gzip.open(path, 'rb') as fh:
            part = pickle.load(fh)
        if cols is None:
            cols, dates = {k: array(v.typecode) for k, v in part['cols'].items()}, part['dates']
        elif part['dates'] != dates:
            raise ValueError(f'dates différentes dans {path} : les lots viennent de calendriers différents')
        for k, v in part['cols'].items():
            cols[k].extend(v)
        for k, v in part['retained'].items():
            retained[k].extend(v)
        splits |= set(part['split_titles'])
    ranked = {}
    configs = {name: strategy.validate(strategy.preset(name)) for name in PRESETS}
    for (t, name), verdicts in retained.items():
        out = strategy.rank(configs[name], [dict(v) for v in verdicts])
        for g in GROUPS:
            keys = [v['key'] for v in sorted((v for v in out if v['group'] == g and v['rank'] is not None), key=lambda v: v['rank'])]
            if keys:
                ranked[(t, name, g)] = keys
    return {'cols': cols, 'dates': dates, 'ranked': ranked, 'split_titles': sorted(splits, key=str), 'rows': len(cols['ti'])}


def build(args):
    directory = os.path.expanduser(args.csv_dir)
    universe = bw.csv_universe(directory)
    calendar = bw.csv_calendar(directory, universe, 0.1, args.min_titles)
    dates = [d for d in bw.pick_dates(calendar, (5,), 21, 0) if d >= args.start]
    os.makedirs(args.out, exist_ok=True)
    print(f'{len(universe)} titres · {len(dates)} dates de {dates[0]} à {dates[-1]}', file=sys.stderr)
    files = [u for u in universe if os.path.exists(bw._history_file(directory, u['key']))]
    if args.sample and args.sample < len(files):
        import random
        files = sorted(random.Random(args.seed).sample(files, args.sample), key=lambda u: u['key'])
    t0, done = time.monotonic(), 0
    for number, start in enumerate(range(0, len(files), args.batch)):
        path = os.path.join(args.out, f'part-{number:04d}.pkl.gz')
        chunk = files[start:start + args.batch]
        if os.path.exists(path):
            done += len(chunk)
            continue
        builder = PanelBuilder(calendar, dates)
        for lot in bw.csv_batches(directory, chunk, 0, 1, batch=len(chunk)):
            builder.add(lot)
        builder.dump(path)
        done += len(chunk)
        print(f'{done}/{len(files)} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr, flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=('build', 'merge'))
    ap.add_argument('--csv-dir')
    ap.add_argument('--out', required=True, help='dossier des lots (build) ou préfixe du panel (merge : lit OUT/part-*.pkl.gz, écrit OUT/panel.pkl.gz)')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--batch', type=int, default=100)
    ap.add_argument('--start', default='1993-01-01')
    ap.add_argument('--min-titles', type=int, default=150)
    args = ap.parse_args(argv)
    args.out = os.path.expanduser(args.out)
    if args.step == 'build':
        if not args.csv_dir:
            ap.error('--csv-dir est requis pour build')
        return build(args)
    parts = sorted(glob.glob(os.path.join(args.out, 'part-*.pkl.gz')))
    if not parts:
        print('Aucun lot à fusionner.', file=sys.stderr)
        return 3
    panel = merge(parts)
    with gzip.open(os.path.join(args.out, 'panel.pkl.gz'), 'wb') as fh:
        pickle.dump(panel, fh, protocol=4)
    print(f"{panel['rows']} lignes · {len(panel['dates'])} dates · {len(panel['ranked'])} classements", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
