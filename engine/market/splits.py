"""Splits et regroupements non ajustés dans l'historique.

Les cours de clôture de Yahoo (Spark et Chart) ne sont PAS toujours ajustés des splits : pour certains titres l'historique garde le saut (constaté sur
DHY, TACK, GOSS : le saut est dans les données et le split est déclaré à part, dans `events.splits` de l'API Chart). Un saut de cours seul ne prouve rien :
ce peut être un vrai mouvement (à garder tel quel) ou un split non ajusté (à corriger). Seul un split DÉCLARÉ par Yahoo, de ratio cohérent avec le saut observé,
est donc corrigé.

1. `detect` repère les sauts de cours qui ressemblent à un ratio usuel (×2, ÷2, ÷10, ×3/2…) et les note dans `split_log` (statut « detected »).
2. `verify` interroge Yahoo (`events.splits`) : un split déclaré à la même date (± 5 jours) dont le ratio explique le saut (± 15 %) devient « confirmed » et est écrit
   dans `corporate_events` (ratio = parts nouvelles / anciennes) ; le calcul des séries (`analytics/series.prepare_series`) ajuste alors les clôtures antérieures.
   Sinon le saut est « real_move » : rien n'est corrigé et le titre reste « non évaluable » sur les fenêtres qui le traversent.
Une chute réelle de 50 % n'est donc jamais « corrigée » : il faut une déclaration du fournisseur.
"""
import datetime

import pymysql.err

from engine.analytics.series import BREAK_RATIO
from engine.market.yahoo import RateLimited

# Ratios usuels parts nouvelles / anciennes (2 = deux pour un) ; leur inverse est le regroupement correspondant.
COMMON_RATIOS = (1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 30, 40, 50, 100)
TOLERANCE = 0.08          # écart toléré entre le saut observé et le ratio exact (le cours bouge aussi le jour du split)


def split_ratio(price_ratio):
    """Ratio parts nouvelles / anciennes si `price_ratio` (cours après / cours avant) ressemble à un split ou un regroupement usuel, sinon None."""
    if not price_ratio or price_ratio <= 0:
        return None
    for k in COMMON_RATIOS:
        if abs(price_ratio * k - 1) <= TOLERANCE:               # le cours est divisé par k : split k pour 1
            return float(k)
        if abs(price_ratio / k - 1) <= TOLERANCE:               # le cours est multiplié par k : regroupement 1 pour k
            return 1.0 / k
    return None


def is_break(price_ratio):
    return price_ratio > BREAK_RATIO or price_ratio < 1 / BREAK_RATIO


def _pair(conn, listing_id, day):
    """(clôture du jour, clôture précédente) pour la séance `day`, ou None."""
    with conn.cursor() as cur:
        cur.execute('SELECT price_date, close_px FROM daily_prices WHERE listing_id=%s AND price_date<=%s ORDER BY price_date DESC LIMIT 2', (listing_id, day))
        rows = cur.fetchall()
    if len(rows) < 2 or rows[0]['price_date'] != day or not float(rows[1]['close_px']) > 0:
        return None
    return float(rows[0]['close_px']), float(rows[1]['close_px'])


def available(conn):
    """La table split_log existe-t-elle (entre le transfert du code et la migration, elle peut manquer) ?"""
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM split_log LIMIT 1')
        return True
    except pymysql.err.ProgrammingError:
        conn.rollback()
        return False


def _stamp(now):
    return now.replace(microsecond=0, tzinfo=None) if isinstance(now, datetime.datetime) else datetime.datetime.combine(now, datetime.time())


def detect(conn, now):
    """Note les nouveaux sauts qui ressemblent à un split (statut « detected »). Renvoie leur nombre."""
    if not available(conn):
        return 0
    stamp = _stamp(now)
    with conn.cursor() as cur:
        cur.execute("""SELECT s.listing_id, s.break_dates FROM series_state s JOIN v_collect_set c ON c.listing_id=s.listing_id
                       WHERE s.break_dates IS NOT NULL AND s.break_dates<>''""")
        candidates = cur.fetchall()
        cur.execute('SELECT listing_id, event_date FROM split_log')
        known = {(r['listing_id'], r['event_date'].isoformat()) for r in cur.fetchall()}
    new = 0
    for r in candidates:
        for day in r['break_dates'].split(','):
            if (r['listing_id'], day) in known:
                continue
            pair = _pair(conn, r['listing_id'], datetime.date.fromisoformat(day))
            ratio = split_ratio(pair[0] / pair[1]) if pair else None
            if ratio is None:
                continue                                                       # saut sans rapport avec un ratio usuel : vrai mouvement, on n'y touche pas
            with conn.cursor() as cur:
                cur.execute("INSERT IGNORE INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (%s,%s,%s,%s,'detected',%s)",
                            (r['listing_id'], day, round(pair[0] / pair[1], 8), round(ratio, 8), stamp))
            new += 1
    conn.commit()
    return new


DATE_TOLERANCE_DAYS = 5      # écart toléré entre la date du saut dans nos données et la date déclarée par Yahoo
RATIO_TOLERANCE = 0.15       # le ratio déclaré doit expliquer le saut observé à 15 % près (le cours bouge aussi le jour du split)


def match_declared(declared, event_date, price_ratio):
    """Split déclaré (date, num, den) qui explique le saut observé à `event_date`, ou None. Renvoie (ratio parts nouvelles / anciennes, date déclarée).

    Le sens de la notation de Yahoo (1:10) n'est pas fiable d'un titre à l'autre (constaté : TACK, dont le cours est divisé par 10, est déclaré « 1:10 ») :
    on retient le sens, direct ou inverse, que le saut OBSERVÉ confirme, avec l'ordre de grandeur déclaré."""
    best = None
    for day, num, den in declared:
        gap = abs((datetime.date.fromisoformat(day) - event_date).days)
        if gap > DATE_TOLERANCE_DAYS:
            continue
        for ratio in (num / den, den / num):
            err = abs(price_ratio * ratio - 1)
            if err <= RATIO_TOLERANCE and (best is None or (err, gap) < best[:2]):
                best = (err, gap, ratio, day)
    return None if best is None else (best[2], best[3])


def verify(conn, client, now, limit=150):
    """Interroge Yahoo pour les sauts « detected » (au plus `limit` titres par passage) : split déclaré cohérent = « confirmed » (écrit dans corporate_events),
    sinon « real_move ». Un titre dont Yahoo ne répond pas reste « detected » pour le passage suivant. Renvoie {'confirmed': n, 'real_move': n, 'unanswered': n}."""
    out = {'confirmed': 0, 'real_move': 0, 'unanswered': 0}
    if not available(conn):
        return out
    stamp = _stamp(now)
    with conn.cursor() as cur:
        cur.execute("""SELECT s.listing_id, s.event_date, s.price_ratio, l.symbol FROM split_log s JOIN listings l ON l.id=s.listing_id
                       WHERE s.status='detected' ORDER BY s.listing_id, s.event_date""")
        rows = cur.fetchall()
    by_listing = {}
    for r in rows:
        by_listing.setdefault(r['listing_id'], []).append(r)
    for lid in list(by_listing)[:limit]:
        events = by_listing[lid]
        try:
            declared = client.splits(events[0]['symbol'])
        except RateLimited:
            raise
        except Exception:                                                      # noqa: BLE001 : réponse absente ou illisible : on réessaiera au prochain passage
            out['unanswered'] += len(events)
            continue
        for r in events:
            hit = match_declared(declared, r['event_date'], float(r['price_ratio']))
            with conn.cursor() as cur:
                if hit:
                    ratio, _ = hit
                    cur.execute('INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE ratio=VALUES(ratio)',
                                (lid, r['event_date'], 'split' if ratio > 1 else 'reverse_split', round(ratio, 8)))
                    cur.execute("UPDATE split_log SET status='confirmed', ratio=%s, checked_at=%s WHERE listing_id=%s AND event_date=%s", (round(ratio, 8), stamp, lid, r['event_date']))
                    out['confirmed'] += 1
                else:
                    cur.execute("UPDATE split_log SET status='real_move', checked_at=%s WHERE listing_id=%s AND event_date=%s", (stamp, lid, r['event_date']))
                    out['real_move'] += 1
        conn.commit()
    return out
