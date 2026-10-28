"""Collecte : Quote (prix, liquidité), taux de change, clôtures quotidiennes, barres de 15 minutes, trous.

Toutes les fonctions prennent une connexion, un client Yahoo et une date `now` (UTC, aware) : testables sans réseau ni horloge.
Le jeu de collecte vient de v_collect_set : sélectionnées principales + cotations détenues (même exclues ou secondaires).
"""
import datetime
import json
import statistics
from collections import defaultdict

from . import hours, prefilter
from .yahoo import RateLimited, local_date

DAILY_KEEP_DAYS = 610          # ≈ 420 séances US (580 jours n'en gardaient que 380-399 : jamais « complet » à 400)
SPARK_BATCH = 20
QUOTE_BATCH = 50
CHUNK = 2000


def setting(conn, name, default):
    with conn.cursor() as cur:
        cur.execute('SELECT value_json FROM settings WHERE name=%s', (name,))
        row = cur.fetchone()
    return json.loads(row['value_json']) if row else default


def collected_rows(conn):
    """(clôtures quotidiennes, barres de 15 minutes) déjà en base pour le jeu de collecte."""
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM daily_prices d JOIN v_collect_set c ON c.listing_id=d.listing_id')
        daily = cur.fetchone()['n']
        cur.execute('SELECT COUNT(*) n FROM intraday_prices d JOIN v_collect_set c ON c.listing_id=d.listing_id')
        return daily, cur.fetchone()['n']


def collection_set(conn, mic=None):
    sql = 'SELECT c.listing_id, c.mic, c.symbol, c.held FROM v_collect_set c'
    with conn.cursor() as cur:
        cur.execute(sql + (' WHERE c.mic=%s' if mic else ''), (mic,) if mic else ())
        return cur.fetchall()


def _batches(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def naive_utc(now):
    return now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)


# ───────── Quote, FX, préfiltre ─────────
def refresh_quotes(conn, client, rows, now, progress=None, stats=None):
    """Met à jour latest_prices (prix de référence, volume moyen 3 mois, capitalisation). Renvoie (ok, erreurs)."""
    ok = err = 0
    by_symbol = {r['symbol'].upper(): r['listing_id'] for r in rows}
    for part in _batches(sorted(by_symbol), QUOTE_BATCH):
        try:
            quotes = client.quotes(part)
        except RateLimited:
            raise
        except Exception:
            err += len(part)
            if stats is not None:
                stats['errors'] = stats.get('errors', 0) + len(part)
            if progress:
                progress(len(part))
            continue
        data = []
        for symbol, q in quotes.items():
            if symbol in by_symbol:
                data.append((by_symbol[symbol], q['price'], q['price_time'] or naive_utc(now), q['currency'], q['avg_volume_3m'], q['market_cap'], naive_utc(now)))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,market_cap,quote_at)
                               VALUES (%s,%s,%s,'quote',%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE price=IF(source='intraday' AND price_time>VALUES(price_time),price,VALUES(price)),
                                 price_time=IF(source='intraday' AND price_time>VALUES(price_time),price_time,VALUES(price_time)),
                                 source=IF(source='intraday' AND price_time>VALUES(price_time),source,'quote'),
                                 currency=VALUES(currency), avg_volume_3m=VALUES(avg_volume_3m), market_cap=VALUES(market_cap), quote_at=VALUES(quote_at)""",
                            [(d[0], d[1], d[2], d[3], d[4], d[5], d[6]) for d in data])
        conn.commit()
        ok += len(data)
        err += len(part) - len(data)
        if progress:
            progress(len(part))
    return ok, err


def refresh_fx(conn, client, now):
    """Taux de change vers l'euro pour les devises présentes dans le catalogue."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT UPPER(currency) c FROM latest_prices WHERE currency IS NOT NULL")
        currencies = sorted({r['c'] for r in cur.fetchall()} - {'EUR'})
    pairs = {c: f'{c}EUR=X' for c in currencies}
    if not pairs:
        return 0
    quotes = client.quotes(list(pairs.values()))
    today = naive_utc(now).date()
    rows = [(c, today, quotes[p]['price']) for c, p in pairs.items() if p in quotes]
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO fx_rates(currency,rate_date,to_eur) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE to_eur=VALUES(to_eur)', rows)
    conn.commit()
    return len(rows)


def to_eur_factor(currency, rates):
    """Facteur de conversion vers l'euro ; 'GBp' (pence) = GBP / 100 ; None si inconnu."""
    if not currency:
        return None
    if currency == 'GBp':
        r = rates.get('GBP')
        return r / 100 if r else None
    if currency.upper() == 'EUR':
        return 1.0
    return rates.get(currency.upper())


def latest_rates(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT f.currency, f.to_eur FROM fx_rates f JOIN (SELECT currency, MAX(rate_date) d FROM fx_rates GROUP BY currency) m ON m.currency=f.currency AND m.d=f.rate_date")
        return {r['currency']: float(r['to_eur']) for r in cur.fetchall()}


def apply_prefilter(conn):
    """Décide selected / excluded pour les cotations ayant un Quote. Ne touche jamais aux exclusions par les règles du catalogue."""
    params = setting(conn, 'prefilter', {})
    rates = latest_rates(conn)
    changed = {'selected': 0, 'excluded': 0}
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.status, l.excluded_reason, i.kind, p.price, p.avg_volume_3m, p.currency
                       FROM listings l JOIN instruments i ON i.id=l.instrument_id JOIN latest_prices p ON p.listing_id=l.id
                       WHERE p.quote_at IS NOT NULL AND (l.excluded_reason IS NULL OR l.excluded_reason LIKE %s)""", (prefilter.PREFIX + '%',))
        updates = []
        for r in cur.fetchall():
            status, reason = prefilter.decide(r['kind'], float(r['price']) if r['price'] is not None else None,
                                              r['avg_volume_3m'], to_eur_factor(r['currency'], rates), params)
            if status and (status != r['status'] or reason != r['excluded_reason']):
                updates.append((status, reason, r['id']))
                changed[status] += 1
        cur.executemany('UPDATE listings SET status=%s, excluded_reason=%s WHERE id=%s', updates)
    conn.commit()
    return changed


# ───────── clôtures quotidiennes ─────────
def collect_daily(conn, client, rows, now, range_='2y', progress=None):
    """Clôtures définitives (séance terminée et publiée). Renvoie (cotations_ok, lignes, erreurs)."""
    by_symbol = {r['symbol'].upper(): r for r in rows}
    ok = lines = err = 0
    for part in _batches(sorted(by_symbol), SPARK_BATCH):
        try:
            data = client.spark(part, range_, '1d')
        except RateLimited:
            raise
        except Exception:
            err += len(part)
            continue
        out = []
        for symbol, series in data.items():
            row = by_symbol[symbol]
            seen = {}
            for ts, close in series['bars']:
                day = local_date(ts, series['timezone'])
                if hours.is_settled(row['mic'], day, now):
                    seen[day] = close
            out += [(row['listing_id'], d, c) for d, c in seen.items()]
            ok += bool(seen)
        with conn.cursor() as cur:
            cur.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE close_px=VALUES(close_px)', out)
        conn.commit()
        lines += len(out)
        err += len(part) - len(data)
        if progress:
            progress(len(part))
    return ok, lines, err


def prune_daily(conn, now):
    with conn.cursor() as cur:
        cur.execute('DELETE FROM daily_prices WHERE price_date < %s', (naive_utc(now).date() - datetime.timedelta(days=DAILY_KEEP_DAYS),))
        n = cur.rowcount
    conn.commit()
    return n


FULL_SESSIONS = 400
RANGES = ((4, '5d'), (25, '1mo'), (80, '3mo'), (170, '6mo'), (350, '1y'))


def latest_settled(mic, now):
    """Date de la dernière séance dont la clôture officielle est publiée."""
    day = hours.session_date(mic, now)
    if not hours.is_settled(mic, day, now):
        day -= datetime.timedelta(days=1)
        while day.weekday() >= 5:
            day -= datetime.timedelta(days=1)
    return day


def daily_plan(conn, rows, now):
    """Pour chaque cotation, la plus petite fenêtre qui comble ce qui manque : ({fenêtre Yahoo: [cotations]}, nombre de cotations déjà à jour).
    Aucun téléchargement pour une cotation dont la dernière clôture publiée est déjà en base."""
    ids = [r['listing_id'] for r in rows]
    stats = {}
    with conn.cursor() as cur:
        for part in _batches(ids, CHUNK):
            cur.execute(f"SELECT listing_id, COUNT(*) n, MIN(price_date) a, MAX(price_date) b FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) GROUP BY listing_id", part)
            stats.update({r['listing_id']: (r['n'], r['a'], r['b']) for r in cur.fetchall()})
    tried = setting(conn, 'daily_backfill_tried', {})
    today = naive_utc(now).date()
    plan, fresh = defaultdict(list), 0
    for r in rows:
        st = stats.get(r['listing_id'])
        if not st:
            plan['2y'].append(r)
            continue
        n, first, last = st
        if n < FULL_SESSIONS and first > today - datetime.timedelta(days=DAILY_KEEP_DAYS - 20):       # historique court : un titre récent n'a peut-être rien de plus
            t = tried.get(str(r['listing_id']))
            if not t or (today - datetime.date.fromisoformat(t)).days > 30:
                plan['2y'].append(r)
                continue
        if last >= latest_settled(r['mic'], now):
            fresh += 1
            continue
        days = (today - last).days
        plan[next((rg for lim, rg in RANGES if days <= lim), '2y')].append(r)
    return dict(plan), fresh


def mark_backfill_tried(conn, rows, now):
    """Mémorise les cotations dont la fenêtre complète vient d'être demandée et qui restent sous 400 séances (titres récents) : on ne les redemande pas chaque jour."""
    ids = [r['listing_id'] for r in rows]
    tried = setting(conn, 'daily_backfill_tried', {})
    keep = {k: v for k, v in tried.items() if (naive_utc(now).date() - datetime.date.fromisoformat(v)).days <= 30}
    with conn.cursor() as cur:
        for part in _batches(ids, CHUNK):
            cur.execute(f"SELECT listing_id FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) GROUP BY listing_id HAVING COUNT(*) < %s", part + [FULL_SESSIONS])
            keep.update({str(r['listing_id']): naive_utc(now).date().isoformat() for r in cur.fetchall()})
        cur.execute('INSERT INTO settings(name, value_json, updated_at) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE value_json=VALUES(value_json), updated_at=VALUES(updated_at)',
                    ('daily_backfill_tried', json.dumps(keep), naive_utc(now)))
    conn.commit()


def intraday_plan(conn, rows, now):
    """Barres de 15 minutes des deux dernières séances de chaque place : ({'5d' | '1d': [cotations]}, résumé).
    '5d' si l'une des deux séances est incomplète ; '1d' si seule la séance en cours (ou tout juste finie) est à rafraîchir ; rien si tout est complet.
    Une séance sans aucune barre pour toute la place (jour férié) n'est pas redemandée une fois qu'une collecte est passée après sa clôture.
    Les places sans horaires connus n'ont pas de barres de 15 minutes."""
    from engine.market import intraday as intra
    plan, summary = defaultdict(list), {'complete': 0, 'unknown_hours': 0, 'holiday': 0}
    by_mic = defaultdict(list)
    for r in rows:
        by_mic[r['mic']].append(r)
    naive = naive_utc(now)
    for mic, group in by_mic.items():
        if not hours.known(mic):
            summary['unknown_hours'] += len(group)
            continue
        cur_day = hours.session_date(mic, now)
        prev_day = cur_day - datetime.timedelta(days=1)
        while prev_day.weekday() >= 5:
            prev_day -= datetime.timedelta(days=1)
        (s0, e0), (s1, e1) = intra.session_window(mic, prev_day), intra.session_window(mic, cur_day)
        expected = max(1, hours.expected_slots(mic))
        counts = {}
        with conn.cursor() as cur:
            for part in _batches([r['listing_id'] for r in group], CHUNK):
                cur.execute(f"""SELECT listing_id, SUM(slot_start>=%s AND slot_start<%s) c0, SUM(slot_start>=%s AND slot_start<%s) c1 FROM intraday_prices
                                WHERE slot_start>=%s AND listing_id IN ({','.join(['%s'] * len(part))}) GROUP BY listing_id""", [s0, e0, s1, e1, s0] + part)
                counts.update({r['listing_id']: (int(r['c0']), int(r['c1'])) for r in cur.fetchall()})
            holiday0 = holiday1 = False
            if counts is not None:
                for end, which in ((e0, 0), (e1, 1)):
                    seen = sum(1 for c in counts.values() if c[which] > 0)
                    if seen < 0.05 * len(group) and end + datetime.timedelta(minutes=hours.SETTLE_MINUTES) < naive:
                        cur.execute("SELECT 1 FROM jobs WHERE job_type IN ('history', %s) AND status IN ('completed','completed_with_errors') AND started_at > %s LIMIT 1",
                                    ('intraday:' + mic, end + datetime.timedelta(minutes=hours.SETTLE_MINUTES)))
                        if cur.fetchone():
                            holiday0, holiday1 = (True, holiday1) if which == 0 else (holiday0, True)
        live = hours.is_open(mic, now) or s1 <= naive < e1 + datetime.timedelta(minutes=hours.SETTLE_MINUTES)
        for r in group:
            c0, c1 = counts.get(r['listing_id'], (0, 0))
            miss0 = not holiday0 and c0 < 0.8 * expected
            miss1 = not holiday1 and (live or c1 < 0.8 * expected)
            if miss0:
                plan['5d'].append(r)
            elif miss1:
                plan['1d'].append(r)
            else:
                summary['complete'] += 1
        summary['holiday'] += holiday0 + holiday1
    return dict(plan), summary


# ───────── barres de 15 minutes ─────────
def slot_of(ts):
    t = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).replace(tzinfo=None)
    return t.replace(minute=t.minute - t.minute % hours.SLOT_MINUTES, second=0, microsecond=0)


def collect_intraday(conn, client, rows, now, range_='1d', progress=None):
    """Barres de 15 min. Une barre provisoire n'écrase jamais une barre définitive. Met à jour latest_prices.
    Renvoie (cotations_ok, barres, erreurs)."""
    by_symbol = {r['symbol'].upper(): r for r in rows}
    cutoff = naive_utc(now)
    ok = lines = err = 0
    for part in _batches(sorted(by_symbol), SPARK_BATCH):
        try:
            data = client.spark(part, range_, '15m')
        except RateLimited:
            raise
        except Exception:
            err += len(part)
            continue
        bars, latest = [], []
        for symbol, series in data.items():
            lid = by_symbol[symbol]['listing_id']
            slots = {}
            for ts, close in series['bars']:
                slots[slot_of(ts)] = close           # dernier prix du créneau
            for slot, close in slots.items():
                bars.append((lid, slot, close, 1 if slot + datetime.timedelta(minutes=hours.SLOT_MINUTES) <= cutoff else 0))
            if slots:
                last = max(slots)
                latest.append((lid, slots[last], last, series['currency']))
                ok += 1
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final) VALUES (%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE close_px=IF(is_final=1,close_px,VALUES(close_px)), is_final=GREATEST(is_final,VALUES(is_final))""", bars)
            cur.executemany("""INSERT INTO latest_prices(listing_id,price,price_time,source,currency) VALUES (%s,%s,%s,'intraday',%s)
                               ON DUPLICATE KEY UPDATE price=IF(price_time IS NULL OR price_time<=VALUES(price_time),VALUES(price),price),
                                 source=IF(price_time IS NULL OR price_time<=VALUES(price_time),'intraday',source),
                                 price_time=IF(price_time IS NULL OR price_time<=VALUES(price_time),VALUES(price_time),price_time),
                                 currency=COALESCE(VALUES(currency),currency)""",
                            [(a, b, c, d) for a, b, c, d in latest])
        conn.commit()
        lines += len(bars)
        err += len(part) - len(data)
        if progress:
            progress(len(part))
    return ok, lines, err


def prune_intraday(conn, now, sessions=None):
    sessions = sessions or setting(conn, 'intraday_retention_sessions', 20)
    limit = naive_utc(now) - datetime.timedelta(days=int(sessions * 7 / 5) + 2)
    with conn.cursor() as cur:
        cur.execute('DELETE FROM intraday_prices WHERE slot_start < %s', (limit,))
        n = cur.rowcount
        cur.execute('DELETE FROM price_gaps WHERE session_date < %s', (limit.date(),))
    conn.commit()
    return n


# ───────── trous ─────────
def coverage(conn, mic, now, sessions=5):
    """{jour local: médiane du nombre de créneaux 15 min par titre} pour les séances récentes terminées de la place."""
    from zoneinfo import ZoneInfo
    ids = [r['listing_id'] for r in collection_set(conn, mic)]
    start = naive_utc(now) - datetime.timedelta(days=sessions * 2)
    tz, counts = ZoneInfo(hours.HOURS[mic][0]), defaultdict(lambda: defaultdict(int))
    with conn.cursor() as cur:
        for part in _batches(ids, CHUNK):
            cur.execute(f"SELECT listing_id, slot_start FROM intraday_prices WHERE slot_start>=%s AND listing_id IN ({','.join(['%s'] * len(part))})", [start] + part)
            for r in cur.fetchall():
                counts[r['slot_start'].replace(tzinfo=datetime.timezone.utc).astimezone(tz).date()][r['listing_id']] += 1
    today = hours.session_date(mic, now)
    return {d: statistics.median(per.values()) for d, per in counts.items()
            if d < today and d.weekday() < 5 and hours.is_settled(mic, d, now)}


def detect_gaps(conn, mic, now, sessions=5):
    """Signale les séances dont la couverture est nettement incomplète. Une séance sans aucune barre est un jour férié, pas un trou.
    Renvoie le nombre de trous ajoutés."""
    expected, added = hours.expected_slots(mic), 0
    with conn.cursor() as cur:
        for day, median in coverage(conn, mic, now, sessions).items():
            if median < 0.8 * expected:
                cur.execute("INSERT INTO price_gaps(mic,session_date,state,detected_at,note) VALUES (%s,%s,'to_repair',%s,%s) ON DUPLICATE KEY UPDATE detected_at=detected_at",
                            (mic, day, naive_utc(now), f'médiane {median:.0f}/{expected} créneaux'))
                added += cur.rowcount == 1
    conn.commit()
    return added


def repair_gaps(conn, client, now, max_batches=30):
    """Récupère 5 jours de barres 15 min pour les places en trou, puis revérifie la couverture :
    réparée si elle est complète, irrécupérable si la séance est trop ancienne pour Yahoo (5 jours) ou reste incomplète."""
    with conn.cursor() as cur:
        cur.execute("SELECT mic, session_date FROM price_gaps WHERE state='to_repair' ORDER BY session_date DESC")
        gaps = cur.fetchall()
    used = 0
    for mic in sorted({g['mic'] for g in gaps}):
        rows = collection_set(conn, mic)
        need = -(-len(rows) // SPARK_BATCH)
        if used + need > max_batches:
            continue
        collect_intraday(conn, client, rows, now, range_='5d')
        used += need
        after = coverage(conn, mic, now, 8)
        for g in [g for g in gaps if g['mic'] == mic]:
            complete = after.get(g['session_date'], 0) >= 0.8 * hours.expected_slots(mic)
            age = (naive_utc(now).date() - g['session_date']).days
            state = 'repaired' if complete else ('unrecoverable' if age > 5 else 'to_repair')
            with conn.cursor() as cur:
                cur.execute('UPDATE price_gaps SET state=%s WHERE mic=%s AND session_date=%s', (state, mic, g['session_date']))
    conn.commit()
    return used
