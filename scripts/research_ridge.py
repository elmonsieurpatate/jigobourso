"""Expérience exploratoire « Ridge » : un modèle linéaire régularisé qui apprend de l'historique améliore-t-il le classement ? (actions seulement, lecture seule, aucun effet sur l'application)

PROTOCOLE : research/PROTOCOLE_RIDGE.md (figé AVANT tout résultat). Résumé :
  * données : historiques exportés (clôture ajustée, volume), actions, À PARTIR DU 1998-01-01 seulement ; titres A3 écartés ; nettoyage v3 (research_cleaning_cases.classify_v3) :
    A2 masqué dans la série ; A1 NEUTRALISÉ (les exemples dont la fenêtre ou l'horizon contient un A1 sont écartés, aucun rendement inventé) ; B et C conservés. Les données d'origine restent
    disponibles : la variante « brut » n'applique AUCUN nettoyage.
  * dates de décision : toutes les 21 séances du calendrier de référence ; indicateurs connus ce jour-là seulement ; cibles = rendement à 21 et 63 séances (entrée à la clôture de t).
  * univers négociable : cotés en USD, valeur échangée médiane >= 1 M sur les 63 séances précédentes, volume sur >= 80 % d'entre elles (pas de taux de change : titres non-USD hors de l'univers principal).
  * cible d'apprentissage : rendement relatif = rendement du titre - médiane des titres négociables à la même date. Indicateurs : rangs (percentiles) par date.
  * walk-forward : réentraînement annuel ; entraînement = exemples dont la cible ET sa classification (horizon + 10 séances) sont connues à la date du réentraînement (PURGE = horizon + 10) ;
    lambda choisi sur les 3 dernières années de l'entraînement (validation interne purgée) ; période finale (>= 2023-01-01) jamais lue en mode `valid`.
  * références : momentum 6-1 seul, momentum 12-1 seul (+ faible volatilité, R², pente seuls). Évaluation sur les rendements RÉELS (jamais écrêtés), frais 10/30/60/100 pb par achat ou vente.
Modes : `valid` (2004 -> fin 2022, écrit ridge_valid.json avec le verdict) ; `final` (période finale, modèle gelé ; refuse de tourner si le verdict de `valid` n'est pas « prometteur », sauf --force).
Usage : python3 scripts/research_ridge.py valid|final ~/tmp-history-long --out dossier [--min-titles 150] [--sample 0]
"""
import argparse
import bisect
import csv
import datetime
import json
import math
import os
import random
import statistics
import sys
import time
from array import array
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_cleaning import load, ratio_steps, title_flag        # noqa: E402
from research_cleaning_cases import classify_v3                     # noqa: E402

NAN = float('nan')
START = datetime.date(1998, 1, 1).toordinal()
FINAL = datetime.date(2023, 1, 1)
STEP, WARM, HZ, LAG = 21, 252, (21, 63), 10
FEATS = ('m61', 'm121', 'slope', 'r2', 'vol', 'dd63', 'r5')
V1, V2 = (0, 1, 2, 3, 4), (0, 1, 2, 3, 4, 5, 6)
LAMBDAS = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)
COSTS = (10, 30, 60, 100)
TOP = 20
LIQ_MIN = 1_000_000


def fin(x):
    return x == x and abs(x) != float('inf')


# ───────────────────────────── construction du jeu de données ─────────────────────────────
def regress(la, i):
    """pente (log par séance) et R² sur les 126 dernières valeurs de log-cours se terminant en i."""
    n = 126
    ys = la[i - n + 1:i + 1]
    xm, ym = (n - 1) / 2, sum(ys) / n
    sxy = sxx = syy = 0.0
    for k, y in enumerate(ys):
        dx, dy = k - xm, y - ym
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    return (sxy / sxx, (sxy * sxy) / (sxx * syy) if syy > 0 else NAN)


def features(a, la, i):
    out = [a[i - 21] / a[i - 126] - 1, a[i - 21] / a[i - 252] - 1]
    slope, r2 = regress(la, i)
    rets = [la[j] - la[j - 1] for j in range(i - 125, i + 1)]
    out += [slope, r2, statistics.pstdev(rets), a[i] / max(a[i - 62:i + 1]) - 1, a[i] / a[i - 5] - 1]
    return out


class Data:
    COLS = ('k', 'ti', 'usd', 'liq', 'cov', 'a1', 'a3', 'cflag', 'any')

    def __init__(self):
        self.cal, self.dec = [], []
        self.c = {n: array('d') for n in self.COLS}
        self.fc, self.fr = [array('d') for _ in FEATS], [array('d') for _ in FEATS]      # indicateurs nettoyés / bruts
        self.t = {n: array('d') for n in ('f21c', 'f63c', 'f21r', 'f63r', 'g21c', 'g63c', 'g21r', 'g63r')}
        self.titles, self.by_date = [], defaultdict(list)


def build(directory, min_titles, sample):
    with open(os.path.join(directory, 'universe.csv'), encoding='utf-8', newline='') as fh:
        universe = [u for u in csv.DictReader(fh) if u['kind'] == 'equity' and os.path.exists(os.path.join(directory, 'history', f"{u['key']}.csv.gz"))]
    if sample and sample < len(universe):
        universe = random.Random(1).sample(universe, sample)
    t0 = time.monotonic()
    count = Counter()
    for n, u in enumerate(universe, 1):
        for r in load(os.path.join(directory, 'history', f"{u['key']}.csv.gz")):
            o = datetime.date.fromisoformat(r[0]).toordinal()
            if o >= START:
                count[o] += 1
        if n % 500 == 0:
            print(f'calendrier {n}/{len(universe)} · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    D = Data()
    D.cal = sorted(o for o, k in count.items() if k >= min_titles)
    D.dec = list(range(WARM, len(D.cal) - 1, STEP))
    stats = Counter()
    for n, u in enumerate(universe, 1):
        rows = [r for r in load(os.path.join(directory, 'history', f"{u['key']}.csv.gz")) if r[0] >= '1998-01-01']
        if len(rows) < WARM + 70:
            stats['trop court'] += 1
            continue
        ords = [datetime.date.fromisoformat(r[0]).toordinal() for r in rows]
        c, a, v = [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]
        a3 = 1 if title_flag(a, c) else 0
        stats['A3'] += a3
        evs = classify_v3(a, c, v)
        steps = [i for i in range(1, len(a)) if (a[i] / c[i]) / (a[i - 1] / c[i - 1]) - 1 > 0.3]
        ac = list(a)
        for i, cls, p, end in evs:
            if cls == 'A2':
                for j in range(i, end + 1):
                    ac[j] = ac[i - 1]
        ev_all = sorted([e[0] for e in evs] + steps)
        ev_a1 = sorted(e[0] for e in evs if e[1] == 'A1')
        ev_c = sorted([e[0] for e in evs if e[1] == 'C'] + steps)
        a2_ev = [e[0] for e in evs if e[1] == 'A2']
        lr, lc = [math.log(x) for x in a], [math.log(x) for x in ac]
        ti = len(D.titles)
        D.titles.append((u['symbol'], u.get('currency', '')))
        usd = 1 if u.get('currency') == 'USD' else 0
        for kk, k in enumerate(D.dec):
            d = D.cal[k]
            i = bisect.bisect_left(ords, d)
            if i >= len(ords) or ords[i] != d or i < WARM:
                continue
            win = range(i - 62, i + 1)
            vols = [v[j] for j in win if v[j]]
            cov = len(vols) / 63
            liq = statistics.median([c[j] * v[j] for j in win if v[j]]) if vols else 0.0
            lo, hi = i - 252, i + 63
            def hit(lst, l, h):
                x = bisect.bisect_right(lst, l)
                return x < len(lst) and lst[x] <= h
            flag_a1 = 1 if hit(ev_a1, lo, hi) else 0
            flag_c = 1 if (hit(ev_c, lo, hi) or hit(ev_all, i - LAG, i)) else 0
            flag_any = 1 if hit(ev_all, lo, hi) else 0
            recent_a2 = any(i - 2 < e <= i for e in a2_ev)
            try:
                fr = features(a, lr, i)
                fc = fr if (not a2_ev or recent_a2) else features(ac, lc, i)
            except (ValueError, ZeroDivisionError):
                stats['indicateur impossible'] += 1
                continue
            def fwd(arr, base, h):
                j = base + h
                if j >= len(arr) or base >= len(arr) or abs(ords[j] - D.cal[min(len(D.cal) - 1, k + h + (base - i))]) > 5:
                    return NAN
                return arr[j] / arr[base] - 1
            D.c['k'].append(kk)
            D.c['ti'].append(ti)
            D.c['usd'].append(usd)
            D.c['liq'].append(liq)
            D.c['cov'].append(cov)
            D.c['a1'].append(flag_a1)
            D.c['a3'].append(a3)
            D.c['cflag'].append(flag_c)
            D.c['any'].append(flag_any)
            for q in range(len(FEATS)):
                D.fc[q].append(fc[q])
                D.fr[q].append(fr[q])
            for h in HZ:
                D.t[f'f{h}c'].append(fwd(ac, i, h))
                D.t[f'f{h}r'].append(fwd(a, i, h))
                D.t[f'g{h}c'].append(fwd(ac, i + 1, h) if i + 1 < len(ac) else NAN)
                D.t[f'g{h}r'].append(fwd(a, i + 1, h) if i + 1 < len(a) else NAN)
            D.by_date[kk].append(len(D.c['k']) - 1)
        stats['titres'] += 1
        if n % 250 == 0:
            print(f'jeu de données {n}/{len(universe)} · {time.monotonic() - t0:.0f} s · {len(D.c["k"])} lignes', file=sys.stderr)
    D.stats = stats
    return D


# ───────────────────────────── statistiques ─────────────────────────────
def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for q in range(i, j + 1):
            r[order[q]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 10:
        return NAN
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx, sy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sx * sy) if sx > 0 and sy > 0 else NAN


def boot(series, block=6, B=2000, seed=11):
    """IC95 (et IC à 98,75 % pour 2 tests) de la moyenne par bootstrap circulaire par blocs."""
    n = len(series)
    if n < 12:
        return (NAN, NAN, NAN, NAN)
    rnd, means = random.Random(seed), []
    for _ in range(B):
        s, got = 0.0, 0
        while got < n:
            st = rnd.randrange(n)
            for q in range(block):
                s += series[(st + q) % n]
                got += 1
                if got >= n:
                    break
        means.append(s / n)
    means.sort()
    return means[int(0.025 * B)], means[int(0.975 * B) - 1], means[int(0.0125 * B)], means[int(0.9875 * B) - 1]


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-18:
            return [0.0] * n
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


# ───────────────────────────── préparation par configuration ─────────────────────────────
class Config:
    """Exemples éligibles d'un mode (principal / brut) et d'un filtre (aucun / S1 / S3), pour un horizon : par date, indicateurs en rangs et cibles."""

    def __init__(self, D, mode, filt, h):
        self.D, self.mode, self.filt, self.h = D, mode, filt, h
        F = D.fc if mode == 'principal' else D.fr
        sfx = 'c' if mode == 'principal' else 'r'
        f, g = D.t[f'f{h}{sfx}'], D.t[f'g{h}{sfx}']
        self.dates = {}
        for kk, idxs in D.by_date.items():
            el = []
            for r in idxs:
                if not (D.c['usd'][r] and D.c['liq'][r] >= LIQ_MIN and D.c['cov'][r] >= 0.8 and fin(f[r]) and all(fin(F[q][r]) for q in range(len(FEATS)))):
                    continue
                if mode == 'principal':
                    if D.c['a3'][r] or D.c['a1'][r]:
                        continue
                    if filt == 'S1' and D.c['cflag'][r]:
                        continue
                    if filt == 'S3' and D.c['any'][r]:
                        continue
                el.append(r)
            if len(el) < 30:
                continue
            cols = []
            for q in range(len(FEATS)):
                rk = ranks([F[q][r] for r in el])
                cols.append([(x + 0.5) / len(el) - 0.5 for x in rk])
            X = [tuple(cols[q][j] for q in range(len(FEATS))) for j in range(len(el))]
            fv = [f[r] for r in el]
            med = statistics.median(fv)
            gv = [g[r] for r in el]
            self.dates[kk] = {'rows': el, 'X': X, 'f': fv, 'y': [x - med for x in fv], 'g': gv}
        self.keys = sorted(self.dates)
        self.stat = {}
        for kk in self.keys:
            X, y = self.dates[kk]['X'], self.dates[kk]['y']
            A = [[0.0] * 7 for _ in range(7)]
            b = [0.0] * 7
            for x, yy in zip(X, y):
                for p in range(7):
                    xp = x[p]
                    b[p] += xp * yy
                    for q in range(p, 7):
                        A[p][q] += xp * x[q]
            self.stat[kk] = (A, b, len(y))

    def train_stats(self, dates, feats, clip=None):
        p = len(feats)
        A = [[0.0] * p for _ in range(p)]
        b = [0.0] * p
        n = 0
        for kk in dates:
            Ad, bd, nd = self.stat[kk]
            n += nd
            for i, fi in enumerate(feats):
                for j, fj in enumerate(feats):
                    A[i][j] += Ad[min(fi, fj)][max(fi, fj)]
                if clip is None:
                    b[i] += bd[fi]
        if clip is not None:
            lo, hi = clip
            for kk in dates:
                for x, yy in zip(self.dates[kk]['X'], self.dates[kk]['y']):
                    yc = min(hi, max(lo, yy))
                    for i, fi in enumerate(feats):
                        b[i] += x[fi] * yc
        return A, b, n

    def clip_bounds(self, dates, lo=0.01, hi=0.99):
        ys = sorted(y for kk in dates for y in self.dates[kk]['y'])
        return ys[int(lo * (len(ys) - 1))], ys[int(hi * (len(ys) - 1))]

    def fit(self, dates, feats, lam, clip=None):
        A, b, n = self.train_stats(dates, feats, clip)
        if n < 500:
            return None
        for i in range(len(feats)):
            A[i][i] += lam * n
        return solve(A, b)

    def mean_ic(self, dates, feats, beta):
        ics = []
        for kk in dates:
            d = self.dates[kk]
            sc = [sum(beta[i] * x[fi] for i, fi in enumerate(feats)) for x in d['X']]
            ic = spearman(sc, d['f'])
            if fin(ic):
                ics.append(ic)
        return statistics.mean(ics) if ics else NAN


def walk_forward(cfg, h, T0s, test_ranges, feats, clip_on, log):
    """T0s : liste d'indices de calendrier de réentraînement ; test_ranges : pour chaque T0, bornes (a, b) des indices de dates de décision à noter."""
    models, betas = {}, []
    for T0, (a, b) in zip(T0s, test_ranges):
        train = [kk for kk in cfg.keys if cfg.D.dec[kk] + h + LAG <= T0]
        assert all(cfg.D.dec[kk] + h + LAG <= T0 for kk in train)           # PURGE : aucune cible ni classification postérieure à la date de réentraînement
        tests = [kk for kk in cfg.keys if a <= cfg.D.dec[kk] < b]
        assert all(cfg.D.dec[kk] >= T0 for kk in tests)
        clip = cfg.clip_bounds(train) if clip_on and train else None
        val_start = T0 - 756
        inner = [kk for kk in train if cfg.D.dec[kk] + h + LAG <= val_start]
        val = [kk for kk in train if cfg.D.dec[kk] >= val_start]
        lam, best = 1e-2, None
        if len(inner) >= 24 and len(val) >= 12:
            for L in LAMBDAS:
                be = cfg.fit(inner, feats, L, clip)
                if be is None:
                    continue
                ic = cfg.mean_ic(val, feats, be)
                if fin(ic) and (best is None or ic > best):
                    best, lam = ic, L
        beta = cfg.fit(train, feats, lam, clip)
        if beta is None:
            continue
        betas.append((T0, lam, beta, len(train)))
        for kk in tests:
            models[kk] = beta
    return models, betas


def evaluate(cfg, h, score_of, keys, entry='f'):
    """Par date : IC, rendement brut du Top 20, rendement de l'univers, sélection. Cibles réelles non écrêtées."""
    out = {}
    for kk in keys:
        d = cfg.dates.get(kk)
        sc = score_of(kk, d)
        if sc is None:
            continue
        ret = d[entry]
        ok = [j for j in range(len(sc)) if fin(ret[j])]
        if len(ok) < 30:
            continue
        order = sorted(ok, key=lambda j: -sc[j])
        top = order[:TOP]
        uni = statistics.mean(ret[j] for j in ok)
        n = len(order)
        dec = []
        for q in range(10):
            seg = order[q * n // 10:(q + 1) * n // 10]
            dec.append(statistics.mean(ret[j] for j in seg) if seg else NAN)
        out[kk] = {'ic': spearman([sc[j] for j in ok], [d['f'][j] for j in ok]), 'top': statistics.mean(ret[j] for j in top), 'uni': uni,
                   'sel': frozenset(int(cfg.D.c['ti'][d['rows'][j]]) for j in top), 'dec': dec, 'n': len(ok)}
    return out


def summarize(res, h):
    """Résumé d'un modèle : moyennes, IC95 par blocs, frais par la rotation réelle de chaque chaîne."""
    keys = sorted(res)
    ics = [res[k]['ic'] for k in keys if fin(res[k]['ic'])]
    gross = [100 * (res[k]['top'] - res[k]['uni']) for k in keys]
    m = h // STEP
    chain_prev, turn, net = {}, {}, {c: [] for c in COSTS}
    absr = {c: [] for c in COSTS}
    for pos, k in enumerate(keys):
        ch = pos % m if m > 1 else 0
        prev = chain_prev.get(ch)
        t = 1.0 if prev is None else 1 - len(prev & res[k]['sel']) / TOP
        chain_prev[ch] = res[k]['sel']
        turn[k] = t
        for c in COSTS:
            ex = 100 * (res[k]['top'] - res[k]['uni']) - 100 * t * 2 * c / 10000
            net[c].append(ex)
            absr[c].append(100 * res[k]['top'] - 100 * t * 2 * c / 10000)
    lo, hi, lo2, hi2 = boot(gross)
    worst = sorted(absr[60])[:max(1, len(absr[60]) // 20)]
    dec = [statistics.mean(res[k]['dec'][q] for k in keys if fin(res[k]['dec'][q])) * 100 for q in range(10)] if keys else []
    return {'dates': len(keys), 'ic': statistics.mean(ics) if ics else NAN, 'ic_pos': 100 * sum(1 for x in ics if x > 0) / len(ics) if ics else NAN,
            'gross': statistics.mean(gross) if gross else NAN, 'ci': (lo, hi), 'ci2': (lo2, hi2), 'net': {c: statistics.mean(net[c]) for c in COSTS} if keys else {},
            'turn': statistics.mean(turn.values()) if turn else NAN, 'cvar': statistics.mean(worst) if worst else NAN, 'dec': dec, 'series': dict(zip(keys, gross)),
            'netseries60': dict(zip(keys, net[60]))}


def f2(x, d=2):
    return '–' if not fin(x) else f'{x:+.{d}f}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('mode', choices=('valid', 'final'))
    ap.add_argument('directory')
    ap.add_argument('--out', required=True)
    ap.add_argument('--min-titles', type=int, default=150)
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--first-year', type=int, default=2004)
    args = ap.parse_args(argv)
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)
    verdict_path = os.path.join(out_dir, 'ridge_valid.json')
    if args.mode == 'final' and not args.force:
        if not os.path.exists(verdict_path) or json.load(open(verdict_path)).get('verdict') != 'prometteur':
            print('REFUS : la validation n\'a pas rendu le verdict « prometteur » : la période finale n\'est pas lue (--force pour passer outre, hors protocole).')
            return 3
    D = build(os.path.expanduser(args.directory), args.min_titles, args.sample)
    cal = D.cal
    final_idx = bisect.bisect_left(cal, FINAL.toordinal())
    L = []
    w = L.append
    w(f'# Expérience Ridge (exploratoire) · mode {args.mode}\n')
    w('*Étude exploratoire sur les survivants sélectionnés aujourd\'hui par Jigobourso : biais de survie et de sélection NON corrigés ; aucune conclusion de surperformance historique réelle ne peut en être tirée. Actions seulement, USD, valeur échangée >= 1 M, données depuis 1998.*\n')
    w(f'{len(D.titles)} titres, {len(D.c["k"])} lignes (titre × date), {len(D.dec)} dates de décision (toutes les {STEP} séances), calendrier {datetime.date.fromordinal(cal[0])} -> {datetime.date.fromordinal(cal[-1])}. '
      f'Écartés : {dict(D.stats)}. Exemples neutralisés (A1) : {int(sum(D.c["a1"]))} ; titres A3 : {D.stats["A3"]}.\n')
    years = range(args.first_year, 2023) if args.mode == 'valid' else [None]
    verdict = {'mode': args.mode, 'horizons': {}}
    for h in HZ:
        if args.mode == 'valid':
            T0s = [bisect.bisect_left(cal, datetime.date(y, 1, 1).toordinal()) for y in years]
            ranges = [(T0s[i], T0s[i + 1] if i + 1 < len(T0s) else final_idx - 63) for i in range(len(T0s))]
            ranges = [(a, min(b, final_idx - 63)) for a, b in ranges]            # aucune cible de validation ne déborde sur la période finale
        else:
            T0s, ranges = [final_idx], [(final_idx, len(cal))]
        w(f'\n## Horizon {h} séances\n')
        cfgs = {key: Config(D, *key[:2], h) for key in (('principal', 'none'),)}
        base = cfgs[('principal', 'none')]
        res = {}

        # références et modèles ; test_keys = dates de test de l'ensemble des plis
        test_keys = {kk for kk in base.keys if any(a <= D.dec[kk] < b for a, b in ranges)}
        refs = {'Momentum 6-1 seul': (0, 1), 'Momentum 12-1 seul': (1, 1), 'Faible volatilité seule': (4, -1), 'R² seul': (3, 1), 'Pente seule': (2, 1)}
        models = {}
        for name, (q, sgn) in refs.items():
            models[name] = (lambda q, sgn: (lambda kk, d: [sgn * x[q] for x in d['X']] if d is not None and kk in test_keys else None))(q, sgn)
        betas_log = {}
        for name, feats, clip in (('Ridge V1 (cœur)', V1, False), ('Ridge V2 (+drawdown, 5 séances)', V2, False), ('Ridge V1 écrêté 1-99 %', V1, True)):
            mdl, betas = walk_forward(base, h, T0s, ranges, feats, clip, log=None)
            betas_log[name] = (feats, betas)
            models[name] = (lambda mdl, feats: (lambda kk, d: [sum(mdl[kk][i] * x[fi] for i, fi in enumerate(feats)) for x in d['X']] if kk in mdl else None))(mdl, feats)
        summ = {}
        for name, fn in models.items():
            summ[name] = summarize(evaluate(base, h, fn, sorted(test_keys)), h)
        w('| Modèle | Dates | IC moyen | % IC > 0 | Excès brut Top 20 (pts) [IC95 blocs] | Net 10 pb | Net 30 pb | Net 60 pb | Net 100 pb | Rotation | CVaR95 (net 60, rendement) |')
        w('|---|---|---|---|---|---|---|---|---|---|---|')
        for name, s in summ.items():
            w(f"| {name} | {s['dates']} | {f2(s['ic'], 3)} | {s['ic_pos']:.0f} | {f2(s['gross'])} [{f2(s['ci'][0])} ; {f2(s['ci'][1])}] | " + ' | '.join(f2(s['net'].get(c, NAN)) for c in COSTS) + f" | {f2(100 * s['turn'], 0)} % | {f2(s['cvar'])} |")
        w('\nDéciles de score (rendement moyen réel à l\'horizon, en %, du plus bas au plus haut) :\n')
        for name in ('Momentum 6-1 seul', 'Ridge V1 (cœur)'):
            w(f"- {name} : " + ', '.join(f2(x, 1) for x in summ[name]['dec']))
        w('\nCoefficients Ridge V1 par pli (rangs d\'indicateurs ; signe stable = part des plis de même signe que la moyenne) :\n')
        feats, betas = betas_log['Ridge V1 (cœur)']
        if betas:
            w('| Indicateur | Coefficient moyen | Signe stable | lambda choisis |')
            w('|---|---|---|---|')
            for i, fi in enumerate(feats):
                vals = [b[2][i] for b in betas]
                mean = statistics.mean(vals)
                w(f"| {FEATS[fi]} | {mean:+.4f} | {100 * sum(1 for x in vals if x * mean > 0) / len(vals):.0f} % | {Counter(b[1] for b in betas).most_common(3)} |")
        # sous-périodes
        ridge, m61, m121 = summ['Ridge V1 (cœur)'], summ['Momentum 6-1 seul'], summ['Momentum 12-1 seul']
        refname = max(('Momentum 6-1 seul', 'Momentum 12-1 seul'), key=lambda n: summ[n]['net'].get(60, -1e9))
        ref = summ[refname]
        common = sorted(set(ridge['series']) & set(ref['series']))
        diff = [ridge['series'][k] - ref['series'][k] for k in common]
        lo, hi, lo2, hi2 = boot(diff) if diff else (NAN,) * 4
        if args.mode == 'valid':
            periods = ((2004, 2010), (2011, 2016), (2017, 2022))
        else:
            periods = ((2023, 2030),)
        wins = []
        w(f'\nÉcart Ridge V1 - {refname} (excès brut Top 20, par date) : moyenne {f2(statistics.mean(diff) if diff else NAN)} · IC95 blocs [{f2(lo)} ; {f2(hi)}] · IC 98,75 % (2 tests) [{f2(lo2)} ; {f2(hi2)}]\n')
        for a, b in periods:
            sub = [x for k, x in zip(common, diff) if a <= datetime.date.fromordinal(cal[D.dec[k]]).year <= b]
            if sub:
                wins.append(statistics.mean(sub) > 0)
                w(f'- {a}-{b} : écart moyen {f2(statistics.mean(sub))} sur {len(sub)} dates')
        # sensibilités
        w('\n**Sensibilités (jamais utilisées pour choisir le modèle principal)** : IC moyen / excès brut Top 20 / net 60 pb, Ridge V1 et Momentum 6-1 seul\n')
        w('| Configuration | Ridge V1 : IC | brut | net 60 | Momentum 6-1 : IC | brut | net 60 |')
        w('|---|---|---|---|---|---|---|')
        sens = {}
        for label, key in (('nettoyage principal (référence)', ('principal', 'none')), ('S1 : sans exemples touchés par C', ('principal', 'S1')), ('S3 : sans exemples touchés par un mouvement de 40 % (borne agressive)', ('principal', 'S3')), ('brut : données d\'origine, aucun nettoyage', ('brut', 'none'))):
            cf = base if key == ('principal', 'none') else Config(D, key[0], key[1], h)
            tk = {kk for kk in cf.keys if any(a <= D.dec[kk] < b for a, b in ranges)}
            mdl, _ = walk_forward(cf, h, T0s, ranges, V1, False, log=None)
            rs = summarize(evaluate(cf, h, lambda kk, d: [sum(mdl[kk][i] * x[fi] for i, fi in enumerate(V1)) for x in d['X']] if kk in mdl else None, sorted(tk)), h)
            ms = summarize(evaluate(cf, h, lambda kk, d: [x[0] for x in d['X']] if d is not None and kk in tk else None, sorted(tk)), h)
            sens[label] = (rs, ms)
            w(f"| {label} | {f2(rs['ic'], 3)} | {f2(rs['gross'])} | {f2(rs['net'].get(60, NAN))} | {f2(ms['ic'], 3)} | {f2(ms['gross'])} | {f2(ms['net'].get(60, NAN))} |")
        g_ridge = summarize(evaluate(base, h, models['Ridge V1 (cœur)'], sorted(test_keys), entry='g'), h)
        g_ref = summarize(evaluate(base, h, models['Momentum 6-1 seul'], sorted(test_keys), entry='g'), h)
        w(f"\nEntrée à la clôture de t+1 (décalage d'exécution) : Ridge V1 excès brut {f2(g_ridge['gross'])} · Momentum 6-1 {f2(g_ref['gross'])}.")
        # règle de décision (fixée dans le protocole)
        crit = {
            'IC et net 60 pb supérieurs à la meilleure référence': fin(ridge['ic']) and ridge['ic'] > ref['ic'] and ridge['net'].get(60, -1e9) > ref['net'].get(60, 1e9),
            'écart brut dont l\'IC à 98,75 % exclut 0 (positif)': fin(lo2) and lo2 > 0,
            'écart positif dans au moins 2 sous-périodes sur 3 (valid)' if args.mode == 'valid' else 'écart positif sur la période finale': (sum(wins) >= 2 if args.mode == 'valid' else bool(wins and wins[0])),
            'CVaR95 non pire de plus de 10 % que la référence': fin(ridge['cvar']) and ridge['cvar'] >= ref['cvar'] - 0.10 * abs(ref['cvar']),
            'survit à S1 et à « brut » (écart brut positif)': all(sens[k][0]['gross'] > sens[k][1]['gross'] for k in ('S1 : sans exemples touchés par C', 'brut : données d\'origine, aucun nettoyage')),
        }
        w('\n**Règle de décision (protocole)** :\n')
        for k, ok in crit.items():
            w(f"- {'OUI' if ok else 'NON'} · {k}")
        ok_all = all(crit.values())
        verdict['horizons'][str(h)] = {'prometteur': ok_all, 'reference': refname, 'criteres': {k: bool(v) for k, v in crit.items()}}
        w(f'\n→ Horizon {h} : **{"prometteur" if ok_all else "non concluant ou écarté"}**.')
    verdict['verdict'] = 'prometteur' if any(v['prometteur'] for v in verdict['horizons'].values()) else 'non concluant'
    w(f"\n## Verdict global : **{verdict['verdict']}**\n")
    w('Un résultat « prometteur » ne prouve rien d\'exploitable : survivants, sélection actuelle du catalogue, pas de taux de change, frais en hypothèses. Il autorise seulement la lecture UNIQUE de la période finale.' if args.mode == 'valid' else
      'Période finale lue UNE fois, modèle gelé (aucune variante n\'a été choisie sur elle).')
    text = '\n'.join(L)
    print(text)
    with open(os.path.join(out_dir, f'ridge_{args.mode}.md'), 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    if args.mode == 'valid':
        with open(verdict_path, 'w') as fh:
            json.dump(verdict, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
