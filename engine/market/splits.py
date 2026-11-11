"""Splits et regroupements non ajustés dans l'historique.

Les cours de clôture de Yahoo (Spark et Chart) ne sont PAS toujours ajustés des splits : pour certains titres l'historique garde le saut (constaté sur
DHY, TACK, GOSS : le saut est dans les données et le split est déclaré à part, dans `events.splits` de l'API Chart). Un saut de cours seul ne prouve rien :
ce peut être un vrai mouvement (à garder tel quel) ou un split non ajusté (à corriger). Seul un split DÉCLARÉ par Yahoo, de ratio cohérent avec le saut observé,
est donc corrigé.

1. `detect` repère les ruptures inexpliquées des séries et les note dans `split_log` (statut « detected »), avec un ratio usuel ou une estimation à vérifier. La détection ne confirme jamais un split.
2. `verify` interroge Yahoo (`events.splits`) : un split déclaré à la même date (± 5 jours) dont le ratio explique le saut (± 15 %) devient « confirmed » et est écrit
   dans `corporate_events` (ratio = parts nouvelles / anciennes) ; le calcul des séries (`analytics/series.prepare_series`) ajuste alors les clôtures antérieures.
   Sinon le saut passe en « real_move » : rien n'est corrigé et le titre reste « non évaluable » sur les fenêtres qui le traversent. Ce statut veut dire « Yahoo n'a pas déclaré de split qui
   explique ce saut AU MOMENT de la vérification » ; ce n'est ni une preuve que le mouvement est réel, ni une preuve qu'aucun split n'existe (Yahoo peut déclarer un split avec retard).
3. `recheck` interroge de nouveau Yahoo, de façon bornée (au plus RECHECK_MAX_CHECKS réponses par saut, espacées de plusieurs jours, sur RECHECK_WINDOW_DAYS jours après le saut, RECHECK_LIMIT titres
   par passage), pour les sauts « real_move » : une déclaration tardive les fait passer en « confirmed » ; une réponse absente ou illisible n'est jamais comptée comme une vérification.
Une chute réelle de 50 % n'est donc jamais « corrigée » : il faut une déclaration du fournisseur.
"""
import datetime

import pymysql.err

from engine.analytics.series import BREAK_RATIO
from engine.market.yahoo import RateLimited

# Ratios usuels parts nouvelles / anciennes (2 = deux pour un) ; leur inverse est le regroupement correspondant.
# CSH2 GBP (LU1230136894) : split 250 pour 1 le 27/10/2026 ;
# la détection reste un candidat, seule la déclaration fournisseur confirme le split.
COMMON_RATIOS = (1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 30, 40, 50, 100, 250)
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


def has_recheck(conn):
    """Les colonnes de revérification (migration 20261102) sont-elles présentes ? Sans elles, le code se comporte comme avant (aucune revérification)."""
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM split_log LIKE 'recheck_after'")
            return cur.fetchone() is not None
    except pymysql.err.ProgrammingError:
        conn.rollback()
        return False


def next_recheck(checks, today):
    """Date de la prochaine revérification après `checks` réponses de Yahoo ; None quand le nombre maximal est atteint."""
    if checks >= RECHECK_MAX_CHECKS:
        return None
    return today + datetime.timedelta(days=RECHECK_DELAYS.get(checks, RECHECK_DELAYS[max(RECHECK_DELAYS)]))


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
            if ratio is None and pair and pair[0] > 0 and is_break(pair[0] / pair[1]):
                ratio = pair[1] / pair[0]  # estimation à revoir : jamais une confirmation
            if ratio is None or not 0.00000001 <= ratio < 10000000000:
                continue
            with conn.cursor() as cur:
                cur.execute("INSERT IGNORE INTO split_log(listing_id,event_date,price_ratio,ratio,status,detected_at) VALUES (%s,%s,%s,%s,'detected',%s)",
                            (r['listing_id'], day, round(pair[0] / pair[1], 8), round(ratio, 8), stamp))
            new += 1
    conn.commit()
    return new


RECHECK_MAX_CHECKS = 3       # réponses de Yahoo au total pour un saut : la vérification initiale et deux revérifications
RECHECK_DELAYS = {1: 7, 2: 14}   # jours à attendre avant la 2e réponse (après la 1re), puis avant la 3e (après la 2e)
RECHECK_WINDOW_DAYS = 60     # au-delà de 60 jours après le saut, une déclaration tardive est improbable : plus de revérification
RECHECK_LIMIT = 30           # titres interrogés au plus par passage de maintenance (en plus de la vérification initiale)
RECHECK_RETRY_DAYS = 3       # délai avant un nouvel essai quand Yahoo n'a pas répondu (la tentative n'est pas comptée)

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


def manual_rejections(conn):
    """Un refus administratif persiste face aux confirmations automatiques ultérieures."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT listing_id,event_date FROM split_reviews WHERE decision='rejected'")
            return {(r['listing_id'], r['event_date']) for r in cur.fetchall()}
    except pymysql.err.ProgrammingError as exc:
        if exc.args[0] != 1146:
            raise
        return set()  # déploiement avant migration additive


def verify(conn, client, now, limit=150):
    """Interroge Yahoo pour les sauts « detected » (au plus `limit` titres par passage) : split déclaré cohérent = « confirmed » (écrit dans corporate_events),
    sinon « real_move » (= non déclaré par Yahoo à cet instant ; une revérification est alors planifiée, voir `recheck`). Un titre dont Yahoo ne répond pas reste « detected » pour le passage suivant.
    Renvoie {'confirmed': n, 'real_move': n, 'unanswered': n}."""
    out = {'confirmed': 0, 'real_move': 0, 'unanswered': 0}
    if not available(conn):
        return out
    recheck_cols = has_recheck(conn)
    stamp = _stamp(now)
    with conn.cursor() as cur:
        cur.execute("""SELECT s.listing_id, s.event_date, s.price_ratio, l.symbol FROM split_log s JOIN listings l ON l.id=s.listing_id
                       WHERE s.status='detected' ORDER BY s.listing_id, s.event_date""")
        rows = cur.fetchall()
    refused = manual_rejections(conn)
    by_listing = {}
    for r in rows:
        if (r['listing_id'], r['event_date']) not in refused:
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
                elif recheck_cols:
                    cur.execute("UPDATE split_log SET status='real_move', checked_at=%s, checks=1, recheck_after=%s WHERE listing_id=%s AND event_date=%s",
                                (stamp, next_recheck(1, stamp.date()), lid, r['event_date']))
                    out['real_move'] += 1
                else:
                    cur.execute("UPDATE split_log SET status='real_move', checked_at=%s WHERE listing_id=%s AND event_date=%s", (stamp, lid, r['event_date']))
                    out['real_move'] += 1
        conn.commit()
    return out


def recheck(conn, client, now, limit=RECHECK_LIMIT):
    """Revérification BORNÉE des sauts « real_move » : Yahoo peut déclarer un split avec retard, et une réponse négative à un instant donné ne prouve rien.
    Concerne les sauts datant de moins de RECHECK_WINDOW_DAYS jours, déjà vérifiés moins de RECHECK_MAX_CHECKS fois, dont la date de revérification est arrivée. Au plus `limit` titres par passage.
    Déclaration cohérente trouvée : « confirmed » (écrit dans corporate_events, comme à la vérification initiale ; le calcul suivant ajuste les clôtures). Sinon la réponse est comptée et la suivante
    planifiée ; réponse absente ou illisible : rien n'est compté, nouvel essai dans RECHECK_RETRY_DAYS jours. Renvoie {'rechecked', 'confirmed', 'unanswered', 'waiting'}."""
    out = {'rechecked': 0, 'confirmed': 0, 'unanswered': 0, 'waiting': 0}
    if not available(conn) or not has_recheck(conn):
        return out
    stamp = _stamp(now)
    today = stamp.date()
    with conn.cursor() as cur:
        cur.execute("""SELECT s.listing_id, s.event_date, s.price_ratio, s.checks, l.symbol FROM split_log s JOIN listings l ON l.id=s.listing_id
                       WHERE s.status='real_move' AND s.checks < %s AND s.event_date >= %s AND (s.recheck_after IS NULL OR s.recheck_after <= %s)
                       ORDER BY s.listing_id, s.event_date""", (RECHECK_MAX_CHECKS, today - datetime.timedelta(days=RECHECK_WINDOW_DAYS), today))
        rows = cur.fetchall()
    refused = manual_rejections(conn)
    by_listing = {}
    for r in rows:
        if (r['listing_id'], r['event_date']) not in refused:
            by_listing.setdefault(r['listing_id'], []).append(r)
    todo = list(by_listing)[:max(0, limit)]
    out['waiting'] = sum(len(v) for k, v in by_listing.items() if k not in todo)
    for lid in todo:
        events = by_listing[lid]
        try:
            declared = client.splits(events[0]['symbol'])
        except RateLimited:
            raise
        except Exception:                                                      # noqa: BLE001 : réponse absente ou illisible : ni confirmation ni vérification comptée
            with conn.cursor() as cur:
                cur.executemany('UPDATE split_log SET recheck_after=%s WHERE listing_id=%s AND event_date=%s',
                                [(today + datetime.timedelta(days=RECHECK_RETRY_DAYS), lid, r['event_date']) for r in events])
            conn.commit()
            out['unanswered'] += len(events)
            continue
        for r in events:
            hit = match_declared(declared, r['event_date'], float(r['price_ratio']))
            with conn.cursor() as cur:
                if hit:
                    ratio, _ = hit
                    cur.execute('INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE ratio=VALUES(ratio)',
                                (lid, r['event_date'], 'split' if ratio > 1 else 'reverse_split', round(ratio, 8)))
                    cur.execute("UPDATE split_log SET status='confirmed', ratio=%s, checked_at=%s, checks=checks+1, recheck_after=NULL WHERE listing_id=%s AND event_date=%s",
                                (round(ratio, 8), stamp, lid, r['event_date']))
                    out['confirmed'] += 1
                else:
                    checks = r['checks'] + 1
                    cur.execute('UPDATE split_log SET checked_at=%s, checks=%s, recheck_after=%s WHERE listing_id=%s AND event_date=%s',
                                (stamp, checks, next_recheck(checks, today), lid, r['event_date']))
                    out['rechecked'] += 1
        conn.commit()
    return out
