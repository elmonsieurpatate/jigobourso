"""Rattrapage autonome : à chaque passage du cron, ce qui manque est cherché et redemandé, sans intervention, jusqu'à ce que ce soit comblé.

Deux sources de retard, toutes deux retrouvées à partir des DONNÉES (un redémarrage après une panne n'a besoin d'aucune mémoire) :
  - clôtures quotidiennes : titres dont la dernière clôture est antérieure à la dernière séance publiée (`collect.daily_plan`) ;
  - barres de 15 min : séances (parmi les deux conservées) où des créneaux manquent VRAIMENT (`collect.session_gaps`, qui ne confond pas un créneau
    sans transaction avec une donnée absente), plus les titres qui n'ont pas répondu pendant une collecte (`note_failed`).
Le registre `settings['catchup']` ne sert qu'à espacer les nouvelles tentatives (délai croissant) et à afficher l'état dans l'administration :
  intraday : {"MIC|AAAA-MM-JJ": {ids|null, tries, first, last, note}}   daily : {id_cotation: {mic, day, n, last}}
  unrecoverable : séances abandonnées (hors des deux séances conservées, ou plus anciennes que ce que Yahoo fournit en 15 min : 5 jours)
Les collectes normales passent avant (voir `tasks.tick`) ; le rattrapage a un budget de temps par passage et reprend au passage suivant.
"""
import datetime
import time

from engine.market import collect, hours
from engine.market.yahoo import RateLimited
from engine.shared import settings

KEY = 'catchup'
CHECK_MINUTES = 10              # une place est revérifiée au plus toutes les 10 minutes (sauf rattrapage en cours)
RETRY = (5, 120)                # délai entre deux tentatives sur une séance : 5, 10, 20… jusqu'à 120 minutes
DAILY_RETRY = (10, 360)         # idem pour une clôture quotidienne introuvable
DAILY_GIVE_UP = datetime.timedelta(hours=24)
COOLDOWN = datetime.timedelta(minutes=15)       # après un refus de Yahoo (429)
MAX_AGE_DAYS = 5                # Yahoo ne fournit des barres de 15 min que sur les 5 derniers jours
BUDGET_SECONDS = 150            # temps maximal de rattrapage par passage
SESSIONS = 2                    # séances de barres de 15 min conservées et surveillées
EPOCH = '2000-01-01 00:00:00'


def _aware(now):
    return now if now.tzinfo else now.replace(tzinfo=datetime.timezone.utc)


def _iso(v):
    return v.replace(microsecond=0).isoformat(sep=' ')


def _at(v):
    return datetime.datetime.fromisoformat(v or EPOCH)


def _backoff(n, lo_hi):
    lo, hi = lo_hi
    return datetime.timedelta(minutes=min(hi, lo * 2 ** min(n, 10)))


def load(conn):
    led = settings.get(conn, KEY, {})
    for k, v in (('intraday', {}), ('daily', {}), ('checked', {}), ('unrecoverable', []), ('cooldown_until', None)):
        led.setdefault(k, v)
    return led


def save(conn, led):
    settings.put(conn, KEY, led)


def _gap_row(conn, mic, day, state, note, now):
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO price_gaps(mic,session_date,state,detected_at,note) VALUES (%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE state=VALUES(state), note=VALUES(note)""", (mic, day, state, collect.naive_utc(now), note[:200]))
    conn.commit()


# ───────── barres de 15 minutes ─────────
def note_failed(conn, mic, session, ids, now):
    """Mémorise les titres (ids=None : toute la place) qui n'ont pas répondu pendant une collecte de la séance `session`."""
    now = collect.naive_utc(now)
    led = load(conn)
    key = f'{mic}|{session.isoformat()}'
    e = led['intraday'].get(key)
    if e:
        e['ids'] = None if (e['ids'] is None or ids is None) else sorted(set(e['ids']) | set(ids))
    else:
        e = led['intraday'][key] = {'ids': None if ids is None else sorted(set(ids)), 'tries': 0, 'first': _iso(now), 'last': _iso(now), 'note': 'titres sans réponse de Yahoo'}
    save(conn, led)


def _lost(led, mic, day):
    return any(u['mic'] == mic and u['session'] == day.isoformat() for u in led['unrecoverable'])


def _give_up(conn, led, mic, day, entry, why, now):
    led['unrecoverable'] = ([{'kind': 'intraday', 'mic': mic, 'session': day.isoformat(), 'at': _iso(now), 'why': why, 'tries': entry.get('tries', 0)}] + led['unrecoverable'])[:30]
    _gap_row(conn, mic, day, 'unrecoverable', why, now)


def plan_intraday(conn, now):
    """Rattrapages de barres à lancer maintenant : [{'mic', 'sessions', 'ids' (None = toute la place)}]. Vide si tout va bien ou si Yahoo est en pause."""
    aware, now = _aware(now), collect.naive_utc(now)
    led = load(conn)
    if led['cooldown_until'] and _at(led['cooldown_until']) > now:
        return []
    tasks = []
    for mic in sorted({r['mic'] for r in collect.collection_set(conn)}):
        if not hours.known(mic):
            continue
        recent = collect.recent_sessions(mic, aware, SESSIONS)
        current = hours.session_date(mic, aware)
        entries = {k.split('|')[1]: (k, e) for k, e in led['intraday'].items() if k.startswith(mic + '|')}
        for iso, (key, e) in list(entries.items()):                       # séances sorties des deux conservées (ou trop anciennes pour Yahoo) : abandon signalé
            day = datetime.date.fromisoformat(iso)
            if _lost(led, mic, day):
                del led['intraday'][key]
                del entries[iso]
            elif day not in recent and day != current:
                _give_up(conn, led, mic, day, e, 'séance sortie des deux séances conservées sans avoir pu être complétée (Yahoo n’a pas fourni ces barres)', now)
                del led['intraday'][key]
                del entries[iso]
            elif (now.date() - day).days > MAX_AGE_DAYS:
                _give_up(conn, led, mic, day, e, f'plus de {MAX_AGE_DAYS} jours : Yahoo ne fournit plus ces barres de 15 minutes', now)
                del led['intraday'][key]
                del entries[iso]
        gaps = {}
        if entries or now - _at(led['checked'].get(mic)) >= datetime.timedelta(minutes=CHECK_MINUTES):
            gaps = collect.session_gaps(conn, mic, aware, 6, report=SESSIONS)
            led['checked'][mic] = _iso(now)
        wanted = {}
        for day, note in gaps.items():
            if _lost(led, mic, day):
                continue
            if (now.date() - day).days > MAX_AGE_DAYS:
                _give_up(conn, led, mic, day, {}, f'plus de {MAX_AGE_DAYS} jours : Yahoo ne fournit plus ces barres de 15 minutes', now)
                continue
            key = f'{mic}|{day.isoformat()}'
            e = led['intraday'].setdefault(key, {'ids': None, 'tries': 0, 'first': _iso(now), 'last': EPOCH, 'note': note})
            e['ids'], e['note'] = None, note                              # un trou de la place : tous ses titres
            _gap_row(conn, mic, day, 'to_repair', note, now)
            wanted[day] = e
        for iso, (key, e) in entries.items():
            day = datetime.date.fromisoformat(iso)
            if day in recent:                                              # une séance pas encore publiée attend sa clôture
                wanted.setdefault(day, led['intraday'][key])
        due = [d for d, e in wanted.items() if now >= _at(e['last']) + _backoff(e['tries'], RETRY)]
        if due:
            ids = None if any(wanted[d]['ids'] is None for d in due) else sorted({i for d in due for i in wanted[d]['ids']})
            tasks.append({'mic': mic, 'sessions': sorted(due), 'ids': ids})
    save(conn, led)
    return tasks


def execute(conn, client, tasks, now, log):
    """Redemande 5 jours de barres aux titres concernés, revérifie, et conserve ce qui reste manquant. Renvoie (ok, erreurs, résumé)."""
    aware, now = _aware(now), collect.naive_utc(now)
    t0, fixed, still, skipped, lines_total = time.monotonic(), [], [], 0, 0
    for t in tasks:
        if time.monotonic() - t0 > BUDGET_SECONDS:
            skipped += 1                                                    # repris au passage suivant (rien n'est perdu : les données manquantes sont retrouvées)
            continue
        mic = t['mic']
        rows = collect.collection_set(conn, mic)
        if t['ids'] is not None:
            keep = set(t['ids'])
            rows = [r for r in rows if r['listing_id'] in keep]
        failed = []
        try:
            _, lines, _ = collect.collect_intraday(conn, client, rows, aware, range_='5d', failed=failed)
        except RateLimited:
            led = load(conn)
            led['cooldown_until'] = _iso(now + COOLDOWN)
            save(conn, led)
            raise
        lines_total += lines
        gaps = collect.session_gaps(conn, mic, aware, 6, report=SESSIONS)
        led = load(conn)
        for day in t['sessions']:
            key = f'{mic}|{day.isoformat()}'
            e = led['intraday'].get(key)
            if e is None:
                continue
            if day in gaps:
                e['ids'], e['note'] = None, gaps[day]
            elif failed:
                e['ids'] = sorted(set(failed))
            else:
                del led['intraday'][key]
                _gap_row(conn, mic, day, 'repaired', 'comblé automatiquement', now)
                fixed.append(f'{mic} {day}')
                continue
            e['tries'] += 1
            e['last'] = _iso(now)
            _gap_row(conn, mic, day, 'to_repair', e['note'], now)
            still.append(f'{mic} {day}')
            log('warning', f'{mic} {day} : toujours incomplète après {e["tries"]} tentative(s) ({e["note"]}) ; nouvelle tentative automatique plus tard')
        save(conn, led)
    summary = f'{len(fixed)} séance(s) comblée(s)' + (f' ({", ".join(fixed)})' if fixed else '') + f', {len(still)} encore à compléter, {lines_total} barres reçues'
    if skipped:
        summary += f', {skipped} place(s) reportée(s) au prochain passage'
    return len(fixed), len(still), summary


# ───────── clôtures quotidiennes ─────────
def daily_due(conn, mic, rows, now):
    """Ids des titres dont la dernière clôture publiée manque et qu'il est temps de redemander (délai croissant, abandon après 24 h) ; None si rien."""
    aware, now = _aware(now), collect.naive_utc(now)
    plan, _ = collect.daily_plan(conn, rows, aware)
    needed = {r['listing_id'] for group in plan.values() for r in group}
    if not needed:
        return None
    day = collect.latest_settled(mic, aware)
    published = collect.settled_at(mic, day)
    attempts = load(conn)['daily']
    due = set()
    for lid in needed:
        a = attempts.get(str(lid))
        if a and a['day'] == day.isoformat():
            if now > published + DAILY_GIVE_UP or now < _at(a['last']) + _backoff(a['n'], DAILY_RETRY):
                continue
        due.add(lid)
    return due or None


def daily_after(conn, mic, ids, now):
    """Après une collecte quotidienne : retient les titres dont la dernière clôture manque toujours, oublie ceux qui sont à jour."""
    aware, now = _aware(now), collect.naive_utc(now)
    ids = list(ids)
    if not ids:
        return
    day = collect.latest_settled(mic, aware)
    last = {}
    with conn.cursor() as cur:
        for i in range(0, len(ids), 1000):
            part = ids[i:i + 1000]
            cur.execute(f"SELECT listing_id, MAX(price_date) d FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) GROUP BY listing_id", part)
            last.update({r['listing_id']: r['d'] for r in cur.fetchall()})
    led = load(conn)
    for lid in ids:
        if last.get(lid) is None or last[lid] < day:
            a = led['daily'].get(str(lid))
            n = a['n'] + 1 if a and a['day'] == day.isoformat() else 1
            led['daily'][str(lid)] = {'mic': mic, 'day': day.isoformat(), 'n': n, 'last': _iso(now)}
        else:
            led['daily'].pop(str(lid), None)
    keep_from = (now - datetime.timedelta(days=7)).date().isoformat()
    led['daily'] = {k: v for k, v in led['daily'].items() if v['day'] >= keep_from}
    save(conn, led)


# ───────── état pour l'administration ─────────
def status(conn, now):
    now = collect.naive_utc(now)
    led = load(conn)
    open_ = []
    for key, e in sorted(led['intraday'].items()):
        mic, day = key.split('|')
        open_.append({'kind': 'intraday', 'mic': mic, 'session': day, 'titles': None if e['ids'] is None else len(e['ids']), 'tries': e['tries'], 'since': e['first'],
                      'last_try': e['last'] if e['last'] != EPOCH else None, 'next_try': _iso(max(now, _at(e['last']) + _backoff(e['tries'], RETRY))), 'note': e['note']})
    waiting, given_up, sample = 0, 0, []
    for lid, a in led['daily'].items():
        if now > collect.settled_at(a['mic'], datetime.date.fromisoformat(a['day'])) + DAILY_GIVE_UP:
            given_up += 1
        else:
            waiting += 1
        if len(sample) < 8:
            sample.append(lid)
    symbols = []
    if sample:
        with conn.cursor() as cur:
            cur.execute(f"SELECT symbol, mic FROM listings WHERE id IN ({','.join(['%s'] * len(sample))})", [int(x) for x in sample])
            symbols = [f'{r["symbol"]} ({r["mic"]})' for r in cur.fetchall()]
    checked = [_at(v) for v in led['checked'].values()]
    return {'open': open_, 'daily': {'waiting': waiting, 'given_up': given_up, 'sample': symbols}, 'unrecoverable': led['unrecoverable'][:10],
            'cooldown_until': led['cooldown_until'] if led['cooldown_until'] and _at(led['cooldown_until']) > now else None,
            'last_check': _iso(max(checked)) if checked else None, 'sessions_kept': SESSIONS}
