"""Verdicts de l'univers : mesures vivantes, jugement par stratégie et cache des résultats (`result_cache`)."""
import datetime
import hashlib
import json
import zlib
import base64
from collections import defaultdict
from engine.market import hours
from engine.market.calendar import window_calendars, session_dates
from ..explorer import strategy
from ..explorer import explorer_config
from ..explorer import explorer_metrics
from ..series import liquidity
from ..series.series import analyze_series
from ..market_views.market_facts import expected_close

def _load_universe(conn, windows, ids=None):
    only = f' WHERE l.id IN ({",".join(["%s"] * len(ids))})' if ids else ''
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.instrument_id, l.symbol, l.mic, l.currency, i.name, i.isin, i.kind, i.country, i.category,
                              p.price, p.price_time, p.quote_at, p.source AS price_source, p.currency AS price_currency, p.avg_volume_3m, p.net_assets,
                              s.last_close_date, s.closes_count, s.close_px, s.ma20, s.ma50, s.ma50_prev, s.ma200, s.ma200_prev, s.daily_change, s.gap_to_ma20, s.quality, s.break_age, s.break_dates,
                       s.coverage_252, s.expected_252, s.momentum_6m, s.momentum_12m, ls.turnover_eur, ls.source AS turnover_source
                       FROM v_recommendable r JOIN listings l ON l.id=r.listing_id JOIN instruments i ON i.id=l.instrument_id
                       LEFT JOIN latest_prices p ON p.listing_id=l.id LEFT JOIN series_state s ON s.listing_id=l.id LEFT JOIN liquidity_state ls ON ls.listing_id=l.id""" + only, list(ids or []))
        universe = cur.fetchall()
        marks = ','.join(['%s'] * len(windows))
        scope = f' AND listing_id IN ({",".join(["%s"] * len(ids))})' if ids else ''
        stored = defaultdict(dict)
        if windows:
            cur.execute(f'SELECT listing_id, sessions, slope, slope_log, r2, perf, volatility, drawdown, er, observations, expected_closes, coverage FROM strategy_metrics WHERE sessions IN ({marks})' + scope, list(windows) + list(ids or []))
            for r in cur.fetchall():
                stored[r['listing_id']][r['sessions']] = {k: (None if v is None else float(v)) for k, v in r.items() if k not in ('listing_id',)}
        cur.execute('SELECT mic, MAX(last_close_date) d FROM series_state s JOIN listings l ON l.id=s.listing_id GROUP BY mic')
        latest_by_mic = {r['mic']: r['d'] for r in cur.fetchall()}
    return universe, stored, latest_by_mic


def _live_measures(conn, ids, windows):
    """Mesures des fenêtres absentes de strategy_metrics, calculées depuis les clôtures (chemin lent, fenêtres non standard)."""
    out = defaultdict(dict)
    if not ids or not windows:
        return out
    mic_by_id = {}
    with conn.cursor() as cur:
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            cur.execute(f"SELECT id, mic FROM listings WHERE id IN ({','.join(['%s'] * len(part))})", part)
            mic_by_id.update({r['id']: r['mic'] for r in cur.fetchall()})
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            cur.execute(f"SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({','.join(['%s'] * len(part))}) ORDER BY listing_id, price_date", part)
            bars = defaultdict(list)
            for r in cur.fetchall():
                bars[r['listing_id']].append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
            cur.execute(f"SELECT listing_id, event_date, ratio FROM corporate_events WHERE listing_id IN ({','.join(['%s'] * len(part))}) AND kind IN ('split','reverse_split')", part)
            splits = defaultdict(list)
            for r in cur.fetchall():
                splits[r['listing_id']].append((r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None))
            for lid, rows in bars.items():
                mic = mic_by_id.get(lid)
                cutoff = expected_close(conn, mic) if mic else None
                calendars = window_calendars(mic, cutoff, windows) if cutoff else {}
                tech_dates = session_dates(mic, cutoff, 55) if cutoff else None
                _, _, _, _, measured, _, _ = analyze_series(rows, windows, splits[lid], calendars, tech_dates)
                out[lid].update({n: m for n, m in measured.items() if m is not None})
    return out


def _missing_reason(count, window, measure, break_age):
    """Motif d'une fenêtre non mesurée : historique trop court, saut de cours (rupture) dans la fenêtre, calendrier ou couverture.
    La dernière rupture (break_age = séances écoulées depuis elle) traverse une fenêtre de n séances si elle est plus récente que n ; les plus anciennes ne la traversent alors pas non plus."""
    if count < window + 1:
        return 'history'
    if measure is None:
        return 'break' if break_age is not None and break_age < window else 'calendar'
    return 'coverage'


def judge_universe(conn, config, ids=None):
    """Verdicts de l'univers recommandable (ou d'un sous-ensemble `ids` : rang et score n'y ont alors pas de sens)."""
    windows = strategy.required_sessions(config)
    universe, stored, latest_by_mic = _load_universe(conn, windows, ids)
    needs_live = [u['id'] for u in universe if any(n not in stored.get(u['id'], {}) or stored[u['id']][n].get('coverage') is None for n in windows)]
    absent = sorted({n for n in windows if any(n not in stored.get(lid, {}) or stored[lid][n].get('coverage') is None for lid in needs_live)})
    live = _live_measures(conn, needs_live, absent) if needs_live and absent else {}
    extra = extended_metrics(conn,universe,windows) if config.get('version')==4 and explorer_config.needs_extended(config) else {}
    verdicts = []
    for u in universe:
        measures = {n: (live.get(u['id'], {}).get(n) if stored.get(u['id'], {}).get(n, {}).get('coverage') is None
                        else stored.get(u['id'], {}).get(n)) or live.get(u['id'], {}).get(n)
                    for n in windows}
        for n,m in measures.items():
            if m is not None and n in extra.get(u['id'],{}):measures[n]={**m,**extra[u['id']][n]}
        count = u['closes_count'] or 0
        missing = {n: _missing_reason(count, n, m, u.get('break_age')) for n, m in measures.items() if m is None}
        for n in windows:
            stored_metric = stored.get(u['id'], {}).get(n)
            if stored_metric and stored_metric.get('coverage') is None and n not in live.get(u['id'], {}):
                missing[n] = _missing_reason(count, n, None, u.get('break_age'))             # historique trop court, rupture dans la fenêtre ou calendrier : le vrai motif
        tech = {k: (None if u[k] is None else float(u[k])) for k in ('close_px', 'ma20', 'ma50', 'ma50_prev', 'ma200', 'ma200_prev', 'daily_change', 'gap_to_ma20')}
        tech['close'] = tech.pop('close_px')
        if config.get('version')==4:
            tech['quoted_avg_volume']=None if u.get('avg_volume_3m') is None else float(u['avg_volume_3m'])
            tech['turnover_eur']=None if u.get('turnover_eur') is None else float(u['turnover_eur']);tech['turnover_source']=u.get('turnover_source');tech['us_listing']=u['mic'] in liquidity.US_MICS
        last = u['last_close_date'].isoformat() if u['last_close_date'] else None
        expected = max(expected_close(conn, u['mic']), str(latest_by_mic.get(u['mic']) or ''))
        if last and last < expected:
            u['quality'] = 'stale'
        elif u['quality'] not in ('break', 'insufficient') and (
                any(n in missing and missing[n] in ('coverage', 'calendar') for n in windows) or
                any((m or {}).get('coverage') is not None and (m or {}).get('coverage') < 1 for m in measures.values())):
            u['quality'] = 'incomplete'
        elif u['quality'] not in ('break', 'insufficient') and any(n in missing and missing[n] == 'calendar' for n in windows):
            u['quality'] = 'calendar_unknown'
        custom_momentum=config.get('version')==4 and any(c['metric'] in ('momentum6','momentum12') for c in config['ranking'].get('components',[]))
        saved_momentum = ({'6m': u.get('momentum_6m'), '12m': u.get('momentum_12m')} if config['ranking']['mode'] == strategy.RISK_MOMENTUM or custom_momentum
                          else u.get('momentum_12m') if config['ranking']['mode'] == 'momentum12' else u.get('momentum_6m'))
        momentum_arg = saved_momentum if isinstance(saved_momentum, dict) else (None if saved_momentum is None else float(saved_momentum))
        effective=explorer_config.effective(config,'etf' if u['kind']=='etf' else 'equity') if config.get('version')==4 else config
        v = strategy.judge(effective, measures, tech, missing, last, expected or None, momentum=momentum_arg)
        if u['quality'] == 'incomplete' and v['status'] == 'unknown':
            v['status_label'] = 'Historique incomplet'
        u['instrument_id'] = u.get('instrument_id', u['id'])
        v.update(key=u['id'], group='etf' if u['kind'] == 'etf' else 'equity', symbol=u['symbol'], row=u)
        verdicts.append(v)
    return strategy.rank(config, verdicts)


CACHE_FORMAT = 8


MAX_NEW_CONFIGS_PER_HOUR = 60       # calculs d'univers complets (réglages jamais vus ou données changées) acceptés par heure, tous utilisateurs confondus


ENTRY_FIELDS = ('id', 'symbol', 'name', 'isin', 'kind', 'mic', 'country', 'status', 'group', 'rank', 'score', 'category', 'fails', 'instrument_id', 'currency', 'price_currency', 'net_assets', 'proximity', 'score_parts', 'score_missing')


def criteria_proximity(reasons):
    """Display order of rejected instruments, separate from retained ranks/scores.

    Complete evidence first, then fewer failed checks, then sum of relative gaps.
    Zero thresholds use a natural metric unit; boolean failures count as one.
    """
    missing = sum(r.get('result') == 'missing' for r in reasons)
    failed = [r for r in reasons if r.get('result') == 'fail']
    gap = 0.0
    for r in failed:
        v, t = r.get('value'), r.get('threshold')
        if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(t, (int, float)) and not isinstance(t, bool):
            floor = .01 if r.get('metric') in ('r2','er','slope') else 1.0
            gap += abs(v-t) / max(abs(t),floor)
        else:
            gap += 1.0
    return [missing, len(failed), gap]


def _fails(v):
    """Critères non satisfaits ou non mesurables d'un verdict : 'période|critère|f' (échec) ou '|m' (mesure absente)."""
    return [f"{r['period'] or ''}|{r['criterion']}|{r['result'][0]}" for r in v['reasons'] if r['result'] in ('fail', 'missing')]


def data_version(conn):
    """Change quand une donnée qui influence les verdicts change : calcul nocturne, jeu recommandable, traitement terminé."""
    with conn.cursor() as cur:
        cur.execute('SELECT MAX(s.computed_at) t, COUNT(*) n FROM series_state s JOIN v_recommendable r ON r.listing_id = s.listing_id')
        a = cur.fetchone()
        cur.execute("SELECT COALESCE(MAX(id), 0) j FROM jobs WHERE job_type NOT LIKE 'intraday%' AND status IN ('completed', 'completed_with_errors')")
        j = cur.fetchone()['j']
    clock = hashlib.sha1(','.join(hours.expected_last_close(m, hours.utcnow()) for m in sorted(hours.HOURS)).encode()).hexdigest()[:12]
    return f"{clock}.{CACHE_FORMAT}.{strategy.VERSION}|{a['t']}|{a['n']}|{j}"


def packed(payload):
    text=json.dumps(payload,separators=(',',':'))
    return json.dumps({'compressed':base64.b64encode(zlib.compress(text.encode())).decode()})


def unpacked(payload):
    data=json.loads(payload)
    return json.loads(zlib.decompress(base64.b64decode(data['compressed']))) if isinstance(data,dict) and 'compressed' in data else data


def compact_parts(v):
    return [[p['id'],p['raw'],p['normalized'],p['effective_weight'],p['contribution'],{k:v for k,v in p.items() if k not in ('raw','normalized','effective_weight','contribution')}] for p in v.get('score_parts',[])]


def expanded_parts(entry,config):
    defs={p['id']:p for p in config['ranking'].get('components',[])}
    return [dict(defs.get(p[0],p[5] if len(p)>5 else {}),raw=p[1],normalized=p[2],effective_weight=p[3],contribution=p[4]) for p in entry.get('score_parts',[]) or []]


def extended_metrics(conn,universe,windows):
    # Shared across configurations. No per-title SQL and no provider access.
    version=data_version(conn);key=hashlib.sha1(('explorer-path-v1:'+','.join(map(str,windows))).encode()).hexdigest()
    with conn.cursor() as q:
        q.execute('SELECT payload,data_version FROM result_cache WHERE cache_key=%s',(key,));hit=q.fetchone()
    if hit and hit['data_version']==version:
        result=unpacked(hit['payload']);wanted={u['id'] for u in universe}
        return {int(lid):{int(n):m for n,m in group.items()} for lid,group in result.items() if int(lid) in wanted}
    result=explorer_metrics.load(conn,universe,windows,expected_close)
    # Only cache complete universe batches: a detail request must not poison it.
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) n FROM v_recommendable');complete=q.fetchone()['n']==len(universe)
        if complete:q.execute('REPLACE INTO result_cache(cache_key,data_version,built_at,payload) VALUES (%s,%s,%s,%s)',(key,version,datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0),packed(result)))
    if complete:conn.commit()
    return result


def cached_verdicts(conn, config):
    """Verdicts légers (identité, statut, groupe, rang, score) de tout l'univers pour cette configuration, mis en cache en base."""
    financial={k:v for k,v in config.items() if k not in ('presentation','scoring')}      # les paramètres de score ne changent aucun verdict de conformité
    key = hashlib.sha1(('explorer-v4:' + json.dumps(financial, sort_keys=True, separators=(',', ':'))).encode()).hexdigest()
    version = data_version(conn)
    if config.get('version')==4 and (any(explorer_config.effective(config,k)['liquidity'].get('min_quoted_volume') is not None for k in ('equity','etf')) or any(p['metric']=='quoted_avg_volume' for p in config['ranking'].get('components',[]))):
        with conn.cursor() as cur:
            cur.execute('SELECT r.listing_id,p.avg_volume_3m FROM v_recommendable r LEFT JOIN latest_prices p ON p.listing_id=r.listing_id ORDER BY r.listing_id')
            version+='|'+hashlib.sha1(json.dumps(cur.fetchall(),default=str,separators=(',',':')).encode()).hexdigest()[:12]
    with conn.cursor() as cur:
        cur.execute('SELECT data_version, payload FROM result_cache WHERE cache_key=%s', (key,))
        hit = cur.fetchone()
    if hit and hit['data_version'] == version:
        return [dict(zip(ENTRY_FIELDS, e)) for e in unpacked(hit['payload'])]
    with conn.cursor() as cur:        # garde-fou : chaque configuration inédite évalue tout l'univers ; on borne le nombre de calculs par heure pour protéger la base partagée
        cur.execute("SELECT COUNT(*) n FROM result_cache WHERE built_at > %s AND data_version <> 'intraday-fetch'", (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=1),))
        if cur.fetchone()['n'] >= MAX_NEW_CONFIGS_PER_HOUR:
            raise ValueError('Trop de réglages différents ont été calculés depuis une heure : réessayez un peu plus tard, ou utilisez un des quatre profils de départ.')
    entries = [[v['key'], v['symbol'], v['row']['name'], v['row']['isin'], v['row']['kind'], v['row']['mic'], v['row']['country'], v['status'], v['group'], v['rank'],
                None if v['score'] is None else round(v['score'], 4), v['row']['category'], _fails(v), v['row'].get('instrument_id'), v['row'].get('currency'), v['row'].get('price_currency'), v['row'].get('net_assets'), criteria_proximity(v['reasons']),compact_parts(v),v.get('score_missing',0)] for v in judge_universe(conn, config)]
    with conn.cursor() as cur:
        cur.execute('REPLACE INTO result_cache(cache_key, data_version, built_at, payload) VALUES (%s,%s,%s,%s)',
                    (key, version, datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0), packed(entries) if config.get('version')==4 else json.dumps(entries, ensure_ascii=False, separators=(',', ':'))))
        cur.execute('DELETE FROM result_cache WHERE built_at < %s', (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=3),))
    conn.commit()
    return [dict(zip(ENTRY_FIELDS, e)) for e in entries]
