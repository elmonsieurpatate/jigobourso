"""Export de l'historique quotidien LONG (jusqu'à 10 ans, dividendes inclus) vers des fichiers, pour la recherche hors production.

Rien n'est écrit en base ni dans l'application : le script lit la liste des titres recommandables (lecture seule), interroge Yahoo (un appel par titre, avec pause), et
dépose un fichier `history/<clé>.csv.gz` par titre dans le dossier choisi, plus `universe.csv` (clé, symbole, place, type, pays, devise). Il est REPRENABLE : un titre
déjà exporté n'est pas redemandé, et un 429 de Yahoo arrête proprement le passage (relancer plus tard reprend là où il s'est arrêté).

Colonnes exportées : date, close (cours de clôture), adjclose (cours ajusté des splits ET des dividendes, base « rendement total »), volume.
Un jour sans cours ajusté est écarté (jamais complété). Les titres radiés n'existent pas chez Yahoo : l'univers reste celui d'aujourd'hui (biais de survie).

Usage : python scripts/export_history.py --out ~/tmp-history [--years 10] [--sample 1500] [--seed 1] [--min-interval 0.6]
Connexion à la base : variables JIGO_DB_* (comme le moteur). Sur l'hébergement : PYTHONPATH=$PWD .venv/bin/python scripts/export_history.py --out ~/tmp-history
"""
import argparse
import csv
import gzip
import json
import os
import random
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.market.yahoo import RateLimited, YahooError, local_date, _num   # noqa: E402

UNIVERSE_FIELDS = ('key', 'symbol', 'mic', 'kind', 'country', 'currency')
HISTORY_FIELDS = ('date', 'close', 'adjclose', 'volume')


def parse_daily(payload):
    """Réponse /v8/finance/chart (1d, avec cours ajusté) -> {'rows': [(date ISO, close, adjclose, volume|None)], 'skipped': n}, ou None si inexploitable.
    Un jour sans clôture ou sans cours ajusté est écarté ; les dates sont celles de la place (fuseau déclaré par Yahoo)."""
    result = (((payload or {}).get('chart') or {}).get('result') or [None])[0]
    if not isinstance(result, dict):
        return None
    meta = result.get('meta') or {}
    tz = meta.get('exchangeTimezoneName') or meta.get('timezone')
    ind = result.get('indicators') or {}
    quote = (ind.get('quote') or [{}])[0] or {}
    adj = ((ind.get('adjclose') or [{}])[0] or {}).get('adjclose') or []
    closes, volumes = quote.get('close') or [], quote.get('volume') or []
    rows, skipped, seen = [], 0, set()
    for i, ts in enumerate(result.get('timestamp') or []):
        close = _num(closes[i]) if i < len(closes) else None
        a = _num(adj[i]) if i < len(adj) else None
        if not isinstance(ts, int) or close is None or close <= 0 or a is None or a <= 0:
            skipped += 1
            continue
        day = local_date(ts, tz).isoformat()
        if day in seen:                              # deux points le même jour (séance partielle du jour) : le dernier gagne
            rows = [r for r in rows if r[0] != day]
        seen.add(day)
        v = volumes[i] if i < len(volumes) else None
        rows.append((day, close, a, int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None))
    rows.sort()
    return {'rows': rows, 'skipped': skipped} if rows else None


def history_path(out, key):
    return os.path.join(out, 'history', f'{key}.csv.gz')


def write_history(out, key, rows):
    """Écriture atomique (fichier .part puis renommage) : un arrêt en cours de route ne laisse jamais un fichier tronqué."""
    path = history_path(out, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + '.part'
    with gzip.open(part, 'wt', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(HISTORY_FIELDS)
        for d, c, a, v in rows:
            w.writerow((d, repr(c), repr(a), '' if v is None else v))
    os.replace(part, path)


def write_universe(out, universe):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'universe.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(UNIVERSE_FIELDS)
        for u in universe:
            w.writerow([u.get(f) if u.get(f) is not None else '' for f in UNIVERSE_FIELDS])


def fetch_daily(transport, symbol, years):
    """Un appel Yahoo : historique quotidien ajusté sur `years` ans (ou `max`)."""
    params = {'range': 'max' if years == 0 else f'{int(years)}y', 'interval': '1d', 'events': 'div|split', 'includeAdjustedClose': 'true', 'includePrePost': 'false'}
    return parse_daily(json.loads(transport.get('/v8/finance/chart/' + urllib.parse.quote(symbol, safe=''), params)))


def export(universe, transport, out, years=10, log=lambda *_: None, sleep=lambda s: None):
    """Exporte les titres pas encore exportés. Renvoie {'done': n, 'already': n, 'empty': n, 'errors': n, 'remaining': n, 'rate_limited': bool}."""
    write_universe(out, universe)
    stats = {'done': 0, 'already': 0, 'empty': 0, 'errors': 0, 'remaining': 0, 'rate_limited': False}
    todo = []
    for u in universe:
        if os.path.exists(history_path(out, u['key'])):
            stats['already'] += 1
        else:
            todo.append(u)
    for n, u in enumerate(todo):
        try:
            data = fetch_daily(transport, u['symbol'], years)
        except RateLimited:
            stats['rate_limited'], stats['remaining'] = True, len(todo) - n
            break
        except (YahooError, ValueError) as e:                      # symbole inconnu, réponse illisible : on passe au suivant, noté dans errors.log
            stats['errors'] += 1
            with open(os.path.join(out, 'errors.log'), 'a', encoding='utf-8') as fh:
                fh.write(f"{u['key']}\t{u['symbol']}\t{type(e).__name__}: {e}\n")
            continue
        if data is None:
            stats['empty'] += 1
            write_history(out, u['key'], [])                         # marque « déjà demandé, rien reçu » : pas de nouvel appel à la relance
        else:
            write_history(out, u['key'], data['rows'])
            stats['done'] += 1
        if (n + 1) % 25 == 0:
            log(f"{n + 1}/{len(todo)} titres")
        sleep(0)
    return stats


def load_universe(conn, sample=0, seed=1):
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id AS `key`, l.symbol, l.mic, i.kind, i.country, l.currency FROM v_recommendable r
                       JOIN listings l ON l.id = r.listing_id JOIN instruments i ON i.id = l.instrument_id ORDER BY l.id""")
        rows = cur.fetchall()
    if sample and sample < len(rows):
        rows = sorted(random.Random(seed).sample(rows, sample), key=lambda r: r['key'])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, help='dossier de destination (créé si besoin, hors de l\'application)')
    ap.add_argument('--years', type=int, default=10, help='profondeur en années (0 = tout ce que Yahoo fournit)')
    ap.add_argument('--sample', type=int, default=1500, help='sous-échantillon aléatoire de l\'univers (0 = tout)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--min-interval', type=float, default=0.6, help='pause minimale entre deux appels Yahoo (secondes)')
    args = ap.parse_args(argv)
    from engine.market.yahoo import UrllibTransport
    from engine.shared.db import connect
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SET SESSION TRANSACTION READ ONLY')
        universe = load_universe(conn, args.sample, args.seed)
        conn.rollback()
    finally:
        conn.close()
    print(f'{len(universe)} titres à exporter vers {args.out}', file=sys.stderr)
    t0 = time.monotonic()
    stats = export(universe, UrllibTransport(min_interval=args.min_interval), os.path.expanduser(args.out), args.years, log=lambda m: print(f'{m} · {time.monotonic() - t0:.0f} s', file=sys.stderr))
    print(json.dumps(stats, ensure_ascii=False))
    if stats['rate_limited']:
        print('Yahoo a répondu « trop de requêtes » : relancez la même commande plus tard, le script reprend là où il s\'est arrêté.', file=sys.stderr)
        return 4
    return 0


if __name__ == '__main__':
    sys.exit(main())
