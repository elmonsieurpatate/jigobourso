"""Revue administrative des opérations suspectes. Aucun accès réseau et aucune transaction de portefeuille réécrite."""
import datetime
import math
from urllib.parse import urlparse

from engine.shared import settings
from . import splits

STATE = "CASE WHEN r.decision IN ('applied','rejected') THEN r.decision WHEN s.status='confirmed' THEN 'confirmed' ELSE 'pending' END"


def state(conn, request):
    view = request.get('state') or 'pending'
    if view not in ('pending', 'applied', 'rejected', 'confirmed', 'all'):
        raise ValueError('Statut inconnu')
    page = max(1, int(request.get('page') or 1))
    query = str(request.get('q') or '').strip()[:80]
    where, args = [], []
    if view != 'all':
        where.append(STATE + '=%s')
        args.append(view)
    if query:
        where.append('(l.symbol LIKE %s OR i.name LIKE %s OR i.isin LIKE %s)')
        args.extend(['%' + query + '%'] * 3)
    join = ' FROM split_log s JOIN listings l ON l.id=s.listing_id JOIN instruments i ON i.id=l.instrument_id LEFT JOIN split_reviews r ON r.listing_id=s.listing_id AND r.event_date=s.event_date'
    clause = ' WHERE ' + ' AND '.join(where) if where else ''
    with conn.cursor() as cur:
        cur.execute('SELECT ' + STATE + ' AS state,COUNT(*) AS n' + join + ' GROUP BY state')
        counts = {v['state']: int(v['n']) for v in cur.fetchall()}
        cur.execute('SELECT COUNT(*) AS n' + join + clause, args)
        total = int(cur.fetchone()['n'])
        pages = max(1, math.ceil(total / 40))
        page = min(page, pages)
        cur.execute('''SELECT s.listing_id,s.event_date,s.price_ratio,s.ratio AS proposed_ratio,s.status AS vendor_state,
                      s.detected_at,s.checked_at,s.checks,l.symbol,l.mic,l.currency,i.name,i.isin,
                      r.ratio AS reviewed_ratio,r.source_url,r.note,r.actor_id,r.updated_at,COALESCE(r.revision,0) AS revision,
                      ''' + STATE + ''' AS state,
                      (SELECT p.close_px FROM daily_prices p WHERE p.listing_id=s.listing_id AND p.price_date<s.event_date ORDER BY p.price_date DESC LIMIT 1) AS price_before,
                      (SELECT p.close_px FROM daily_prices p WHERE p.listing_id=s.listing_id AND p.price_date=s.event_date) AS price_after
                      ''' + join + clause + ' ORDER BY s.event_date DESC,s.listing_id LIMIT 40 OFFSET %s', args + [(page - 1) * 40])
        rows = cur.fetchall()
        ids = sorted({r['listing_id'] for r in rows})
        history = []
        if ids:
            cur.execute('SELECT * FROM split_review_history WHERE listing_id IN (' + ','.join(['%s'] * len(ids)) + ') ORDER BY id DESC LIMIT 200', ids)
            history = cur.fetchall()
    for row in rows:
        row['history'] = [h for h in history if h['listing_id'] == row['listing_id'] and h['event_date'] == row['event_date']][:5]
    return {'rows': rows, 'counts': counts, 'total': total, 'page': page, 'pages': pages,
            'recompute_pending': bool(settings.get(conn, 'split_metrics_pending', False))}


def scan(conn, request):
    return {'detected': splits.detect(conn, datetime.datetime.now(datetime.timezone.utc))}


def _ratio(request):
    try:
        old = float(request.get('old_shares'))
        new = float(request.get('new_shares'))
        ratio = new / old
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        raise ValueError('Indiquez des nombres de parts positifs') from None
    if not all(math.isfinite(v) and v > 0 for v in (old, new, ratio)) or not 0.00000001 <= ratio <= 1000000 or abs(ratio - 1) < 1e-8:
        raise ValueError('Le ratio du split doit être positif et différent de 1')
    return round(ratio, 8)


def decide(conn, request):
    action = request.get('decision')
    if action not in ('applied', 'rejected', 'pending'):
        raise ValueError('Décision inconnue')
    try:
        lid, actor = int(request['listing_id']), int(request['actor_id'])
        day = datetime.date.fromisoformat(request['event_date'])
        revision = int(request.get('revision', 0))
    except (KeyError, TypeError, ValueError):
        raise ValueError('Titre, date ou révision invalide') from None
    if lid <= 0 or actor <= 0 or day > datetime.date.today():
        raise ValueError('Titre, administrateur ou date invalide')
    note = str(request.get('note') or '').strip()
    source = str(request.get('source_url') or '').strip()
    if len(note) > 1000 or len(source) > 1000 or any(ord(c) < 32 for c in source):
        raise ValueError('Source ou commentaire trop long ou invalide')
    if source:
        parsed = urlparse(source)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('La source doit être une URL http ou https')
    ratio = _ratio(request) if action == 'applied' else None
    if action == 'applied' and not source and len(note) < 3:
        raise ValueError('Ajoutez une source ou une explication avant de confirmer le split')
    with conn.cursor() as cur:
        cur.execute("SELECT GET_LOCK('jigo:job:compute',0) AS got")
        if not cur.fetchone()['got']:
            raise ValueError('Un calcul est en cours. Réessayez après sa fin.')
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM split_log WHERE listing_id=%s AND event_date=%s FOR UPDATE', (lid, day))
            event = cur.fetchone()
            if not event:
                raise ValueError('Split suspect introuvable. Actualisez la page.')
            cur.execute('SELECT * FROM split_reviews WHERE listing_id=%s AND event_date=%s FOR UPDATE', (lid, day))
            previous = cur.fetchone()
            if previous and previous['decision'] == 'applied' and action == 'applied' and float(previous['ratio']) == ratio:
                conn.rollback()
                return {'changed': False, 'decision': action}
            if (previous['revision'] if previous else 0) != revision:
                raise ValueError('Cette décision a changé. Actualisez la page avant de continuer.')
            if event['status'] == 'confirmed':
                raise ValueError('Ce split est déjà confirmé. Il ne peut pas être modifié depuis cette page.')
            if action == 'applied':
                if abs(float(event['price_ratio']) * ratio - 1) > splits.RATIO_TOLERANCE:
                    raise ValueError('Le ratio saisi n’explique pas le saut observé. Vérifiez le sens et le nombre de parts.')
                cur.execute("SELECT kind,ratio FROM corporate_events WHERE listing_id=%s AND event_date=%s AND kind IN ('split','reverse_split') FOR UPDATE", (lid, day))
                existing = cur.fetchall()
                if any(abs(float(e['ratio'] or 0) - ratio) > 1e-7 for e in existing):
                    raise ValueError('Une autre opération existe déjà à cette date. Aucun changement effectué.')
                cur.execute('INSERT INTO corporate_events(listing_id,event_date,kind,ratio) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE ratio=VALUES(ratio)',
                            (lid, day, 'split' if ratio > 1 else 'reverse_split', ratio))
                cur.execute("UPDATE split_log SET status='confirmed',ratio=%s,checked_at=UTC_TIMESTAMP(),recheck_after=NULL WHERE listing_id=%s AND event_date=%s", (ratio, lid, day))
                # La demande est conservée dans la même transaction ; le cron reprend un lancement interrompu.
                cur.execute("INSERT INTO settings(name,value_json,updated_at) VALUES ('split_metrics_pending','true',UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE value_json='true',updated_at=UTC_TIMESTAMP()")
            note = note or ('Refus manuel du split' if action == 'rejected' else 'Remis en attente')
            values = (lid, day, action, ratio, source or None, note, actor)
            cur.execute('''INSERT INTO split_reviews(listing_id,event_date,decision,ratio,source_url,note,actor_id,revision,updated_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,1,UTC_TIMESTAMP())
                           ON DUPLICATE KEY UPDATE decision=VALUES(decision),ratio=VALUES(ratio),source_url=VALUES(source_url),note=VALUES(note),actor_id=VALUES(actor_id),revision=revision+1,updated_at=UTC_TIMESTAMP()''', values)
            cur.execute('''INSERT INTO split_review_history(listing_id,event_date,decision,ratio,source_url,note,actor_id,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP())''', values)
        conn.commit()
        return {'changed': True, 'decision': action, 'recompute_pending': action == 'applied'}
    except Exception:
        conn.rollback()
        raise
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK('jigo:job:compute')")
