"""Les pires périodes du Momentum 6-1 : pertes maximales, successions de pertes, concentration des sélections, comportement pendant les crises, comparaison à l'univers éligible.

LECTURE SEULE : aucune écriture en base, aucun appel réseau, aucune modification de l'application. Rapport en français, écrit pour être LU par quelqu'un qui n'est pas spécialiste :
il décrit ce qui s'est passé dans l'historique, sans prévision et sans affirmer qu'une stratégie est supérieure.

PROTOCOLE FIXÉ AVANT TOUT RÉSULTAT :
  - Sélection : les 20 premiers titres au Momentum 6-1 (variation du cours entre J−126 et J−21 séances), parmi les titres ÉLIGIBLES à la date selon les règles de liquidité de
    scripts/backtest_liquidity.py (médiane de cours × volume sur les 63 séances précédentes, couverture ≥ 80 %, sans split non ajusté dans la fenêtre).
  - Scénarios : « aucun » (aucun filtre, référence), « usd_1M » (titres en dollars échangeant au moins 1 M$/jour), « relatif_50% » (moitié la plus liquide de chaque devise).
  - Une période = 21 séances (environ un mois) : portefeuille de 20 titres à poids égaux, renouvelé en totalité à chaque date. Comparé au rendement moyen (poids égaux) de TOUS les titres
    éligibles à la même date. Coûts : aucun (« brut ») puis 30 points de base par achat ou vente (aller-retour 0,6 % par période).
  - Crises : fenêtres de dates fixées ci-dessous, avant de regarder les données.

DEUX MODES :
  --json-in FICHIER  relit le fichier produit par backtest_liquidity.py --json (instantané). Donne tout SAUF la concentration, car ce fichier ne contient pas les titres choisis.
  --csv-dir DOSSIER  recalcule depuis l'historique exporté par scripts/export_history.py (environ une heure) et ajoute la concentration (secteur si l'univers en contient, pays, devise,
                     renouvellement des titres, part des trois plus gros contributeurs). Pour le secteur : python scripts/export_history.py --out DOSSIER --update-universe.

Usage : python3 scripts/analyze_momentum_risk.py --json-in result-liquidity.json [--from 1993-01-01] [--out rapport.md]
"""
import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCENARIOS = ('aucun', 'usd_1M', 'relatif_50%')
COSTS_BPS = (0, 30)
HORIZON = 21
GAP_DAYS = 40                    # au-delà, deux dates consécutives ne sont plus « le mois suivant » (dates écartées faute d'un univers éligible assez grand)
CRISES = (
    ('Crise asiatique et LTCM', '1997-07-01', '1998-10-31'),
    ('Éclatement de la bulle internet', '2000-03-01', '2002-10-31'),
    ('Crise financière', '2007-10-01', '2009-02-28'),
    ('Rebond de 2009 (« krach du momentum »)', '2009-03-01', '2009-12-31'),
    ('Covid : krach puis rebond', '2020-02-01', '2020-12-31'),
    ('Inflation et hausse des taux', '2022-01-01', '2022-12-31'),
)


# ───────── mesures (fonctions pures) ─────────
def net_returns(rows, cost_bps):
    """Rendement de chaque période après coûts : aller-retour = 2 × coût par sens, renouvellement complet."""
    return [r['pick'] - 2 * cost_bps / 100.0 for r in rows]


def compound(returns):
    value = 1.0
    for r in returns:
        value *= 1 + r / 100.0
    return 100 * (value - 1)


def segments(rows):
    """Découpe en suites de mois consécutifs : un trou de plus de 40 jours coupe la suite (successions de pertes jamais comptées à travers un trou)."""
    out, current = [], []
    for r in rows:
        if current and (date.fromisoformat(r['date']) - date.fromisoformat(current[-1]['date'])).days > GAP_DAYS:
            out.append(current)
            current = []
        current.append(r)
    if current:
        out.append(current)
    return out


def drawdown_episodes(dates, returns):
    """Épisodes de baisse depuis un sommet : [{'peak', 'trough', 'recovery' (ou None), 'depth' (%, négatif), 'months_down', 'months_to_recover'}], du plus profond au moins profond.
    Le sommet de départ est la valeur initiale (date 'début'). Une baisse se mesure sur des clôtures MENSUELLES : un creux survenu en cours de mois n'apparaît pas."""
    wealth, peak, peak_date, peak_i = 1.0, 1.0, 'début', -1
    episodes, current = [], None
    for i, (d, r) in enumerate(zip(dates, returns)):
        wealth *= 1 + r / 100.0
        if wealth >= peak:
            if current:
                current['recovery'], current['months_to_recover'] = d, i - peak_i
                episodes.append(current)
                current = None
            peak, peak_date, peak_i = wealth, d, i
        elif current is None:
            current = {'peak': peak_date, 'trough': d, 'depth': 100 * (wealth / peak - 1), 'months_down': i - peak_i, 'recovery': None, 'months_to_recover': None, '_w': wealth}
        elif wealth < current['_w']:
            current.update(trough=d, depth=100 * (wealth / peak - 1), months_down=i - peak_i, _w=wealth)
    if current:
        episodes.append(current)
    for e in episodes:
        e.pop('_w', None)
    return sorted(episodes, key=lambda e: e['depth'])


def loss_streaks(rows_by_segment, values_of):
    """Longueurs des suites de périodes consécutives où `values_of(r)` < 0 : {'counts': {1: n, 2: n, 3: n, '4+': n}, 'longest': {...}}."""
    counts, longest = Counter(), {'length': 0}
    for seg in rows_by_segment:
        run = []
        for r in seg + [None]:
            if r is not None and values_of(r) < 0:
                run.append(r)
                continue
            if run:
                counts['4+' if len(run) >= 4 else len(run)] += 1
                if len(run) > longest['length']:
                    longest = {'length': len(run), 'start': run[0]['date'], 'end': run[-1]['date'], 'cumulative': compound([values_of(x) for x in run])}
            run = []
    return {'counts': {k: counts.get(k, 0) for k in (1, 2, 3, '4+')}, 'longest': longest}


def worst_periods(rows, key, n=8):
    return sorted(rows, key=key)[:n]


def crisis_table(rows, windows=CRISES, cost_bps=0):
    out = []
    for name, start, end in windows:
        inside = [r for r in rows if start <= r['date'] <= end]
        if not inside:
            out.append({'name': name, 'start': start, 'end': end, 'months': 0})
            continue
        picks, uni = net_returns(inside, cost_bps), [r['universe'] for r in inside]
        out.append({'name': name, 'start': start, 'end': end, 'months': len(inside), 'pick_total': compound(picks), 'universe_total': compound(uni),
                    'mean_excess': statistics.fmean(p - u for p, u in zip(picks, uni)), 'worst_month': min(picks), 'universe_worst_month': min(uni),
                    'share_negative_excess': 100 * sum(1 for p, u in zip(picks, uni) if p < u) / len(inside)})
    return out


def overview(rows, cost_bps):
    picks, uni = net_returns(rows, cost_bps), [r['universe'] for r in rows]
    excess = [p - u for p, u in zip(picks, uni)]
    ordered = sorted(excess)

    def q(x):
        return ordered[min(len(ordered) - 1, int(x * len(ordered)))]
    dd_p = drawdown_episodes([r['date'] for r in rows], picks)
    dd_u = drawdown_episodes([r['date'] for r in rows], uni)
    return {'months': len(rows), 'mean': statistics.fmean(picks), 'universe_mean': statistics.fmean(uni), 'median': statistics.median(picks), 'universe_median': statistics.median(uni),
            'spread': statistics.pstdev(picks), 'universe_spread': statistics.pstdev(uni), 'worst': min(picks), 'universe_worst': min(uni), 'best': max(picks),
            'negative_share': 100 * sum(1 for p in picks if p < 0) / len(picks), 'universe_negative_share': 100 * sum(1 for u in uni if u < 0) / len(uni),
            'max_drawdown': dd_p[0]['depth'] if dd_p else 0.0, 'universe_max_drawdown': dd_u[0]['depth'] if dd_u else 0.0,
            'excess_p5': q(0.05), 'excess_p25': q(0.25), 'excess_p50': q(0.50), 'excess_p75': q(0.75), 'excess_p95': q(0.95), 'excess_mean': statistics.fmean(excess),
            'share_negative_excess': 100 * sum(1 for e in excess if e < 0) / len(excess), 'total': compound(picks), 'universe_total': compound(uni)}


def concentration(rows, meta, fields=('category', 'country', 'currency')):
    """Concentration des sélections. rows[i]['returns'] = {clé: rendement} des titres choisis ; meta[clé] = {'category', 'country', 'currency', 'symbol'}."""
    out = {'fields': {}}
    for field in fields:
        shares, hhi, distinct, known = [], [], [], 0
        for r in rows:
            values = [(meta.get(k) or {}).get(field) or None for k in r['returns']]
            labelled = [v for v in values if v]
            if len(labelled) < 0.8 * len(values):
                continue
            known += 1
            counts = Counter(labelled)
            total = sum(counts.values())
            shares.append(max(counts.values()) / total)
            hhi.append(sum((c / total) ** 2 for c in counts.values()))
            distinct.append(len(counts))
        if known:
            out['fields'][field] = {'months': known, 'top_share_mean': 100 * statistics.fmean(shares), 'top_share_max': 100 * max(shares), 'hhi_mean': statistics.fmean(hhi),
                                    'distinct_mean': statistics.fmean(distinct), 'months_half_in_one': sum(1 for s in shares if s >= 0.5)}
    repeats = [len(set(b['returns']) & set(a['returns'])) / len(b['returns']) for a, b in zip(rows, rows[1:])
               if b['returns'] and (date.fromisoformat(b['date']) - date.fromisoformat(a['date'])).days <= GAP_DAYS]
    out['repeat_share'] = 100 * statistics.fmean(repeats) if repeats else None
    tops = []
    for r in rows:
        contributions = sorted((abs(v) / len(r['returns']) for v in r['returns'].values()), reverse=True)
        if sum(contributions):
            tops.append(sum(contributions[:3]) / sum(contributions))
    out['top3_contribution_mean'] = 100 * statistics.fmean(tops) if tops else None
    return out


def worst_month_detail(row, meta, n=3):
    """Les `n` titres qui ont le plus pesé sur un mois donné (contribution = rendement ÷ nombre de titres)."""
    worst = sorted(row['returns'].items(), key=lambda kv: kv[1])[:n]
    return [((meta.get(k) or {}).get('symbol') or str(k), v) for k, v in worst]


# ───────── lecture des deux sources ─────────
def rows_from_json(data, scenario, start=None, horizon=HORIZON):
    """Reconstitue les périodes (date, rendement du portefeuille, rendement de l'univers éligible) depuis le JSON de backtest_liquidity.py."""
    by_date = {}
    for r in data['results']:
        if r['scenario'] == scenario and r['horizon'] == horizon:
            for d in r.get('by_date') or []:
                if start is None or d['date'] >= start:
                    by_date[d['date']] = {'date': d['date'], 'pick': d['pick'], 'universe': d['universe'], 'picks_count': d['picks']}
    return [by_date[d] for d in sorted(by_date)]


def rows_from_study(study, rule, dates, min_pool):
    rows = []
    for t in dates:
        eligible = study.eligible(t, rule)
        uni = {k: r[HORIZON] for k, r in study.fwd.get(t, {}).items() if k in eligible and HORIZON in r}
        got = {k: uni[k] for k in study.picks(t, rule) if k in uni}
        if not got or len(uni) < max(2 * len(got), min_pool):
            continue
        rows.append({'date': t, 'pick': statistics.fmean(got.values()), 'universe': statistics.fmean(uni.values()), 'picks_count': len(got), 'returns': got, 'pool': len(uni)})
    return rows


# ───────── rapport ─────────
def pct(x, digits=1, signed=False):
    return '—' if x is None else f"{x:{'+' if signed else ''}.{digits}f} %".replace('.', ',')


def table(head, lines):
    return ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|'] + ['| ' + ' | '.join(str(c) for c in line) + ' |' for line in lines]


def render(results, meta):
    L = [f"# Momentum 6-1 : les pires périodes de l'historique", '',
         f"*Source : {meta['source']} · {meta['span']} · portefeuille de {meta['top']} titres à poids égaux, renouvelé toutes les 21 séances (environ un mois). "
         "Ce rapport décrit le passé. Il ne prévoit rien et ne démontre la supériorité d'aucune stratégie.*", '',
         '## Comment lire ce rapport', '',
         "- **Le portefeuille** : chaque mois, on achète les 20 titres dont le cours a le plus progressé entre il y a 6 mois et il y a 1 mois (le dernier mois est ignoré), parmi les titres assez négociables à cette date.",
         "- **L'univers éligible** : la moyenne de TOUS les titres qui étaient négociables ce mois-là. C'est le point de comparaison : on regarde si le portefeuille a fait mieux ou moins bien que l'ensemble dont il est tiré.",
         "- **Une perte maximale** est la plus forte baisse entre un sommet et le creux suivant. Elle répond à la question : « si j'avais commencé au pire moment, qu'est-ce que j'aurais vu ? ».",
         "- **Brut** = sans frais ; **net 30 pb** = après 0,3 % de frais à l'achat et à la vente (0,6 % par mois, car le portefeuille est entièrement renouvelé). Plus un titre est peu négociable, plus ses frais réels sont élevés.", '']
    for name, per_cost in results.items():
        L += [f'## Scénario « {name} »', '']
        for cost, block in per_cost.items():
            tag = 'brut (sans frais)' if cost == 0 else f'net de {cost} points de base par achat ou vente'
            o = block['overview']
            L += [f'### {tag}', '', '**Vue d\'ensemble** (rendement d\'un mois)', '']
            L += table(['', 'Portefeuille', 'Univers éligible'], [
                ['Mois observés', o['months'], o['months']], ['Rendement moyen par mois', pct(o['mean'], 2, True), pct(o['universe_mean'], 2, True)],
                ['Rendement médian par mois', pct(o['median'], 2, True), pct(o['universe_median'], 2, True)], ['Dispersion des rendements mensuels', pct(o['spread'], 2), pct(o['universe_spread'], 2)],
                ['Pire mois', pct(o['worst'], 1, True), pct(o['universe_worst'], 1, True)], ['Mois négatifs', pct(o['negative_share'], 0), pct(o['universe_negative_share'], 0)],
                ['Perte maximale (sommet → creux, sur clôtures mensuelles)', pct(o['max_drawdown'], 1, True), pct(o['universe_max_drawdown'], 1, True)],
                ['Cumul sur toute la période', pct(o['total'], 0, True), pct(o['universe_total'], 0, True)]])
            L += ['', f"*Écart mensuel portefeuille − univers : médiane {pct(o['excess_p50'], 2, True)} · 5 % des mois sont pires que {pct(o['excess_p5'], 1, True)} · 5 % sont meilleurs que {pct(o['excess_p95'], 1, True)} · "
                      f"le portefeuille a fait moins bien que l'univers {pct(o['share_negative_excess'], 0)} des mois.*", '']
            L += ['**Les plus fortes baisses depuis un sommet** (le portefeuille)', '']
            L += table(['Sommet', 'Creux', 'Perte', 'Mois de baisse', 'Retour au sommet'], [
                [e['peak'], e['trough'], pct(e['depth'], 1, True), e['months_down'], (f"{e['recovery']} ({e['months_to_recover']} mois)" if e['recovery'] else 'pas encore retrouvé')] for e in block['drawdowns'][:3]] or [['—'] * 5])
            L += ['', '**Les pires mois**', '']
            L += table(['Date', 'Portefeuille', 'Univers éligible', 'Écart'] + (['Titres qui ont le plus pesé'] if block.get('worst_detail') else []), [
                [r['date'], pct(r['pick'], 1, True), pct(r['universe'], 1, True), pct(r['pick'] - r['universe'], 1, True)] + ([', '.join(f'{s} {pct(v, 0, True)}' for s, v in r['detail'])] if block.get('worst_detail') else [])
                for r in block['worst']])
            s = block['streaks']
            L += ['', '**Successions de mois perdants**', '',
                  f"Mois perdants isolés : {s['loss']['counts'][1]} · deux de suite : {s['loss']['counts'][2]} · trois de suite : {s['loss']['counts'][3]} · quatre ou plus : {s['loss']['counts']['4+']}.",
                  (f"La plus longue série : {s['loss']['longest']['length']} mois ({s['loss']['longest']['start']} → {s['loss']['longest']['end']}), cumul {pct(s['loss']['longest']['cumulative'], 1, True)}." if s['loss']['longest']['length'] else 'Aucune série de mois perdants.'),
                  f"Mois où le portefeuille a fait moins bien que l'univers, de suite : isolés {s['lag']['counts'][1]} · deux {s['lag']['counts'][2]} · trois {s['lag']['counts'][3]} · quatre ou plus {s['lag']['counts']['4+']} ; "
                  f"la plus longue : {s['lag']['longest']['length']} mois" + (f" ({s['lag']['longest']['start']} → {s['lag']['longest']['end']})." if s['lag']['longest']['length'] else '.'), '']
            L += ['**Comportement pendant les crises**', '']
            L += table(['Épisode', 'Mois', 'Portefeuille (cumul)', 'Univers (cumul)', 'Écart moyen par mois', 'Pire mois', 'Mois sous l\'univers'], [
                [c['name'] + f" ({c['start']} → {c['end']})", c['months'], pct(c.get('pick_total'), 0, True), pct(c.get('universe_total'), 0, True), pct(c.get('mean_excess'), 1, True),
                 pct(c.get('worst_month'), 0, True), pct(c.get('share_negative_excess'), 0)] if c['months'] else [c['name'] + f" ({c['start']} → {c['end']})", 0, '—', '—', '—', '—', '—'] for c in block['crises']])
            L += ['']
            if block.get('concentration'):
                c = block['concentration']
                L += ['**Concentration des sélections**', '']
                for field, label in (('category', 'secteur'), ('country', 'pays'), ('currency', 'devise')):
                    f = c['fields'].get(field)
                    if f:
                        L.append(f"- Par {label} : le plus représenté pèse en moyenne {pct(f['top_share_mean'], 0)} des 20 titres (maximum {pct(f['top_share_max'], 0)}) ; {f['distinct_mean']:.1f} {label}s différents en moyenne ; "
                                 f"{f['months_half_in_one']} mois sur {f['months']} où la moitié des titres venait d'un même {label}.")
                L += [f"- Renouvellement : {pct(c['repeat_share'], 0)} des titres sont déjà dans la sélection du mois précédent.",
                      f"- Les trois titres qui contribuent le plus (en gain ou en perte) pèsent en moyenne {pct(c['top3_contribution_mean'], 0)} du mouvement total du mois (20 titres égaux : 15 % si tous contribuaient pareil).", '']
    L += ['## Ce que ces chiffres ne disent pas', '',
          "- **Rien sur l'avenir** : un historique, même long, ne dit pas ce qui se passera. Un portefeuille peut subir des pertes plus fortes ou plus longues que celles observées.",
          "- **Aucune supériorité démontrée** : comparer à l'univers éligible montre un écart dans cet échantillon, pas une règle. Les périodes ont déjà été consultées plusieurs fois pour d'autres tests.",
          "- **Les titres disparus manquent** : l'univers est celui des titres encore cotés en 2026. Cela rend probablement les résultats plus favorables que ce qu'un investisseur aurait réellement obtenu.",
          "- **Pertes « de clôture à clôture »** : on ne voit que les fins de mois ; en cours de mois, les creux ont pu être plus profonds.",
          "- **Frais, impôts, écarts d'achat-vente, titres difficiles à revendre en période de crise** ne sont représentés que par un coût forfaitaire.",
          "- **Les périodes de crise sont peu nombreuses** : quelques mois par épisode. Une moyenne sur si peu de mois est très sensible au hasard.", '']
    return '\n'.join(L)


def analyse(rows, with_detail=False, meta_titles=None):
    out = {}
    for cost in COSTS_BPS:
        picks = net_returns(rows, cost)
        dates = [r['date'] for r in rows]
        segs = segments(rows)
        block = {'overview': overview(rows, cost), 'drawdowns': drawdown_episodes(dates, picks),
                 'streaks': {'loss': loss_streaks([[dict(r, v=net_returns([r], cost)[0]) for r in seg] for seg in segs], lambda r: r['v']),
                             'lag': loss_streaks([[dict(r, v=net_returns([r], cost)[0] - r['universe']) for r in seg] for seg in segs], lambda r: r['v'])},
                 'crises': crisis_table(rows, cost_bps=cost)}
        ranked = sorted(zip(rows, picks), key=lambda x: x[1])[:8]
        block['worst'] = [dict(r, pick=p) for r, p in ranked]
        if with_detail and meta_titles is not None:
            for r in block['worst']:
                r['detail'] = worst_month_detail(r, meta_titles)
            block['worst_detail'] = True
        if with_detail and meta_titles is not None:
            block['concentration'] = concentration(rows, meta_titles)
        out[cost] = block
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json-in', help='résultat de backtest_liquidity.py --json (mode rapide, sans concentration)')
    ap.add_argument('--csv-dir', help="historique exporté par scripts/export_history.py (mode complet)")
    ap.add_argument('--from', dest='start', default='1993-01-01')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--min-pool', type=int, default=100)
    ap.add_argument('--min-titles', type=int, default=150)
    ap.add_argument('--out', help='écrit le rapport dans ce fichier (Markdown)')
    ap.add_argument('--json-out', help='écrit aussi les chiffres détaillés (JSON)')
    args = ap.parse_args(argv)
    if bool(args.json_in) == bool(args.csv_dir):
        ap.error('choisir exactement un mode : --json-in ou --csv-dir')
    scenario_rows, titles = {}, None
    if args.json_in:
        with open(args.json_in, encoding='utf-8') as fh:
            data = json.load(fh)
        for name in SCENARIOS:
            scenario_rows[name] = rows_from_json(data, name, args.start)
        source = f'fichier {os.path.basename(args.json_in)} (périodes déjà calculées par le test de liquidité ; 2016 absent de ce fichier)'
    else:
        sys.path.insert(0, ROOT)
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import backtest_liquidity as bl
        import backtest_walkforward as bw
        directory = os.path.expanduser(args.csv_dir)
        universe = [u for u in bw.csv_universe(directory) if u.get('kind') != 'etf']
        calendar = bw.csv_calendar(directory, universe, 0.1, args.min_titles)
        dates = [d for d in bw.pick_dates(calendar, (HORIZON,), 21, 0) if d >= args.start]
        study = bl.LiquidityStudy(calendar, dates, horizons=(HORIZON,))
        done, t0 = 0, time.monotonic()
        for lot in bw.csv_batches(directory, universe, args.sample, 1):
            study.add(lot)
            done += len(lot)
            print(f'{done} actions · {time.monotonic() - t0:.0f} s', file=sys.stderr)
        rules = dict(bl.SCENARIOS)
        for name in SCENARIOS:
            scenario_rows[name] = rows_from_study(study, rules[name], dates, args.min_pool)
        titles = {u['key']: {'symbol': u['symbol'], 'category': u.get('category') or None, 'country': u.get('country') or None, 'currency': u.get('currency') or None} for u in universe}
        source = f'historique exporté ({done} actions, recalcul complet)'
    results = {}
    for name, rows in scenario_rows.items():
        if len(rows) < 12:
            print(f'Scénario « {name} » : moins de 12 mois, ignoré.', file=sys.stderr)
            continue
        results[name] = analyse(rows, with_detail=titles is not None, meta_titles=titles)
    if not results:
        print('Aucun scénario exploitable.', file=sys.stderr)
        return 3
    first = min(r[0]['date'] for r in scenario_rows.values() if r)
    last = max(r[-1]['date'] for r in scenario_rows.values() if r)
    report = render(results, {'source': source, 'span': f'{first} → {last}', 'top': 20})
    print(report)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(report + '\n')
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump({'scenarios': {n: {str(c): b for c, b in blocks.items()} for n, blocks in results.items()}}, fh, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == '__main__':
    sys.exit(main())
