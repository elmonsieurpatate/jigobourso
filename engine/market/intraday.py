"""Vue intrajournalière d'un titre : ses deux dernières séances de cotation, en barres de 15 minutes.

Principes : aucune interpolation (un créneau sans donnée reste un trou signalé) ; les séances sont celles de la place, dans son fuseau
(les jours fériés et week-ends n'existent tout simplement pas) ; une barre est « définitive » quand son créneau est terminé.
Les bougies complètes (ouverture, haut, bas, volume) sont lues chez Yahoo (API chart) à la consultation et conservées en base.
"""
import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

from . import hours
from .collect import slot_of

SESSIONS = 2
COOLDOWN_MINUTES = 10        # pas de nouvel appel Yahoo pour un même titre avant ce délai
DELAY_FLAG_MINUTES = 20      # au-delà, une séance en cours est signalée comme différée


def _utc(dt):
    return dt.replace(tzinfo=datetime.timezone.utc)


def session_window(mic, day):
    """(ouverture, clôture) régulières de la séance locale `day`, en UTC naïf."""
    tzname, opens, closes = hours.HOURS[mic]
    tz = ZoneInfo(tzname)
    start = datetime.datetime.combine(day, opens, tz).astimezone(datetime.timezone.utc).replace(tzinfo=None)
    end = datetime.datetime.combine(day, closes, tz).astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return start, end


def expected_slot_starts(mic, day):
    start, end = session_window(mic, day)
    out, t = [], start
    while t < end:
        out.append(t)
        t += datetime.timedelta(minutes=hours.SLOT_MINUTES)
    return out


def local_day(slot, tzname):
    return _utc(slot).astimezone(ZoneInfo(tzname)).date()


def tz_label(tzname, day):
    t = datetime.datetime.combine(day, datetime.time(12, 0), ZoneInfo(tzname))
    off = t.utcoffset()
    minutes = int(off.total_seconds() // 60)
    return f"{t.tzname()} (UTC{'+' if minutes >= 0 else '-'}{abs(minutes) // 60}{':%02d' % (abs(minutes) % 60) if minutes % 60 else ''})"


def build_view(mic, bars, now, sessions=SESSIONS):
    """bars : [(slot_utc_naïf, open, high, low, close, volume, is_final)] triées. Renvoie les `sessions` dernières séances avec bars.

    Chaque séance : barres, créneaux attendus et absents, complétude, en cours ou non, résumé (ouverture, clôture, haut, bas, volume)."""
    tzname = hours.HOURS[mic][0]
    by_day = {}
    for b in bars:
        by_day.setdefault(local_day(b[0], tzname), []).append(b)
    now_naive = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    out = []
    for day in sorted(by_day)[-sessions:]:
        rows = sorted(by_day[day], key=lambda b: b[0])
        start, end = session_window(mic, day)
        expected = expected_slot_starts(mic, day)
        present = {b[0] for b in rows}
        in_progress = start <= now_naive < end
        due = [s for s in expected if s + datetime.timedelta(minutes=hours.SLOT_MINUTES) <= now_naive]
        missing = [s for s in due if s not in present]
        outside = [b for b in rows if not (start <= b[0] < end)]
        first, last = rows[0], rows[-1]
        highs = [b[2] if b[2] is not None else b[4] for b in rows]
        lows = [b[3] if b[3] is not None else b[4] for b in rows]
        vols = [b[5] for b in rows]
        full_volume = all(v is not None for v in vols)
        opening = first[1] if first[1] is not None else first[4]
        out.append({
            'date': day.isoformat(), 'weekday': day.strftime('%A'), 'tz_label': tz_label(tzname, day),
            'open_utc': start.isoformat() + 'Z', 'close_utc': end.isoformat() + 'Z',
            'expected': len(expected), 'count': len(rows), 'in_progress': in_progress,
            'complete': not missing and not in_progress and len(rows) >= len(expected),
            'missing': [s.isoformat() + 'Z' for s in missing], 'outside_regular': [b[0].isoformat() + 'Z' for b in outside],
            'bars': [[b[0].isoformat() + 'Z', b[1], b[2], b[3], b[4], b[5], bool(b[6])] for b in rows],
            'summary': {'open': opening, 'close': last[4], 'high': max(highs), 'low': min(lows),
                        'change_pct': 100 * (last[4] / opening - 1) if opening else None,
                        'volume': sum(v for v in vols if v is not None) if any(v is not None for v in vols) else None,
                        'volume_complete': full_volume, 'ohlc_complete': all(b[1] is not None and b[2] is not None and b[3] is not None for b in rows)}})
    return out


def _load(conn, listing_id, now, days=9):
    since = now.astimezone(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute("""SELECT slot_start, open_px, high_px, low_px, close_px, volume, is_final FROM intraday_prices
                       WHERE listing_id=%s AND slot_start>=%s ORDER BY slot_start""", (listing_id, since))
        f = lambda v: None if v is None else float(v)
        return [(r['slot_start'], f(r['open_px']), f(r['high_px']), f(r['low_px']), float(r['close_px']), r['volume'], r['is_final']) for r in cur.fetchall()]


def store_chart(conn, listing_id, bars, now):
    """Enregistre des bougies Yahoo : complète les barres existantes sans créer de doublon (clé listing + créneau)."""
    cutoff = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    slots = {}
    for ts, o, h, l, c, v in bars:
        slots[slot_of(ts)] = (o, h, l, c, v)          # plusieurs barres dans un créneau : la dernière gagne
    rows = [(listing_id, s, c, 1 if s + datetime.timedelta(minutes=hours.SLOT_MINUTES) <= cutoff else 0, o, h, l, v) for s, (o, h, l, c, v) in sorted(slots.items())]
    with conn.cursor() as cur:
        cur.executemany("""INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final,open_px,high_px,low_px,volume) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON DUPLICATE KEY UPDATE close_px=IF(is_final=1 AND VALUES(is_final)=0, close_px, VALUES(close_px)), is_final=GREATEST(is_final, VALUES(is_final)),
                             open_px=VALUES(open_px), high_px=VALUES(high_px), low_px=VALUES(low_px), volume=VALUES(volume)""", rows)
    conn.commit()
    return len(rows)


def _cooldown_key(listing_id):
    return hashlib.sha1(f'intraday:{listing_id}'.encode()).hexdigest()


def _recently_fetched(conn, listing_id, now):
    with conn.cursor() as cur:
        cur.execute('SELECT built_at FROM result_cache WHERE cache_key=%s', (_cooldown_key(listing_id),))
        r = cur.fetchone()
    return bool(r) and now.astimezone(datetime.timezone.utc).replace(tzinfo=None) - r['built_at'] < datetime.timedelta(minutes=COOLDOWN_MINUTES)


def _mark_fetched(conn, listing_id, now):
    with conn.cursor() as cur:
        cur.execute("REPLACE INTO result_cache(cache_key, data_version, built_at, payload) VALUES (%s,'intraday-fetch',%s,'{}')",
                    (_cooldown_key(listing_id), now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)))
    conn.commit()


def _needs_fetch(view):
    if len(view) < SESSIONS:
        return True
    return any((s['missing'] and not s['in_progress']) or not s['summary']['ohlc_complete'] or not s['summary']['volume_complete'] or s['in_progress'] for s in view)


def view(conn, listing_id, now=None, client=None, fetch=True):
    """Résultat complet pour la page : séances, source, fraîcheur, avertissements."""
    now = now or hours.utcnow()
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.symbol, l.mic, l.currency, i.name, p.currency AS price_currency FROM listings l JOIN instruments i ON i.id=l.instrument_id
                       LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.id=%s""", (listing_id,))
        l = cur.fetchone()
    if not l:
        raise ValueError('Titre introuvable')
    if l['mic'] not in hours.HOURS:
        return {'supported': False, 'note': 'Horaires de cette place non connus : pas de vue intrajournalière.'}
    notes, source, fetched_at = [], 'stockée', None
    sessions = build_view(l['mic'], _load(conn, listing_id, now), now)
    if fetch and client is not None and _needs_fetch(sessions) and not _recently_fetched(conn, listing_id, now):
        try:
            data = client.chart(l['symbol'], '5d', '15m')
            if data and data['bars']:
                store_chart(conn, listing_id, data['bars'], now)
                source, fetched_at = 'Yahoo Finance (API chart), enregistrée', now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0).isoformat() + 'Z'
                sessions = build_view(l['mic'], _load(conn, listing_id, now), now)
            else:
                notes.append('Yahoo Finance n’a renvoyé aucune barre de 15 minutes pour ce titre.')
        except Exception as e:      # réseau, limitation, symbole inconnu : on montre ce qui est stocké
            notes.append('Yahoo Finance indisponible pour le moment (' + str(e)[:80] + ') : données stockées affichées.')
        _mark_fetched(conn, listing_id, now)
    now_naive = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    last_bar = None
    if sessions and sessions[-1]['bars']:
        last_bar = datetime.datetime.fromisoformat(sessions[-1]['bars'][-1][0].rstrip('Z'))
    lag = max(0, int((now_naive - (last_bar + datetime.timedelta(minutes=hours.SLOT_MINUTES))).total_seconds() // 60)) if last_bar else None
    live = bool(sessions and sessions[-1]['in_progress'])
    if live and lag is not None and lag > DELAY_FLAG_MINUTES:
        notes.append(f'Données différées : dernière barre il y a {lag} minutes alors que la place est ouverte.')
    if len(sessions) < SESSIONS:
        notes.append('Moins de deux séances disponibles pour ce titre.')
    for s in sessions:
        if s['missing']:
            notes.append(f"Séance du {s['date']} : {len(s['missing'])} créneau(x) de 15 min sans donnée (trou de source, journée écourtée ou suspension de cotation) ; ils ne sont pas inventés.")
        if not s['summary']['volume_complete']:
            notes.append(f"Séance du {s['date']} : volumes absents ou partiels.")
    return {'supported': True, 'listing': {'id': l['id'], 'symbol': l['symbol'], 'name': l['name'], 'mic': l['mic'], 'market': hours.HOURS[l['mic']][0]},
            'tz': hours.HOURS[l['mic']][0], 'currency': l['price_currency'] or l['currency'], 'interval_minutes': hours.SLOT_MINUTES,
            'sessions': sessions, 'source': source, 'fetched_at': fetched_at, 'now_utc': now_naive.isoformat() + 'Z', 'market_open': hours.is_open(l['mic'], now),
            'last_bar_utc': last_bar.isoformat() + 'Z' if last_bar else None, 'lag_minutes': lag, 'delayed': bool(live and lag is not None and lag > DELAY_FLAG_MINUTES),
            'notes': list(dict.fromkeys(notes))}
