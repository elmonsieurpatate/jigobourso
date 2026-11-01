"""Audit LECTURE SEULE n°2 du moteur de production : ruptures de cours, exemples de critères, rotation réelle, actions sans cotation, profil « Hausse calme ».

Session SQL en LECTURE SEULE, aucun cache, aucun changement de classement, de filtre ou d'interface. Option `--probe N` : interroge Yahoo (lecture seule, sans rien enregistrer) pour N symboles
d'actions sans cotation afin de savoir combien peuvent être récupérées ; 0 par défaut. Usage : PYTHONPATH=$PWD .venv/bin/python scripts/audit_production2.py [--probe 60]
"""
import argparse
import collections
import datetime
import os
import random
import re
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from engine.shared.db import connect                       # noqa: E402
from engine.analytics import service, strategy             # noqa: E402
from engine.analytics.series import prepare_series         # noqa: E402
from research_cleaning_cases import classify_v3            # noqa: E402

CRIT = {f: (m, op) for f, m, op in strategy.CRITERIA}
DOC = {'regular': (191, 67), 'fast': (389, 11), 'recovery': (196, 497), 'low_volatility': (38, 45)}      # docs/METHODE.md : calibrage du 28/10/2026 (actions, ETF)
LABELS = {'regular': 'Croissance régulière', 'fast': 'Croissance rapide', 'recovery': 'Rebond', 'low_volatility': 'Hausse calme (low_volatility)', 'momentum': 'Momentum 6 mois', 'momentum12': 'Momentum 12 mois'}
SUFFIX = {'XETR': '.DE', 'XPAR': '.PA', 'XLON': '.L', 'XAMS': '.AS', 'XMIL': '.MI', 'XMAD': '.MC', 'XSTO': '.ST', 'XOSL': '.OL', 'XSWX': '.SW', 'XBRU': '.BR', 'XLIS': '.LS', 'XHEL': '.HE', 'XCSE': '.CO'}
US = ('XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS')


def sql(conn, query, args=()):
    with conn.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def margin(r):
    f, v, t = r['criterion'], r.get('value'), r.get('threshold')
    if v is None or t is None or f not in CRIT:
        return None
    return (((t - v) if CRIT[f][1] == '>=' else (v - t)) / max(abs(t), 1e-9))


def pct(a, b):
    return f'{100 * a / b:.1f} %' if b else '–'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--probe', type=int, default=0)
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('SET SESSION TRANSACTION READ ONLY')
    out = []
    w = out.append
    w('# Audit de production n°2 (lecture seule)\n')
    # ───── 1. ruptures de cours en production
    w('## 1. Ruptures de cours dans la production (actions de l\'univers)\n')
    ids = [r['id'] for r in sql(conn, """SELECT l.id FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id
                                         WHERE i.kind='equity' AND s.quality='break'""")]
    info = {r['id']: r for r in sql(conn, "SELECT l.id, l.symbol, l.mic, i.name FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE l.id IN (" + ','.join(['%s'] * len(ids)) + ")", ids)} if ids else {}
    counts, declared, examples = collections.Counter(), 0, collections.defaultdict(list)
    events_total = 0
    for lid in ids:
        bars = sql(conn, 'SELECT price_date, close_px, adj_close_px, volume FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        splits = sql(conn, "SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))
        sp = [(s['event_date'].isoformat(), float(s['ratio']) if s['ratio'] else None) for s in splits]
        series = [(b['price_date'].isoformat(), float(b['close_px']), None if b['adj_close_px'] is None else float(b['adj_close_px'])) for b in bars]
        dates, closes, basis, breaks = prepare_series(series, sp)
        vol = {b['price_date'].isoformat(): (None if b['volume'] is None else float(b['volume'])) for b in bars}
        evmap = {dates[i]: cls for i, cls, p, end in classify_v3(closes, closes, [vol.get(d) for d in dates])}
        for b in breaks:
            if len(dates) - 1 - b > 251:
                continue
            ratio = closes[b] / closes[b - 1]
            direction = 'hausse' if ratio > 1 else 'baisse'
            cls = evmap.get(dates[b]) or 'sous seuil 40 % ou non classé'
            decl = any(abs((datetime.date.fromisoformat(dates[b]) - datetime.date.fromisoformat(d)).days) <= 3 for d, _ in sp)
            declared += decl
            events_total += 1
            counts[(cls, direction)] += 1
            if len(examples[(cls, direction)]) < 3:
                i = info.get(lid, {})
                examples[(cls, direction)].append(f"{i.get('symbol')} ({i.get('mic')}) {dates[b]} ×{ratio:.3g}{' [split déclaré]' if decl else ''}")
    w(f'{len(ids)} actions de l\'univers ont une rupture dans les 252 dernières séances ({events_total} événements ; dont {declared} coïncident avec un split déclaré par Yahoo, déjà traité par le moteur).\n')
    w('| Nature (classification v3, volume compris) | Hausses | Baisses | Exemples |')
    w('|---|---|---|---|')
    for cls in ('A1', 'A2', 'C', 'B', 'sous seuil 40 % ou non classé'):
        up, down = counts.get((cls, 'hausse'), 0), counts.get((cls, 'baisse'), 0)
        w(f"| {cls} | {up} | {down} | " + '; '.join(examples.get((cls, 'hausse'), [])[:2] + examples.get((cls, 'baisse'), [])[:2]) + ' |')
    w('\nA1 = split ou regroupement confirmé par le volume ; A2 = erreur isolée ; B = mouvement plausible ; C = incertain. Les sauts des 10 dernières séances ne peuvent pas être classés (pas de recul) : ils tombent dans « non classé ».\n')
    # ───── 2. exemples de critères
    w('## 2. Exemples d\'actions écartées par les critères de pente, de régularité et de volatilité (état actuel)\n')
    w('Unités du moteur : pente en % par séance, volatilité en % par séance, R² entre 0 et 1. « Raté de peu » = seul critère en échec, à moins de 15 % du seuil ; « loin du seuil » = seul critère en échec, à plus de 50 %.\n')
    verdicts = {}
    for name in ('regular', 'fast', 'recovery', 'low_volatility'):
        verdicts[name] = [v for v in service.judge_universe(conn, strategy.validate(strategy.preset(name))) if v['group'] == 'equity']
        rej = [v for v in verdicts[name] if v['status'] == 'rejected']
        sole = collections.defaultdict(list)
        for v in rej:
            fails = [r for r in v['reasons'] if r['result'] == 'fail']
            keys = {(r['period'], r['criterion']) for r in fails}
            if len(keys) == 1:
                r = fails[0]
                m = margin(r)
                if m is not None:
                    sole[(r['period'], r['criterion'])].append((m, v, r))
        w(f"**{LABELS[name]}** : {len(rej)} actions écartées, dont {sum(len(x) for x in sole.values())} par un seul critère.")
        for (period, crit_), lst in sorted(sole.items(), key=lambda kv: -len(kv[1])):
            if crit_ not in ('min_slope', 'min_r2', 'max_volatility', 'min_return', 'max_return'):
                continue
            lst.sort(key=lambda x: x[0])
            near = [x for x in lst if 0 < x[0] <= 0.15][:3]
            far = [x for x in lst if x[0] >= 0.5][-2:]
            def fmt(x):
                m, v, r = x
                op = '≥' if CRIT[crit_][1] == '>=' else '≤'
                return f"{v['symbol']} ({v['row']['mic']}) {str(v['row']['name'])[:28]} : {r['value']:.3g} (seuil {op} {r['threshold']:.3g}, écart {100 * m:.0f} %)"
            w(f"  - {period}·{crit_} : seul critère en échec pour {len(lst)} actions · raté de peu : " + ('; '.join(fmt(x) for x in near) or 'aucun') + ' · loin du seuil : ' + ('; '.join(fmt(x) for x in far) or 'aucun'))
    # ───── 3. rotation réelle
    w('\n## 3. Rotation réelle observée sur les instantanés quotidiens du Suivi (Top 20 actions de chaque stratégie)\n')
    snaps = sql(conn, "SELECT snap_date, preset, listing_id, origin FROM ranking_snapshots WHERE grp='equity'")
    by = collections.defaultdict(lambda: collections.defaultdict(set))
    origin = {}
    for s in snaps:
        by[(s['preset'], s['origin'])][s['snap_date']].add(s['listing_id'])
    w('| Stratégie | Origine | Instantanés | Période | Rotation d\'un jour au suivant | Rotation à environ 4 semaines | Séjour moyen dans le Top 20 (jours consécutifs) |')
    w('|---|---|---|---|---|---|---|')
    for (preset, org), days in sorted(by.items()):
        ds = sorted(days)
        if len(ds) < 2:
            w(f'| {preset} | {org} | {len(ds)} | {ds[0] if ds else "–"} | – | – | – |')
            continue
        day_turn = [1 - len(days[a] & days[b]) / max(1, len(days[b])) for a, b in zip(ds, ds[1:])]
        month_turn = []
        for a in ds:
            target = a + datetime.timedelta(days=28)
            cand = [b for b in ds if abs((b - target).days) <= 3]
            if cand:
                b = min(cand, key=lambda x: abs((x - target).days))
                month_turn.append(1 - len(days[a] & days[b]) / max(1, len(days[b])))
        runs, cur_run = [], {}
        for d in ds:
            for t in list(cur_run):
                if t not in days[d]:
                    runs.append(cur_run.pop(t))
            for t in days[d]:
                cur_run[t] = cur_run.get(t, 0) + 1
        runs += list(cur_run.values())
        w(f"| {preset} | {org} | {len(ds)} | {ds[0]} → {ds[-1]} | {100 * statistics.mean(day_turn):.0f} % | " + (f'{100 * statistics.mean(month_turn):.0f} % ({len(month_turn)} paires)' if month_turn else '–') + f" | {statistics.mean(runs):.1f} |")
    w('\n« rebuilt » = reconstitué après coup sur l\'univers actuel (biais de survie) ; « live » = enregistré chaque soir. Les stratégies récentes (Momentum) n\'ont que peu de jours.\n')
    # ───── 4. actions sans cotation
    w('## 4. Actions « candidate » à cotation principale (sans décision, jamais examinées)\n')
    cand = sql(conn, """SELECT l.id, l.mic, l.symbol, l.currency, l.excluded_reason, l.instrument_id, i.name, i.country, p.price, p.quote_at, p.avg_volume_3m,
                               (SELECT COUNT(*) FROM daily_prices d WHERE d.listing_id=l.id) AS bars,
                               (SELECT COUNT(*) FROM listings o WHERE o.instrument_id=l.instrument_id AND o.id<>l.id AND o.status='selected') AS other_selected
                        FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id
                        WHERE i.kind='equity' AND l.status='candidate' AND l.is_primary=1""")
    cause = collections.defaultdict(list)
    for r in cand:
        if r['excluded_reason'] and 'non convertible' in r['excluded_reason']:
            c = 'devise non convertible (taux de change absent)'
        elif r['excluded_reason']:
            c = 'autre motif enregistré : ' + str(r['excluded_reason'])[:50]
        elif r['quote_at'] is None and r['price'] is None:
            if r['other_selected']:
                c = 'aucune cotation reçue, mais le produit a une AUTRE cotation retenue'
            elif r['bars']:
                c = 'aucune cotation reçue, historique de cours présent'
            else:
                c = 'aucune cotation reçue de Yahoo (symbole inconnu, titre inactif ou récupération en échec)'
        elif r['price'] is None or r['quote_at'] is None:
            c = 'réponse de cotation sans prix exploitable'
        else:
            c = 'autre (cotation présente)'
        cause[c].append(r)
    w(f'{len(cand)} actions. Causes (exclusives, dans cet ordre) :\n')
    for c, lst in sorted(cause.items(), key=lambda kv: -len(kv[1])):
        w(f"- **{c}** : {len(lst)} ({pct(len(lst), len(cand))}) · places : " + ', '.join(f'{m} {n}' for m, n in collections.Counter(x['mic'] for x in lst).most_common(5)) + ' · exemples : ' + '; '.join(f"{x['symbol']} ({x['mic']}) {str(x['name'])[:25]}" for x in lst[:4]))
    bad = [r for r in cand if (r['mic'] in SUFFIX and not r['symbol'].upper().endswith(SUFFIX[r['mic']])) or (r['mic'] in US and '.' in r['symbol'] and not re.search(r'\.[A-Z]$', r['symbol'])) or not re.fullmatch(r'[A-Za-z0-9.\-^=]{1,12}', r['symbol'])]
    w(f"\nSymbole de forme douteuse pour sa place (suffixe attendu absent, caractère inattendu) : {len(bad)} · exemples : " + '; '.join(f"{x['symbol']} ({x['mic']})" for x in bad[:6]))
    if args.probe:
        pool = [r for r in cand if r['quote_at'] is None and r['price'] is None]
        random.Random(args.seed).shuffle(pool)
        sample = pool[:args.probe]
        from engine.market.yahoo import YahooClient, RateLimited
        client, found, asked = YahooClient(), [], 0
        try:
            for i in range(0, len(sample), 20):
                part = sample[i:i + 20]
                quotes = client.quotes([r['symbol'].upper() for r in part])
                asked += len(part)
                found += [r for r in part if r['symbol'].upper() in quotes]
                time.sleep(1.0)
        except RateLimited:
            w('\n(Yahoo limite les appels : sondage interrompu.)')
        except Exception as e:                  # noqa: BLE001
            w(f'\n(Sondage Yahoo interrompu : {e})')
        if asked:
            w(f"\nSondage Yahoo (lecture seule, rien n'est enregistré) : {len(found)} symboles sur {asked} renvoient aujourd'hui un cours exploitable ({pct(len(found), asked)}). Extrapolation à l'ensemble des {len(pool)} sans cotation : environ {len(found) * len(pool) // max(1, asked)} récupérables par le prochain passage de cotation.")
            if found:
                w('Exemples récupérables : ' + '; '.join(f"{x['symbol']} ({x['mic']})" for x in found[:6]))
    # ───── 5. Hausse calme
    w('\n## 5. « Hausse calme » (low_volatility) : fonctionnement normal ou décalage ?\n')
    cfg = strategy.preset('low_volatility')
    w('Réglage actuel : ' + '; '.join(f"{p['id']} ({p['sessions']} séances) : " + ', '.join(f'{k}={p[k]:.3g}' for k in ('min_slope', 'min_r2', 'max_volatility', 'max_drawdown') if p.get(k) is not None) for p in cfg['periods'] if p['enabled']) + '.')
    w('Documenté (`docs/METHODE.md`, calibrage du 28/10/2026 sur 9 700 titres) : régulière 191 actions + 67 ETF ; rapide 389 + 11 ; rebond 196 + 497 ; hausse calme 38 + 45. La cible « 4 à 8 % de l\'univers » du commentaire de `preset()` vaut donc pour les trois premiers, pas pour la hausse calme.\n')
    w('| Profil | Actions retenues (aujourd\'hui) | ETF retenus (aujourd\'hui) | Documenté au calibrage (actions + ETF) | Actions : part retenue |')
    w('|---|---|---|---|---|')
    allv = {}
    for name in ('regular', 'fast', 'recovery', 'low_volatility'):
        vs = service.judge_universe(conn, strategy.validate(strategy.preset(name)))
        allv[name] = vs
        eq = [v for v in vs if v['group'] == 'equity']
        et = [v for v in vs if v['group'] == 'etf']
        re_, rt_ = sum(v['status'] == 'retained' for v in eq), sum(v['status'] == 'retained' for v in et)
        d = DOC[name]
        w(f"| {LABELS[name]} | {re_} | {rt_} | {d[0]} + {d[1]} | {pct(re_, len(eq))} |")
    eq = [v for v in allv['low_volatility'] if v['group'] == 'equity' and v['status'] != 'unknown']
    w(f'\nHausse calme, actions évaluables ({len(eq)}) : taux de réussite de chaque critère (un titre peut échouer à plusieurs) :')
    for key in ('month·min_slope', 'month·min_r2', 'month·max_volatility', 'month·max_drawdown', 'quarter·min_slope', 'quarter·min_r2', 'quarter·max_volatility', 'quarter·max_drawdown'):
        per, cr = key.split('·')
        fails = sum(1 for v in eq if any(r['period'] == per and r['criterion'] == cr and r['result'] == 'fail' for r in v['reasons']))
        w(f'  - {key} : réussi par {pct(len(eq) - fails, len(eq))}')
    metrics = sql(conn, """SELECT m.sessions, m.perf, m.volatility, m.slope FROM strategy_metrics m JOIN v_recommendable r ON r.listing_id=m.listing_id JOIN listings l ON l.id=m.listing_id JOIN instruments i ON i.id=l.instrument_id
                           WHERE i.kind='equity' AND m.sessions IN (21,63) AND m.perf IS NOT NULL""")
    for n in (21, 63):
        rows = [m for m in metrics if m['sessions'] == n]
        if rows:
            w(f"  - contexte actuel, fenêtre de {n} séances (actions) : rendement médian {statistics.median(float(m['perf']) for m in rows):+.1f} % ; volatilité médiane {statistics.median(float(m['volatility']) for m in rows if m['volatility'] is not None):.2f} %/séance (plafond du profil : 1,5) ; "
              f"part avec pente >= doux {pct(sum(1 for m in rows if m['slope'] is not None and float(m['slope']) >= strategy.SLOPE_LEVELS['gentle']), len(rows))} ; part sous le plafond de volatilité {pct(sum(1 for m in rows if m['volatility'] is not None and float(m['volatility']) <= 1.5), len(rows))}")
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
