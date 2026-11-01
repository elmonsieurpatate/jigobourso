"""Audit LECTURE SEULE du moteur de production : l'Explorer examine-t-il bien tout l'univers, dans le bon ordre, et que perd-on à chaque étage ?

Aucune écriture : la session SQL est en LECTURE SEULE (toute tentative d'écriture échouerait bruyamment) et le cache de résultats n'est pas utilisé (les verdicts sont recalculés par
`judge_universe`, la fonction même du site). Aucune modification de classement, de filtre, de paramètre ou d'interface. Usage (depuis la racine du site, variables JIGO_DB_* chargées) :
  PYTHONPATH=$PWD .venv/bin/python scripts/audit_production.py
Sorties : (1) entonnoir du catalogue (statuts, motifs d'exclusion) ; (2) pour chacun des six profils, statuts des actions (retenu / écarté / non évaluable), motifs de non-évaluabilité,
critères qui écartent le plus ; (3) négociabilité des titres retenus (pastilles du site) ; (4) cohérence de l'Explorer : tout l'univers examiné, rang contigu, retenus avant écartés,
pagination sans trou ni doublon, tailles de page différentes -> mêmes lignes ; (5) titres dont le momentum est absent à cause d'une rupture de cours.
"""
import argparse
import collections
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.shared.db import connect            # noqa: E402
from engine.analytics import service, signals, strategy   # noqa: E402
from engine.market.collect import latest_rates   # noqa: E402
from engine.shared import settings as settings_mod   # noqa: E402

PRESETS = strategy.PRESETS


def sql(conn, query, args=()):
    with conn.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def pct(a, b):
    return f'{100 * a / b:.1f} %' if b else '–'


def reason_key(r):
    return f"{r['period'] or 'général'}·{r['criterion']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pages', type=int, default=12, help='nombre de pages parcourues pour le test de pagination')
    args = ap.parse_args()
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('SET SESSION TRANSACTION READ ONLY')
    out = []
    w = out.append
    w('# Audit du moteur de production (lecture seule)\n')
    # 1. entonnoir du catalogue
    w('## 1. Entonnoir : du catalogue à l\'univers examiné\n')
    rows = sql(conn, "SELECT i.kind, l.status, l.is_primary, COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id GROUP BY i.kind, l.status, l.is_primary ORDER BY i.kind, l.status, l.is_primary")
    w('| Type | Statut | Cotation principale | Cotations |')
    w('|---|---|---|---|')
    for r in rows:
        w(f"| {r['kind']} | {r['status']} | {r['is_primary']} | {r['n']} |")
    reasons = sql(conn, "SELECT l.excluded_reason r, COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity' AND l.status='excluded' GROUP BY l.excluded_reason ORDER BY n DESC LIMIT 15")
    w('\nMotifs d\'exclusion des actions (15 premiers) : ' + '; '.join(f"{r['r']} ({r['n']})" for r in reasons) + '.')
    n_equity = sql(conn, "SELECT COUNT(*) n FROM v_recommendable r JOIN listings l ON l.id=r.listing_id JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity'")[0]['n']
    w(f'\nUnivers examiné (vue `v_recommendable` : status = selected ET cotation principale) : {n_equity} actions. Aucune présélection de type « Top N » n\'existe dans `judge_universe` : chaque titre de cette vue est évalué.')
    cand = sql(conn, "SELECT COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE i.kind='equity' AND l.status='candidate'")[0]['n']
    w(f'Actions « candidate » (en attente de cotation Yahoo, jamais examinées) : {cand}.')
    # 2. verdicts par profil
    w('\n## 2. Verdicts des six profils (actions de l\'univers, calcul direct, sans cache)\n')
    verdicts_by = {}
    w('| Profil | Retenus | Écartés | Non évaluables | Part retenue | Non évaluables : motifs |')
    w('|---|---|---|---|---|---|')
    crit = {}
    for name in PRESETS:
        cfg = strategy.validate(strategy.preset(name))
        t0 = time.monotonic()
        vs = [v for v in service.judge_universe(conn, cfg) if v['group'] == 'equity']
        verdicts_by[name] = vs
        c = collections.Counter(v['status'] for v in vs)
        why = collections.Counter()
        fails = collections.Counter()
        sole = collections.Counter()
        for v in vs:
            if v['status'] == 'unknown':
                for r in v['reasons']:
                    if r['result'] == 'missing':
                        why[f"{r['period'] or 'général'}:{r['metric']}"] += 1
                        break
            if v['status'] == 'rejected':
                f = [reason_key(r) for r in v['reasons'] if r['result'] == 'fail']
                for k in set(f):
                    fails[k] += 1
                if len(set(f)) == 1:
                    sole[f[0]] += 1
        crit[name] = (fails, sole)
        w(f"| {name} | {c['retained']} | {c['rejected']} | {c['unknown']} | {pct(c['retained'], len(vs))} | " + ', '.join(f'{k} {n}' for k, n in why.most_common(5)) + ' |')
        print(f'{name} évalué en {time.monotonic() - t0:.0f} s', file=sys.stderr)
    w('\nCritères qui écartent le plus de titres (titres écartés qui échouent au critère ; « seul » = c\'est le seul critère en échec) :\n')
    for name in ('regular', 'fast', 'recovery', 'low_volatility'):
        fails, sole = crit[name]
        w(f"- **{name}** : " + '; '.join(f'{k} {n} (seul : {sole[k]})' for k, n in fails.most_common(8)))
    # 3. négociabilité
    w('\n## 3. Négociabilité des titres retenus (pastilles du site)\n')
    rates = latest_rates(conn)
    prefilter_cfg = settings_mod.prefilter_rules(conn)
    aux = service._aux(conn, 126, rates)
    w(f"Seuils : prix ≥ {prefilter_cfg['price'].get('min_eur')} €, liquidité actions ≥ {prefilter_cfg['liquidity_equity'].get('min_eur'):,.0f} €/jour (moyenne 3 mois × cours, EUR, données du JOUR), volume inconnu exclu du catalogue : {prefilter_cfg['unknown_volume']['enabled']}. "
      f"Le filtre du site masque « limitée » = sous {signals.FLOOR_FACTOR:g} × le minimum ; « facilement négociable » à partir de {signals.LIQ_FACTOR:g} × le minimum ; donnée absente ou plus ancienne que {signals.STALE_QUOTE_DAYS} jours = « non déterminée », jamais masquée.\n")
    w('| Profil | Retenus | Facilement négociables | À surveiller | Limitées (masquées par défaut) | Non déterminées (affichées) |')
    w('|---|---|---|---|---|---|')
    for name in PRESETS:
        retained = [v for v in verdicts_by[name] if v['status'] == 'retained']
        lv = collections.Counter()
        for v in retained:
            a = aux.get(v['key'], {})
            lv[signals.liquidity(service._daily_eur(a), 'equity', prefilter_cfg, a.get('quote_age_days'))['level']] += 1
        w(f"| {name} | {len(retained)} | {lv['ok']} | {lv['warn']} | {lv['bad']} | {lv['unknown']} |")
    # 4. cohérence de l'Explorer
    w('\n## 4. Cohérence de l\'Explorer (fonction `explore` du site, sans cache)\n')
    real = service.cached_verdicts
    def no_cache(conn_, config):
        out_ = []
        for v in service.judge_universe(conn_, config):
            out_.append(dict(zip(service.ENTRY_FIELDS, [v['key'], v['symbol'], v['row']['name'], v['row']['isin'], v['row']['kind'], v['row']['mic'], v['row']['country'], v['status'], v['group'], v['rank'],
                                                          None if v['score'] is None else round(v['score'], 4), v['row']['category'], service._fails(v)])))
        return out_
    service.cached_verdicts = no_cache
    try:
        for name in PRESETS:
            problems = []
            base = {'config': name, 'view': {'kind': 'equity', 'status': 'retained', 'tradable': True, 'page': 1, 'page_size': 100}}
            first = service.explore(conn, base)
            ids100 = [r['id'] for r in first['rows']]
            ids24 = []
            for p in range(1, 6):
                ids24 += [r['id'] for r in service.explore(conn, {'config': name, 'view': dict(base['view'], page=p, page_size=24)})['rows']]
            if ids24[:len(ids100)] != ids100[:len(ids24)]:
                problems.append('pages de 24 et de 100 lignes différentes')
            seen, dup, last_rank, order_ok, pages = set(), 0, 0, True, 0
            for p in range(1, args.pages + 1):
                res = service.explore(conn, {'config': name, 'view': dict(base['view'], page=p, page_size=24)})
                pages = res['pages']
                for r in res['rows']:
                    if r['id'] in seen:
                        dup += 1
                    seen.add(r['id'])
                    if r['status'] != 'retained':
                        order_ok = False
                    if r['rank'] is not None and r['rank'] < last_rank:
                        order_ok = False
                    last_rank = r['rank'] or last_rank
                if p >= res['pages']:
                    break
            if dup:
                problems.append(f'{dup} doublon(s) entre pages')
            if not order_ok:
                problems.append('ordre de rang non croissant ou titre non retenu parmi les retenus')
            retained_ranks = sorted(v['rank'] for v in verdicts_by[name] if v['status'] == 'retained' and v['rank'] is not None)
            contiguous = retained_ranks == list(range(1, len(retained_ranks) + 1))
            if not contiguous:
                problems.append('rangs des retenus non contigus 1..n')
            w(f"- **{name}** : univers {first['universe']}, examinés {first['examined']}, total de la vue {first['total']} (masqués par la négociabilité : {first['tradable']['masked']}), {pages} page(s) de 24 ; "
              f"rangs contigus : {contiguous} ; " + ('aucun problème de cohérence' if not problems else 'PROBLÈMES : ' + ' ; '.join(problems)))
    finally:
        service.cached_verdicts = real
    # 5. ruptures de cours
    w('\n## 5. Momentum absent à cause d\'une rupture de cours\n')
    w(f"Règle : un saut de cours d'une séance au-delà de ×{1.6:g} ou en deçà de ÷{1.6:g} (soit une baisse de plus de 37,5 %) est une « rupture » ; toute rupture située après le début de la fenêtre (J−126 ou J−252) rend le momentum NON ÉVALUABLE (y compris si elle tombe dans le dernier mois ignoré par la formule).\n")
    brk = sql(conn, "SELECT COUNT(*) n FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity' AND s.quality='break'")[0]['n']
    nomom6 = sql(conn, "SELECT COUNT(*) n FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity' AND s.closes_count >= 127 AND s.momentum_6m IS NULL")[0]['n']
    nomom12 = sql(conn, "SELECT COUNT(*) n FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity' AND s.closes_count >= 253 AND s.momentum_12m IS NULL")[0]['n']
    w(f'Actions de l\'univers : {n_equity} ; qualité « rupture » dans les 252 dernières séances : {brk} ({pct(brk, n_equity)}) ; momentum 6 mois absent alors que l\'historique suffit : {nomom6} ; momentum 12 mois absent : {nomom12}.')
    ex = sql(conn, "SELECT l.symbol, l.mic, s.break_dates FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id WHERE i.kind='equity' AND s.quality='break' ORDER BY l.symbol LIMIT 12")
    w('Exemples : ' + '; '.join(f"{r['symbol']} ({r['mic']}) {str(r['break_dates'])[:40]}" for r in ex) + '.')
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
