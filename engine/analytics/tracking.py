"""Suivi des classements : chaque soir, les meilleurs titres de chaque stratégie sont enregistrés (preuve datée) ;
quelques séances plus tard, leur rendement est comparé à celui de tout l'univers recommandable.

Rien ici ne promet un résultat : on mesure ce qui s'est passé après les classements passés.
Les instantanés « reconstitués » (backfill) utilisent l'univers actuel : ils sont étiquetés, jamais présentés comme du vécu.
"""
import bisect
import datetime
import statistics
from collections import defaultdict

from . import service, strategy
from .repository import recommendable_candidates
from .series import usable_closes, find_breaks, prepare_series

HORIZONS = (1, 3, 5)
TOP_N = 20              # titres gardés par groupe (actions / ETF) et par stratégie
MAX_STALE_DAYS = 5      # base de calcul trop ancienne : le titre n'est pas évalué ce jour-là


def forward_returns(bars, snap_date, horizons=HORIZONS, splits=()):
    """Rendement (%) N séances après `snap_date`, par horizon disponible. bars = [(date, close, adj_close|None)] triées.

    Base = dernière clôture ≤ snap_date. Un saut de cours non expliqué entre la base et la cible invalide l'horizon."""
    dates, closes, basis, breaks = prepare_series(bars, splits)
    base = bisect.bisect_right(dates, snap_date) - 1
    if base < 0:
        return {}
    gap = datetime.date.fromisoformat(snap_date) - datetime.date.fromisoformat(dates[base])
    if gap.days > MAX_STALE_DAYS:
        return {}
    out = {}
    for k in horizons:
        j = base + k
        if j >= len(closes):
            break
        if any(base < b <= j for b in breaks):
            continue
        out[k] = 100 * (closes[j] / closes[base] - 1)
    return out


def summarize(returns, benchmarks, benchmarks_mean=None):
    """returns : [(snap_date, rendement)], benchmarks : {snap_date: médiane de l'univers}, benchmarks_mean : {snap_date: moyenne de l'univers}. Statistiques descriptives ou None.

    `edge` compare des choses comparables : la MOYENNE des titres choisis à la MOYENNE de l'univers (si fournie ; sinon, comme avant, à sa médiane, ce qui flatte
    quand les rendements sont asymétriques). `edge_median` = écart médian à la médiane de l'univers ; `beat_pct` = part des titres qui battent la médiane.
    `days` = nombre de jours de classement distincts : les observations d'un même jour et de jours voisins se chevauchent, `n` ne compte donc pas autant de cas indépendants."""
    if not returns:
        return None
    rets = [r for _, r in returns]
    diffs = [r - benchmarks[d] for d, r in returns if d in benchmarks]
    mean_diffs = [r - benchmarks_mean[d] for d, r in returns if benchmarks_mean and d in benchmarks_mean]
    edge = statistics.fmean(mean_diffs) if mean_diffs else (statistics.fmean(diffs) if diffs else None)
    return {'n': len(rets), 'days': len({d for d, _ in returns}), 'mean': statistics.fmean(rets), 'median': statistics.median(rets),
            'win_pct': 100 * sum(1 for r in rets if r > 0) / len(rets),
            'edge': edge, 'edge_basis': 'mean' if mean_diffs else 'median', 'edge_median': statistics.median(diffs) if diffs else None,
            'beat_pct': 100 * sum(1 for x in diffs if x > 0) / len(diffs) if diffs else None}


def reference_calendar(conn):
    """Séances de référence : dates où au moins la moitié des séries recommandables ont une clôture."""
    with conn.cursor() as cur:
        cur.execute("""SELECT d.price_date, COUNT(*) n FROM daily_prices d JOIN v_recommendable r ON r.listing_id = d.listing_id
                       GROUP BY d.price_date ORDER BY d.price_date""")
        rows = cur.fetchall()
    if not rows:
        return []
    biggest = max(r['n'] for r in rows)
    return [r['price_date'].isoformat() for r in rows if r['n'] >= biggest / 2]


def _top_picks(verdicts):
    picks = []
    for group in ('equity', 'etf'):
        ranked = sorted((v for v in verdicts if v['group'] == group and v['status'] == 'retained' and v['rank'] is not None and v['rank'] <= TOP_N),
                        key=lambda v: v['rank'])
        picks += [(v['key'], group, v['rank'], v['score']) for v in ranked]
    return picks


def _store(conn, snap_date, preset, picks, origin):
    verb = 'INSERT' if origin == 'live' else 'INSERT IGNORE'     # une reconstitution n'écrase jamais un instantané existant
    rows = [(snap_date, preset, lid, grp, rank, None if score is None else round(score, 2), origin) for lid, grp, rank, score in picks]
    with conn.cursor() as cur:
        if origin == 'live':      # le classement vécu du jour remplace tout ce qui existait pour cette stratégie ce jour-là
            cur.execute('DELETE FROM ranking_snapshots WHERE snap_date=%s AND preset=%s', (snap_date, preset))
            cur.execute('DELETE FROM ranking_outcomes WHERE snap_date=%s AND preset=%s', (snap_date, preset))
            cur.execute('DELETE FROM universe_outcomes WHERE snap_date=%s', (snap_date,))    # forcera le recalcul des résultats
        if rows:
            cur.executemany(f'{verb} INTO ranking_snapshots(snap_date,preset,listing_id,grp,rank_pos,score,origin) VALUES (%s,%s,%s,%s,%s,%s,%s)', rows)
    conn.commit()
    return len(rows)


def record_snapshot(conn):
    """Enregistre le classement du jour pour chaque stratégie de départ. Renvoie (date, lignes) ; (None, 0) sans donnée."""
    with conn.cursor() as cur:
        cur.execute('SELECT MAX(s.last_close_date) d FROM series_state s JOIN v_recommendable r ON r.listing_id = s.listing_id')
        day = cur.fetchone()['d']
    if day is None:
        return None, 0
    total = 0
    for name in strategy.PRESETS:
        total += _store(conn, day.isoformat(), name, _top_picks(service.judge_universe(conn, strategy.preset(name))), 'live')
    return day.isoformat(), total


def backfill(conn, sessions=30, log=lambda *_: None, batch=300):
    """Reconstitue les classements des `sessions` dernières séances à partir des clôtures (univers actuel, origine « rebuilt »).

    Lecture par lots de cotations ; seuls les verdicts retenus restent en mémoire, car le rang ne dépend que d'eux."""
    configs = {name: strategy.validate(strategy.preset(name)) for name in strategy.PRESETS}
    days = reference_calendar(conn)[-sessions:]
    with conn.cursor() as cur:
        cur.execute('SELECT listing_id FROM v_recommendable ORDER BY listing_id')
        ids = [r['listing_id'] for r in cur.fetchall()]
    retained = defaultdict(list)
    for start in range(0, len(ids), batch):
        for c in recommendable_candidates(conn, history=400, ids=ids[start:start + batch]):
            ds = [b[0] for b in c['bars']]
            for day in days:
                n = bisect.bisect_right(ds, day)
                if not n or (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(ds[n - 1])).days > MAX_STALE_DAYS:
                    continue
                cut = dict(c, bars=c['bars'][:n])
                for name, cfg in configs.items():
                    v = dict(strategy.evaluate_one(cfg, cut), key=c['key'], group=c['group'], symbol=c['symbol'])
                    if v['status'] == 'retained':
                        retained[(day, name)].append(v)
        log(f'{min(start + batch, len(ids))}/{len(ids)} cotations')
    total = 0
    for day in days:
        for name, cfg in configs.items():
            total += _store(conn, day, name, _top_picks(strategy.rank(cfg, retained[(day, name)])), 'rebuilt')
    return total


def update_outcomes(conn):
    """Calcule les rendements des classements passés dont l'horizon est écoulé (une séance de marge). Renvoie le nombre de lignes."""
    calendar = reference_calendar(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT snap_date FROM ranking_snapshots ORDER BY snap_date')
        days = [r['snap_date'].isoformat() for r in cur.fetchall()]
        cur.execute('SELECT DISTINCT snap_date, horizon FROM universe_outcomes')
        done = {(r['snap_date'].isoformat(), r['horizon']) for r in cur.fetchall()}
        cur.execute('SELECT l.id, i.kind FROM v_recommendable r JOIN listings l ON l.id = r.listing_id JOIN instruments i ON i.id = l.instrument_id')
        universe = {r['id']: ('etf' if r['kind'] == 'etf' else 'equity') for r in cur.fetchall()}
    written = 0
    for day in days:
        later = len(calendar) - bisect.bisect_right(calendar, day)
        todo = [h for h in HORIZONS if (day, h) not in done and later >= h + 1]
        if not todo:
            continue
        with conn.cursor() as cur:
            cur.execute('SELECT preset, listing_id FROM ranking_snapshots WHERE snap_date=%s', (day,))
            picks = [(r['preset'], r['listing_id']) for r in cur.fetchall()]
        ids = sorted(set(universe) | {lid for _, lid in picks})
        start = datetime.date.fromisoformat(day) - datetime.timedelta(days=10)
        stop = datetime.date.fromisoformat(day) + datetime.timedelta(days=21)
        bars = defaultdict(list)
        with conn.cursor() as cur:
            for i in range(0, len(ids), 3000):
                part = ids[i:i + 3000]
                cur.execute(f"""SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices
                                WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND price_date BETWEEN %s AND %s ORDER BY listing_id, price_date""", part + [start, stop])
                for r in cur.fetchall():
                    bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
        splits = defaultdict(list)
        with conn.cursor() as cur:
            cur.execute("SELECT listing_id,event_date,ratio FROM corporate_events WHERE kind IN ('split','reverse_split')")
            for r in cur.fetchall():
                splits[r['listing_id']].append((r['event_date'].isoformat(),float(r['ratio']) if r['ratio'] else None))
        fwd = {lid: forward_returns(rows, day, todo, splits[lid]) for lid, rows in bars.items()}
        outcome_rows = [(day, preset, lid, h, round(fwd[lid][h], 4)) for preset, lid in picks for h in todo if h in fwd.get(lid, {})]
        universe_rows = []
        for h in todo:
            for group in ('equity', 'etf'):
                values = [fwd[lid][h] for lid, g in universe.items() if g == group and h in fwd.get(lid, {})]
                if values:
                    universe_rows.append((day, group, h, len(values), round(statistics.median(values), 4), round(statistics.fmean(values), 4)))
        with conn.cursor() as cur:
            if outcome_rows:
                cur.executemany('REPLACE INTO ranking_outcomes(snap_date,preset,listing_id,horizon,ret) VALUES (%s,%s,%s,%s,%s)', outcome_rows)
            if universe_rows:
                cur.executemany('REPLACE INTO universe_outcomes(snap_date,grp,horizon,n,median_ret,mean_ret) VALUES (%s,%s,%s,%s,%s,%s)', universe_rows)
        conn.commit()
        written += len(outcome_rows)
    return written


def summary(conn, recent_days=8):
    """Page Suivi : statistiques par stratégie, groupe et horizon, plus les derniers classements avec leurs résultats."""
    with conn.cursor() as cur:
        cur.execute('SELECT snap_date, origin, COUNT(*) n FROM ranking_snapshots GROUP BY snap_date, origin ORDER BY snap_date')
        snaps = cur.fetchall()
        cur.execute('SELECT snap_date, grp, horizon, median_ret, mean_ret FROM universe_outcomes')
        bench, bench_mean = defaultdict(dict), defaultdict(dict)
        for r in cur.fetchall():
            bench[(r['grp'], r['horizon'])][r['snap_date'].isoformat()] = float(r['median_ret'])
            bench_mean[(r['grp'], r['horizon'])][r['snap_date'].isoformat()] = float(r['mean_ret'])
        cur.execute("""SELECT o.snap_date, o.preset, o.horizon, o.ret, s.grp FROM ranking_outcomes o
                       JOIN ranking_snapshots s ON s.snap_date = o.snap_date AND s.preset = o.preset AND s.listing_id = o.listing_id""")
        outcomes = cur.fetchall()
    if not snaps:
        return {'horizons': list(HORIZONS), 'days': 0, 'presets': {}, 'recent': {}}
    grouped = defaultdict(list)
    for r in outcomes:
        d = r['snap_date'].isoformat()
        for key in ((r['preset'], r['grp'], r['horizon']), ('*', r['grp'], r['horizon'])):
            grouped[key].append((d, float(r['ret'])))
    presets = {}
    for name in ('*',) + strategy.PRESETS:
        presets[name] = {'label': name,
                         'groups': {g: {str(h): summarize(grouped.get((name, g, h), []), bench.get((g, h), {}), bench_mean.get((g, h), {})) for h in HORIZONS} for g in ('equity', 'etf')}}
    resolved = {str(h): len({d for (g, hh), m in bench.items() if hh == h for d in m}) for h in HORIZONS}
    recent = _recent(conn, [s['snap_date'].isoformat() for s in snaps][-recent_days:])
    return {'horizons': list(HORIZONS), 'days': len(snaps), 'first': snaps[0]['snap_date'].isoformat(), 'last': snaps[-1]['snap_date'].isoformat(),
            'rebuilt_days': sum(1 for s in snaps if s['origin'] == 'rebuilt'), 'resolved_days': resolved, 'presets': presets, 'recent': recent}


def _recent(conn, days):
    if not days:
        return {}
    marks = ','.join(['%s'] * len(days))
    with conn.cursor() as cur:
        cur.execute(f"""SELECT s.snap_date, s.preset, s.grp, s.rank_pos, s.score, s.origin, l.id, l.symbol, i.name
                        FROM ranking_snapshots s JOIN listings l ON l.id = s.listing_id JOIN instruments i ON i.id = l.instrument_id
                        WHERE s.snap_date IN ({marks}) ORDER BY s.snap_date DESC, s.preset, s.grp, s.rank_pos""", days)
        rows = cur.fetchall()
        cur.execute(f'SELECT snap_date, preset, listing_id, horizon, ret FROM ranking_outcomes WHERE snap_date IN ({marks})', days)
        rets = defaultdict(dict)
        for r in cur.fetchall():
            rets[(r['snap_date'], r['preset'], r['listing_id'])][str(r['horizon'])] = float(r['ret'])
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[r['preset']][r['snap_date'].isoformat()].append({
            'id': r['id'], 'symbol': r['symbol'], 'name': r['name'], 'group': r['grp'], 'rank': r['rank_pos'],
            'score': None if r['score'] is None else float(r['score']), 'origin': r['origin'],
            'returns': rets.get((r['snap_date'], r['preset'], r['id']), {})})
    return {p: [{'date': d, 'origin': e[0]['origin'], 'entries': e} for d, e in by_day.items()] for p, by_day in out.items()}
