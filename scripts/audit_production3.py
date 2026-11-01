"""Audit LECTURE SEULE n°3 : les ruptures de cours du moteur, vues par le circuit de vérification des splits déjà en place (split_log / corporate_events).

Question : parmi les titres rendus « non évaluables » par une rupture, combien ressemblent à un split non vérifié (protection à garder), combien sont des mouvements que Yahoo a vérifiés comme
n'étant pas des splits ou dont le ratio ne ressemble à aucun split usuel (à SIGNALER séparément, sans les réintroduire dans un classement) ? Aucune écriture, aucun changement de règle.
Usage : PYTHONPATH=$PWD .venv/bin/python scripts/audit_production3.py
"""
import collections
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine.shared.db import connect                       # noqa: E402
from engine.analytics.series import prepare_series         # noqa: E402
from engine.market.splits import split_ratio               # noqa: E402


def sql(conn, query, args=()):
    with conn.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def main():
    conn = connect()
    with conn.cursor() as cur:
        cur.execute('SET SESSION TRANSACTION READ ONLY')
    out = []
    w = out.append
    w('# Audit de production n°3 : ruptures de cours et circuit de vérification des splits (lecture seule)\n')
    st = sql(conn, "SELECT s.status, COUNT(*) n FROM split_log s JOIN v_recommendable r ON r.listing_id=s.listing_id GROUP BY s.status")
    w('Journal des sauts ressemblant à un split (`split_log`, titres de l\'univers) : ' + ', '.join(f"{r['status']} {r['n']}" for r in st) + f". Splits déclarés par Yahoo et appliqués (`corporate_events`) : {sql(conn, 'SELECT COUNT(*) n FROM corporate_events')[0]['n']}.\n")
    ids = [r['id'] for r in sql(conn, """SELECT l.id FROM series_state s JOIN v_recommendable r ON r.listing_id=s.listing_id JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id
                                         WHERE i.kind='equity' AND s.quality='break'""")]
    info = {r['id']: r for r in sql(conn, 'SELECT l.id, l.symbol, l.mic FROM listings l WHERE l.id IN (' + ','.join(['%s'] * len(ids)) + ')', ids)} if ids else {}
    cat = collections.Counter()
    examples = collections.defaultdict(list)
    per_title = collections.defaultdict(set)
    for lid in ids:
        bars = sql(conn, 'SELECT price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        splits = [(s['event_date'].isoformat(), float(s['ratio']) if s['ratio'] else None) for s in sql(conn, "SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))]
        log = sql(conn, 'SELECT event_date, status FROM split_log WHERE listing_id=%s', (lid,))
        series = [(b['price_date'].isoformat(), float(b['close_px']), None if b['adj_close_px'] is None else float(b['adj_close_px'])) for b in bars]
        dates, closes, basis, breaks = prepare_series(series, splits)
        for b in breaks:
            if len(dates) - 1 - b > 251:
                continue
            ratio = closes[b] / closes[b - 1]
            direction = 'hausse' if ratio > 1 else 'baisse'
            like = split_ratio(ratio) is not None
            day = datetime.date.fromisoformat(dates[b])
            row = next((r for r in log if abs((r['event_date'] - day).days) <= 5), None)
            if like and row is None:
                c = 'ressemble à un split, JAMAIS vérifié (pas de ligne dans le journal)'
            elif like and row['status'] == 'detected':
                c = 'ressemble à un split, vérification en attente'
            elif like and row['status'] == 'real_move':
                c = 'ressemble à un split mais Yahoo ne déclare aucun split (mouvement réel)'
            elif like:
                c = 'ressemble à un split, « confirmé » mais la rupture subsiste'
            else:
                c = 'ratio ne ressemblant à aucun split usuel (mouvement extrême)'
            cat[(c, direction)] += 1
            per_title[lid].add(c)
            if len(examples[c]) < 4:
                i = info.get(lid, {})
                examples[c].append(f"{i.get('symbol')} ({i.get('mic')}) {dates[b]} ×{ratio:.3g}")
    total = sum(cat.values())
    w(f'{len(ids)} actions de l\'univers rendues non évaluables par au moins une rupture ({total} événements dans les 252 dernières séances).\n')
    w('| Catégorie de la rupture | Hausses | Baisses | Exemples |')
    w('|---|---|---|---|')
    for c in sorted({k[0] for k in cat}):
        w(f"| {c} | {cat.get((c, 'hausse'), 0)} | {cat.get((c, 'baisse'), 0)} | " + '; '.join(examples[c]) + ' |')
    keep = {'ressemble à un split, JAMAIS vérifié (pas de ligne dans le journal)', 'ressemble à un split, vérification en attente', 'ressemble à un split, « confirmé » mais la rupture subsiste'}
    only_real = [lid for lid, s in per_title.items() if not (s & keep)]
    w(f"\nTitres dont TOUTES les ruptures sont des mouvements réels ou vérifiés comme tels (aucune ne ressemble à un split non vérifié) : {len(only_real)} sur {len(ids)}. "
      f"Ce sont ceux qu'on pourrait signaler séparément comme « mouvement extrême à vérifier » sans toucher à la protection contre les splits non ajustés ; les {len(ids) - len(only_real)} autres resteraient exclus tant que le split n'est pas vérifié.")
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
