"""Splits et regroupements non ajustés dans l'historique.

Yahoo corrige rétroactivement ses historiques d'un split, mais nous ne redemandons jamais ce que nous avons déjà : après un split, nos anciennes clôtures
restent à l'ancienne échelle et la série montre un faux saut. On ne peut pas décider seul si un saut est un split (à corriger) ou un vrai mouvement (à garder) :
le fournisseur tranche.

1. `detect` repère les sauts de cours qui ressemblent à un ratio usuel (×2, ÷2, ÷10, ×3/2…) et les note dans `split_log` (statut « detected ») ;
   chaque nouveau saut programme UNE redemande de l'historique complet du titre (`listings.next_daily_check`).
2. La collecte quotidienne redemande cet historique (`due_ids`, utilisé par `collect.daily_plan`) : Yahoo renvoie les cours ajustés, qui écrasent les nôtres.
3. `resolve` regarde ensuite le même saut : disparu = split confirmé (« confirmed », l'historique est maintenant à l'échelle actuelle) ;
   toujours là = vrai mouvement de cours (« real_move », rien n'est corrigé et le titre reste « non évaluable » sur les fenêtres qui le traversent).
Une chute réelle de 50 % n'est donc jamais « corrigée » : seul le fournisseur peut ajuster. Sans redemande, rien n'est modifié.
"""
import datetime

import pymysql.err

from engine.analytics.series import BREAK_RATIO

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


def detect(conn, now):
    """Note les nouveaux sauts qui ressemblent à un split et programme la redemande de l'historique. Renvoie le nombre de nouveaux sauts."""
    if not available(conn):
        return 0
    today = now.date() if isinstance(now, datetime.datetime) else now
    stamp = now.replace(microsecond=0, tzinfo=None) if isinstance(now, datetime.datetime) else datetime.datetime.combine(now, datetime.time())
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
                cur.execute('UPDATE listings SET next_daily_check=%s WHERE id=%s AND next_daily_check IS NULL', (today, r['listing_id']))
            new += 1
    conn.commit()
    return new


def due_ids(conn, ids, today):
    """Parmi `ids`, les cotations dont l'historique complet doit être redemandé (saut à vérifier auprès du fournisseur)."""
    due = []
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            cur.execute(f"SELECT id FROM listings WHERE next_daily_check IS NOT NULL AND next_daily_check<=%s AND id IN ({','.join(['%s'] * len(part))})", [today] + part)
            due += [r['id'] for r in cur.fetchall()]
    return due


def available(conn):
    """La table split_log existe-t-elle (entre le transfert du code et la migration, elle peut manquer) ?"""
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM split_log LIMIT 1')
        return True
    except pymysql.err.ProgrammingError:
        conn.rollback()
        return False


def resolve(conn, ids, now):
    """Après la redemande : chaque saut « detected » de ces cotations devient « confirmed » (disparu) ou « real_move » (toujours là). Efface la programmation."""
    if not available(conn):
        return {'confirmed': 0, 'real_move': 0}
    stamp = now.replace(microsecond=0, tzinfo=None) if isinstance(now, datetime.datetime) else datetime.datetime.combine(now, datetime.time())
    counts = {'confirmed': 0, 'real_move': 0}
    for lid in ids:
        with conn.cursor() as cur:
            cur.execute("SELECT event_date FROM split_log WHERE listing_id=%s AND status='detected'", (lid,))
            events = [r['event_date'] for r in cur.fetchall()]
        for day in events:
            pair = _pair(conn, lid, day)
            if pair is None:
                continue                                                       # séance disparue de l'historique : on reverra plus tard
            status = 'real_move' if is_break(pair[0] / pair[1]) else 'confirmed'
            with conn.cursor() as cur:
                cur.execute('UPDATE split_log SET status=%s, checked_at=%s WHERE listing_id=%s AND event_date=%s', (status, stamp, lid, day))
            counts[status] += 1
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = list(ids)[i:i + 2000]
            cur.execute(f"UPDATE listings SET next_daily_check=NULL WHERE id IN ({','.join(['%s'] * len(part))})", part)
    conn.commit()
    return counts


def postpone(conn, ids, day):
    """Reporte la redemande de ces cotations au jour `day` (le fournisseur n'a pas répondu)."""
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = list(ids)[i:i + 2000]
            cur.execute(f"UPDATE listings SET next_daily_check=%s WHERE id IN ({','.join(['%s'] * len(part))})", [day] + part)
    conn.commit()
