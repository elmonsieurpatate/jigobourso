"""Test chronologique (« walk-forward ») des stratégies de départ. LECTURE SEULE : aucune écriture en base, aucun appel réseau.

À chaque date de rééquilibrage t (tous les `--step` séances), le script rejoue l'Explorer avec les seules clôtures antérieures ou égales à t, garde les `--top` premiers
titres de chaque groupe (actions / ETF) pour chaque profil, puis mesure leur rendement `h` séances plus tard. Il le compare :
  - à l'univers entier (moyenne équipondérée des titres évaluables ce jour-là) ;
  - à des tirages au hasard de même taille (p-valeur : part des tirages qui font au moins aussi bien) ;
  - à un momentum naïf « 6 mois moins le dernier mois », classé sur la même date.
Les coûts sont retirés : `--cost-bps` points de base par achat ou vente, renouvellement complet supposé à chaque rééquilibrage.

CE QUE LE TEST NE PEUT PAS FAIRE (rappelé dans la sortie) : l'univers est celui d'AUJOURD'HUI (titres radiés absents, préfiltre de liquidité d'aujourd'hui appliqué au passé),
les rendements sont hors dividendes et en devise locale, et l'historique en base (≈ 400 séances) ne donne que quelques dates indépendantes. Un résultat favorable n'est donc
pas une promesse ; un résultat nul ou défavorable, lui, est une information.

Usage : python scripts/backtest_walkforward.py [--horizon 21 63] [--step 21] [--dates 10] [--top 20] [--cost-bps 10] [--sample 3000] [--seed 1] [--json sortie.json]
Connexion : variables JIGO_DB_* (comme le moteur). Sur l'hébergement : PYTHONPATH=$PWD .venv/bin/python scripts/backtest_walkforward.py
"""
import argparse
import bisect
import datetime
import json
import math
import os
import random
import statistics
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.analytics import strategy                                        # noqa: E402
from engine.analytics.series import analyze_series, prepare_series          # noqa: E402

MAX_STALE_DAYS = 5          # dernière clôture trop ancienne à la date t : le titre n'est pas évalué ce jour-là (comme le Suivi)
MIN_CLOSES = 30
BASELINE = 'mom_6_1'
CAVEATS = (
    "Univers d'aujourd'hui : les titres radiés ou sortis du catalogue sont absents (biais de survie) et le préfiltre de liquidité d'aujourd'hui est appliqué au passé.",
    "Rendements en devise locale, hors dividendes, sur cours bruts corrigés des seuls splits confirmés.",
    "Peu de dates indépendantes : lire la t-stat et la p-valeur, pas seulement la moyenne. Les rendements de dates voisines se chevauchent quand `step` < `horizon`.",
    "Le test mesure si le classement aurait précédé de meilleurs rendements dans l'échantillon ; il ne prouve rien sur l'avenir.",
)


# ───────── calendrier et données ─────────
def reference_dates(candidates):
    """Séances de référence : dates où au moins la moitié du plus grand nombre de séries a une clôture (même règle que tracking.reference_calendar)."""
    count = defaultdict(int)
    for c in candidates:
        for d in c['dates']:
            count[d] += 1
    if not count:
        return []
    biggest = max(count.values())
    return sorted(d for d, n in count.items() if n >= biggest / 2)


def pick_dates(calendar, horizons, step, how_many, first_index=126):
    """Dates de rééquilibrage : les plus récentes possibles (il faut `max(horizons)` séances derrière chacune), espacées de `step`."""
    last = len(calendar) - 1 - max(horizons)
    out, i = [], last
    while i >= first_index and len(out) < how_many:
        out.append(calendar[i])
        i -= step
    return sorted(out)


def prepare(candidate):
    """Ajoute à un candidat (format `repository.recommendable_candidates`) la liste de ses dates et sa série corrigée, calculée UNE fois sur toute la période,
    seulement pour mesurer les rendements futurs (jamais pour décider)."""
    c = dict(candidate)
    c['dates'] = [b[0] for b in c['bars']]
    c['full'] = prepare_series(c['bars'], c.get('split_dates') or ())
    return c


def forward_return(full, t, h):
    """Rendement (%) h séances après t sur la série complète ; None si la base est trop ancienne, si la série s'arrête avant, ou si une rupture non expliquée est traversée."""
    dates, closes, _, breaks = full
    base = bisect.bisect_right(dates, t) - 1
    if base < 0 or (datetime.date.fromisoformat(t) - datetime.date.fromisoformat(dates[base])).days > MAX_STALE_DAYS:
        return None
    j = base + h
    if j >= len(closes) or any(base < b <= j for b in breaks):
        return None
    return 100 * (closes[j] / closes[base] - 1)


# ───────── passage d'un lot de titres ─────────
class Study:
    """Accumule, date par date, les verdicts retenus et les rendements futurs. Seuls les verdicts retenus restent en mémoire (le rang ne dépend que d'eux)."""

    def __init__(self, presets, horizons, dates):
        self.configs = {name: strategy.validate(strategy.preset(name)) for name in presets}
        self.horizons, self.dates = tuple(horizons), tuple(dates)
        self.windows = sorted({n for cfg in self.configs.values() for n in strategy.required_sessions(cfg)})
        self.retained = defaultdict(list)       # (date, preset) -> [verdict retenu]
        self.universe = defaultdict(dict)       # (date, group) -> {clé: {h: rendement}}
        self.momentum = defaultdict(dict)       # (date, group) -> {clé: score}

    def add(self, candidates):
        for raw in candidates:
            c = raw if 'full' in raw else prepare(raw)
            for t in self.dates:
                n = bisect.bisect_right(c['dates'], t)
                if n < MIN_CLOSES or (datetime.date.fromisoformat(t) - datetime.date.fromisoformat(c['dates'][n - 1])).days > MAX_STALE_DAYS:
                    continue
                dates, closes, _, breaks, measures, missing, tech = analyze_series(c['bars'][:n], self.windows, c.get('split_dates') or ())
                fwd = {h: forward_return(c['full'], t, h) for h in self.horizons}
                # Le titre est évalué et classé même sans rendement futur : écarter d'avance ceux dont l'avenir est inconnu ou cassé ferait entrer le futur dans la sélection.
                # Leur résultat manquera seulement à la mesure (voir `results` : colonne « sél. » = titres de la sélection dont le rendement est connu).
                self.universe[(t, c['group'])][c['key']] = {h: r for h, r in fwd.items() if r is not None}
                if len(closes) > 127 and not any(b > len(closes) - 128 for b in breaks):
                    self.momentum[(t, c['group'])][c['key']] = closes[-22] / closes[-127] - 1
                for name, cfg in self.configs.items():
                    v = strategy.judge(cfg, measures, tech, missing, dates[-1], None)
                    if v['status'] == 'retained':
                        self.retained[(t, name)].append(dict(v, key=c['key'], group=c['group'], symbol=c['symbol']))

    # ───────── agrégation ─────────
    def picks(self, top):
        """{(date, nom, groupe): [clés]} : les `top` premiers de chaque profil, et du momentum naïf."""
        out = {}
        for t in self.dates:
            for name, cfg in self.configs.items():
                ranked = strategy.rank(cfg, self.retained.get((t, name), []))
                for group in ('equity', 'etf'):
                    keys = [v['key'] for v in sorted((v for v in ranked if v['group'] == group and v['rank'] is not None), key=lambda v: v['rank'])[:top]]
                    if keys:
                        out[(t, name, group)] = keys
            for group in ('equity', 'etf'):
                scores = self.momentum.get((t, group), {})
                keys = [k for k, _ in sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))[:top]]
                if keys:
                    out[(t, BASELINE, group)] = keys
        return out

    def results(self, top=20, cost_bps=10.0, step=21, draws=500, seed=1):
        picks = self.picks(top)
        rng = random.Random(seed)
        cost = 2 * cost_bps / 100.0                         # aller-retour, en points de rendement, une fois par rééquilibrage
        names = list(self.configs) + [BASELINE]
        out = []
        for name in names:
            for group in ('equity', 'etf'):
                for h in self.horizons:
                    rows = []
                    for t in self.dates:
                        keys = picks.get((t, name, group))
                        uni = {k: r[h] for k, r in self.universe.get((t, group), {}).items() if h in r}
                        got = [uni[k] for k in (keys or []) if k in uni]
                        if not got or len(uni) < 2 * len(got):
                            continue
                        rows.append({'date': t, 'k': len(got), 'pick': statistics.fmean(got), 'uni': statistics.fmean(uni.values()), 'pool': list(uni.values())})
                    if not rows:
                        continue
                    excess = [r['pick'] - r['uni'] for r in rows]
                    spacing = max(1, math.ceil(h / step))
                    indep = excess[::spacing]                # sous-échantillon sans chevauchement pour la t-stat
                    net = [e - cost for e in excess]
                    net_indep = net[::spacing]
                    sims = []
                    for _ in range(draws):
                        sims.append(statistics.fmean(statistics.fmean(rng.sample(r['pool'], r['k'])) - r['uni'] for r in rows))
                    obs = statistics.fmean(excess)
                    out.append({
                        'strategy': name, 'group': group, 'horizon': h, 'dates': len(rows), 'independent_dates': len(indep),
                        'avg_picks': round(statistics.fmean(r['k'] for r in rows), 1),
                        'pick_mean': round(statistics.fmean(r['pick'] for r in rows), 2), 'universe_mean': round(statistics.fmean(r['uni'] for r in rows), 2),
                        'excess_gross': round(obs, 2), 'excess_net': round(statistics.fmean(net), 2),
                        't_net': _tstat(net_indep), 'share_positive': round(100 * sum(1 for e in net if e > 0) / len(net)),
                        'p_random': round((1 + sum(1 for s in sims if s >= obs)) / (draws + 1), 3),
                    })
        return out


def _tstat(values):
    if len(values) < 3:
        return None
    sd = statistics.stdev(values)
    return None if sd == 0 else round(statistics.fmean(values) / (sd / math.sqrt(len(values))), 2)


# ───────── présentation ─────────
def render(results, meta):
    lines = [f"Test chronologique · {meta['titles']} titres · {len(meta['dates'])} dates ({meta['dates'][0]} → {meta['dates'][-1]}) · top {meta['top']} par groupe · coût {meta['cost_bps']} pb par sens", '']
    head = f"{'profil':<15}{'groupe':<8}{'h':>4}{'dates':>6}{'indép.':>7}{'sél.':>6}{'sélection':>10}{'univers':>9}{'excès brut':>11}{'excès net':>10}{'t net':>7}{'% dates+':>9}{'p hasard':>9}"
    lines.append(head)
    lines.append('-' * len(head))
    for r in sorted(results, key=lambda r: (r['group'], r['horizon'], r['strategy'])):
        t = '—' if r['t_net'] is None else f"{r['t_net']:.2f}"
        lines.append(f"{r['strategy']:<15}{r['group']:<8}{r['horizon']:>4}{r['dates']:>6}{r['independent_dates']:>7}{r['avg_picks']:>6}{r['pick_mean']:>9.2f}%{r['universe_mean']:>8.2f}%"
                     f"{r['excess_gross']:>10.2f}%{r['excess_net']:>9.2f}%{t:>7}{r['share_positive']:>8}%{r['p_random']:>9.3f}")
    lines += ['', 'Lecture : « excès » = rendement moyen de la sélection moins celui de l\'univers, en points de rendement sur l\'horizon h (séances).',
              '« p hasard » : part de tirages au hasard de même taille qui font au moins aussi bien (petit = peu probable par chance). « t net » : sur dates sans chevauchement.', '', 'Limites :']
    lines += [f'  - {c}' for c in CAVEATS]
    return '\n'.join(lines)


# ───────── lecture de la base (lecture seule) ─────────
def load_batches(conn, history, sample, seed, batch=300):
    from engine.analytics.repository import recommendable_candidates
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id FROM v_recommendable ORDER BY listing_id')
        ids = [r['listing_id'] for r in cur.fetchall()]
    if sample and sample < len(ids):
        ids = sorted(random.Random(seed).sample(ids, sample))
    for start in range(0, len(ids), batch):
        yield recommendable_candidates(conn, history=history, ids=ids[start:start + batch])


def reference_calendar_db(conn):
    from engine.analytics.tracking import reference_calendar
    return reference_calendar(conn)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--horizon', type=int, nargs='+', default=[21, 63], help='horizons en séances')
    ap.add_argument('--step', type=int, default=21, help='séances entre deux rééquilibrages')
    ap.add_argument('--dates', type=int, default=10, help='nombre de dates de rééquilibrage')
    ap.add_argument('--top', type=int, default=20, help='titres gardés par groupe et par profil')
    ap.add_argument('--cost-bps', type=float, default=10.0, help='coût par achat ou vente, en points de base')
    ap.add_argument('--sample', type=int, default=0, help='sous-échantillon aléatoire de l\'univers (0 = tout)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--draws', type=int, default=500, help='tirages au hasard pour la p-valeur')
    ap.add_argument('--json', help='écrit aussi les résultats dans ce fichier')
    args = ap.parse_args(argv)
    from engine.shared.db import connect
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SET SESSION TRANSACTION READ ONLY')
        calendar = reference_calendar_db(conn)
        dates = pick_dates(calendar, args.horizon, args.step, args.dates)
        if len(dates) < 3:
            print('Historique insuffisant pour un test chronologique (moins de 3 dates).', file=sys.stderr)
            return 3
        study, titles, t0 = Study(strategy.PRESETS, args.horizon, dates), 0, time.monotonic()
        for lot in load_batches(conn, history=len(calendar) + 5, sample=args.sample, seed=args.seed):
            study.add(prepare(c) for c in lot)
            titles += len(lot)
            print(f'{titles} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
        conn.rollback()
    finally:
        conn.close()
    results = study.results(args.top, args.cost_bps, args.step, args.draws, args.seed)
    meta = {'titles': titles, 'dates': dates, 'top': args.top, 'cost_bps': args.cost_bps, 'horizons': args.horizon, 'caveats': CAVEATS}
    print(render(results, meta))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'meta': meta, 'results': results}, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
