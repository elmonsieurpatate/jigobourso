"""Lecture des candidats de stratégie depuis la base. Seule porte d'entrée : la vue v_recommendable."""
from collections import defaultdict


def recommendable_candidates(conn, history=300, ids=None):
    """Cotations recommandables (sélectionnées ET principales) avec leurs `history` dernières clôtures.
    Les cotations exclues ou non principales ne sont jamais lues ici, même détenues. `ids` limite la lecture à un lot (mémoire)."""
    only = f' AND l.id IN ({",".join(["%s"] * len(ids))})' if ids else ''
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.symbol, l.mic, i.kind, i.name, i.isin FROM v_recommendable r
                       JOIN listings l ON l.id = r.listing_id JOIN instruments i ON i.id = l.instrument_id WHERE 1=1""" + only, list(ids or []))
        listings = cur.fetchall()
        bars = defaultdict(list)
        cur.execute("""SELECT d.listing_id, d.price_date, d.close_px, d.adj_close_px FROM daily_prices d
                       JOIN v_recommendable r ON r.listing_id = d.listing_id WHERE 1=1""" + only.replace('l.id', 'd.listing_id') + ' ORDER BY d.listing_id, d.price_date', list(ids or []))
        for row in cur.fetchall():
            bars[row['listing_id']].append((row['price_date'].isoformat(), float(row['close_px']),
                                            None if row['adj_close_px'] is None else float(row['adj_close_px'])))
        cur.execute("""SELECT e.listing_id, e.event_date FROM corporate_events e JOIN v_recommendable r ON r.listing_id = e.listing_id
                       WHERE e.kind IN ('split','reverse_split')""" + only.replace('l.id', 'e.listing_id'), list(ids or []))
        splits = defaultdict(list)
        for row in cur.fetchall():
            splits[row['listing_id']].append(row['event_date'].isoformat())
    return [{'key': l['id'], 'symbol': l['symbol'], 'name': l['name'], 'isin': l['isin'], 'mic': l['mic'],
             'group': 'etf' if l['kind'] == 'etf' else 'equity', 'bars': bars[l['id']][-history:],
             'split_dates': splits[l['id']]} for l in listings]
