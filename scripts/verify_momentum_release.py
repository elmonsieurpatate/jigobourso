"""Contrôle en LECTURE SEULE des deux stratégies Momentum sur une base réelle (essai isolé ou production) : valeurs stockées, cohérence avec la formule des tests chronologiques, classements du moteur.
Usage : PYTHONPATH=$PWD python scripts/verify_momentum_release.py   (variables JIGO_DB_*)   Code de sortie 0 = tout est cohérent."""
import json
import random
import sys

from engine.shared.db import connect
from engine.analytics import service, strategy
from engine.analytics.series import prepare_series

SAMPLE = 150
TOLERANCE = 1e-3


def main():
    conn = connect()
    problems = []
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n, SUM(momentum_6m IS NOT NULL) m6, SUM(momentum_12m IS NOT NULL) m12 FROM series_state')
        counts = cur.fetchone()
    print(f"series_state : {counts['n']} lignes, momentum 6 mois renseigné : {counts['m6']}, momentum 12 mois renseigné : {counts['m12']}")
    if not counts['m6'] or not counts['m12']:
        problems.append('aucune valeur de momentum stockée')
    for column, window in (('momentum_6m', 126), ('momentum_12m', 252)):          # cohérence avec la formule des tests : cours[-22] / cours[-1-fenêtre] - 1
        with conn.cursor() as cur:
            cur.execute(f'SELECT listing_id, {column} v FROM series_state WHERE {column} IS NOT NULL')
            stored = {r['listing_id']: float(r['v']) for r in cur.fetchall()}
        ids = sorted(stored)
        random.Random(1).shuffle(ids)
        agree = total = 0
        for lid in ids[:SAMPLE]:
            with conn.cursor() as cur:
                cur.execute('SELECT price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
                bars = [(r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])) for r in cur.fetchall()]
                cur.execute("SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))
                splits = [(r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None) for r in cur.fetchall()]
            _, closes, _, breaks = prepare_series(bars, splits)
            if len(closes) <= window:
                continue
            total += 1
            expected = 100 * (closes[-22] / closes[-1 - window] - 1)
            agree += 1 if abs(expected - stored[lid]) < TOLERANCE else 0
        rate = 100.0 * agree / total if total else 0.0
        print(f'{column} : {agree}/{total} valeurs identiques à la formule des tests chronologiques ({rate:.0f} %)')
        if total < 20 or rate < 90:
            problems.append(f'{column} : cohérence insuffisante ({agree}/{total})')
    for name in strategy.PRESETS:
        res = service.explore(conn, {'config': name, 'view': {'status': 'retained', 'kind': 'equity', 'page_size': 20}})
        rows = res['rows']
        label = f"{name:15} retenus : {res.get('total')} · premiers : " + ', '.join(f"{r['symbol']}" + (f" {r['momentum']:+.0f}%" if r.get('momentum') is not None else '') for r in rows[:5])
        print(label)
        if not rows:
            problems.append(f'{name} : aucun titre retenu')
        if name in strategy.MOMENTUM_WINDOWS:
            moms = [r['momentum'] for r in rows if r.get('momentum') is not None]
            if len(moms) != len(rows) or moms != sorted(moms, reverse=True):
                problems.append(f'{name} : classement non ordonné par momentum décroissant')
    print('contrôle terminé :', 'AUCUN PROBLÈME' if not problems else json.dumps(problems, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
