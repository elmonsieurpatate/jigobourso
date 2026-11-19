"""Matrice des cours détenus : deux fenêtres adjacentes, indépendantes des achats.

Lecture groupée des cours existants uniquement ; aucune collecte ni modification
financière. Le registre PHP reste l'unique source des gains personnels en euros.
"""

import bisect
import calendar
import datetime
import hashlib
import json
import math

from engine.market import hours
from engine.market.calendar import session_dates
from engine.analytics.series.loader import load_bars_and_splits
from engine.analytics.series.series import prepare_series

VERSION = 3
# key, label, sessions (courts), mois calendaires (longs), famille
HORIZONS = (
    ('1d', '1J', 1, None, 'short'),
    ('2d', '2J', 2, None, 'short'),
    ('3d', '3J', 3, None, 'short'),
    ('1w', '1S', 5, None, 'short'),
    ('2w', '2S', 10, None, 'short'),
    ('1m', '1M', None, 1, 'medium'),
    ('3m', '3M', None, 3, 'medium'),
    ('6m', '6M', None, 6, 'medium'),
    ('1y', '1A', None, 12, 'long'),
    ('2y', '2A', None, 24, 'long'),
    ('4y', '4A', None, 48, 'long'),
)


def shift_months(day, months):
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    return datetime.date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


MAX_LAG = 5  # séances de retard tolérées sur la dernière clôture attendue


def heat(value, sessions):
    """Sept intensités (échelle de température) : bruit de 0,05 %, variation modérée à 1 %,
    forte à 3 %, multipliés par sqrt(nombre de séances). Calibration descriptive, pas un score.
    """
    if value is None:
        return 'missing'
    x = value / math.sqrt(max(1, sessions))
    if x >= 3:
        return 'gain-strong'
    if x >= 1:
        return 'gain'
    if x >= 0.05:
        return 'gain-soft'
    if x > -0.05:
        return 'neutral'
    if x > -1:
        return 'loss-soft'
    if x > -3:
        return 'loss'
    return 'loss-strong'


def measure(bars, splits, mic, now, expected=None):
    """Un calcul de préparation et un calendrier par titre, onze découpages en mémoire.
    `expected` permet les tests figés sans calendrier externe ni horloge système.
    """
    settled = hours.latest_settled(mic, now)
    days = expected if expected is not None else session_dates(mic, settled.isoformat(), 2200)
    dates, closes, basis, breaks = prepare_series([b for b in bars if b[0] <= settled.isoformat()], splits)
    obs = dict(zip(dates, closes))
    break_days = [dates[i] for i in breaks]
    # Collecte en retard de quelques séances : les fenêtres se terminent à la dernière clôture connue
    # (la date de fin reste affichée dans chaque cellule). Au-delà de MAX_LAG séances, rien n'est affiché.
    if dates and days:
        known = [d for d in days if d <= dates[-1]]
        lag = len(days) - len(known)
        if 0 < lag <= MAX_LAG:
            days = known
    result = {'basis': basis, 'currency_basis': 'listing', 'as_of': days[-1] if days else None, 'last_available': dates[-1] if dates else None, 'cells': {}}
    if not days:
        for key, *_ in HORIZONS:
            result['cells'][key] = {'return': None, 'previous': None, 'delta': None, 'reason': 'calendar', 'previous_reason': 'calendar', 'heat': 'missing', 'arrow': None}
        return result
    anchor = datetime.date.fromisoformat(days[-1])

    def at_boundary(months):
        return bisect.bisect_right(days, shift_months(anchor, months).isoformat()) - 1

    def window(start, end):
        if start < 0 or end < 0 or not dates or days[start] < dates[0]:
            return None, 'history'
        if any(days[start] < d <= days[end] for d in break_days):
            return None, 'break'
        if any(d not in obs for d in days[start : end + 1]):
            return None, 'missing'
        return 100 * (obs[days[end]] / obs[days[start]] - 1), None

    end = len(days) - 1
    for key, _, n, months, _ in HORIZONS:
        mid, start = (end - n, end - 2 * n) if n else (at_boundary(months), at_boundary(2 * months))
        value, reason = window(mid, end)
        previous, prev_reason = window(start, mid)
        delta = value - previous if value is not None and previous is not None else None
        count = max(1, end - mid)
        noise = 0.05 * math.sqrt(2 * count)
        result['cells'][key] = {
            'return': value,
            'previous': previous,
            'delta': delta,
            'reason': reason,
            'previous_reason': prev_reason,
            'start': days[mid] if mid >= 0 else None,
            'end': days[end],
            'previous_start': days[start] if start >= 0 else None,
            'heat': heat(value, count),
            'arrow': None if delta is None else 'up' if delta > noise else 'down' if delta < -noise else 'flat',
            'neutral_points': noise,
        }
    return result


def run(conn, request, now=None):
    """Une lecture de cours et de splits pour toutes les positions encore détenues.
    Cache partagé existant, signature du contenu : corrections/splits compris.
    Aucun résultat personnel ni identifiant de compte dans ce cache de marché.
    """
    now = now or hours.utcnow()
    ids = sorted({int(x) for x in request.get('listing_ids', [])})
    if not ids:
        return {'horizons': [dict(key=k, label=l, group=g) for k, l, _, _, g in HORIZONS], 'listings': {}}
    bars, splits = load_bars_and_splits(conn, ids)
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, mic, currency FROM listings WHERE id IN ({','.join(['%s'] * len(ids))})", ids)
        meta = {r['id']: r for r in cur.fetchall()}
    key = hashlib.sha1(('portfolio-dynamics:' + ','.join(map(str, ids))).encode()).hexdigest()
    version = hashlib.sha1(
        json.dumps([VERSION, now.date().isoformat(), {i: str(hours.latest_settled(meta[i]['mic'], now)) for i in ids if i in meta}, bars, splits, meta], sort_keys=True, default=str).encode()
    ).hexdigest()
    with conn.cursor() as cur:
        cur.execute('SELECT data_version, payload FROM result_cache WHERE cache_key=%s', (key,))
        cached = cur.fetchone()
        if cached and cached['data_version'] == version:
            return json.loads(cached['payload'])
    out = {'horizons': [dict(key=k, label=l, group=g) for k, l, _, _, g in HORIZONS], 'listings': {}}
    for lid in ids:
        if lid not in meta:
            continue
        out['listings'][str(lid)] = measure(bars.get(lid, []), splits.get(lid, []), meta[lid]['mic'], now) | {'currency': meta[lid]['currency']}
    with conn.cursor() as cur:
        cur.execute('REPLACE INTO result_cache(cache_key,data_version,built_at,payload) VALUES (%s,%s,%s,%s)', (key, version, now.replace(tzinfo=None), json.dumps(out)))
    conn.commit()
    return out
