"""Calcul nocturne : mesures par fenêtre (strategy_metrics) et état de série (series_state) pour chaque cotation suivie."""

import datetime
from engine.shared import units

from .loader import load_splits
from .series import analyze_series, momentum_6_1, momentum_12_1, MOMENTUM_LONG, MOMENTUM_LONG_12
from . import liquidity as liq
from ..scoring.score_inputs import window_inputs
from ..scoring.scores import MIN_SESSIONS
from ...market import collect
from ...market.calendar import session_dates, window_calendars
from ...market.hours import expected_last_close  # noqa: F401 (conservé pour compatibilité)
from ...shared import settings
from ...shared.db import ensure

BASE_WINDOWS = (1, 21, 252)
SPIKE_SHARE_CAP = 9999.0  # colonne DECIMAL(10,6) : sur 3 à 5 ans un cours quasi inchangé donne un gain net minuscule et un rapport énorme ; toute valeur ≥ 1 sature déjà les notes et les filtres (≤ 1)


def bounded_spike_share(value):
    """spike_share à stocker : plafonné pour tenir dans DECIMAL(10,6) (inchangé en dessous du plafond)."""
    return None if value is None else min(value, SPIKE_SHARE_CAP)


LOAD_MIN_DAYS = 610  # lecture minimale des clôtures (≈ 420 séances) : l'historique conservé est plus profond, mais seules les séances utiles au calcul sont lues


def wanted_windows(conn):
    """Fenêtres techniques et périodes actives effectivement demandées par les stratégies."""
    windows = set(BASE_WINDOWS)
    from ..scoring import scores_specs
    from engine.shared.period_requests import requested_sessions

    for item in scores_specs.V4_STRATEGIES.values():
        cfg = item['build']()
        windows.update(p['sessions'] for p in cfg['periods'] if p['enabled'])
    windows.update(requested_sessions(conn))
    return sorted(w for w in windows if type(w) is int and 1 <= w <= 1260)


def history_since(windows, now):
    """Première date de clôture lue pour le calcul : la plus longue fenêtre demandée (1,6 jour calendaire par séance, plus une marge), au moins LOAD_MIN_DAYS.
    L'historique de 1 260 séances conservé en base ne coûte donc ni mémoire ni temps tant qu'aucune stratégie ne demande une période longue."""
    days = max(LOAD_MIN_DAYS, int(max(windows) * 1.6) + 40)
    return now.date() - datetime.timedelta(days=days)


def _dec(v, places=6):
    return None if v is None else round(v, places)


CODE_MODULES = (
    'engine.analytics.series.compute',
    'engine.analytics.series.series',
    'engine.analytics.series.measures',
    'engine.analytics.series.liquidity',
    'engine.analytics.series.loader',
    'engine.analytics.scoring.score_inputs',
    'engine.analytics.scoring.scores',
    'engine.shared.units',
    'engine.market.calendar',
)  # code dont dépendent les mesures stockées : un changement de méthode (déploiement) impose un recalcul complet
FINGERPRINT_SETTING = 'compute_fingerprint'
LAST = {}  # statistiques du dernier passage : mode (full / incremental / unchanged), titres recalculés, raison d'un recalcul complet


def method_fingerprint(windows):
    """Empreinte de la méthode : fenêtres demandées par les stratégies et code des calculs. Elle change quand une stratégie ajoute ou retire une période, ou quand le code des mesures change."""
    import hashlib
    import importlib
    import json

    h = hashlib.md5(json.dumps(sorted(windows)).encode())
    for name in CODE_MODULES:
        with open(importlib.import_module(name).__file__, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def _signature_since(since):
    """Début de la plage couverte par l'empreinte : le 1er du mois, pour que le glissement quotidien de la plage lue ne rende pas tous les titres « modifiés » chaque jour."""
    return since.replace(day=1)


def input_signatures(conn, ids, since, group_of, group_state, splits, factors, quotes):
    """{listing_id: (empreinte des données, empreinte de la cotation)} : les données qui déterminent les résultats d'un titre sont ses clôtures (nombre, bornes, sommes exactes), ses splits, l'état de
    sa place (dernière séance attendue et dernière date de marché) et son facteur de change ; sa cotation (cours, volume moyen) ne compte que tant que sa liquidité est estimée
    (voir `final_signature`). Une clôture ajoutée, corrigée ou disparue change l'empreinte."""
    import hashlib

    agg = {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT listing_id, COUNT(*) n, MIN(price_date) a, MAX(price_date) b, SUM(close_px) s, SUM(COALESCE(adj_close_px,0)) sa, SUM(COALESCE(volume,0)) sv, COUNT(volume) cv
               FROM daily_prices WHERE price_date >= %s GROUP BY listing_id""",
            (_signature_since(since),),
        )
        for r in cur.fetchall():
            agg[r['listing_id']] = (r['n'], r['a'], r['b'], str(r['s']), str(r['sa']), str(r['sv']), r['cv'])
    out = {}
    for lid in ids:
        q = quotes.get(lid) or {}
        base = repr((agg.get(lid), splits.get(lid, ()), group_state.get(group_of[lid]), factors.get(lid)))
        out[lid] = (hashlib.md5(base.encode()).hexdigest(), repr((str(q.get('price')), str(q.get('avg_volume_3m')))))
    return out


def final_signature(parts, liquidity_source):
    """Empreinte stockée : données du titre, plus sa cotation tant que sa liquidité n'est pas établie sur des volumes quotidiens réels (la cotation sert alors à l'estimer)."""
    import hashlib

    return parts[0] if liquidity_source == 'daily' else hashlib.md5((parts[0] + parts[1]).encode()).hexdigest()


def compute_all(conn, now, batch=400, full=False):
    """Recalcule les tables d'analyse du jeu de collecte. Renvoie (cotations, lignes de mesures) de l'ensemble des tables après le passage.

    Incrémental : chaque titre porte une empreinte de ses données d'entrée (`compute_signatures`) ; seuls les titres dont l'empreinte a changé (clôture ajoutée ou corrigée, nouvelle séance
    attendue sur leur place, split, change, cotation tant que la liquidité est estimée, nouveau titre) sont recalculés. Tout est recalculé quand la méthode change (fenêtres demandées ou code
    des calculs, voir `method_fingerprint`), sur demande (`full=True`) ou si les empreintes manquent. Résultat identique à un calcul complet (testé).

    Les clôtures sont lues par lots de `batch` cotations : la mémoire reste de l'ordre de la centaine de Mo (hébergement mutualisé)."""
    import time

    started = time.monotonic()
    windows = wanted_windows(conn)
    since = history_since(windows, now)
    splits = load_splits(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, mic FROM v_collect_set')
        mics = {r['listing_id']: r['mic'] for r in cur.fetchall()}
        cur.execute("""SELECT d.listing_id, MAX(d.price_date) last_date FROM daily_prices d
                       JOIN v_collect_set c ON c.listing_id=d.listing_id GROUP BY d.listing_id""")
        market_latest = {}
        for r in cur.fetchall():
            m = mics[r['listing_id']]
            market_latest[m] = max(market_latest.get(m, ''), r['last_date'].isoformat())
    stamp = now.astimezone(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    expected_by_mic = {m: collect.effective_expected_close(conn, m, now) for m in sorted(set(mics.values()))}  # jours fériés déduits des données
    cutoff_by_mic = {m: max(expected_by_mic.get(m) or '', market_latest.get(m) or '') for m in set(mics.values())}
    calendars_by_mic = {m: window_calendars(m, cutoff_by_mic.get(m), windows) for m in set(mics.values())}
    technical_by_mic = {m: session_dates(m, cutoff_by_mic.get(m), 205) for m in set(mics.values())}
    rates = collect.latest_rates(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, price, currency, avg_volume_3m FROM latest_prices')
        quotes = {r['listing_id']: r for r in cur.fetchall()}
        cur.execute('SELECT id, currency FROM listings')
        listing_currency = {r['id']: r['currency'] for r in cur.fetchall()}
        cur.execute('SELECT listing_id, source FROM liquidity_state')
        daily_source = {r['listing_id']: r['source'] for r in cur.fetchall()}
    factors = {lid: units.to_eur_factor((quotes.get(lid) or {}).get('currency') or listing_currency.get(lid), rates) for lid in mics}
    ids = sorted(mics)
    parts = input_signatures(conn, ids, since, mics, {m: (expected_by_mic.get(m), market_latest.get(m)) for m in set(mics.values())}, splits, factors, quotes)
    signatures = {lid: final_signature(parts[lid], daily_source.get(lid)) for lid in ids}
    fingerprint = method_fingerprint(windows)
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id, signature FROM compute_signatures')
        stored = {r['listing_id']: r['signature'] for r in cur.fetchall()}
        cur.execute('SELECT listing_id FROM series_state')
        present = {r['listing_id'] for r in cur.fetchall()}
    reason = 'sur demande' if full else None
    if reason is None and settings.get(conn, FINGERPRINT_SETTING, None) != fingerprint:
        reason = 'méthode modifiée (fenêtres des stratégies ou code des calculs)'
    dirty = ids if reason else [lid for lid in ids if stored.get(lid) != signatures[lid] or lid not in present]  # nouveau titre, données modifiées, ou ligne d'état manquante
    removed = sorted(present - set(ids))
    LAST.clear()
    LAST.update(mode='full' if reason else ('incremental' if dirty else 'unchanged'), reason=reason, recomputed=len(dirty), total=len(ids), removed=len(removed))
    metric_rows, state_rows, score_rows, liquidity_rows = [], [], [], []
    for start in range(0, len(dirty), batch):
        part = dirty[start : start + batch]
        bars = {}
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT listing_id, price_date, close_px, adj_close_px, volume FROM daily_prices
                            WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND price_date >= %s ORDER BY listing_id, price_date""",
                part + [since],
            )
            volumes = {}
            for r in cur.fetchall():
                bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
                volumes.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), r['volume']))
        for lid in part:
            _compute_one(
                lid,
                mics[lid],
                bars.get(lid, []),
                splits.get(lid, ()),
                windows,
                market_latest,
                stamp,
                metric_rows,
                state_rows,
                expected_by_mic.get(mics[lid]),
                calendars_by_mic.get(mics[lid]),
                technical_by_mic.get(mics[lid]),
                score_rows=score_rows,
                volume_bars=volumes.get(lid, []),
                eur_factor=factors[lid],
            )
            q = quotes.get(lid) or {}
            last20 = [(c, v) for _d, c, v in volumes.get(lid, [])][-liq.WINDOW :]
            info = liq.liquidity(last20, float(q['price']) if q.get('price') is not None else None, q.get('avg_volume_3m'), factors[lid])
            liquidity_rows.append((lid, None if info['turnover_eur'] is None else round(info['turnover_eur'], 2), info['days'] if info['source'] == 'daily' else None, info['source'], stamp))
    sources = {row[0]: row[3] for row in liquidity_rows}  # source de liquidité établie par ce calcul : elle décide si la cotation compte dans l'empreinte stockée
    ensure(conn)  # le calcul ci-dessus n'interroge pas la base : la connexion a pu être fermée ; rien n'est encore écrit
    stale = sorted(set(dirty) | set(removed))
    with conn.cursor() as cur:
        for i in range(0, len(stale), 1000):
            marks = ','.join(['%s'] * len(stale[i : i + 1000]))
            for table in ('strategy_metrics', 'series_state', 'score_inputs'):
                cur.execute(f'DELETE FROM {table} WHERE listing_id IN ({marks})', stale[i : i + 1000])
            cur.execute(f'DELETE FROM compute_signatures WHERE listing_id IN ({marks})', stale[i : i + 1000])
        for i in range(0, len(metric_rows), 5000):
            cur.executemany(
                '''INSERT INTO strategy_metrics(listing_id,sessions,slope,slope_log,r2,perf,volatility,drawdown,er,acceleration,observations,expected_closes,coverage)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                metric_rows[i : i + 5000],
            )
        for i in range(0, len(score_rows), 5000):
            cur.executemany(
                '''INSERT INTO score_inputs(listing_id,sessions,up_fraction,spike_share,accel,r2_prev,momentum_perf,recovery,mrar,turnover_eur,volume_days) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                score_rows[i : i + 5000],
            )
        # volume_checked_at (passage du collecteur de volumes) est conservé : mise à jour des seuls champs calculés.
        for i in range(0, len(liquidity_rows), 5000):
            cur.executemany(
                '''INSERT INTO liquidity_state(listing_id,turnover_eur,days,source,computed_at) VALUES (%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE turnover_eur=VALUES(turnover_eur), days=VALUES(days), source=VALUES(source), computed_at=VALUES(computed_at)''',
                liquidity_rows[i : i + 5000],
            )
        if state_rows:
            cur.executemany(
                '''INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma20,ma50,ma50_prev,ma200,ma200_prev,daily_change,gap_to_ma20,break_age,break_dates,coverage_252,observed_252,expected_252,momentum_6m,momentum_12m,quality)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                state_rows,
            )
        cur.executemany('INSERT INTO compute_signatures(listing_id,signature,computed_at) VALUES (%s,%s,%s)', [(lid, final_signature(parts[lid], sources[lid]), stamp) for lid in dirty])
        cur.execute('UPDATE series_state SET computed_at=%s', (stamp,))  # « dernier calcul » = dernière vérification : les titres inchangés ont été contrôlés à cet instant
        cur.execute('UPDATE liquidity_state SET computed_at=%s', (stamp,))
        cur.execute('SELECT COUNT(*) n FROM series_state')
        n_series = cur.fetchone()['n']
        cur.execute('SELECT COUNT(*) n FROM strategy_metrics')
        n_metrics = cur.fetchone()['n']
    settings.put(conn, FINGERPRINT_SETTING, fingerprint)
    conn.commit()
    LAST['seconds'] = round(time.monotonic() - started, 1)
    return n_series, n_metrics


def _compute_one(
    lid,
    mic,
    rows,
    splits,
    windows,
    market_latest,
    stamp,
    metric_rows,
    state_rows,
    expected_close=None,
    session_windows=None,
    technical_sessions=None,
    score_rows=None,
    previous_windows=None,
    volume_bars=None,
    eur_factor=None,
):
    dates, closes, basis, breaks, measures, missing, t = analyze_series(rows, windows, splits, session_windows, technical_sessions)
    if score_rows is not None and session_windows:
        observations = dict(zip(dates, closes))
        volumes_by_date = {d: (c, v) for d, c, v in (volume_bars or [])}
        for n in windows:
            if n < MIN_SESSIONS or not session_windows.get(n):
                continue
            cur_dates = session_windows[n]
            if any(cur_dates[0] < dates[i] <= cur_dates[-1] for i in breaks):
                continue  # saut de cours dans la fenêtre : aucune mesure de score
            m = window_inputs(cur_dates, [], observations)
            period_bars = [volumes_by_date.get(d, (None, None)) for d in cur_dates[1:]]
            turnover, days = liq.period_turnover(period_bars, eur_factor)
            score_rows.append(
                (
                    lid,
                    n,
                    _dec(m['up_fraction'], 6),
                    _dec(bounded_spike_share(m['spike_share']), 6),
                    _dec(m['accel']),
                    _dec(m['r2_prev'], 6),
                    _dec(m['momentum_perf'], 4),
                    _dec(m['recovery'], 4),
                    _dec(m['mrar'], 4),
                    _dec(turnover, 4),
                    days,
                )
            )
    for n, m in measures.items():
        metric_rows.append(
            (
                lid,
                n,
                _dec(m.get('slope') if m else None),
                _dec(m.get('slope_log') if m else None, 10),
                _dec(m.get('r2') if m else None),
                _dec(m.get('perf') if m else None, 4),
                _dec(m.get('volatility') if m else None),
                _dec(m.get('drawdown') if m else None, 4),
                _dec(m.get('er') if m else None),
                None,
                (m or {}).get('observations'),
                (m or {}).get('expected_closes'),
                _dec((m or {}).get('coverage'), 6),
            )
        )
    expected = max(expected_close or expected_last_close(mic, stamp), market_latest.get(mic, ''))
    stale = bool(dates) and dates[-1] < expected
    year = measures.get(252) or {}
    # `quality` is an existing ENUM in production. New statuses (incomplete,
    # calendar_unknown) are derived from coverage at read time, not persisted
    # through an unsafe enum conversion.
    quality = 'insufficient' if len(closes) < 22 else 'stale' if stale else 'break' if breaks and breaks[-1] > len(closes) - 253 else 'ok'
    state_rows.append(
        (
            lid,
            stamp,
            dates[-1] if dates else None,
            len(closes),
            t['close'],
            _dec(t['ma20']),
            _dec(t['ma50']),
            _dec(t['ma50_prev']),
            _dec(t['ma200']),
            _dec(t['ma200_prev']),
            _dec(t['daily_change'], 4),
            _dec(t['gap_to_ma20'], 4),
            (len(closes) - 1 - breaks[-1]) if breaks else None,
            ','.join(dates[i] for i in breaks[-3:])[:80] or None,
            year.get('coverage'),
            year.get('observations'),
            year.get('expected_closes'),
            _dec(momentum_6_1(dates, closes, breaks, (session_windows or {}).get(MOMENTUM_LONG)), 6),
            _dec(momentum_12_1(dates, closes, breaks, (session_windows or {}).get(MOMENTUM_LONG_12)), 6),
            quality,
        )
    )
