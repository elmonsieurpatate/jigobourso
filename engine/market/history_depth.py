"""Profondeur permanente de l'historique quotidien : 1 260 séances (cinq ans de bourse) pour chaque titre de l'univers, quelles que soient les périodes actives des stratégies.

Conserver les cours et calculer les scores sont deux besoins distincts : ce module ne connaît aucune stratégie et ne calcule rien. Les Scores 1 et 2 ne lisent que les
séances de leurs périodes actives ; avoir 1 260 séances en base ne change aucune note.

Principes
  * La demande à Yahoo (point d'accès « chart », un appel par titre) se déduit des SÉANCES attendues par le calendrier de la place, depuis la première séance manquante moins une
    marge, par dates (period1/period2) : cinq années civiles ne suffisent pas toujours à couvrir 1 260 séances.
  * Seuls les jours absents sont insérés (INSERT IGNORE : une clôture existante n'est jamais modifiée) ; les volumes vides sont complétés (UPDATE ... WHERE volume IS NULL).
  * Le registre `history_state` distingue : complete (1 260 séances présentes), recent (titre plus jeune que la profondeur : Yahoo n'a rien de plus ancien), incomplete (Yahoo a omis
    des jours), unavailable (rien chez Yahoo), error (échec, repris). Un titre sans ligne dans le registre est à traiter : c'est ce qui fait qu'un nouveau titre reçoit son historique complet.
  * Une séance où presque aucun titre de la place n'a de barre est une fermeture exceptionnelle inconnue du calendrier (ex. 9 janvier 2025 à Wall Street), pas un trou.
"""

import datetime
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from engine.shared import settings

from . import hours
from .yahoo import RateLimited, YahooError, local_date

HISTORY_SESSIONS = 1260  # profondeur de référence, en séances (la plus longue période de score)
HISTORY_CLOSES = HISTORY_SESSIONS + 1  # clôtures nécessaires : une période de n séances mesure n variations entre n+1 clôtures (la première sert de base)
CLOSES_SETTING = 'history_closes'  # profondeur en clôtures à laquelle le registre a été établi : un changement de définition fait réexaminer les titres « complets"
KEEP_DAYS = 2000  # rétention des clôtures : 1 260 séances ≈ 1 830 à 1 920 jours calendaires selon les places, plus une marge
FALLBACK_DAYS = 2000  # place sans calendrier connu : période calendaire large
MARGIN_DAYS = 7  # marge avant la première séance manquante (fériés, décalages horaires)
RECENT_TOLERANCE_DAYS = 5  # écart toléré entre le premier cours de Yahoo et les séances manquantes les plus anciennes
CLOSED_SHARE = 0.05  # un jour où moins de 5 % des titres récupérés d'une place ont une barre est une fermeture de la place
CLOSED_MIN_TITLES = 20  # il faut au moins 20 titres récupérés sur la place pour en juger
CLOSED_MAX_PER_PLACE = 10  # au-delà, la liste d'une place est suspecte (panne de données, pas fermetures) : aucune fermeture n'est retenue pour elle
CLOSED_OUTAGE_SHARE = 0.5  # un jour « fermé » pour plus de la moitié des places jugées est une panne générale de données, jamais une fermeture
CLOSED_OUTAGE_MIN_PLACES = 3  # nombre minimal de places jugées pour appliquer ce contrôle croisé
CLOSED_SETTING = 'market_closed_days'
RETRY_DAYS = {'error': 0.25, 'unavailable': 7, 'incomplete': 30}  # délai avant de redemander un titre selon son état ; complete et recent ne sont plus redemandés
DEEP_LIMIT = 100  # titres traités au plus par passage de maintenance
DEEP_BUDGET_S = 90  # ...et au plus ce temps (secondes)
MAX_PLAUSIBLE_VOLUME = 1e13


def _volume(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_PLAUSIBLE_VOLUME else None


class Calendars:
    """Les 1 260 dernières séances de chaque place jusqu'à la dernière clôture publiée ; `dates` vaut None si la place n'a pas de calendrier."""

    def __init__(self, now):
        self.now = now
        self.cache = {}

    def get(self, mic):
        if mic not in self.cache:
            from .calendar import session_dates

            try:
                last = hours.latest_settled(mic, self.now)
                days = session_dates(mic, last.isoformat(), HISTORY_CLOSES)
            except Exception:  # noqa: BLE001 - place inconnue : repli par dates calendaires
                last, days = None, None
            if last is None:
                last = self.now.date() - datetime.timedelta(days=1)
            dates = [datetime.date.fromisoformat(d) for d in days] if days and len(days) == HISTORY_CLOSES else None
            start = dates[0] if dates else last - datetime.timedelta(days=FALLBACK_DAYS)
            self.cache[mic] = {'last': last, 'dates': dates, 'set': set(dates) if dates else None, 'start': start}
        return self.cache[mic]


def classify(cal, have, closed, first_bar, first_trade):
    """(état, jours omis par Yahoo, séances absentes) pour un titre dont `have` est l'ensemble des dates en base. `closed` : fermetures exceptionnelles de la place."""
    if cal['dates'] is not None:
        still = [d for d in cal['dates'] if d not in have and d not in closed]
    else:
        still = [None] * max(0, HISTORY_CLOSES - sum(1 for d in have if d >= cal['start']))
    if not still:
        return 'complete', 0, 0
    known = [x for x in (first_bar, first_trade) if x is not None]
    if cal['dates'] is not None and known:
        boundary = max(known) + datetime.timedelta(days=RECENT_TOLERANCE_DAYS)
        holes = sum(1 for d in still if d >= boundary)
        return ('incomplete' if holes else 'recent'), holes, len(still)
    young = first_bar is not None and first_bar > cal['start'] + datetime.timedelta(days=MARGIN_DAYS)
    return ('recent' if young else 'incomplete'), 0, len(still)


# ───────── fermetures exceptionnelles ─────────
def _compute_closed(conn, now):
    cals = Calendars(now)
    out = {}
    states = "('complete','incomplete','recent')"
    with conn.cursor() as cur:
        cur.execute(f'SELECT l.mic, COUNT(*) n FROM history_state h JOIN listings l ON l.id=h.listing_id WHERE h.status IN {states} GROUP BY l.mic')
        titles = {r['mic']: r['n'] for r in cur.fetchall()}
        for mic, n in titles.items():
            cal = cals.get(mic)
            if cal['dates'] is None or n < CLOSED_MIN_TITLES:
                continue
            cur.execute(
                f'SELECT d.price_date, COUNT(*) c FROM daily_prices d JOIN listings l ON l.id=d.listing_id JOIN history_state h ON h.listing_id=d.listing_id '
                f'WHERE l.mic=%s AND h.status IN {states} AND d.price_date >= %s GROUP BY d.price_date',
                (mic, cal['start']),
            )
            count = {r['price_date']: r['c'] for r in cur.fetchall()}
            out[mic] = sorted(d for d in cal['dates'] if count.get(d, 0) < CLOSED_SHARE * n)
    return _reject_outages(out)


def _reject_outages(flagged):
    """Écarte ce qui ressemble à une panne de données plutôt qu'à une fermeture : un jour signalé sur la majorité des places jugées, ou une place qui en cumule trop."""
    if len(flagged) >= CLOSED_OUTAGE_MIN_PLACES:
        votes = Counter(d for ds in flagged.values() for d in ds)
        general = {d for d, v in votes.items() if v > CLOSED_OUTAGE_SHARE * len(flagged)}
        flagged = {mic: [d for d in ds if d not in general] for mic, ds in flagged.items()}
    return {mic: ds for mic, ds in flagged.items() if len(ds) <= CLOSED_MAX_PER_PLACE}


def closed_days(conn, now, refresh=False):
    """{place: {dates}} des fermetures exceptionnelles, recalculées au plus une fois par jour (ou sur demande) et mémorisées dans `settings`."""
    today = now.date().isoformat()
    doc = settings.get(conn, CLOSED_SETTING, None) or {}
    if refresh or doc.get('computed') != today:
        days = _compute_closed(conn, now)
        doc = {'computed': today, 'days': {mic: [d.isoformat() for d in ds] for mic, ds in days.items()}}
        settings.put(conn, CLOSED_SETTING, doc)
    return {mic: {datetime.date.fromisoformat(d) for d in ds} for mic, ds in (doc.get('days') or {}).items()}


# ───────── registre ─────────
def _save(conn, lid, now, status, first_bar=None, holes=0, missing=0, closed=0, added=0, detail=None):
    with conn.cursor() as cur:
        cur.execute(
            'INSERT INTO history_state(listing_id,status,checked_at,first_bar,holes,missing,closed_days,added,detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) '
            'ON DUPLICATE KEY UPDATE status=VALUES(status), checked_at=VALUES(checked_at), first_bar=VALUES(first_bar), holes=VALUES(holes), missing=VALUES(missing), '
            'closed_days=VALUES(closed_days), added=VALUES(added), detail=VALUES(detail)',
            (lid, status, now, first_bar, holes, missing, closed, added, (detail or '')[:120] or None),
        )


def _align_registry(conn):
    """Si la profondeur de référence (en clôtures) a changé depuis l'établissement du registre, les titres « complets » sont réexaminés : ils repassent « incomplets » avec une date de contrôle
    ancienne (ils restent comptés dans le calcul des fermetures exceptionnelles), `_plan` les revoit sans appel réseau quand leurs clôtures sont déjà toutes là et n'interroge Yahoo
    que pour la clôture de base manquante (fenêtre étroite, une requête par titre). Aucun cours, aucun volume n'est modifié ; les titres « récents » ne sont pas redemandés."""
    if settings.get(conn, CLOSES_SETTING, None) == HISTORY_CLOSES:
        return
    with conn.cursor() as cur:
        cur.execute("UPDATE history_state SET status='incomplete', checked_at='2000-01-01 00:00:00', detail='profondeur 1 261 clôtures' WHERE status='complete'")
    settings.put(conn, CLOSES_SETTING, HISTORY_CLOSES)
    conn.commit()


def candidates(conn, rows, now):
    """Titres à traiter : sans ligne dans le registre (nouveau titre, ou première passe), ou dont l'état demande une nouvelle tentative. Les nouveaux d'abord."""
    ledger = {}
    ids = [r['listing_id'] for r in rows]
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = ids[i : i + 2000]
            cur.execute(f"SELECT listing_id, status, checked_at FROM history_state WHERE listing_id IN ({','.join(['%s'] * len(part))})", part)
            ledger.update({r['listing_id']: r for r in cur.fetchall()})
    naive = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    out = []
    for r in rows:
        led = ledger.get(r['listing_id'])
        if led is None:
            out.append((0, r['listing_id'], r))
        elif led['status'] in RETRY_DAYS and naive - led['checked_at'] >= datetime.timedelta(days=RETRY_DAYS[led['status']]):
            out.append((1, r['listing_id'], r))
    out.sort(key=lambda t: t[:2])
    return [r for _, _, r in out]


def _plan(conn, rows, now, closed):
    """Lit les séances déjà en base : renvoie (titres à interroger, titres déjà complets). Aucun appel réseau."""
    cals = Calendars(now)
    need, done = [], []
    oldest = min((cals.get(r['mic'])['start'] for r in rows), default=now.date())
    for i in range(0, len(rows), 300):
        part = rows[i : i + 300]
        have, nullvol = defaultdict(set), defaultdict(set)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT listing_id, price_date, volume IS NULL AS nv FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND price_date >= %s",
                [r['listing_id'] for r in part] + [oldest],
            )
            for x in cur.fetchall():
                have[x['listing_id']].add(x['price_date'])
                if x['nv']:
                    nullvol[x['listing_id']].add(x['price_date'])
        for r in part:
            lid, cal = r['listing_id'], cals.get(r['mic'])
            shut = closed.get(r['mic'], set())
            if cal['dates'] is not None:
                missing = [d for d in cal['dates'] if d not in have[lid] and d not in shut]
                nulls = {d for d in nullvol[lid] if d in cal['set']}
            else:
                missing = [None] * max(0, HISTORY_CLOSES - sum(1 for d in have[lid] if d >= cal['start']))
                nulls = {d for d in nullvol[lid] if d >= cal['start']}
            item = {'row': r, 'cal': cal, 'have': have[lid], 'nullvol': nulls, 'closed': shut}
            if not missing and not nulls:
                done.append(item)
                continue
            real = [d for d in missing if d is not None]
            earliest = min(real + sorted(nulls)) if (real or nulls) else cal['start']
            item['p1'] = (earliest if cal['dates'] is not None else cal['start']) - datetime.timedelta(days=MARGIN_DAYS)
            item['p2'] = cal['last'] + datetime.timedelta(days=2)
            need.append(item)
    return need, done


def store_and_classify(conn, item, data, now):
    """Insère les clôtures absentes, complète les volumes vides, enregistre l'état du titre. Ne modifie jamais une clôture existante. Renvoie le résumé."""
    from engine.shared.db import ensure

    r, cal, have = item['row'], item['cal'], item['have']
    lid = r['listing_id']
    new, fill, all_days = {}, [], []
    for ts, _o, _h, _l, close, volume in data['bars']:
        day = local_date(ts, data['timezone'])
        all_days.append(day)
        if day < cal['start'] or day > cal['last'] or not hours.is_settled(r['mic'], day, now):
            continue
        volume = _volume(volume)
        if day not in have:
            new[day] = (close, volume)
        elif volume is not None and day in item['nullvol']:
            fill.append((volume, lid, day))
    added = volumes = 0
    ensure(conn)
    with conn.cursor() as cur:
        if new:
            cur.executemany('INSERT IGNORE INTO daily_prices(listing_id,price_date,close_px,volume) VALUES (%s,%s,%s,%s)', [(lid, d, c, v) for d, (c, v) in new.items()])
            added = cur.rowcount
        if fill:
            cur.executemany('UPDATE daily_prices SET volume=%s WHERE listing_id=%s AND price_date=%s AND volume IS NULL', fill)
            volumes = cur.rowcount
    volumes += sum(1 for _c, v in new.values() if v is not None)
    first_bar = min(all_days) if all_days else None
    status, holes, missing = classify(cal, set(have) | set(new), item['closed'], first_bar, data.get('first_trade'))
    _save(conn, lid, now, status, first_bar, holes, missing, len(item['closed']), added)
    conn.commit()
    return {'status': status, 'added': added, 'volumes': volumes}


def run(conn, client, rows, now, limit=DEEP_LIMIT, budget_s=DEEP_BUDGET_S, workers=1, client_factory=None, progress=None):
    """Complète l'historique des titres à traiter. S'arrête au budget de temps, à `limit`, ou au premier 429 (le titre n'est pas marqué : repris ensuite).
    Un échec isolé est enregistré (error) et repris à un passage ultérieur. Renvoie les chiffres du passage."""
    from engine.shared.db import ensure

    closed = closed_days(conn, now)
    _align_registry(conn)
    todo = candidates(conn, rows, now)
    stats = Counter(candidates=len(todo))
    stats['rate_limited'] = False
    if limit is not None:
        todo = todo[:limit]
    started = time.monotonic()
    local = threading.local()
    need, done = _plan(conn, todo, now, closed) if todo else ([], [])
    for item in done:  # déjà complets en base : aucun appel Yahoo
        _save(conn, item['row']['listing_id'], now, 'complete', None, 0, 0, len(item['closed']), 0, 'déjà complet')
        stats['complete'] += 1
        stats['examined'] += 1
    conn.commit()

    def fetch(item):
        c = client
        if workers > 1:
            if not hasattr(local, 'client'):
                local.client = client_factory()
            c = local.client
        try:
            return item, c.chart_dates(item['row']['symbol'], item['p1'], item['p2']), None
        except Exception as e:  # noqa: BLE001
            return item, None, e

    pool = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
    chunk = workers * 4 if workers > 1 else 1
    try:
        for start in range(0, len(need), chunk):
            if time.monotonic() - started > budget_s or stats['rate_limited']:
                break
            part = need[start : start + chunk]
            for item, data, err in list(pool.map(fetch, part)) if pool else [fetch(i) for i in part]:
                if isinstance(err, RateLimited):
                    stats['rate_limited'] = True
                    continue
                ensure(conn)
                lid = item['row']['listing_id']
                if err is not None:
                    status = 'unavailable' if isinstance(err, YahooError) and str(err) == 'HTTP 404' else 'error'
                    _save(conn, lid, now, status, detail=str(err))
                    conn.commit()
                    stats[status] += 1
                elif not data or not data.get('bars'):
                    _save(conn, lid, now, 'unavailable', detail='aucune barre')
                    conn.commit()
                    stats['unavailable'] += 1
                else:
                    res = store_and_classify(conn, item, data, now)
                    stats[res['status']] += 1
                    stats['added'] += res['added']
                    stats['volumes'] += res['volumes']
                stats['examined'] += 1
                if progress:
                    progress(stats['examined'], len(todo))
    finally:
        if pool:
            pool.shutdown()
    stats['errors'] = stats['error']
    stats['remaining'] = max(0, stats['candidates'] - stats['examined'])
    return dict(stats)


def reclassify(conn, now):
    """Reclasse les titres « incomplets » en retirant les fermetures exceptionnelles (jours où presque aucun titre de la place n'a de barre). Ne touche ni aux cours ni aux volumes."""
    closed = closed_days(conn, now, refresh=True)
    cals = Calendars(now)
    with conn.cursor() as cur:
        cur.execute('SELECT h.listing_id, h.first_bar, l.mic FROM history_state h JOIN listings l ON l.id=h.listing_id WHERE h.status=%s', ('incomplete',))
        todo = cur.fetchall()
    changes = Counter()
    for i in range(0, len(todo), 300):
        part = todo[i : i + 300]
        have = defaultdict(set)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT listing_id, price_date FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND price_date >= %s",
                [x['listing_id'] for x in part] + [min(cals.get(x['mic'])['start'] for x in part)],
            )
            for x in cur.fetchall():
                have[x['listing_id']].add(x['price_date'])
        for x in part:
            cal = cals.get(x['mic'])
            if cal['dates'] is None:
                continue
            shut = closed.get(x['mic'], set())
            status, holes, missing = classify(cal, have[x['listing_id']], shut, x['first_bar'], None)
            if status != 'incomplete':
                changes[f'incomplete -> {status}'] += 1
            with conn.cursor() as cur:
                cur.execute('UPDATE history_state SET status=%s, holes=%s, missing=%s, closed_days=%s WHERE listing_id=%s', (status, holes, missing, len(shut & cal['set']), x['listing_id']))
    conn.commit()
    return dict(changes)


def coverage(conn):
    """Profondeur de l'historique du jeu de collecte, pour l'administration : UNE définition, celle du registre `history_state` (la même que le job `history_deep`).
    complete : 1 260 séances présentes ; recent : titre plus jeune que la profondeur (rien de plus ancien chez Yahoo) ; incomplete : séances omises par Yahoo ;
    unavailable / error : à reprendre ; pending : jamais vérifié (le titre a des cours, la profondeur n'a pas encore été contrôlée) ; absent : aucun cours du tout."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT CASE WHEN h.status IS NOT NULL THEN h.status WHEN EXISTS (SELECT 1 FROM daily_prices d WHERE d.listing_id=c.listing_id) THEN 'pending' ELSE 'absent' END s,
                      COUNT(*) n, COALESCE(SUM(h.holes),0) holes
               FROM v_collect_set c LEFT JOIN history_state h ON h.listing_id=c.listing_id GROUP BY s"""
        )
        rows = cur.fetchall()
    out = {s: 0 for s in ('complete', 'recent', 'incomplete', 'unavailable', 'error', 'pending', 'absent')}
    holes = 0
    for r in rows:
        out[r['s']] = int(r['n'])
        if r['s'] == 'incomplete':
            holes = int(r['holes'])
    out['holes'] = holes
    out['target'] = HISTORY_SESSIONS
    return out
