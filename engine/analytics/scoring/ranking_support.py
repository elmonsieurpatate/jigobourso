"""Briques communes du classement des scores (ordre et rangs, courbes de clôtures) : utilisées par le tableau des classements (ranking_table)
et par l'administration des scores (admin/scores_ranking) ; ne dépendent ni de l'un ni de l'autre."""
from . import scores as SC


def ordered(book, key):
    """Source unique de l'ordre et des rangs d'un score (simple ou complexe) : (entrées triées, {id: rang}, {id: position}).
    Ordre : score décroissant, puis l'autre score, puis l'identifiant. Rang commun uniquement pour des scores bruts strictement identiques."""
    other = 'complex' if key == 'simple' else 'simple'
    order, ranks = SC.rank_order({l: e[key] for l, e in book.items()}, {l: e[other] for l, e in book.items()})
    return [book[l] for l in order], ranks, {l: i for i, l in enumerate(order, 1)}


def closes(conn, ids, sessions):
    """Dernières clôtures sur la même base ajustée que la fiche et les performances."""
    from ..series.series import prepare_series
    ids = list(ids)
    out = {i: [] for i in ids}
    if not ids or sessions < 1:
        return out
    import datetime
    since = datetime.date.today() - datetime.timedelta(days=int(sessions * 2 + 10))
    with conn.cursor() as cur:
        for k in range(0, len(ids), 200):
            part = ids[k:k + 200]
            marks = ','.join(['%s'] * len(part))
            cur.execute(f"""SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices
                            WHERE listing_id IN ({marks}) AND price_date>=%s
                            ORDER BY listing_id, price_date""", part + [since])
            bars = {i: [] for i in part}
            for r in cur.fetchall():
                bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']) if r['close_px'] is not None else None,
                                             float(r['adj_close_px']) if r['adj_close_px'] is not None else None))
            cur.execute(f"""SELECT listing_id, event_date, ratio FROM corporate_events
                            WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split') AND event_date>=%s
                            ORDER BY event_date""", part + [since])
            splits = {i: [] for i in part}
            for r in cur.fetchall():
                splits[r['listing_id']].append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
            for lid in part:
                dates, closes, _, _ = prepare_series(bars[lid], splits[lid])
                out[lid] = list(zip(dates, closes))[-(sessions + 1):]
    return out


def series(conn, ids, sessions):
    """Dernières clôtures (sessions + 1 points) de chaque titre : petites courbes du classement. Un titre sans historique n'a pas de courbe (liste vide)."""
    return {i: [round(px, 4) for _, px in v] for i, v in closes(conn, ids, sessions).items()}


def dated_series(conn, lid, sessions):
    """Courbe détaillée d'un titre : date ISO et cours de chaque séance, pour l'infobulle de la simulation."""
    return [{'d': d.isoformat() if hasattr(d, 'isoformat') else str(d), 'p': round(px, 4)} for d, px in closes(conn, [lid], sessions).get(lid, [])]
