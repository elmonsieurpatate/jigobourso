"""Score appris (apprentissage automatique) contre le Momentum 6-1 : deux modèles fixés d'avance (research/PROTOCOLE_APPRENTISSAGE.md).

LECTURE SEULE sur le panel de scripts/research_panel.py ; aucun réseau, aucune base, aucune modification de l'application.
Le modèle n'apprend qu'avec des dates dont le rendement cible était entièrement connu au moment de la décision (fenêtre croissante, écart de 2 dates, réapprentissage tous les 12 dates).

Usage :
  PYTHONPATH=$PWD python3 scripts/research_ml.py --panel ~/tmp-backtest/research/out/panel/panel.pkl.gz [--out apprentissage.md] [--json apprentissage.json]
"""
import argparse
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import research_analyses as ra                                     # noqa: E402
import research_stats as rs                                        # noqa: E402
import research_strategies as st                                   # noqa: E402

FEATURES = ('m61', 'm121', 'm31', 'm1', 'vol126', 'slope', 'r2', 'hi', 'mdd252', 'ma200', 'ma50', 'vtr', 'liq')
MODELS = ('lineaire', 'courbe')
LABELS = {'lineaire': 'M1 score appris linéaire (13 rangs)', 'courbe': 'M2 score appris courbe (13 rangs + carrés)', 'mom_6_1': 'Momentum 6-1 (référence)'}
TOP, HORIZON, LAG, MAIN_COST, MIN_POOL = st.TOP, st.HORIZON, st.LAG, st.MAIN_COST, st.MIN_POOL
EMBARGO = 2                    # dates : g21 (entrée t+1, 21 séances) se termine 22 séances après t, avant la 2e date suivante (42 séances)
MIN_TRAIN_DATES = 60
REFIT_EVERY = 12
RIDGE = 0.01                   # λ = RIDGE × lignes / 12 (1 % de la variance d'un rang percentile)
SQUARE_CENTER = 1.0 / 12.0     # moyenne de r² pour r uniforme sur [−0,5 ; 0,5]
BONFERRONI = 0.05 / len(MODELS)
HOLDOUT_DATES = 36
SCENARIOS = st.SCENARIOS
PRIMARY = st.PRIMARY


def nan(x):
    return x != x


def centered_ranks(values):
    """Rangs percentiles centrés (−0,5 … +0,5) ; une valeur manquante vaut 0 (la médiane)."""
    known = [j for j, v in enumerate(values) if not nan(v)]
    out = [0.0] * len(values)
    if len(known) < 2:
        return out
    r = rs.ranks([values[j] for j in known])
    m = len(known) - 1
    for j, x in zip(known, r):
        out[j] = (x - 1) / m - 0.5
    return out


def design(data, rows):
    """Matrice (liste de lignes) des variables du modèle « courbe » ; les 13 premières colonnes sont celles du modèle linéaire."""
    c = data.c
    cols = [centered_ranks([c[f][i] for i in rows]) for f in FEATURES]
    out = []
    for j in range(len(rows)):
        base = [col[j] for col in cols]
        out.append(base + [x * x - SQUARE_CENTER for x in base])
    return out


def width(model):
    return len(FEATURES) * (1 if model == 'lineaire' else 2)


def solve(a, b):
    """Résout a·x = b (élimination de Gauss avec pivot partiel) ; a est symétrique définie positive grâce à la pénalité ridge."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(m[i][k]))
        m[k], m[p] = m[p], m[k]
        if abs(m[k][k]) < 1e-15:
            raise ValueError('système singulier')
        for i in range(k + 1, n):
            f = m[i][k] / m[k][k]
            if f:
                row_i, row_k = m[i], m[k]
                for j in range(k, n + 1):
                    row_i[j] -= f * row_k[j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x


class DateStats:
    """Contributions d'une date à l'apprentissage : X'X, X'y et nombre de lignes (modèle courbe ; le linéaire en prend le bloc 13 × 13)."""
    __slots__ = ('xtx', 'xty', 'n')

    def __init__(self, x, y):
        k = len(x[0]) if x else 0
        xtx = [[0.0] * k for _ in range(k)]
        xty = [0.0] * k
        for row, t in zip(x, y):
            for a in range(k):
                ra_ = row[a]
                if ra_ == 0.0:
                    continue
                xty[a] += ra_ * t
                line = xtx[a]
                for b in range(a, k):
                    line[b] += ra_ * row[b]
        for a in range(k):
            for b in range(a):
                xtx[a][b] = xtx[b][a]
        self.xtx, self.xty, self.n = xtx, xty, len(y)


def fit(stats, model):
    """Coefficients ridge sur la somme des contributions des dates d'entraînement."""
    k = width(model)
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    n = 0
    for s in stats:
        n += s.n
        for a in range(k):
            xty[a] += s.xty[a]
            src, dst = s.xtx[a], xtx[a]
            for b in range(k):
                dst[b] += src[b]
    lam = RIDGE * n / 12.0
    for a in range(k):
        xtx[a][a] += lam
    return solve(xtx, xty), n


def prepare_dates(data, scen):
    """Par date : lignes éligibles, variables, contributions (si assez de rendements cibles connus)."""
    col = ra.column(data, HORIZON, LAG)
    out = {}
    for ti in range(len(data.dates)):
        elig = sorted(data.eligible(ti, 0, scen))
        if len(elig) < MIN_POOL:
            continue
        x = design(data, elig)
        known = [j for j, i in enumerate(elig) if not nan(col[i])]
        stats = None
        if len(known) >= MIN_POOL:
            y = centered_ranks([col[elig[j]] for j in known])
            stats = DateStats([x[j] for j in known], y)
        out[ti] = {'rows': elig, 'x': x, 'stats': stats}
    return out


def learn_scores(data, prepared, model):
    """{ti: {ligne: score}} et l'historique des coefficients. Le modèle utilisé à la date ti n'a vu que des dates ≤ (date d'apprentissage − EMBARGO)."""
    k = width(model)
    scores, history, beta, last_fit = {}, [], None, None
    for ti in sorted(prepared):
        if beta is None or ti - last_fit >= REFIT_EVERY:
            train = [prepared[tj]['stats'] for tj in prepared if tj <= ti - EMBARGO and prepared[tj]['stats'] is not None]
            if len(train) >= MIN_TRAIN_DATES:
                beta, n = fit(train, model)
                last_fit = ti
                history.append({'ti': ti, 'date': data.dates[ti], 'train_dates': len(train), 'train_rows': n, 'beta': beta})
        if beta is None:
            continue
        p = prepared[ti]
        scores[ti] = {i: sum(b * v for b, v in zip(beta, row[:k])) for i, row in zip(p['rows'], p['x'])}
    return scores, history


def run_scores(data, scores, scen, cost=MAIN_COST):
    """Même comptabilité que research_strategies.run_variant, avec le panier « 20 meilleurs scores »."""
    col = ra.column(data, HORIZON, LAG)
    rows, previous = [], {}
    for ti in range(len(data.dates)):
        elig = data.eligible(ti, 0, scen)
        if len(elig) < MIN_POOL or ti not in scores:
            previous = {}
            continue
        pool = [col[i] for i in elig if not nan(col[i])]
        if len(pool) < MIN_POOL:
            previous = {}
            continue
        pick_rows = sorted(scores[ti], key=lambda i: (-scores[ti][i], data.c['key'][i]))[:TOP]
        known = [i for i in pick_rows if not nan(col[i])]
        if len(known) < 0.5 * len(pick_rows):
            previous = {}
            continue
        keys = {int(data.c['key'][i]): 1.0 / len(known) for i in known}
        change = sum(abs(keys.get(k, 0.0) - previous.get(k, 0.0)) for k in set(keys) | set(previous))
        previous = keys
        pick = statistics.fmean(col[i] for i in known)
        rows.append({'ti': ti, 'date': data.dates[ti], 'pick': pick, 'universe': statistics.fmean(pool), 'turnover': 0.5 * change, 'invested': 1.0,
                     'keys': sorted(keys), 'k': len(keys), 'net': pick - (cost / 100.0) * change})
    return rows


def information(data, scores, scen, by_column=None):
    """IC (Spearman) date par date entre le score (ou une colonne du panel) et g21, sur les titres éligibles au rendement connu."""
    col = ra.column(data, HORIZON, LAG)
    out = []
    for ti in sorted(scores):
        rows = [i for i in data.eligible(ti, 0, scen) if not nan(col[i]) and (by_column is None or not nan(data.c[by_column][i]))]
        if len(rows) < MIN_POOL:
            continue
        s = [data.c[by_column][i] if by_column else scores[ti].get(i, 0.0) for i in rows]
        ic = rs.spearman(s, [col[i] for i in rows])
        if ic is not None:
            out.append(ic)
    return rs.summary(out, HORIZON)


def coefficient_table(history, model):
    if not history:
        return []
    names = list(FEATURES) + ([f'{f}²' for f in FEATURES] if model == 'courbe' else [])
    last = history[-1]['beta']
    out = []
    for j, name in enumerate(names):
        same = sum(1 for h in history if (h['beta'][j] > 0) == (last[j] > 0))
        out.append({'variable': name, 'label': ra.SIGNAL_LABELS.get(name.rstrip('²'), name) + (' (au carré)' if name.endswith('²') else ''),
                    'last': last[j], 'sign_stability': 100.0 * same / len(history), 'mean': statistics.fmean(h['beta'][j] for h in history)})
    out.sort(key=lambda r: -abs(r['last']))
    return out


def compare(data, rows, base_by, label):
    common = [r for r in rows if r['ti'] in base_by]
    diff_series = [r['net'] - base_by[r['ti']]['net'] for r in common]
    diff = rs.summary(diff_series, HORIZON)
    periods = st.period_means(data, common, diff_series)
    m = st.metrics(rows)
    base_m = st.metrics([base_by[r['ti']] for r in common]) if common else None
    tail = common[-HOLDOUT_DATES:]
    holdout = {'dates': len(tail), 'from': tail[0]['date'] if tail else None,
               'model_net': statistics.fmean(r['net'] for r in tail) if tail else None,
               'reference_net': statistics.fmean(base_by[r['ti']]['net'] for r in tail) if tail else None}
    return {'label': label, 'metrics': m, 'reference_same_dates': base_m, 'diff': diff, 'periods_diff': periods, 'common_dates': len(common), 'holdout': holdout,
            'verdict': verdict(diff, periods, m, base_m) if base_m else 'données insuffisantes'}


def verdict(diff, periods, m, base):
    if not diff:
        return 'données insuffisantes'
    positive_periods = sum(1 for v in periods.values() if v is not None and v > 0) >= 2
    better_cvar = m['cvar95'] is not None and base['cvar95'] is not None and m['cvar95'] >= base['cvar95'] * (1 - st.CVAR_GAIN)
    ratio_ok = m['ratio'] is not None and base['ratio'] is not None and m['ratio'] >= base['ratio']
    if diff['ci_low'] is not None and diff['ci_low'] > 0 and diff['p_block'] is not None and diff['p_block'] < BONFERRONI and positive_periods:
        return 'améliore le rendement'
    if better_cvar and ratio_ok and diff['ci_high'] is not None and diff['ci_high'] >= 0 and positive_periods:
        return 'meilleur compromis rendement/risque'
    if better_cvar and not ratio_ok:
        return 'réduit le risque mais coûte du rendement'
    return 'pas mieux'


def analyse(data, scen):
    prepared = prepare_dates(data, scen)
    base_rows = st.run_variant(data, st.BASELINE, scen)
    base_by = {r['ti']: r for r in base_rows}
    out = {'baseline': dict(st.metrics(base_rows), label=LABELS['mom_6_1']), 'models': []}
    first_scores = None
    for model in MODELS:
        scores, history = learn_scores(data, prepared, model)
        if not scores:
            continue
        first_scores = first_scores or scores
        rows = run_scores(data, scores, scen)
        if len(rows) < 20:
            continue
        block = compare(data, rows, base_by, LABELS[model])
        block.update({'model': model, 'ic': information(data, scores, scen), 'refits': len(history), 'first_decision': rows[0]['date'],
                      'train_rows_last': history[-1]['train_rows'], 'coefficients': coefficient_table(history, model),
                      'cost_sensitivity': {str(c): statistics.fmean(r['net'] for r in run_scores(data, scores, scen, c)) for c in st.COST_BPS}})
        out['models'].append(block)
    if first_scores:
        out['baseline']['ic_same_dates'] = information(data, first_scores, scen, by_column='m61')
    return out


def f(x, d=2, signed=True):
    return '—' if x is None else f"{x:{'+' if signed else ''}.{d}f}"


def render(report):
    L = ['# Score appris contre le Momentum 6-1', '',
         '*Actions négociables, 20 titres, rééquilibrage toutes les 21 séances, entrée à la clôture suivante, frais 30 pb par sens. Le modèle n\'apprend que sur des dates passées '
         '(fenêtre croissante, écart de 2 dates, réapprentissage tous les 12 dates). Univers des titres encore cotés en 2026 (biais de survie) ; exploratoire. '
         'Protocole : research/PROTOCOLE_APPRENTISSAGE.md.*', '']
    for scen, block in report.items():
        b = block['baseline']
        L += [f"## Scénario « {scen} »{' (référence des conclusions)' if scen == PRIMARY else ' (robustesse)'}", '',
              '| Modèle | Dates | Rendement net moyen | Réf. mêmes dates | Écart vs référence [IC95 blocs] | Stabilité (1993-2007 / 2008-2015 / 2017-2026) | Rapport rdt/écart-type (réf.) | CVaR 95 % (réf.) | Rotation | IC moyen | 36 dernières dates (réf.) | Verdict |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|']
        for m in block['models']:
            mm, rr, d, ho = m['metrics'], m['reference_same_dates'], m['diff'], m['holdout']
            per = ' / '.join(f(x) for x in m['periods_diff'].values())
            L.append(f"| {m['label']} | {m['common_dates']} (dès {m['first_decision']}) | {f(mm['mean_net'])} | {f(rr['mean_net'])} | "
                     f"{f(d['mean'])} [{f(d['ci_low'])} ; {f(d['ci_high'])}] p={f(d['p_block'], 3, False)} | {per} | {f(mm['ratio'], 3)} ({f(rr['ratio'], 3)}) | "
                     f"{f(mm['cvar95'], 1)} ({f(rr['cvar95'], 1)}) | {mm['turnover']:.2f} ({rr['turnover']:.2f}) | {f(m['ic']['mean'], 4)} | {f(ho['model_net'])} ({f(ho['reference_net'])}) | **{m['verdict']}** |")
        ic = b.get('ic_same_dates')
        if ic:
            L += ['', f"IC moyen du momentum 6-1 sur les mêmes dates : {f(ic['mean'], 4)} [{f(ic['ci_low'], 4)} ; {f(ic['ci_high'], 4)}]."]
        L += ['', 'Sensibilité aux frais (rendement net moyen, 10 / 30 / 60 pb) : ' + ' ; '.join(f"{m['model']} {'/'.join(f(x) for x in m['cost_sensitivity'].values())}" for m in block['models']), '']
        for m in block['models']:
            L += [f"### Ce que {m['label'].split(' ')[0]} a appris (dernier apprentissage, {m['refits']} réapprentissages, {m['train_rows_last']} lignes)", '',
                  '| Variable | Poids | Même signe qu\'au dernier apprentissage |', '|---|---|---|']
            for r in m['coefficients'][:8]:
                L.append(f"| {r['label']} | {f(r['last'], 4)} | {r['sign_stability']:.0f} % |")
            L.append('')
    L += ['## Lecture', '',
          '- **Poids** : effet d\'un titre qui passe du milieu au haut du classement de la variable sur son rang futur attendu (positif = favorable). Seules les 8 variables les plus lourdes sont listées.',
          '- **Verdict** : fixé d\'avance (Bonferroni sur 2 modèles, p < 0,025 ; au moins 2 sous-périodes sur 3). « pas mieux » ne prouve pas l\'inutilité ; un verdict favorable reste un indice à confirmer par le Suivi en production.',
          '- **Limites** : biais de survie, pas de change, clôtures seulement, pas de secteur ; périodes déjà consultées par les analyses précédentes.']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--panel', required=True)
    ap.add_argument('--out')
    ap.add_argument('--json')
    ap.add_argument('--scenario', choices=SCENARIOS, action='append', help='par défaut : les deux')
    args = ap.parse_args(argv)
    data = ra.load_data(args.panel, None)
    report = {scen: analyse(data, scen) for scen in (args.scenario or SCENARIOS)}
    text = render(report)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    if args.json:
        with open(os.path.expanduser(args.json), 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, default=lambda o: None if o != o else str(o))
    return 0


if __name__ == '__main__':
    sys.exit(main())
