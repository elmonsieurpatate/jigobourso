"""Calcul nocturne : mesures par fenêtre (strategy_metrics) et état de série (series_state) pour chaque cotation suivie."""
import datetime
import json

from .measures import window_metrics, technical_state
from .series import usable_closes, find_breaks, clean_window, analyze_series
from . import strategy
from ..market import collect
from ..market.calendar import session_dates, window_calendars
from ..market.hours import expected_last_close  # noqa: F401 (conservé pour compatibilité)

BASE_WINDOWS = (1, 5, 21, 63, 126, 252)


def wanted_windows(conn):
    """Fenêtres de base + toutes celles demandées par une stratégie enregistrée dans un portefeuille."""
    windows = set(BASE_WINDOWS)
    with conn.cursor() as cur:
        cur.execute('SELECT strategy_config FROM portfolios WHERE strategy_config IS NOT NULL')
        for row in cur.fetchall():
            try:
                cfg = json.loads(row['strategy_config'])
                if cfg.get('version') == strategy.VERSION:
                    windows |= set(strategy.required_sessions(cfg))
            except (TypeError, ValueError, KeyError):
                continue
    return sorted(w for w in windows if 1 <= w <= 252)


def _dec(v, places=6):
    return None if v is None else round(v, places)


def compute_all(conn, now, batch=400):
    """Recalcule les tables d'analyse pour le jeu de collecte. Renvoie (cotations, lignes de mesures).

    Les clôtures sont lues par lots de `batch` cotations : la mémoire reste de l'ordre de la centaine de Mo (hébergement mutualisé)."""
    windows = wanted_windows(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, mic FROM v_collect_set')
        mics = {r['listing_id']: r['mic'] for r in cur.fetchall()}
        cur.execute('SELECT listing_id, event_date, ratio FROM corporate_events WHERE kind IN (%s,%s)', ('split', 'reverse_split'))
        splits = {}
        for r in cur.fetchall():
            splits.setdefault(r['listing_id'], []).append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
        cur.execute("""SELECT d.listing_id, MAX(d.price_date) last_date FROM daily_prices d
                       JOIN v_collect_set c ON c.listing_id=d.listing_id GROUP BY d.listing_id""")
        market_latest = {}
        for r in cur.fetchall():
            m = mics[r['listing_id']]
            market_latest[m] = max(market_latest.get(m, ''), r['last_date'].isoformat())
    metric_rows, state_rows = [], []
    stamp = now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    expected_by_mic = {m: collect.effective_expected_close(conn, m, now) for m in sorted(set(mics.values()))}      # jours fériés déduits des données
    cutoff_by_mic = {m: max(expected_by_mic.get(m) or '', market_latest.get(m) or '') for m in set(mics.values())}
    calendars_by_mic = {m: window_calendars(m, cutoff_by_mic.get(m), windows) for m in set(mics.values())}
    technical_by_mic = {m: session_dates(m, cutoff_by_mic.get(m), 55) for m in set(mics.values())}
    ids = sorted(mics)
    for start in range(0, len(ids), batch):
        part = ids[start:start + batch]
        bars = {}
        with conn.cursor() as cur:
            cur.execute(f"""SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices
                            WHERE listing_id IN ({','.join(['%s'] * len(part))}) ORDER BY listing_id, price_date""", part)
            for r in cur.fetchall():
                bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
        for lid in part:
            _compute_one(lid, mics[lid], bars.get(lid, []), splits.get(lid, ()), windows, market_latest, stamp, metric_rows, state_rows,
                         expected_by_mic.get(mics[lid]), calendars_by_mic.get(mics[lid]), technical_by_mic.get(mics[lid]))
    with conn.cursor() as cur:
        cur.execute('DELETE FROM strategy_metrics')
        cur.execute('DELETE FROM series_state')
        for i in range(0, len(metric_rows), 5000):
            cur.executemany('''INSERT INTO strategy_metrics(listing_id,sessions,slope,slope_log,r2,perf,volatility,drawdown,er,acceleration,observations,expected_closes,coverage)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', metric_rows[i:i + 5000])
        cur.executemany('''INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma20,ma50,ma50_prev,daily_change,gap_to_ma20,break_age,break_dates,coverage_252,observed_252,expected_252,quality)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', state_rows)
    conn.commit()
    from . import etf
    etf.build(conn, now)
    return len(state_rows), len(metric_rows)


def _compute_one(lid, mic, rows, splits, windows, market_latest, stamp, metric_rows, state_rows, expected_close=None,
                 session_windows=None, technical_sessions=None):
    dates, closes, basis, breaks, measures, missing, t = analyze_series(rows, windows, splits, session_windows, technical_sessions)
    for n, m in measures.items():
        metric_rows.append((lid, n, _dec(m.get('slope') if m else None), _dec(m.get('slope_log') if m else None, 10),
                            _dec(m.get('r2') if m else None), _dec(m.get('perf') if m else None, 4),
                            _dec(m.get('volatility') if m else None), _dec(m.get('drawdown') if m else None, 4),
                            _dec(m.get('er') if m else None), None, (m or {}).get('observations'),
                            (m or {}).get('expected_closes'), _dec((m or {}).get('coverage'), 6)))
    expected = max(expected_close or expected_last_close(mic, stamp), market_latest.get(mic, ''))
    stale = bool(dates) and dates[-1] < expected
    year = measures.get(252) or {}
    # `quality` is an existing ENUM in production. New statuses (incomplete,
    # calendar_unknown) are derived from coverage at read time, not persisted
    # through an unsafe enum conversion.
    quality = 'insufficient' if len(closes) < 22 else 'stale' if stale else 'break' if breaks and breaks[-1] > len(closes) - 253 else 'ok'
    state_rows.append((lid, stamp, dates[-1] if dates else None, len(closes), t['close'], _dec(t['ma20']), _dec(t['ma50']), _dec(t['ma50_prev']),
                       _dec(t['daily_change'], 4), _dec(t['gap_to_ma20'], 4), (len(closes) - 1 - breaks[-1]) if breaks else None,
                       ','.join(dates[i] for i in breaks[-3:])[:80] or None, year.get('coverage'), year.get('observations'), year.get('expected_closes'), quality))
