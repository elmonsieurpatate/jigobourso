"""Chargement commun des clôtures quotidiennes et des splits (même forme partout : `prepare_series` / `analyze_series`)."""


def load_bars(conn, ids):
    """{listing_id: [(date ISO, clôture, clôture ajustée ou None)]} pour les cotations `ids`, triées par date."""
    bars = {}
    if not ids:
        return bars
    with conn.cursor() as cur:
        cur.execute(f"SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(ids))}) ORDER BY listing_id, price_date", list(ids))
        for r in cur.fetchall():
            bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
    return bars


def load_splits(conn, ids=None):
    """{listing_id: [(date ISO, ratio ou None)]} : splits et regroupements ; toutes les cotations si `ids` vaut None."""
    splits = {}
    sql, args = "SELECT listing_id, event_date, ratio FROM corporate_events WHERE kind IN ('split','reverse_split')", []
    if ids is not None:
        if not ids:
            return splits
        sql += f" AND listing_id IN ({','.join(['%s'] * len(ids))})"
        args = list(ids)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        for r in cur.fetchall():
            splits.setdefault(r['listing_id'], []).append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
    return splits


def load_bars_and_splits(conn, ids):
    """(bars, splits) pour les cotations `ids`."""
    return load_bars(conn, ids), load_splits(conn, ids)
