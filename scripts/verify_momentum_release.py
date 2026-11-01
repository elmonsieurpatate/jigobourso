"""Contrôle en LECTURE SEULE des deux stratégies Momentum sur une base réelle (essai isolé ou production) : valeurs stockées, cohérence avec la formule des tests chronologiques, classements du moteur.
Usage : PYTHONPATH=$PWD python scripts/verify_momentum_release.py   (variables JIGO_DB_*)   Code de sortie 0 = tout est cohérent."""
import json
import random
import sys

from engine.shared.db import connect
from engine.analytics import service, strategy
import os

from engine.analytics.series import prepare_series
from engine.market.calendar import session_dates

SAMPLE = 150
TOLERANCE = 1e-3
MIN_SAMPLES = int(os.environ.get('JIGO_VERIFY_MIN', '20'))


def main():
    conn = connect()
    problems = []
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n, SUM(momentum_6m IS NOT NULL) m6, SUM(momentum_12m IS NOT NULL) m12 FROM series_state')
        counts = cur.fetchone()
    print(f"series_state : {counts['n']} lignes, momentum 6 mois renseigné : {counts['m6']}, momentum 12 mois renseigné : {counts['m12']}")
    if not counts['m6'] or not counts['m12']:
        problems.append('aucune valeur de momentum stockée')
    # Deux contrôles indépendants du code de la stratégie, sur un échantillon de titres :
    #  - « daté » : formule du calendrier de la place (cours à J−fenêtre et J−21 séances attendues, relevés dans la série) ; doit correspondre à 100 % aux valeurs stockées ;
    #  - « indices » : formule des tests chronologiques sur les clôtures disponibles (cours[-22] / cours[-1-fenêtre]) ; elle diffère légèrement si la série a des séances manquantes
    #    (trous au milieu de la fenêtre), cas où le calcul daté est le bon : indicatif seulement.
    with conn.cursor() as cur:        # comme le calcul des indicateurs : la fenêtre se termine à la dernière séance de la PLACE (un titre en retard d'une séance garde la fenêtre de sa place)
        cur.execute('SELECT l.mic, MAX(s.last_close_date) d FROM series_state s JOIN listings l ON l.id=s.listing_id GROUP BY l.mic')
        market_latest = {r['mic']: r['d'].isoformat() for r in cur.fetchall()}
    for column, window in (('momentum_6m', 126), ('momentum_12m', 252)):
        with conn.cursor() as cur:
            cur.execute(f'SELECT s.listing_id, s.{column} v, s.last_close_date d, l.mic FROM series_state s JOIN listings l ON l.id=s.listing_id WHERE s.{column} IS NOT NULL')
            stored = {r['listing_id']: (float(r['v']), r['d'].isoformat(), r['mic']) for r in cur.fetchall()}
        ids = sorted(stored)
        random.Random(1).shuffle(ids)
        dated = index = total = 0
        shown = 0
        for lid in ids[:SAMPLE]:
            value, last, mic = stored[lid]
            with conn.cursor() as cur:
                cur.execute('SELECT price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
                bars = [(r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])) for r in cur.fetchall()]
                cur.execute("SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))
                splits = [(r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None) for r in cur.fetchall()]
            dates, closes, _, breaks = prepare_series(bars, splits)
            if len(closes) <= window:
                continue
            total += 1
            expected_sessions = session_dates(mic, max(last, market_latest.get(mic, last)), window + 1)
            seen = dict(zip(dates, closes))
            if expected_sessions and expected_sessions[0] in seen and expected_sessions[-22] in seen:
                by_date = 100 * (seen[expected_sessions[-22]] / seen[expected_sessions[0]] - 1)
                dated += 1 if abs(by_date - value) < TOLERANCE else 0
            by_index = 100 * (closes[-22] / closes[-1 - window] - 1)
            if abs(by_index - value) < TOLERANCE:
                index += 1
            elif shown < 3:
                shown += 1
                print(f'   écart {column} #{lid} {mic}: stocké {value:+.2f} · indices {by_index:+.2f} · séances présentes sur la fenêtre {sum(1 for d in dates if expected_sessions and expected_sessions[0] <= d <= expected_sessions[-1])}/{window + 1}')
        print(f'{column} : {dated}/{total} identiques à la formule datée du calendrier ; {index}/{total} identiques à la formule des tests par indices')
        if total < MIN_SAMPLES or dated < total:
            problems.append(f'{column} : valeurs stockées différentes du calcul daté ({dated}/{total})')
        if total and index < 0.8 * total:
            problems.append(f'{column} : formule des tests par indices trop différente ({index}/{total})')
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
