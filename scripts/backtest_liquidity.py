"""Momentum 6-1 avec une condition de liquidité HISTORIQUE. LECTURE SEULE : aucune écriture en base, aucun appel réseau, aucune modification des stratégies de l'application.

Question : le résultat du Momentum 6-1 (rendement de il y a 6 mois à il y a 1 mois, les 20 premiers actions) résiste-t-il quand on n'a le droit de choisir que des titres
qui étaient NÉGOCIABLES à la date de la sélection ?

RÈGLES DE CE TEST (fixées dans le code AVANT de regarder le moindre résultat ; un test garde ces constantes) :
  - La liquidité d'un titre à la date t est la MÉDIANE de (cours de clôture × volume) sur les 63 séances du calendrier de référence qui PRÉCÈDENT t (t exclu), calculée avec les seules
    données de ces séances. Aucun volume, aucune capitalisation, aucun filtre ni aucun cours actuel (2026) n'intervient : seules les données historiques du fichier de chaque titre.
  - Données manquantes : le titre doit avoir un cours ET un volume sur au moins 80 % de ces 63 séances, sinon il n'est pas éligible ce jour-là.
  - Splits : un saut du cours brut qui ressemble à un split usuel alors que le cours ajusté reste continu (split non ajusté dans le cours brut) rend le titre non éligible tant qu'il
    est dans la fenêtre : le produit cours × volume y mélangerait deux unités. (Le rendement, lui, vient du cours ajusté des splits et des dividendes.)
  - Devises : le volume est en devise locale. Les seuils ABSOLUS ne s'appliquent qu'aux titres cotés en dollars (aucun taux de change n'est utilisé) ; les seuils RELATIFS se calculent
    à l'intérieur de chaque devise. L'étiquette de devise est celle du fichier d'univers (une caractéristique statique, pas un filtre de négociabilité).
  - Scénarios (tous présentés, favorables ou non) : aucun filtre ; USD ≥ 0,25 M$/jour ; USD ≥ 1 M$/jour ; USD ≥ 5 M$/jour ; moitié la plus liquide de chaque devise ; quart le plus liquide.
  - Univers comparé : les titres ÉLIGIBLES à la date (au moins 100 avec un rendement connu, sinon la date est écartée et comptée). Références : le rendement moyen de cet univers
    éligible, et des tirages au hasard de même taille dans ce même univers (p-valeur sur les dates sans chevauchement).
  - Frais : 10, 30 et 60 points de base par achat ou vente (aller-retour : 0,2 %, 0,6 %, 1,2 %), renouvellement complet à chaque période de détention. Les titres peu liquides coûtent plus cher.
  - Périodes, horizons : 1993-2015 et 2017-2026 ; 21 et 63 séances. Ces périodes ont DÉJÀ été consultées : ce n'est plus une validation totalement vierge.

Usage : python scripts/backtest_liquidity.py --csv-dir ~/tmp-history-long [--sample 0] [--json sortie.json]
"""
import argparse
import bisect
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import backtest_walkforward as bw                                         # noqa: E402
from engine.market.splits import split_ratio                              # noqa: E402

# ───────── protocole figé (voir l'en-tête) ─────────
WINDOW = 63                    # séances de calendrier précédant la date de sélection (date exclue)
MIN_COVERAGE = 0.80            # part minimale de ces séances avec cours ET volume
MIN_POOL = 100                 # titres éligibles avec un rendement connu, au minimum, pour comparer une date
MIN_CURRENCY_POOL = 20         # titres d'une même devise pour appliquer un seuil relatif dans cette devise
TOP = 20
STEP = 21
DRAWS = 1000
SEED = 1
HORIZONS = (21, 63)
COSTS_BPS = (10, 30, 60)
SCENARIOS = (
    ('aucun', None),
    ('usd_0,25M', ('usd', 250_000.0)),
    ('usd_1M', ('usd', 1_000_000.0)),
    ('usd_5M', ('usd', 5_000_000.0)),
    ('relatif_50%', ('rel', 0.50)),
    ('relatif_25%', ('rel', 0.25)),
)
PERIODS = (('1993-2015', None, '2015-12-31'), ('2017-2026', '2017-01-01', None))
SIGNAL = 'mom_6_1'


# ───────── liquidité, à partir des seules données antérieures ─────────
class LiquidityStudy:
    def __init__(self, calendar, dates, horizons=HORIZONS):
        self.calendar = tuple(calendar)
        self.index = {d: i for i, d in enumerate(self.calendar)}
        self.dates, self.horizons = tuple(dates), tuple(horizons)
        self.score = defaultdict(dict)          # date -> {clé: score momentum}
        self.fwd = defaultdict(dict)            # date -> {clé: {h: rendement}}
        self.liq = defaultdict(dict)            # date -> {clé: (valeur échangée médiane | None, statut, devise)}
        self.split_titles = set()               # titres dont le cours brut montre un split non ajusté (diagnostic)
        self.currencies = Counter()             # devises des titres traités

    def _aligned(self, c):
        """Valeur échangée (cours brut × volume) et marques de split non ajusté, alignées sur le calendrier de référence."""
        n = len(self.calendar)
        dv, marks = [None] * n, [0] * n
        volumes, prev = c.get('volumes') or [], None
        for k, (day, close, adj) in enumerate(c['bars']):
            idx = self.index.get(day)
            vol = volumes[k] if k < len(volumes) else None
            if idx is not None and vol and vol > 0 and close > 0:
                dv[idx] = close * vol
            if prev and idx is not None and prev[0] > 0 and prev[1] > 0:
                raw_ratio, adj_ratio = close / prev[0], adj / prev[1]
                if split_ratio(raw_ratio) is not None and 0.85 <= adj_ratio <= 1.18:           # le cours brut saute, le cours ajusté non : split non ajusté dans le brut
                    marks[idx] = 1
            prev = (close, adj)
        prefix = [0]
        for m in marks:
            prefix.append(prefix[-1] + m)
        if prefix[-1]:
            self.split_titles.add(c['key'])
        return dv, prefix

    @staticmethod
    def liquidity(i, dv, prefix):
        """(statut, valeur échangée médiane) à la date d'indice `i` du calendrier, avec les seules séances i-63 … i-1."""
        if i < WINDOW:
            return 'history', None
        values = [x for x in dv[i - WINDOW:i] if x is not None]
        if len(values) < MIN_COVERAGE * WINDOW:
            return 'coverage', None
        if prefix[i] - prefix[i - WINDOW] > 0:
            return 'split', None
        return 'ok', statistics.median(values)

    def add(self, candidates):
        for raw in candidates:
            if raw.get('group') != 'equity':
                continue
            c = bw.prepare(raw)
            dv, prefix = self._aligned(c)
            self.currencies[c.get('currency') or 'inconnue'] += 1
            for t in self.dates:
                n = bisect.bisect_right(c['dates'], t)
                if n < bw.MIN_CLOSES or (bw.datetime.date.fromisoformat(t) - bw.datetime.date.fromisoformat(c['dates'][n - 1])).days > bw.MAX_STALE_DAYS:
                    continue
                status, value = self.liquidity(self.index[t], dv, prefix)
                visible = c['bars'][max(0, n - bw.DECISION_BARS):n]                          # jamais une clôture postérieure à t
                _, closes, _, breaks, *_ = bw.analyze_series(visible, [], c.get('split_dates') or ())
                self.fwd[t][c['key']] = {h: r for h, r in ((h, bw.forward_return(c['full'], t, h)) for h in self.horizons) if r is not None}
                self.liq[t][c['key']] = (value, status, c.get('currency') or None)
                usable = closes[breaks[-1]:] if breaks else closes
                score = bw.SIGNALS[SIGNAL][0](usable)
                if score is not None and math.isfinite(score):
                    self.score[t][c['key']] = score

    # ───────── éligibilité par scénario ─────────
    def eligible(self, t, rule):
        rows = self.liq.get(t, {})
        if rule is None:
            return set(rows)
        ok = {k: v for k, v in rows.items() if v[1] == 'ok'}
        mode, x = rule
        if mode == 'usd':
            return {k for k, v in ok.items() if v[2] == 'USD' and v[0] >= x}
        by_currency = defaultdict(list)
        for k, v in ok.items():
            by_currency[v[2] or 'inconnue'].append((v[0], k))
        out = set()
        for items in by_currency.values():
            if len(items) < MIN_CURRENCY_POOL:
                continue
            values = sorted(v for v, _ in items)
            cut = values[min(len(values) - 1, int((1 - x) * len(values)))]
            out |= {k for v, k in items if v >= cut}
        return out

    def picks(self, t, rule, top=TOP):
        """Les `top` premiers au momentum 6-1 PARMI les titres éligibles à la date t."""
        eligible = self.eligible(t, rule)
        scores = {k: s for k, s in self.score.get(t, {}).items() if k in eligible}
        return [k for k, _ in sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))[:top]]

    # ───────── mesure ─────────
    def results(self, name, rule, dates, h, period, top=TOP, draws=DRAWS, seed=SEED, step=STEP, min_pool=MIN_POOL):
        rng = random.Random(seed)
        rows, eligible_counts, dropped = [], [], 0
        for t in dates:
            eligible = self.eligible(t, rule)
            eligible_counts.append(len(eligible))
            uni = {k: r[h] for k, r in self.fwd.get(t, {}).items() if k in eligible and h in r}
            keys = self.picks(t, rule, top)
            got = [uni[k] for k in keys if k in uni]
            if not got or len(uni) < max(2 * len(got), min_pool):
                dropped += 1
                continue
            pool = list(uni.values())
            rows.append({'date': t, 'k': len(got), 'got': got, 'pool': pool, 'pick': statistics.fmean(got), 'uni': statistics.fmean(pool),
                         'median_gap': statistics.median(got) - statistics.median(pool)})
        out = {'scenario': name, 'period': period, 'horizon': h, 'dates_total': len(dates), 'dates_used': len(rows), 'dates_dropped': dropped,
               'eligible_min': min(eligible_counts) if eligible_counts else 0, 'eligible_median': int(statistics.median(eligible_counts)) if eligible_counts else 0,
               'eligible_max': max(eligible_counts) if eligible_counts else 0}
        if not rows:
            return out
        spacing = max(1, math.ceil(h / step))
        indep = rows[::spacing]
        excess = [r['pick'] - r['uni'] for r in rows]
        nets = {c: [e - 2 * c / 100.0 for e in excess] for c in COSTS_BPS}
        p_random = random_mean = None
        if len(indep) >= 3:
            observed = statistics.fmean(r['pick'] - r['uni'] for r in indep)
            sims = [statistics.fmean(statistics.fmean(rng.sample(r['pool'], r['k'])) - r['uni'] for r in indep) for _ in range(draws)]
            p_random, random_mean = round((1 + sum(1 for s in sims if s >= observed)) / (draws + 1), 3), round(statistics.fmean(sims), 2)
        main_cost = COSTS_BPS[0]
        out.update({
            'independent_dates': len(indep), 'avg_picks': round(statistics.fmean(r['k'] for r in rows), 1),
            'pick_mean': round(statistics.fmean(r['pick'] for r in rows), 2), 'universe_mean': round(statistics.fmean(r['uni'] for r in rows), 2),
            'excess_gross': round(statistics.fmean(excess), 2), 'excess_net': {str(c): round(statistics.fmean(v), 2) for c, v in nets.items()},
            'excess_median': round(statistics.fmean(r['median_gap'] for r in rows), 2),
            't_net': bw._tstat([e - 2 * main_cost / 100.0 for e in (r['pick'] - r['uni'] for r in indep)]),
            'share_positive': round(100 * sum(1 for e in nets[main_cost] if e > 0) / len(rows)),
            'p_random': p_random, 'random_mean_excess': random_mean,
            'spread_ratio': round(statistics.pstdev([x for r in rows for x in r['got']]) / max(1e-9, statistics.pstdev([x for r in rows for x in r['pool']])), 2),
            'by_date': [{'date': r['date'], 'picks': r['k'], 'pick': round(r['pick'], 2), 'universe': round(r['uni'], 2)} for r in rows],
        })
        return out

    def quality(self, dates):
        """Diagnostic de données sur les couples (titre, date) de ces dates : statuts de liquidité et devises."""
        statuses, by_currency = Counter(), Counter()
        for t in dates:
            for value, status, currency in self.liq.get(t, {}).values():
                statuses[status] += 1
                by_currency[currency or 'inconnue'] += 1
        return {'title_dates': sum(statuses.values()), 'status': dict(statuses), 'currencies': dict(by_currency.most_common(6))}


# ───────── présentation ─────────
def render(results, quality, meta):
    lines = [f"Momentum 6-1 et liquidité historique · {meta['titles']} actions · top {meta['top']} · fenêtre de liquidité {WINDOW} séances précédant la date · couverture ≥ {int(MIN_COVERAGE * 100)} %",
             "Protocole fixé avant résultats : voir l'en-tête de scripts/backtest_liquidity.py. Ces périodes ont DÉJÀ été consultées : ce n'est plus une validation totalement vierge.",
             f"Titres avec au moins un split non ajusté détecté dans le cours brut : {meta.get('unadjusted_split_titles', '?')} sur {meta['titles']} · devises des titres : " + ', '.join(f'{k} {v}' for k, v in meta.get('currencies', {}).items()), '']
    head = (f"{'scénario':<13}{'h':>4}{'dates':>8}{'indép.':>7}{'éligibles (min/méd/max)':>25}{'sél.':>6}{'sélection':>10}{'univers':>9}{'excès brut':>11}"
            + ''.join(f"{'net ' + str(c) + 'pb':>11}" for c in COSTS_BPS) + f"{'méd.':>7}{'t net':>7}{'% dates+':>9}{'p hasard':>9}{'hasard':>8}{'disp.':>7}")
    for period in dict.fromkeys(r['period'] for r in results):
        part = [r for r in results if r['period'] == period]
        lines += [f'── {period} ──', head, '-' * len(head)]
        for r in sorted(part, key=lambda r: (r['horizon'], [n for n, _ in SCENARIOS].index(r['scenario']))):
            el = f"{r['eligible_min']}/{r['eligible_median']}/{r['eligible_max']}"
            if 'pick_mean' not in r:
                lines.append(f"{r['scenario']:<13}{r['horizon']:>4}{str(r['dates_used']) + '/' + str(r['dates_total']):>8}{'—':>7}{el:>25}  aucune date comparable (univers éligible trop petit)")
                continue
            t = '—' if r['t_net'] is None else f"{r['t_net']:.2f}"
            p = '—' if r['p_random'] is None else f"{r['p_random']:.3f}"
            rnd = '—' if r['random_mean_excess'] is None else f"{r['random_mean_excess']:+.2f}"
            lines.append(f"{r['scenario']:<13}{r['horizon']:>4}{str(r['dates_used']) + '/' + str(r['dates_total']):>8}{r['independent_dates']:>7}{el:>25}{r['avg_picks']:>6}"
                         f"{r['pick_mean']:>9.2f}%{r['universe_mean']:>8.2f}%{r['excess_gross']:>10.2f}%" + ''.join(f"{r['excess_net'][str(c)]:>10.2f}%" for c in COSTS_BPS)
                         + f"{r['excess_median']:>6.2f}%{t:>7}{r['share_positive']:>8}%{p:>9}{rnd:>8}{r['spread_ratio']:>7.2f}")
        q = quality[period]
        lines += ['', f"Qualité des données · {period} ({q['title_dates']} couples titre-date) : " + ', '.join(f'{k} {v}' for k, v in sorted(q['status'].items())),
                  '  ok = liquidité calculée · coverage = moins de 80 % des séances avec cours et volume · split = split non ajusté dans le cours brut de la fenêtre · history = moins de 63 séances de calendrier avant la date',
                  '  Devises (couples titre-date) : ' + ', '.join(f'{k} {v}' for k, v in q['currencies'].items()), '']
    lines += ['Lecture : « excès » = rendement moyen de la sélection moins celui de l\'UNIVERS ÉLIGIBLE, en points sur l\'horizon h (séances). « hasard » = excès moyen de tirages au hasard de même taille dans cet univers',
              '(proche de 0 : attendu) ; « p hasard » : part des tirages qui font au moins aussi bien, sur les dates sans chevauchement ; « disp. » = dispersion des rendements de la sélection / de l\'univers éligible.',
              '« éligibles » : nombre de titres éligibles par date (min/médiane/max) ; « dates » : dates comparables / dates de la période (une date est écartée si l\'univers éligible a moins de ' + str(meta['min_pool']) + ' titres avec un rendement connu).',
              '', 'Limites : univers des titres encore cotés en 2026 (biais de survie : les titres disparus manquent) ; volumes tels que fournis par Yahoo (leur ajustement des splits n\'est pas garanti) ;',
              'rendements en devise locale, cours ajustés des splits et dividendes ; peu de dates indépendantes ; six scénarios, deux horizons, deux périodes : quelques résultats « significatifs » arrivent par hasard.']
    return '\n'.join(lines)


def parse_period(text):
    name, start, end = (text.split(',') + ['', ''])[:3]
    return name, start or None, end or None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--csv-dir', required=True, help='dossier produit par scripts/export_history.py')
    ap.add_argument('--sample', type=int, default=0, help="sous-échantillon aléatoire de l'univers (0 = tout)")
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--dates', type=int, default=0, help='nombre maximal de dates (les plus récentes) ; 0 = toutes')
    ap.add_argument('--period', action='append', help='NOM,DÉBUT,FIN (dates AAAA-MM-JJ, vides = ouvert) ; par défaut les deux périodes du protocole')
    ap.add_argument('--min-pool', type=int, default=MIN_POOL, help="(essais seulement) univers éligible minimal par date")
    ap.add_argument('--min-titles', type=int, default=150, help='titres minimaux ayant une clôture pour qu\'une date entre au calendrier')
    ap.add_argument('--json', help='écrit aussi les résultats (avec le détail par date) dans ce fichier')
    args = ap.parse_args(argv)
    directory = os.path.expanduser(args.csv_dir)
    periods = [parse_period(p) for p in args.period] if args.period else list(PERIODS)
    universe = [u for u in bw.csv_universe(directory) if u.get('kind') != 'etf']
    calendar = bw.csv_calendar(directory, universe, 0.1, args.min_titles)
    dates = bw.pick_dates(calendar, HORIZONS, STEP, args.dates)
    spans = {name: [d for d in dates if (start is None or d >= start) and (end is None or d <= end)] for name, start, end in periods}
    study = LiquidityStudy(calendar, sorted({d for part in spans.values() for d in part}))
    titles, t0 = 0, time.monotonic()
    for lot in bw.csv_batches(directory, universe, args.sample, args.seed):
        study.add(lot)
        titles += len(lot)
        print(f'{titles} actions · {time.monotonic() - t0:.0f} s', file=sys.stderr)
    results, quality = [], {}
    for name, part in spans.items():
        label = f'{name} ({part[0]} → {part[-1]}, {len(part)} dates)' if part else f'{name} (aucune date)'
        quality[label] = study.quality(part)
        for h in HORIZONS:
            for scenario, rule in SCENARIOS:
                results.append(study.results(scenario, rule, part, h, label, min_pool=args.min_pool))
    meta = {'titles': titles, 'top': TOP, 'window': WINDOW, 'min_coverage': MIN_COVERAGE, 'min_pool': args.min_pool, 'costs_bps': COSTS_BPS,
            'scenarios': [(n, r) for n, r in SCENARIOS], 'unadjusted_split_titles': len(study.split_titles), 'currencies': dict(study.currencies.most_common(8))}
    print(render(results, quality, meta))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'meta': meta, 'results': results, 'quality': quality}, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
