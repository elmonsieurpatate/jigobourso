"""Rattrapage autonome : à chaque passage du cron, ce qui manque est cherché et redemandé, sans intervention, jusqu'à ce que ce soit comblé
ou que Yahoo ait prouvé qu'il ne le fournit pas.

Deux sources de retard, toutes deux retrouvées à partir des DONNÉES (un redémarrage après une panne n'a besoin d'aucune mémoire) :
  - clôtures quotidiennes : titres dont la dernière clôture est antérieure à la dernière séance publiée (`collect.daily_plan`) ;
  - barres de 15 min : séances, parmi TOUTES celles conservées (`collect.retention_sessions`, jamais plus que Yahoo ne fournit), où des données manquent
    vraiment (`collect.session_gaps`), plus les titres qui n'ont pas répondu pendant une collecte (`note_failed`).
`price_gaps` reflète la réalité des données à chaque vérification : une séance n'y est « réparée » que si ses données sont là, et une séance « non récupérable »
est revérifiée (si les données arrivent un jour, elle redevient réparée). Une séance n'est déclarée non récupérable que lorsque Yahoo a répondu à tous les
titres, plusieurs fois, plus de 24 h après la clôture, sans fournir les barres — avec les chiffres de sa réponse — ou lorsqu'elle est au-delà de sa profondeur.
Le registre `settings['catchup']` ne sert qu'à espacer les nouvelles tentatives (délai croissant) et à garder les titres encore à demander :
  intraday : {"MIC|AAAA-MM-JJ": {ids|null (null = toute la place), tries, first, last, note}}   daily : {id_cotation: {mic, day, n, last}}
Les collectes normales passent avant (voir `tasks.tick`) ; le rattrapage a un budget de temps par passage, s'interrompt entre deux lots de Yahoo et reprend
exactement où il s'est arrêté au passage suivant.
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
BUDGET_SECONDS = 150            # temps maximal de rattrapage par passage
CONFIRM_TRIES = 3               # réponses complètes de Yahoo, sans les barres, avant de conclure qu'il ne les fournit pas
CONFIRM_AFTER = datetime.timedelta(hours=24)    # et jamais avant 24 h après la clôture de la séance (Yahoo peut publier avec retard)
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
                       ON DUPLICATE KEY UPDATE state=VALUES(state), note=VALUES(note)""", (mic, day, state, collect.naive_utc(now), note[:160]))
    conn.commit()


def _rows(conn, mic):
    with conn.cursor() as cur:
        cur.execute('SELECT session_date, state FROM price_gaps WHERE mic=%s', (mic,))
        return {r['session_date']: r['state'] for r in cur.fetchall()}


def _depth(mic, day, aware):
    """Nombre de séances (jour courant compris, avec une séance de marge) entre `day` et maintenant : de quoi choisir la plage Yahoo."""
    today = hours._local(mic, aware).date()
    n, d = 0, day
    while d <= today:
        n += d.weekday() < 5
        d += datetime.timedelta(days=1)
    return n + 1


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
        e = led['intraday'][key] = {'ids': None if ids is None else sorted(set(ids)), 'tries': 0, 'first': _iso(now), 'last': EPOCH, 'note': 'titres sans réponse de Yahoo', 'src': 'failed'}
    save(conn, led)


def _give_up(conn, led, mic, day, entry, why, now):
    led['unrecoverable'] = ([{'kind': 'intraday', 'mic': mic, 'session': day.isoformat(), 'at': _iso(now), 'why': why, 'tries': entry.get('tries', 0)}] + led['unrecoverable'])[:30]
    _gap_row(conn, mic, day, 'unrecoverable', why, now)


def _plan_mic(conn, led, mic, aware, now, horizon, rows_state):
    """Réconcilie `price_gaps` avec les données de la place et renvoie la tâche de rattrapage due maintenant (ou None)."""
    examined = collect.recent_sessions(mic, aware, horizon)
    entries = {k.split('|')[1]: (k, e) for k, e in led['intraday'].items() if k.startswith(mic + '|')}
    oldest = min(examined) if examined else None
    for iso, (key, e) in list(entries.items()):                           # séance sortie de la rétention : la donnée n'est plus voulue, l'abandon est signalé
        day = datetime.date.fromisoformat(iso)
        if oldest and day < oldest:
            _give_up(conn, led, mic, day, e, f'séance sortie des {horizon} séances conservées sans avoir pu être complétée', now)
            del led['intraday'][key]
            del entries[iso]
    gaps = None
    if entries or now - _at(led['checked'].get(mic)) >= datetime.timedelta(minutes=CHECK_MINUTES):
        gaps = collect.session_gaps(conn, mic, aware, horizon)
        led['checked'][mic] = _iso(now)
    wanted = {}
    if gaps is not None:
        partial = {datetime.date.fromisoformat(iso) for iso, (_, e) in entries.items() if e['ids'] is not None}      # titres restant à demander : seule une réponse de Yahoo les résout
        for day, state in rows_state.items():                              # la table reflète les données : plus de trou = réparé, même si elle disait « non récupérable »
            if day not in gaps and state != 'repaired' and day in examined and day not in partial:
                _gap_row(conn, mic, day, 'repaired', 'données présentes', now)
        for iso, (key, e) in list(entries.items()):
            day = datetime.date.fromisoformat(iso)
            if day in examined and day not in gaps and e.get('src') == 'gap' and e['ids'] is None:
                del led['intraday'][key]
                del entries[iso]
        for day, note in gaps.items():
            if rows_state.get(day) == 'unrecoverable':
                continue                                                   # conclusion déjà établie par la réponse de Yahoo (revérifiée ci-dessus)
            depth = _depth(mic, day, aware)
            if collect.intraday_range(depth) is None:
                _give_up(conn, led, mic, day, {}, f'à {depth} séances en arrière : Yahoo ne fournit pas les barres de 15 minutes aussi loin ({collect.YAHOO_DEPTH_SESSIONS} séances)', now)
                continue
            key = f'{mic}|{day.isoformat()}'
            e = led['intraday'].setdefault(key, {'ids': None, 'tries': 0, 'first': _iso(now), 'last': EPOCH, 'note': note, 'src': 'gap'})
            e['note'] = note
            _gap_row(conn, mic, day, 'to_repair', note, now)
            wanted[day] = e
    for iso, (key, e) in entries.items():
        day = datetime.date.fromisoformat(iso)
        if day in examined:                                                # une séance pas encore publiée attend sa clôture
            wanted.setdefault(day, e)
    due = [d for d, e in wanted.items() if now >= _at(e['last']) + _backoff(e['tries'], RETRY)]
    if not due:
        return None
    ids = None if any(wanted[d]['ids'] is None for d in due) else sorted({i for d in due for i in wanted[d]['ids']})
    return {'mic': mic, 'sessions': sorted(due), 'ids': ids, 'last_try': min(_at(wanted[d]['last']) for d in due)}


def plan_intraday(conn, now):
    """Rattrapages de barres à lancer maintenant : [{'mic', 'sessions', 'ids' (None = toute la place)}], les moins récemment essayés d'abord
    (aucune place ne peut en affamer une autre). Vide si tout va bien ou si Yahoo est en pause. Une place en erreur n'empêche pas les autres."""
    aware, now = _aware(now), collect.naive_utc(now)
    led = load(conn)
    if led['cooldown_until'] and _at(led['cooldown_until']) > now:
        return []
    horizon = collect.retention_sessions(conn)
    tasks = []
    for mic in sorted({r['mic'] for r in collect.collection_set(conn)}):
        if not hours.known(mic):
            continue
        try:
            t = _plan_mic(conn, led, mic, aware, now, horizon, _rows(conn, mic))
        except Exception as e:                                             # noqa: BLE001
            conn.rollback()
            from engine.jobs import schedule                                # import tardif : schedule importe ce module
            schedule.record_error(conn, aware, f'rattrapage:{mic}', e)
            continue
        if t:
            tasks.append(t)
    save(conn, led)
    tasks.sort(key=lambda t: (t['last_try'], t['mic']))
    return tasks


def execute(conn, client, tasks, now, log):
    """Redemande aux titres concernés la plage Yahoo qui remonte jusqu'à la séance manquante, revérifie, et conserve ce qui reste à faire. Renvoie (ok, erreurs, résumé)."""
    aware, now = _aware(now), collect.naive_utc(now)
    t0 = time.monotonic()
    deadline = t0 + BUDGET_SECONDS
    fixed, still, given_up, errors, lines_total, postponed = [], [], [], 0, 0, 0
    for t in tasks:
        if time.monotonic() > deadline:
            postponed += 1                                                  # repris au prochain passage : rien n'est perdu, les données manquantes sont retrouvées
            continue
        mic = t['mic']
        rows = collect.collection_set(conn, mic)
        total = len(rows)
        if t['ids'] is not None:
            keep = set(t['ids'])
            rows = [r for r in rows if r['listing_id'] in keep]
        rng = collect.intraday_range(max(_depth(mic, d, aware) for d in t['sessions']))
        failed, unfetched, limited = [], [], False
        try:
            _, lines, _ = collect.collect_intraday(conn, client, rows, aware, range_=rng, failed=failed, deadline=deadline, unfetched=unfetched)
            lines_total += lines
        except RateLimited:
            limited = True
        except Exception as e:                                              # noqa: BLE001 — une place en erreur ne bloque pas les autres
            conn.rollback()
            errors += 1
            failed = [r['listing_id'] for r in rows]
            log('error', f'{mic} : {type(e).__name__}: {e}')
        gaps = collect.session_gaps(conn, mic, aware)
        led = load(conn)
        pending = sorted(set(failed) | set(unfetched))
        for day in t['sessions']:
            key = f'{mic}|{day.isoformat()}'
            e = led['intraday'].get(key)
            if e is None:
                continue
            if day not in gaps and not pending:
                del led['intraday'][key]
                _gap_row(conn, mic, day, 'repaired', f'comblé automatiquement ({collect.session_titles(conn, mic, day, [r["listing_id"] for r in collect.collection_set(conn, mic)])} titres avec barres)', now)
                fixed.append(f'{mic} {day}')
                continue
            if day not in gaps:                                             # comblée pour ce qui a été demandé ; le reste (titres sans réponse, lots non faits) suit
                e['ids'], e['note'] = pending, 'titres restant à demander'
            elif pending:
                e['ids'], e['note'] = pending, gaps[day]
            else:
                e['ids'], e['note'] = None, gaps[day]
            if not (unfetched or limited) or failed:                       # un arrêt faute de temps (ou 429) n'est pas une tentative échouée
                e['tries'] += 1
                e['last'] = _iso(now)
            complete_answer = not pending and day in gaps
            if complete_answer and e['tries'] >= CONFIRM_TRIES and now >= collect.settled_at(mic, day) + CONFIRM_AFTER:
                have = collect.session_titles(conn, mic, day, [r['listing_id'] for r in collect.collection_set(conn, mic)])
                _give_up(conn, led, mic, day, e, f'Yahoo a répondu pour les {total} titres, {e["tries"]} fois, sans fournir ces barres ({have} titres en ont) : {gaps[day]}', now)
                del led['intraday'][key]
                given_up.append(f'{mic} {day}')
                continue
            _gap_row(conn, mic, day, 'to_repair', e['note'], now)
            still.append(f'{mic} {day}')
            if not (unfetched or limited):
                log('warning', f'{mic} {day} : toujours incomplète après {e["tries"]} tentative(s) ({e["note"]}) ; nouvelle tentative automatique plus tard')
        save(conn, led)
        if limited:
            led = load(conn)
            led['cooldown_until'] = _iso(now + COOLDOWN)
            save(conn, led)
            raise RateLimited()
    summary = f'{len(fixed)} séance(s) comblée(s)' + (f' ({", ".join(fixed)})' if fixed else '') + f', {len(still)} encore à compléter, {lines_total} barres reçues'
    if given_up:
        summary += f', {len(given_up)} non récupérable(s) confirmée(s) par Yahoo ({", ".join(given_up)})'
    if postponed:
        summary += f', {postponed} place(s) reportée(s) au prochain passage'
    return len(fixed), errors, summary


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
            'last_check': _iso(max(checked)) if checked else None, 'sessions_kept': collect.retention_sessions(conn)}
