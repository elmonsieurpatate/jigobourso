"""Collecte : Quote (prix, liquidité), taux de change, clôtures quotidiennes, barres de 15 minutes, trous.

Toutes les fonctions prennent une connexion, un client Yahoo et une date `now` (UTC, aware) : testables sans réseau ni horloge.
Le jeu de collecte vient de v_collect_set : sélectionnées principales + cotations détenues (même exclues ou secondaires).
"""
import datetime
import json
import statistics
import time
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
                data.append((by_symbol[symbol], q['price'], q['price_time'] or naive_utc(now), q['currency'], q['avg_volume_3m'], q['market_cap'], naive_utc(now), q.get('expense_ratio'), q.get('avg_volume_10d'), q.get('analyst_rating'), q.get('net_assets')))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,market_cap,quote_at,expense_ratio,avg_volume_10d,analyst_rating,net_assets)
                               VALUES (%s,%s,%s,'quote',%s,%s,%s,%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE price=IF(source='intraday' AND price_time>VALUES(price_time),price,VALUES(price)),
                                 price_time=IF(source='intraday' AND price_time>VALUES(price_time),price_time,VALUES(price_time)),
                                 source=IF(source='intraday' AND price_time>VALUES(price_time),source,'quote'),
                                 currency=IF(source='intraday' AND price_time>VALUES(price_time),currency,VALUES(currency)), avg_volume_3m=VALUES(avg_volume_3m), market_cap=VALUES(market_cap), quote_at=VALUES(quote_at),
                                 expense_ratio=VALUES(expense_ratio), avg_volume_10d=VALUES(avg_volume_10d), analyst_rating=VALUES(analyst_rating), net_assets=VALUES(net_assets)""",
                            data)
        conn.commit()
        ok += len(data)
        err += len(part) - len(data)
        if progress:
            progress(len(part))
    return ok, err


def refresh_fx(conn, client, now):
    """Taux de change vers l'euro pour les devises présentes dans le catalogue."""
    with conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT CASE WHEN BINARY currency IN ('GBp','ZAc') OR UPPER(currency) IN ('GBX','ILA') THEN
                                          CASE WHEN UPPER(currency) IN ('GBP','GBX') THEN 'GBP' WHEN UPPER(currency)='ZAC' THEN 'ZAR' ELSE 'ILS' END
                                        ELSE UPPER(currency) END c FROM latest_prices WHERE currency IS NOT NULL""")
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


# Devises cotées dans une sous-unité : code Yahoo (sensible à la casse quand il l'est) -> (devise principale, diviseur).
SUBUNITS = {'GBp': ('GBP', 100), 'GBX': ('GBP', 100), 'ZAc': ('ZAR', 100), 'ZAC': ('ZAR', 100), 'ILA': ('ILS', 100)}


FX_HISTORY_DAYS = 300        # profondeur d'historique de change visée (les transactions plus anciennes exigent un taux saisi à la main)


def backfill_fx(conn, client, now):
    """Complète l'historique de change (clôtures quotidiennes Yahoo) des devises dont le premier taux connu est récent. Sans cela, une opération antérieure au
    début de la collecte exige un taux saisi à la main. N'écrase jamais un taux existant ; une devise sans réponse n'est redemandée qu'une fois par semaine.
    Renvoie le nombre de taux ajoutés."""
    today = naive_utc(now).date()
    with conn.cursor() as cur:
        cur.execute('SELECT currency, MIN(rate_date) first FROM fx_rates GROUP BY currency')
        first = {r['currency']: r['first'] for r in cur.fetchall()}
    tried = setting(conn, 'fx_backfill_tried', {})
    wanted = sorted(c for c, d in first.items() if d > today - datetime.timedelta(days=FX_HISTORY_DAYS)
                    and (not tried.get(c) or (today - datetime.date.fromisoformat(tried[c])).days >= 7))
    added = 0
    for part in _batches(wanted, SPARK_BATCH):
        pairs = {f'{c}EUR=X': c for c in part}
        data = client.spark(list(pairs), '2y', '1d')
        rows = []
        for symbol, series in data.items():
            c = pairs.get(symbol.upper())
            if c:
                rows += [(c, local_date(ts, series['timezone']), close) for ts, close in series['bars'] if close and close > 0]
        with conn.cursor() as cur:
            cur.executemany('INSERT IGNORE INTO fx_rates(currency,rate_date,to_eur) VALUES (%s,%s,%s)', rows)
            added += max(0, cur.rowcount or 0)
        for c in part:
            tried[c] = today.isoformat()
        with conn.cursor() as cur:
            cur.execute('INSERT INTO settings(name, value_json, updated_at) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE value_json=VALUES(value_json), updated_at=VALUES(updated_at)',
                        ('fx_backfill_tried', json.dumps(tried), naive_utc(now)))
        conn.commit()
    return added


def to_eur_factor(currency, rates):
    """Facteur de conversion vers l'euro ; 'GBp' (pence), 'ZAc' (cents du rand) et 'ILA' (agorot) sont des sous-unités ; None si inconnu."""
    if not currency:
        return None
    sub = SUBUNITS.get(currency) or SUBUNITS.get(currency.upper())
    if sub:
        r = rates.get(sub[0])
        return r / sub[1] if r else None
    if currency.upper() == 'EUR':
        return 1.0
    return rates.get(currency.upper())


def latest_rates(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT f.currency, f.to_eur FROM fx_rates f JOIN (SELECT currency, MAX(rate_date) d FROM fx_rates GROUP BY currency) m ON m.currency=f.currency AND m.d=f.rate_date")
        return {r['currency']: float(r['to_eur']) for r in cur.fetchall()}


def apply_prefilter(conn, now=None):
    """Décide selected / excluded pour les cotations ayant un Quote. Ne touche jamais aux exclusions par les règles du catalogue."""
    params = setting(conn, 'prefilter', {})
    now = naive_utc(now) if now else datetime.datetime.utcnow()
    rates = latest_rates(conn)
    changed = {'selected': 0, 'excluded': 0}
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.status, l.excluded_reason, i.kind, p.price, p.avg_volume_3m, p.currency, p.price_time
                       FROM listings l JOIN instruments i ON i.id=l.instrument_id JOIN latest_prices p ON p.listing_id=l.id
                       WHERE p.quote_at IS NOT NULL AND (l.excluded_reason IS NULL OR l.excluded_reason LIKE %s)""", (prefilter.PREFIX + '%',))
        updates = []
        for r in cur.fetchall():
            status, reason = prefilter.decide(r['kind'], float(r['price']) if r['price'] is not None else None,
                                              r['avg_volume_3m'], to_eur_factor(r['currency'], rates), params,
                                              age_days=(now - r['price_time']).total_seconds() / 86400 if r['price_time'] else None)
            if status is None and r['price'] is not None and to_eur_factor(r['currency'], rates) is None:
                # Aucun taux de change : on ne décide pas, mais on le dit (sinon le titre reste « candidat » sans explication).
                status, reason = 'candidate', f'{prefilter.PREFIX} : devise {r["currency"] or "inconnue"} non convertible en euros (taux indisponible)'
            if status and (status != r['status'] or reason != r['excluded_reason']):
                updates.append((status, reason, r['id']))
                changed[status] = changed.get(status, 0) + 1
        cur.executemany('UPDATE listings SET status=%s, excluded_reason=%s WHERE id=%s', updates)
    conn.commit()
    return changed


# ───────── clôtures quotidiennes ─────────
def fill_daily_gaps(conn, client, rows, now, range_='1y'):
    """Comble les clôtures absentes de l'historique avec le point d'accès « chart » (un symbole par appel) : le point d'accès groupé « spark » omet certains jours que « chart » fournit.
    N'ajoute que les jours manquants (jamais de modification d'une clôture déjà en base) et seulement des séances terminées. Renvoie (titres examinés, clôtures ajoutées)."""
    added = 0
    for r in rows:
        data = client.chart(r['symbol'], range_, '1d')                       # RateLimited remonte : le passage s'arrête, la suite reprend plus tard
        if not data or not data.get('bars'):
            continue
        with conn.cursor() as cur:
            cur.execute('SELECT price_date FROM daily_prices WHERE listing_id=%s', (r['listing_id'],))
            have = {x['price_date'] for x in cur.fetchall()}
            out = {}
            for ts, _o, _h, _l, close, _v in data['bars']:
                day = local_date(ts, data['timezone'])
                if day not in have and hours.is_settled(r['mic'], day, now):
                    out[day] = close
            if out:
                cur.executemany('INSERT IGNORE INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)', [(r['listing_id'], d, c) for d, c in out.items()])
                added += len(out)
        conn.commit()
    return len(rows), added


GAP_LIMIT = 150            # titres examinés au plus par passage de maintenance
GAP_BUDGET_S = 60          # ...et au plus ce temps (secondes) : un appel Yahoo par titre
GAP_RETRY_DAYS = 30        # un titre déjà examiné n'est pas redemandé avant ce délai (les jours que Yahoo n'a vraiment pas restent absents)


def fill_gaps_batch(conn, client, rows, now, limit=GAP_LIMIT, budget_s=GAP_BUDGET_S, force=False, progress=None):
    """Un lot de titres dont l'historique d'un an est incomplet, les moins troués d'abord. Arrêt au premier 429 (le titre en cours n'est pas marqué : il sera repris).
    `force` (demande manuelle) ignore le délai de 30 jours entre deux essais sur un même titre. `progress(faits, total)` est appelé après chaque titre."""
    tried = setting(conn, 'gap_fill_tried', {})
    today = naive_utc(now).date()
    by_id = {r['listing_id']: r for r in rows}
    missing = {}
    with conn.cursor() as cur:
        for part in _batches(list(by_id), CHUNK):
            cur.execute(f"SELECT listing_id, expected_252 - observed_252 m FROM series_state WHERE coverage_252 < 1 AND expected_252 IS NOT NULL AND listing_id IN ({','.join(['%s'] * len(part))})", part)
            missing.update({r['listing_id']: int(r['m']) for r in cur.fetchall()})
    todo = [i for i in sorted(missing, key=lambda i: (missing[i], i)) if force or not tried.get(str(i)) or (today - datetime.date.fromisoformat(tried[str(i)])).days >= GAP_RETRY_DAYS]
    started, done, added, limited = time.monotonic(), 0, 0, False
    for i in todo[:limit]:
        if time.monotonic() - started > budget_s:
            break
        try:
            _, n = fill_daily_gaps(conn, client, [by_id[i]], now)
        except RateLimited:
            limited = True
            break
        except Exception:                                                              # noqa: BLE001 : réponse absente ou illisible : réessai au prochain passage
            continue
        tried[str(i)] = today.isoformat()
        done, added = done + 1, added + n
        if progress:
            progress(done, min(len(todo), limit))
    keep = {k: v for k, v in tried.items() if (today - datetime.date.fromisoformat(v)).days < GAP_RETRY_DAYS}
    with conn.cursor() as cur:
        cur.execute('INSERT INTO settings(name, value_json, updated_at) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE value_json=VALUES(value_json), updated_at=VALUES(updated_at)',
                    ('gap_fill_tried', json.dumps(keep), naive_utc(now)))
    conn.commit()
    return {'candidates': len(todo), 'examined': done, 'added': added, 'remaining': len(todo) - done, 'rate_limited': limited}


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


def observed_holiday(conn, mic, day):
    """Jour férié déduit des données : la collecte quotidienne de la place est passée après le règlement SANS erreur notable, et pourtant moins de 5 % des
    titres suivis ont une clôture ce jour-là. Une panne du fournisseur (beaucoup d'erreurs, ou collecte pas encore passée) n'est jamais prise pour un férié."""
    settled = hours.settle_utc(mic, day)
    with conn.cursor() as cur:
        cur.execute("""SELECT 1 FROM jobs WHERE job_type IN ('history', %s) AND status IN ('completed','completed_with_errors') AND COALESCE(items_ok, 0) > 0
                       AND items_error <= 0.05 * (COALESCE(items_ok, 0) + items_error) AND started_at > %s LIMIT 1""", ('daily:' + mic, settled))
        if not cur.fetchone():
            return False
        cur.execute("""SELECT COUNT(*) total, COUNT(d.listing_id) closed
                       FROM v_collect_set c JOIN listings l ON l.id=c.listing_id
                       LEFT JOIN daily_prices d ON d.listing_id=c.listing_id AND d.price_date=%s WHERE l.mic=%s""", (day, mic))
        r = cur.fetchone()
    total = int(r['total'] or 0)
    return total > 0 and int(r['closed'] or 0) < 0.05 * total


def effective_expected_close(conn, mic, now, lookback=5):
    """Dernière clôture due (ISO) : celle de l'horloge (jours ouvrés + délai de publication) en reculant sur les jours fériés observés dans les données.
    Sans cela, un jour férié rendrait toute la place « périmée » (donc « non évaluable ») jusqu'à la collecte du lendemain."""
    day = datetime.date.fromisoformat(hours.expected_last_close(mic, now))
    for _ in range(lookback):
        if not observed_holiday(conn, mic, day):
            break
        day -= datetime.timedelta(days=1)
        while day.weekday() >= 5:
            day -= datetime.timedelta(days=1)
    return day.isoformat()


def is_holiday(conn, mic, group, day, settled):
    """Jour sans séance pour la place : aucune barre de 15 min ET aucune clôture quotidienne, alors qu'une collecte quotidienne est passée après le règlement.
    Une absence de données Yahoo (barres manquantes mais clôtures présentes) n'est JAMAIS un jour férié : la séance reste à rattraper."""
    ids = [r['listing_id'] for r in group]
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM jobs WHERE job_type IN ('history', %s) AND status IN ('completed','completed_with_errors') AND started_at > %s LIMIT 1", ('daily:' + mic, settled))
        if not cur.fetchone():
            return False                                    # la clôture du jour n'a pas encore été cherchée : on ne conclut pas
        with_close = 0
        for part in _batches(ids, CHUNK):
            cur.execute(f"SELECT COUNT(DISTINCT listing_id) n FROM daily_prices WHERE price_date=%s AND listing_id IN ({','.join(['%s'] * len(part))})", [day] + part)
            with_close += cur.fetchone()['n']
    return with_close < 0.05 * len(ids)


def intraday_plan(conn, rows, now, previous=True):
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
            for end, which, day in ((e0, 0, prev_day), (e1, 1, cur_day)):
                seen = sum(1 for c in counts.values() if c[which] > 0)
                settled = end + datetime.timedelta(minutes=hours.SETTLE_MINUTES)
                if seen >= 0.05 * len(group) or settled >= naive:
                    continue
                if is_holiday(conn, mic, group, day, settled):
                    holiday0, holiday1 = (True, holiday1) if which == 0 else (holiday0, True)
        live = hours.is_open(mic, now) or s1 <= naive < e1 + datetime.timedelta(minutes=hours.SETTLE_MINUTES)
        for r in group:
            c0, c1 = counts.get(r['listing_id'], (0, 0))
            miss0 = previous and not holiday0 and c0 < 0.8 * expected      # le passage du cron laisse la séance précédente au rattrapage (catchup.py)
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


def collect_intraday(conn, client, rows, now, range_='1d', progress=None, failed=None, deadline=None, unfetched=None):
    """Barres de 15 min. Une barre provisoire n'écrase jamais une barre définitive. Met à jour latest_prices.
    `failed` reçoit les cotations que Yahoo n'a pas renvoyées ; `deadline` (temps monotonic) interrompt entre deux lots et `unfetched` reçoit alors les cotations
    pas encore demandées (également sur un 429 : l'appelant sait exactement ce qui reste à faire). Renvoie (cotations_ok, barres, erreurs)."""
    by_symbol = {r['symbol'].upper(): r for r in rows}
    cutoff = naive_utc(now)
    ok = lines = err = 0
    batches = list(_batches(sorted(by_symbol), SPARK_BATCH))
    for i, part in enumerate(batches):
        if deadline is not None and time.monotonic() > deadline:
            if unfetched is not None:
                unfetched.extend(by_symbol[x]['listing_id'] for rest in batches[i:] for x in rest)
            break
        try:
            data = client.spark(part, range_, '15m')
        except RateLimited:
            if unfetched is not None:
                unfetched.extend(by_symbol[x]['listing_id'] for rest in batches[i:] for x in rest)
            raise
        except Exception:
            err += len(part)
            if failed is not None:
                failed.extend(by_symbol[x]['listing_id'] for x in part)
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
        if failed is not None:
            failed.extend(by_symbol[x]['listing_id'] for x in part if x not in data)
        if progress:
            progress(len(part))
    return ok, lines, err


# Profondeur réelle de Yahoo en 15 minutes (mesurée le 2026-10-28) : 5d → 5 séances, 1mo → 22, 60d → 60 (du 5 août au 28 octobre) ; 3mo est refusé (HTTP 422).
# Le nombre de séances comptées ici est celui des jours ouvrés (fériés compris) : on demande 60d jusqu'à 64 pour laisser Yahoo répondre lui-même sur la limite.
INTRADAY_RANGES = ((5, '5d'), (22, '1mo'), (64, '60d'))
YAHOO_DEPTH_SESSIONS = 60


def intraday_range(sessions_back):
    """Plus petite plage Yahoo qui remonte à `sessions_back` séances (jour courant compris) ; None si c'est au-delà de ce que Yahoo peut fournir."""
    return next((rg for n, rg in INTRADAY_RANGES if sessions_back <= n), None)


def retention_sessions(conn):
    """Séances de barres de 15 minutes conservées ET surveillées : la même limite pour la rétention, la détection et la réparation (jamais plus que Yahoo ne fournit)."""
    return max(1, min(int(setting(conn, 'intraday_retention_sessions', 20)), YAHOO_DEPTH_SESSIONS))


def prune_intraday(conn, now, sessions=None):
    sessions = sessions or retention_sessions(conn)
    limit = naive_utc(now) - datetime.timedelta(days=int(sessions * 7 / 5) + 2)
    with conn.cursor() as cur:
        cur.execute('DELETE FROM intraday_prices WHERE slot_start < %s', (limit,))
        n = cur.rowcount
        cur.execute('DELETE FROM price_gaps WHERE session_date < %s', (limit.date(),))
    conn.commit()
    return n


# ───────── trous ─────────
GAP_MISSING_RATIO = 0.4        # un créneau est manquant s'il compte moins de 40 % de la part de titres qu'il a d'habitude
GAP_MIN_SLOTS = 2              # il faut au moins 2 créneaux manquants dans la séance
GAP_EMPTY_RATIO = 0.05         # sous 5 % des titres avec une barre, la séance est « vide »
GAP_COVERAGE_RATIO = 0.85      # une séance couvre au moins 85 % du nombre de titres habituel


def _quantile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))] if v else 0


def settled_at(mic, day):
    """Instant (UTC naïf) où la clôture officielle de la séance `day` est publiée (fermeture + délai de règlement)."""
    from zoneinfo import ZoneInfo
    tz, _, closes = hours.spec(mic)
    return (datetime.datetime.combine(day, closes, ZoneInfo(tz)).astimezone(datetime.timezone.utc).replace(tzinfo=None)
            + datetime.timedelta(minutes=hours.SETTLE_MINUTES))


def recent_sessions(mic, now, n=2):
    """Les `n` dernières séances terminées et publiées de la place (jours ouvrés, la plus récente d'abord)."""
    today = hours.session_date(mic, now)
    days, d = [], today
    while len(days) < n and (today - d).days <= n * 2 + 4:
        if d.weekday() < 5 and hours.is_settled(mic, d, now):
            days.append(d)
        d -= datetime.timedelta(days=1)
    return days


def session_titles(conn, mic, day, ids):
    """Nombre de titres de la place qui ont au moins une barre de 15 minutes pendant la séance `day`."""
    from engine.market import intraday as intra
    start, end = intra.session_window(mic, day)
    n = 0
    with conn.cursor() as cur:
        for part in _batches(ids, CHUNK):
            cur.execute(f"SELECT COUNT(DISTINCT listing_id) n FROM intraday_prices WHERE slot_start>=%s AND slot_start<%s AND listing_id IN ({','.join(['%s'] * len(part))})", [start, end] + part)
            n += cur.fetchone()['n']
    return n


def session_gaps(conn, mic, now, sessions=None):
    """{jour local: description} des séances terminées et publiées, parmi les `sessions` dernières (par défaut la rétention), où des DONNÉES MANQUENT vraiment.
    Un titre peu échangé n'a pas de barre sur les créneaux sans transaction : on ne regarde donc jamais « combien de barres par titre »
    mais, pour chaque créneau, la part des titres de la place qui ont une barre, comparée à ce même créneau les autres jours, et le nombre de titres couverts.
      - séance sans (presque) aucune barre ALORS QUE les clôtures quotidiennes existent : trou (Yahoo n'a pas répondu, ce n'est pas un jour férié) — même si
        la place n'a JAMAIS eu de barre ;
      - créneaux nettement sous leur niveau habituel (≥ 2) : trou ;
      - titres couverts nettement sous le niveau habituel (collecte interrompue en cours de route) : trou ;
      - séance sans barre ni clôture : jour férié (ou clôtures pas encore collectées : revu dès qu'elles arrivent), pas un trou."""
    from engine.market import intraday as intra
    rows = collection_set(conn, mic)
    ids = [r['listing_id'] for r in rows]
    if not ids or not hours.known(mic):
        return {}
    days = recent_sessions(mic, now, sessions or retention_sessions(conn))
    if not days:
        return {}
    per_slot, closes = defaultdict(int), {}
    first = intra.session_window(mic, min(days))[0]
    with conn.cursor() as cur:
        for part in _batches(ids, CHUNK):
            marks = ','.join(['%s'] * len(part))
            cur.execute(f"SELECT slot_start, COUNT(*) n FROM intraday_prices WHERE slot_start>=%s AND listing_id IN ({marks}) GROUP BY slot_start", [first] + part)
            for r in cur.fetchall():
                per_slot[r['slot_start']] += r['n']
            cur.execute(f"SELECT price_date, COUNT(DISTINCT listing_id) n FROM daily_prices WHERE price_date>=%s AND listing_id IN ({marks}) GROUP BY price_date", [min(days)] + part)
            for r in cur.fetchall():
                closes[r['price_date']] = closes.get(r['price_date'], 0) + r['n']
    n = len(ids)
    ratios = {day: [per_slot.get(t, 0) / n for t in intra.expected_slot_starts(mic, day)] for day in days}
    out, usable = {}, []
    for day in days:
        if max(ratios[day]) < GAP_EMPTY_RATIO:
            if closes.get(day, 0) >= GAP_EMPTY_RATIO * n:
                out[day] = 'aucune barre alors que les clôtures quotidiennes existent (données Yahoo absentes)'
            continue                                                 # sans barre ni clôture : jour férié
        usable.append(day)
    titles = {day: session_titles(conn, mic, day, ids) for day in usable}
    for day in usable:
        others = [ratios[x] for x in usable if len(ratios[x]) == len(ratios[day])]
        flat = _quantile(ratios[day], 0.85)
        profile = [statistics.median(r[i] for r in others) if len(others) >= 3 else flat for i in range(len(ratios[day]))]
        slots = intra.expected_slot_starts(mic, day)
        missing = [t for t, ratio, ref in zip(slots, ratios[day], profile) if ref >= GAP_EMPTY_RATIO and ratio < GAP_MISSING_RATIO * ref]
        if len(missing) >= GAP_MIN_SLOTS:
            out[day] = f'{len(missing)} créneaux sur {len(slots)} nettement sous leur niveau habituel (de {missing[0]:%H:%M} à {missing[-1]:%H:%M} UTC)'
            continue
        rest = [titles[x] for x in usable if x != day]
        usual = statistics.median(rest) if len(rest) >= 3 else 0
        if usual and titles[day] < GAP_COVERAGE_RATIO * usual:
            out[day] = f'{titles[day]} titres avec des barres sur {int(usual)} habituellement'
    return out
