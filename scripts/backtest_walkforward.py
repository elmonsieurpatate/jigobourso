"""Test chronologique (« walk-forward ») des stratégies de départ. LECTURE SEULE : aucune écriture en base, aucun appel réseau.

À chaque date de rééquilibrage t (tous les `--step` séances), le script rejoue l'Explorer avec les seules clôtures antérieures ou égales à t, garde les `--top` premiers
titres de chaque groupe (actions / ETF) pour chaque profil, puis mesure leur rendement `h` séances plus tard. Il le compare :
  - à l'univers entier (moyenne équipondérée des titres évaluables ce jour-là) ;
  - à des tirages au hasard de même taille (p-valeur : part des tirages qui font au moins aussi bien, sur les dates SANS chevauchement) ;
  - à d'autres règles de classement (momentum 12-1, faible volatilité, retournement…, voir SIGNALS), classées sur la même date, avec le même nombre de titres.
Les coûts sont retirés : `--cost-bps` points de base par achat ou vente, renouvellement complet supposé à chaque rééquilibrage.
Il rapporte aussi le risque de chaque sélection (dispersion des rendements, 10 % les plus bas, part de rendements négatifs) et des écarts MÉDIANS, moins sensibles aux cas extrêmes.

Deux sources de données :
  --source db  (défaut) : la base de l'application (≈ 400 séances), variables JIGO_DB_* ;
  --source csv --csv-dir DOSSIER : l'historique long produit par scripts/export_history.py (jusqu'à 10 ans, cours ajustés des dividendes). Beaucoup plus de dates, donc des
                          résultats moins dépendants d'un seul climat de marché.
`--split-date AAAA-MM-JJ` coupe les dates en deux : « calibration » (avant) et « validation » (à partir de cette date). Règle de méthode : on peut ajuster un réglage en regardant la
calibration ; la validation, elle, ne se regarde qu'UNE fois, pour confirmer, jamais pour ajuster.

CE QUE LE TEST NE PEUT PAS FAIRE (rappelé dans la sortie) : l'univers est celui d'AUJOURD'HUI (titres radiés absents, préfiltre de liquidité d'aujourd'hui appliqué au passé),
et le nombre de dates indépendantes reste limité. Un résultat favorable n'est pas une promesse ; un résultat nul ou défavorable, lui, est une information.

Usage : python scripts/backtest_walkforward.py [--source csv --csv-dir ~/tmp-history] [--horizon 21 63] [--step 21] [--dates N] [--top 20] [--cost-bps 10]
                                              [--split-date 2023-01-01] [--sample 3000] [--seed 1] [--json sortie.json]
"""
import argparse
import bisect
import csv
import datetime
import gzip
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
from engine.analytics.measures import window_metrics                         # noqa: E402
from engine.analytics.series import analyze_series, prepare_series          # noqa: E402

MAX_STALE_DAYS = 5          # dernière clôture trop ancienne à la date t : le titre n'est pas évalué ce jour-là (comme le Suivi)
MIN_CLOSES = 30
DECISION_BARS = 420         # clôtures visibles par le classement à chaque date (l'application en garde environ 400)
BASELINE = 'mom_6_1'
CAVEATS = (
    "Univers d'aujourd'hui : les titres radiés ou sortis du catalogue sont absents (biais de survie) et le préfiltre de liquidité d'aujourd'hui est appliqué au passé.",
    "Source « db » : rendements en devise locale, hors dividendes. Source « csv » : cours ajustés des dividendes et des splits, en devise locale.",
    "Peu de dates indépendantes : lire la t-stat et la p-valeur (calculées sans chevauchement), pas seulement la moyenne. Une ligne « significative » sur vingt arrive par hasard.",
    "Le test mesure si le classement aurait précédé de meilleurs rendements dans l'échantillon ; il ne prouve rien sur l'avenir.",
)


# ───────── calendrier et données ─────────
def calendar_from_counts(count, min_share=0.5, min_titles=0):
    """Séances de référence : dates où au moins `min_share` du plus grand nombre de séries (et au moins `min_titles` titres) ont une clôture.
    Par défaut la moitié, comme tracking.reference_calendar. Pour un historique LONG, cette règle écarte tout ce qui précède l'arrivée de la moitié des titres
    (ici mi-2016 : près de la moitié des titres ont moins de dix ans) ; on la baisse alors (`--min-share`), en acceptant des univers plus petits aux dates anciennes."""
    if not count:
        return []
    biggest = max(count.values())
    return sorted(d for d, n in count.items() if n >= max(biggest * min_share, min_titles))


def reference_dates(candidates, min_share=0.5, min_titles=0):
    count = defaultdict(int)
    for c in candidates:
        for d in c['dates']:
            count[d] += 1
    return calendar_from_counts(count, min_share, min_titles)


def pick_dates(calendar, horizons, step, how_many, first_index=126):
    """Dates de rééquilibrage : les plus récentes possibles (il faut `max(horizons)` séances derrière chacune), espacées de `step`. `how_many` = 0 : toutes."""
    last = len(calendar) - 1 - max(horizons)
    out, i = [], last
    while i >= first_index and (not how_many or len(out) < how_many):
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



# ───────── autres stratégies : des règles de classement sur les seuls cours passés ─────────
# Chaque signal reçoit les clôtures visibles à la date t (jamais une clôture postérieure, et seulement celles qui suivent la dernière rupture de cours) et renvoie un score
# (plus haut = mieux classé) ou None (titre non classé ce jour-là). Ajouter une idée = ajouter une ligne ici ; elle est alors testée comme les profils de l'application.
# Règle de méthode : la liste est COURTE et fixée À L'AVANCE. Chaque variante testée de plus augmente la part de « succès » dus au hasard.
def _mom(long, skip):
    """Rendement entre il y a `long` séances et il y a `skip` séances (on ignore le dernier mois, dont l'effet tend à se retourner)."""
    return lambda c: c[-1 - skip] / c[-1 - long] - 1 if len(c) > long else None


def _vol(window):
    def spread(c):
        if len(c) <= window:
            return None
        return statistics.pstdev([math.log(c[i] / c[i - 1]) for i in range(len(c) - window, len(c))])
    return spread


def _low_vol(c):
    v = _vol(126)(c)
    return None if v is None else -v


def _risk_adjusted(c):
    m, v = _mom(126, 21)(c), _vol(126)(c)
    return None if m is None or not v else m / v


def _near_high(c):
    return c[-1] / max(c[-252:]) if len(c) >= 252 else None


def _trend_filtered(c):
    m = _mom(126, 21)(c)
    return m if m is not None and len(c) >= 200 and c[-1] > statistics.fmean(c[-200:]) else None


def _smooth(c):
    w = window_metrics(c[-127:]) if len(c) >= 127 else None
    return None if not w or w['slope'] is None or w['r2'] is None else w['slope'] * w['r2']


def _dual(c):
    m = _mom(252, 21)(c)
    return m if m is not None and m > 0 else None


SIGNALS = {
    'mom_6_1': (_mom(126, 21), "momentum simple : rendement de il y a 6 mois à il y a 1 mois (référence)"),
    'mom_12_1': (_mom(252, 21), "momentum classique : de il y a 12 mois à il y a 1 mois"),
    'mom_3_1': (_mom(63, 21), "momentum court : de il y a 3 mois à il y a 1 mois"),
    'reversal_1m': (lambda c: -(c[-1] / c[-22] - 1) if len(c) > 21 else None, "retournement : les plus mauvais du dernier mois (contraire du momentum)"),
    'low_vol_126': (_low_vol, "faible volatilité : variations quotidiennes les plus faibles sur 6 mois"),
    'risk_adj_mom': (_risk_adjusted, "momentum 6-1 divisé par la volatilité (rendement par unité de risque)"),
    'near_52w_high': (_near_high, "proximité du plus haut sur 12 mois"),
    'trend_mom': (_trend_filtered, "momentum 6-1, seulement si le cours est au-dessus de sa moyenne sur 200 séances"),
    'smooth_mom': (_smooth, "pente × régularité (R²) sur 6 mois : montée droite plutôt que saccadée"),
    'dual_mom': (_dual, "momentum 12-1, seulement s'il est positif (momentum absolu + relatif)"),
}
COMPOSITES = {'mix_mom_lowvol': (('mom_12_1', 'low_vol_126'), "moyenne des rangs de momentum 12-1 et de faible volatilité")}
DEFAULT_SIGNALS = tuple(SIGNALS) + tuple(COMPOSITES)


def signal_labels():
    return {**{k: v[1] for k, v in SIGNALS.items()}, **{k: v[1] for k, v in COMPOSITES.items()}}


def _percentile_ranks(scores):
    """{clé: rang centile 0-100} (ex æquo = moyenne des rangs), comme le classement de l'application."""
    return strategy._percentiles(scores)


# ───────── passage d'un lot de titres ─────────
class Study:
    """Accumule, date par date, les verdicts retenus et les rendements futurs. Seuls les verdicts retenus restent en mémoire (le rang ne dépend que d'eux)."""

    def __init__(self, presets, horizons, dates, signals=DEFAULT_SIGNALS):
        self.configs = {name: strategy.validate(strategy.preset(name)) for name in presets}
        unknown = [n for n in signals if n not in SIGNALS and n not in COMPOSITES]
        if unknown:
            raise ValueError('Signal inconnu : ' + ', '.join(unknown))
        self.signal_names = tuple(signals)
        needed = {n for n in self.signal_names if n in SIGNALS} | {c for n in self.signal_names if n in COMPOSITES for c in COMPOSITES[n][0]}
        self.computed = tuple(sorted(needed))
        self.horizons, self.dates = tuple(horizons), tuple(dates)
        self.windows = sorted({n for cfg in self.configs.values() for n in strategy.required_sessions(cfg)})
        self.retained = defaultdict(list)       # (date, preset) -> [verdict retenu]
        self.universe = defaultdict(dict)       # (date, group) -> {clé: {h: rendement}}
        self.scores = defaultdict(dict)         # (date, group, signal) -> {clé: score}

    def add(self, candidates):
        for raw in candidates:
            c = raw if 'full' in raw else prepare(raw)
            for t in self.dates:
                n = bisect.bisect_right(c['dates'], t)
                if n < MIN_CLOSES or (datetime.date.fromisoformat(t) - datetime.date.fromisoformat(c['dates'][n - 1])).days > MAX_STALE_DAYS:
                    continue
                visible = c['bars'][max(0, n - DECISION_BARS):n]                    # jamais une clôture postérieure à t
                dates, closes, _, breaks, measures, missing, tech = analyze_series(visible, self.windows, c.get('split_dates') or ())
                fwd = {h: forward_return(c['full'], t, h) for h in self.horizons}
                # Le titre est évalué et classé même sans rendement futur : écarter d'avance ceux dont l'avenir est inconnu ou cassé ferait entrer le futur dans la sélection.
                # Leur résultat manquera seulement à la mesure (voir `results` : colonne « sél. » = titres de la sélection dont le rendement est connu).
                self.universe[(t, c['group'])][c['key']] = {h: r for h, r in fwd.items() if r is not None}
                usable = closes[breaks[-1]:] if breaks else closes                      # seulement les clôtures qui suivent la dernière rupture de cours
                for name in self.computed:
                    score = SIGNALS[name][0](usable)
                    if score is not None and math.isfinite(score):
                        self.scores[(t, c['group'], name)][c['key']] = score
                for name, cfg in self.configs.items():
                    v = strategy.judge(cfg, measures, tech, missing, dates[-1], None)
                    if v['status'] == 'retained':
                        self.retained[(t, name)].append(dict(v, key=c['key'], group=c['group'], symbol=c['symbol']))

    # ───────── agrégation ─────────
    def picks(self, top, only_dates=None):
        """{(date, nom, groupe): [clés]} : les `top` premiers de chaque profil de l'application et de chaque signal testé."""
        out = {}
        for t in (only_dates if only_dates is not None else self.dates):
            for name, cfg in self.configs.items():
                ranked = strategy.rank(cfg, self.retained.get((t, name), []))
                for group in ('equity', 'etf'):
                    keys = [v['key'] for v in sorted((v for v in ranked if v['group'] == group and v['rank'] is not None), key=lambda v: v['rank'])[:top]]
                    if keys:
                        out[(t, name, group)] = keys
            for group in ('equity', 'etf'):
                for name in self.signal_names:
                    if name in COMPOSITES:
                        parts = [self.scores.get((t, group, c), {}) for c in COMPOSITES[name][0]]
                        common = set.intersection(*(set(p) for p in parts)) if parts else set()
                        ranks = [_percentile_ranks({k: p[k] for k in common}) for p in parts]
                        scores = {k: statistics.fmean(r[k] for r in ranks) for k in common}
                    else:
                        scores = self.scores.get((t, group, name), {})
                    keys = [k for k, _ in sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))[:top]]
                    if keys:
                        out[(t, name, group)] = keys
        return out

    def results(self, top=20, cost_bps=10.0, step=21, draws=500, seed=1, only_dates=None, period=None, min_pool=0):
        dates = tuple(only_dates) if only_dates is not None else self.dates
        picks = self.picks(top, dates)
        rng = random.Random(seed)
        cost = 2 * cost_bps / 100.0                         # aller-retour, en points de rendement, une fois par rééquilibrage
        out = []
        for name in list(self.configs) + list(self.signal_names):
            for group in ('equity', 'etf'):
                for h in self.horizons:
                    rows = []
                    for t in dates:
                        keys = picks.get((t, name, group))
                        uni = {k: r[h] for k, r in self.universe.get((t, group), {}).items() if h in r}
                        got = [uni[k] for k in (keys or []) if k in uni]
                        if not got or len(uni) < max(2 * len(got), min_pool):          # univers trop petit à cette date pour que « top N » soit une vraie sélection
                            continue
                        pool = list(uni.values())
                        rows.append({'date': t, 'k': len(got), 'got': got, 'pool': pool, 'pick': statistics.fmean(got), 'uni': statistics.fmean(pool),
                                     'median_gap': statistics.median(got) - statistics.median(pool)})
                    if not rows:
                        continue
                    for r in rows:
                        r['excess'] = r['pick'] - r['uni']
                    spacing = max(1, math.ceil(h / step))
                    indep = rows[::spacing]                  # sous-échantillon sans chevauchement : t-stat et p-valeur n'utilisent que lui
                    net = [r['excess'] - cost for r in rows]
                    p_random = None
                    if len(indep) >= 3:
                        obs = statistics.fmean(r['excess'] for r in indep)
                        sims = [statistics.fmean(statistics.fmean(rng.sample(r['pool'], r['k'])) - r['uni'] for r in indep) for _ in range(draws)]
                        p_random = round((1 + sum(1 for s in sims if s >= obs)) / (draws + 1), 3)
                    pick_all, uni_all = [x for r in rows for x in r['got']], [x for r in rows for x in r['pool']]
                    out.append({
                        'strategy': name, 'group': group, 'horizon': h, 'period': period, 'dates': len(rows), 'independent_dates': len(indep),
                        'avg_picks': round(statistics.fmean(r['k'] for r in rows), 1),
                        'pick_mean': round(statistics.fmean(r['pick'] for r in rows), 2), 'universe_mean': round(statistics.fmean(r['uni'] for r in rows), 2),
                        'excess_gross': round(statistics.fmean(r['excess'] for r in rows), 2), 'excess_net': round(statistics.fmean(net), 2),
                        'excess_median': round(statistics.fmean(r['median_gap'] for r in rows), 2),
                        't_net': _tstat([e - cost for e in (r['excess'] for r in indep)]), 'share_positive': round(100 * sum(1 for e in net if e > 0) / len(net)),
                        'p_random': p_random,
                        'risk': {'pick_spread': round(statistics.pstdev(pick_all), 2), 'universe_spread': round(statistics.pstdev(uni_all), 2),
                                 'pick_p10': round(_quantile(pick_all, 0.10), 2), 'universe_p10': round(_quantile(uni_all, 0.10), 2),
                                 'pick_negative': round(100 * sum(1 for x in pick_all if x < 0) / len(pick_all)),
                                 'universe_negative': round(100 * sum(1 for x in uni_all if x < 0) / len(uni_all))},
                        'by_date': [{'date': r['date'], 'picks': r['k'], 'pick': round(r['pick'], 2), 'universe': round(r['uni'], 2), 'excess': round(r['excess'], 2)} for r in rows],
                    })
        return out


def _quantile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))]


def _tstat(values):
    if len(values) < 3:
        return None
    sd = statistics.stdev(values)
    return None if sd == 0 else round(statistics.fmean(values) / (sd / math.sqrt(len(values))), 2)


# ───────── présentation ─────────
def render(results, meta):
    dates = meta['dates']
    lines = [f"Test chronologique · {meta['titles']} titres · {len(dates)} dates ({dates[0]} → {dates[-1]}) · top {meta['top']} par groupe · coût {meta['cost_bps']} pb par sens"
             + (f" · coupure {meta['split_date']}" if meta.get('split_date') else ''), '']
    head = (f"{'profil':<15}{'groupe':<8}{'h':>4}{'dates':>6}{'indép.':>7}{'sél.':>6}{'sélection':>10}{'univers':>9}{'excès brut':>11}{'excès net':>10}{'excès méd.':>11}"
            f"{'t net':>7}{'% dates+':>9}{'p hasard':>9}")
    for period in dict.fromkeys(r.get('period') for r in results):
        part = [r for r in results if r.get('period') == period]
        lines += ([f'── {period} ──'] if period else []) + [head, '-' * len(head)]
        for r in sorted(part, key=lambda r: (r['group'], r['horizon'], r['strategy'])):
            t = '—' if r['t_net'] is None else f"{r['t_net']:.2f}"
            p = '—' if r['p_random'] is None else f"{r['p_random']:.3f}"
            lines.append(f"{r['strategy']:<15}{r['group']:<8}{r['horizon']:>4}{r['dates']:>6}{r['independent_dates']:>7}{r['avg_picks']:>6}{r['pick_mean']:>9.2f}%{r['universe_mean']:>8.2f}%"
                         f"{r['excess_gross']:>10.2f}%{r['excess_net']:>9.2f}%{r['excess_median']:>10.2f}%{t:>7}{r['share_positive']:>8}%{p:>9}")
        lines += ['', f"Risque des sélections{' · ' + period if period else ''} (rendements individuels sur l'horizon, tous titres et dates confondus) :",
                  f"{'profil':<15}{'groupe':<8}{'h':>4}{'dispersion':>11}{'univers':>9}{'10 % bas':>10}{'univers':>9}{'% négatifs':>11}{'univers':>9}"]
        for r in sorted(part, key=lambda r: (r['group'], r['horizon'], r['strategy'])):
            k = r['risk']
            lines.append(f"{r['strategy']:<15}{r['group']:<8}{r['horizon']:>4}{k['pick_spread']:>10.1f}%{k['universe_spread']:>8.1f}%{k['pick_p10']:>9.1f}%{k['universe_p10']:>8.1f}%"
                         f"{k['pick_negative']:>10}%{k['universe_negative']:>8}%")
        lines += [f"{len(part)} lignes dans cette période : environ {0.05 * len(part):.1f} d'entre elles auront p < 0,05 par pur hasard.", '']
    lines += ['Lecture : « excès » = rendement moyen de la sélection moins celui de l\'univers, en points de rendement sur l\'horizon h (séances) ; « méd. » = même écart sur les médianes.',
              '« p hasard » : part de tirages au hasard de même taille qui font au moins aussi bien (petit = peu probable par chance). « t net » et « p hasard » : dates sans chevauchement.', '', 'Limites :']
    lines += [f'  - {c}' for c in CAVEATS]
    if meta.get('signals'):
        lines += ['', f"Stratégies testées en plus des profils de l'application ({meta.get('variants', '?')} variantes au total) :"] + [f'  - {n} : {d}' for n, d in meta['signals'].items()]
    return '\n'.join(lines)


# ───────── sources de données ─────────
def load_batches(conn, history, sample, seed, batch=300):
    """Base de l'application (lecture seule)."""
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


MAX_MEDIAN_GAP_DAYS = 4


def is_daily(dates):
    """Vrai si l'écart médian entre deux dates consécutives est de quelques jours au plus (un fichier mensuel ou hebdomadaire fausserait tout le test)."""
    if len(dates) < 10:
        return True
    days = [datetime.date.fromisoformat(d) for d in dates]
    return statistics.median((b - a).days for a, b in zip(days, days[1:])) <= MAX_MEDIAN_GAP_DAYS


def csv_universe(directory):
    with open(os.path.join(directory, 'universe.csv'), encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def _history_file(directory, key):
    return os.path.join(directory, 'history', f'{key}.csv.gz')


def csv_calendar(directory, universe, min_share=0.5, min_titles=0):
    """Séances de référence, en ne lisant que la colonne des dates (le calendrier doit être connu avant de traiter les titres par lots)."""
    count, skipped = defaultdict(int), 0
    for u in universe:
        path = _history_file(directory, u['key'])
        if not os.path.exists(path):
            continue
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
            dates = [row['date'] for row in csv.DictReader(fh)]
        if not is_daily(dates):
            skipped += 1
            continue
        for d in dates:
            count[d] += 1
    if skipped:
        print(f'{skipped} fichier(s) non quotidien(s) ignoré(s) (écart médian > {MAX_MEDIAN_GAP_DAYS} jours) : refaire l\'export avec le script à jour.', file=sys.stderr)
    return calendar_from_counts(count, min_share, min_titles)


def csv_batches(directory, universe, sample=0, seed=1, batch=100):
    """Historique long exporté par scripts/export_history.py : les cours ajustés servent de base (rendement total), le cours brut est conservé."""
    rows = [u for u in universe if os.path.exists(_history_file(directory, u['key']))]
    if sample and sample < len(rows):
        rows = sorted(random.Random(seed).sample(rows, sample), key=lambda u: u['key'])
    for start in range(0, len(rows), batch):
        out = []
        for u in rows[start:start + batch]:
            with gzip.open(_history_file(directory, u['key']), 'rt', encoding='utf-8', newline='') as fh:
                bars = [(r['date'], float(r['close']), float(r['adjclose'])) for r in csv.DictReader(fh)]
            if bars and is_daily([b[0] for b in bars]):
                out.append({'key': u['key'], 'symbol': u['symbol'], 'mic': u.get('mic'), 'group': 'etf' if u.get('kind') == 'etf' else 'equity', 'bars': bars, 'split_dates': []})
        yield out


def split_periods(dates, split_date):
    before = [d for d in dates if d < split_date]
    after = [d for d in dates if d >= split_date]
    return [('calibration', before), ('validation', after)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--source', choices=('db', 'csv'), default='db')
    ap.add_argument('--csv-dir', help="dossier produit par scripts/export_history.py (avec --source csv)")
    ap.add_argument('--horizon', type=int, nargs='+', default=[21, 63], help='horizons en séances')
    ap.add_argument('--step', type=int, default=21, help='séances entre deux rééquilibrages')
    ap.add_argument('--dates', type=int, default=None, help='nombre de dates de rééquilibrage (défaut : 10 pour la base, toutes pour csv ; 0 = toutes)')
    ap.add_argument('--top', type=int, default=20, help='titres gardés par groupe et par profil')
    ap.add_argument('--signals', nargs='+', default=list(DEFAULT_SIGNALS), help='stratégies à tester en plus des profils de l\'application (voir SIGNALS) ; liste COURTE, fixée à l\'avance')
    ap.add_argument('--no-presets', action='store_true', help='ne pas rejouer les quatre profils de l\'application (plus rapide, moins de variantes comptées)')
    ap.add_argument('--cost-bps', type=float, default=10.0, help='coût par achat ou vente, en points de base')
    ap.add_argument('--min-share', type=float, default=None, help="part minimale du plus grand nombre de titres ayant une clôture pour qu'une date soit retenue (défaut : 0,5 base ; 0,1 csv)")
    ap.add_argument('--min-titles', type=int, default=None, help='nombre minimal de titres ayant une clôture à une date (défaut : 0 base ; 150 csv)')
    ap.add_argument('--min-pool', type=int, default=None, help="univers minimal d'un groupe à une date pour la comparer (défaut : 0 base ; 100 csv) : en dessous, « les 20 premiers » n'est pas une sélection")
    ap.add_argument('--split-date', help='AAAA-MM-JJ : sépare « calibration » (avant) et « validation » (à partir de cette date)')
    ap.add_argument('--sample', type=int, default=0, help="sous-échantillon aléatoire de l'univers (0 = tout)")
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--draws', type=int, default=500, help='tirages au hasard pour la p-valeur')
    ap.add_argument('--json', help='écrit aussi les résultats (avec le détail par date) dans ce fichier')
    args = ap.parse_args(argv)
    if args.split_date:
        datetime.date.fromisoformat(args.split_date)
    how_many = args.dates if args.dates is not None else (10 if args.source == 'db' else 0)
    long_history = args.source == 'csv'
    min_share = args.min_share if args.min_share is not None else (0.1 if long_history else 0.5)
    min_titles = args.min_titles if args.min_titles is not None else (150 if long_history else 0)
    min_pool = args.min_pool if args.min_pool is not None else (100 if long_history else 0)
    conn = None
    try:
        if args.source == 'csv':
            if not args.csv_dir:
                ap.error('--csv-dir est obligatoire avec --source csv')
            directory = os.path.expanduser(args.csv_dir)
            universe = csv_universe(directory)
            calendar = csv_calendar(directory, universe, min_share, min_titles)
            batches = lambda: csv_batches(directory, universe, args.sample, args.seed)          # noqa: E731
        else:
            from engine.shared.db import connect
            conn = connect()
            with conn.cursor() as cur:
                cur.execute('SET SESSION TRANSACTION READ ONLY')
            calendar = reference_calendar_db(conn)
            batches = lambda: load_batches(conn, len(calendar) + 5, args.sample, args.seed)     # noqa: E731
        dates = pick_dates(calendar, args.horizon, args.step, how_many)
        if len(dates) < 3:
            print('Historique insuffisant pour un test chronologique (moins de 3 dates).', file=sys.stderr)
            return 3
        presets = () if args.no_presets else strategy.PRESETS
        study, titles, t0 = Study(presets, args.horizon, dates, args.signals), 0, time.monotonic()
        for lot in batches():
            study.add(prepare(c) for c in lot)
            titles += len(lot)
            print(f'{titles} titres · {time.monotonic() - t0:.0f} s', file=sys.stderr)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    results = []
    if args.split_date:
        for label, part in split_periods(dates, args.split_date):
            if len(part) < 3:
                print(f'Période « {label} » : moins de 3 dates, ignorée.', file=sys.stderr)
                continue
            results += study.results(args.top, args.cost_bps, args.step, args.draws, args.seed, only_dates=part, period=f'{label} ({part[0]} → {part[-1]}, {len(part)} dates)', min_pool=min_pool)
    else:
        results = study.results(args.top, args.cost_bps, args.step, args.draws, args.seed, min_pool=min_pool)
    meta = {'titles': titles, 'dates': dates, 'top': args.top, 'cost_bps': args.cost_bps, 'horizons': args.horizon, 'split_date': args.split_date, 'source': args.source, 'caveats': CAVEATS,
            'variants': len(study.configs) + len(study.signal_names), 'signals': {n: signal_labels()[n] for n in study.signal_names}}
    print(render(results, meta))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'meta': meta, 'results': results}, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
