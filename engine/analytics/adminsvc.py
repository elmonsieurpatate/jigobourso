"""Données de l'administration : une page = un appel (FinanceDatabase, Yahoo Finance, Actions / ETF, historique des traitements)."""
import datetime

from engine.catalogue import rules as cat_rules
from engine.jobs import tasks
from engine.market import collect, hours, prefilter
from engine.shared import settings
from . import funnel

LEVELS = {'catalogue': cat_rules, 'prefilter': prefilter}
SETTING = {'catalogue': 'catalogue_rules', 'prefilter': 'prefilter'}
GROUPS = {'products': 'Produits', 'markets': 'Places de cotation', 'quality': 'Qualité des lignes'}


def _iso(v):
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=' ')
    return v.isoformat() if hasattr(v, 'isoformat') else v


def _level(conn, name):
    mod = LEVELS[name]
    current = settings.catalogue_rules(conn) if name == 'catalogue' else settings.prefilter_rules(conn)
    applied = settings.get(conn, 'rules_applied', {}).get(name)
    rules, technical = [], []
    for r in mod.RULES:
        spec = {k: v for k, v in r.items() if k != 'reason'}
        if r.get('locked'):
            technical.append({'label': r['label'], 'role': r['role']})
            continue
        spec['current'], spec['default'] = current[r['id']], mod.DEFAULT_CONFIG[r['id']]
        spec['is_default'] = spec['current'] == spec['default']
        spec.setdefault('group', 'liquidity' if name == 'prefilter' else 'quality')
        rules.append(spec)
    return {'level': name, 'rules': rules, 'technical': technical, 'is_default': current == mod.DEFAULT_CONFIG, 'groups': GROUPS,
            'applied_at': applied and applied['at'], 'pending': applied is None or applied['hash'] != settings.digest(current)}


def rules_save(conn, level, config):
    if level not in LEVELS:
        raise ValueError('Niveau inconnu')
    settings.put(conn, SETTING[level], LEVELS[level].normalize(config))      # ValueError affichable si invalide
    return _level(conn, level)


def rules_reset(conn, level):
    if level not in LEVELS:
        raise ValueError('Niveau inconnu')
    settings.put(conn, SETTING[level], LEVELS[level].DEFAULT_CONFIG)
    return _level(conn, level)


# ───────── traitements ─────────
def _last_job(conn, job_type):
    with conn.cursor() as cur:
        cur.execute("""SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary, TIMESTAMPDIFF(SECOND, started_at, finished_at) duration_s
                       FROM jobs WHERE job_type=%s ORDER BY id DESC LIMIT 1""", (job_type,))
        r = cur.fetchone()
    return None if not r else {**r, 'started_at': _iso(r['started_at']), 'finished_at': _iso(r['finished_at'])}


def _running(conn):
    """Traitement manuel en cours, avec son avancement (le résumé est mis à jour pendant l'exécution)."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, job_type, started_at, summary FROM jobs WHERE status IN ('queued','running') AND job_type IN %s ORDER BY id LIMIT 1", (tasks.JOBS,))
        r = cur.fetchone()
    return None if not r else {'id': r['id'], 'job_type': r['job_type'], 'started_at': _iso(r['started_at']), 'progress': r['summary']}


def jobs_list(conn, request):
    where, args = [], []
    if request.get('type'):
        where.append('job_type LIKE %s')
        args.append(str(request['type']).replace('%', '') + '%')
    if request.get('status'):
        where.append('status=%s')
        args.append(request['status'])
    if request.get('trigger') in ('cron', 'admin', 'system'):
        where.append('trigger_by=%s')
        args.append(request['trigger'])
    if request.get('since'):
        where.append('started_at >= %s')
        args.append(request['since'])
    page = max(1, int(request.get('page') or 1))
    sql = ' WHERE ' + ' AND '.join(where) if where else ''
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM jobs' + sql, args)
        total = cur.fetchone()['n']
        cur.execute('SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary, TIMESTAMPDIFF(SECOND, started_at, finished_at) duration_s '
                    'FROM jobs' + sql + ' ORDER BY id DESC LIMIT 40 OFFSET %s', args + [(page - 1) * 40])
        rows = cur.fetchall()
    return {'total': total, 'page': page, 'pages': max(1, -(-total // 40)), 'jobs': rows}


def job_detail(conn, job_id):
    with conn.cursor() as cur:
        cur.execute('SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary FROM jobs WHERE id=%s', (job_id,))
        job = cur.fetchone()
        if not job:
            raise KeyError('Traitement introuvable')
        cur.execute('SELECT seq, name, started_at, duration_ms, detail FROM job_steps WHERE job_id=%s ORDER BY seq', (job_id,))
        steps = cur.fetchall()
        cur.execute('SELECT level, message, logged_at FROM job_logs WHERE job_id=%s ORDER BY id LIMIT 200', (job_id,))
        logs = cur.fetchall()
    return {'job': job, 'steps': steps, 'logs': logs, 'funnels': {s: funnel.stored(conn, job_id, s) for s in ('catalogue', 'yahoo')}}


# ───────── page FinanceDatabase ─────────
def fdb_state(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT source_commit, loaded_at, rows_read FROM catalogue_loads ORDER BY id DESC LIMIT 1')
        load = cur.fetchone()
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        raw = cur.fetchone()['n']
        cur.execute("SELECT mic, kind, COUNT(*) n FROM catalogue_raw WHERE mic<>'' GROUP BY mic, kind")
        places = {}
        for r in cur.fetchall():
            places.setdefault(r['mic'], {'mic': r['mic'], 'equity': 0, 'etf': 0})[r['kind']] = r['n']
        cur.execute("SELECT category, COUNT(*) n FROM catalogue_raw WHERE category IS NOT NULL AND category<>'' GROUP BY category ORDER BY n DESC LIMIT 300")
        categories = cur.fetchall()
    level = _level(conn, 'catalogue')
    wanted = next(r for r in level['rules'] if r['id'] == 'markets')['current']['values']
    for m in set(cat_rules.DEFAULT_MARKETS) | set(wanted):
        places.setdefault(m, {'mic': m, 'equity': 0, 'etf': 0})
    for p in places.values():
        p['name'] = cat_rules.MARKET_NAMES.get(p['mic'], '')
        p['hours_known'] = hours.known(p['mic'])
        p['default'] = p['mic'] in cat_rules.DEFAULT_MARKETS
    return {'import': {'last': _last_job(conn, 'fdb_import'), 'load': None if not load else {'commit': load['source_commit'][:8], 'loaded_at': _iso(load['loaded_at']), 'rows_read': load['rows_read']},
                       'raw_rows': raw, 'source': 'FinanceDatabase (github.com/JerBouma/FinanceDatabase)'},
            'filters': level, 'places': sorted(places.values(), key=lambda p: (-(p['equity'] + p['etf']), p['mic'])), 'categories': categories,
            'last_filter': _last_job(conn, 'fdb_filter'), 'funnel': funnel.last_run(conn, 'catalogue'), 'running': _running(conn)}


# ───────── page Yahoo Finance ─────────
def yahoo_state(conn):
    stats = settings.get(conn, 'last_stats', {})
    with conn.cursor() as cur:
        cur.execute("SELECT i.kind, COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE l.status='selected' AND l.is_primary=1 GROUP BY i.kind")
        kinds = {r['kind']: r['n'] for r in cur.fetchall()}
        cur.execute('SELECT COUNT(*) n, MAX(quote_at) t FROM latest_prices WHERE quote_at IS NOT NULL')
        q = cur.fetchone()
        cur.execute("""SELECT COUNT(DISTINCT t.listing_id) n FROM portfolio_transactions t JOIN listings l ON l.id=t.listing_id
                       WHERE t.listing_id IS NOT NULL AND NOT (l.status='selected' AND l.is_primary=1)""")
        held_extra = cur.fetchone()['n']
    info, filt, fdb_filter, hist = _last_job(conn, 'yahoo_info'), _last_job(conn, 'yahoo_filter'), _last_job(conn, 'fdb_filter'), _last_job(conn, 'history')
    ok = ('completed', 'completed_with_errors')
    pending = [] 
    if fdb_filter and fdb_filter['status'] in ok and (not info or (info['finished_at'] or '') < (fdb_filter['finished_at'] or '')):
        pending.append('Le filtrage FinanceDatabase a changé depuis le dernier import Yahoo : relancez l’import des informations Yahoo.')
    if info and info['status'] in ok and (not filt or (filt['finished_at'] or '') < (info['finished_at'] or '')):
        pending.append('Des informations Yahoo plus récentes n’ont pas encore été filtrées : cliquez sur « Filtrer ».')
    level = _level(conn, 'prefilter')
    final = kinds.get('equity', 0) + kinds.get('etf', 0)
    coverage = tasks.history_coverage(conn) if final else {'absent': 0, 'partial': 0, 'complete': 0, 'last_day': None, 'gap_titles': 0, 'gap_days': 0, 'gap_small': 0}
    return {'info': {'last': info, 'stats': stats.get('yahoo_info'), 'quotes': q['n'], 'quote_at': _iso(q['t']), 'asked_now': len(tasks.info_set(conn))},
            'filters': level, 'funnel': funnel.last_run(conn, 'yahoo'), 'last_filter': filt, 'pending': pending,
            'final': {'equity': kinds.get('equity', 0), 'etf': kinds.get('etf', 0), 'total': final, 'held_extra': held_extra, 'coverage': coverage,
                      'last_history': hist, 'stats': stats.get('history'), 'cron_daily': stats.get('daily'), 'cron_intraday': stats.get('intraday'), 'full': collect.FULL_SESSIONS},
            'running': _running(conn)}


# ───────── page Actions / ETF ─────────
SORTS = {'name': 'r.name', 'mic': 'r.mic', 'symbol': 'r.symbol', 'country': 'r.country', 'price_time': 'p.price_time', 'closes': 's.closes_count'}
FDB_STEP = {r['id']: r['label'] for r in cat_rules.RULES}
Y_EXPR = ("CASE WHEN r.removed_step IS NOT NULL OR l.id IS NULL THEN 'na' WHEN l.status='excluded' THEN 'removed' WHEN l.is_primary=0 THEN 'secondary' "
          "WHEN l.status='selected' THEN 'kept' ELSE 'pending' END")
FINAL_EXPR = "((r.removed_step IS NULL AND l.status='selected' AND l.is_primary=1) OR h.listing_id IS NOT NULL)"
D_EXPR = f"CASE WHEN NOT {FINAL_EXPR} THEN 'na' WHEN s.closes_count IS NULL OR s.closes_count=0 THEN 'absent' WHEN s.closes_count>=%s THEN 'complete' ELSE 'partial' END"


def _intraday_status(conn, mic, lid, now):
    from engine.market import intraday as intra
    if not hours.known(mic):
        return 'na'
    cur_day = hours.session_date(mic, now)
    prev = cur_day - datetime.timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= datetime.timedelta(days=1)
    expected = max(1, hours.expected_slots(mic))
    counts = []
    with conn.cursor() as cur:
        for day in (prev, cur_day):
            a, b = intra.session_window(mic, day)
            cur.execute('SELECT COUNT(*) n FROM intraday_prices WHERE listing_id=%s AND slot_start>=%s AND slot_start<%s', (lid, a, b))
            counts.append(cur.fetchone()['n'])
    if all(c >= 0.8 * expected for c in counts):
        return 'complete'
    return 'partial' if any(counts) else 'absent'


def titles(conn, req):
    now = hours.utcnow()
    where, args = [], []
    q = (req.get('q') or '').strip().lower().replace('%', '').replace('_', '')
    if q:
        where.append('(LOWER(r.name) LIKE %s OR LOWER(r.symbol) LIKE %s OR LOWER(COALESCE(r.isin,"")) LIKE %s)')
        args += [f'%{q}%'] * 3
    for key, col in (('kind', 'r.kind'), ('mic', 'r.mic')):
        if req.get(key):
            where.append(f'{col}=%s')
            args.append(str(req[key]).upper() if key == 'mic' else req[key])
    if req.get('fdb') == 'kept':
        where.append('r.removed_step IS NULL')
    elif req.get('fdb') == 'removed':
        where.append('r.removed_step IS NOT NULL')
    if req.get('yahoo') in ('kept', 'removed', 'pending', 'secondary', 'na'):
        where.append(f'{Y_EXPR}=%s')
        args.append(req['yahoo'])
    if req.get('final') in ('1', '0', 1, 0):
        where.append(FINAL_EXPR if str(req['final']) == '1' else f'NOT {FINAL_EXPR}')
    if req.get('daily') in ('complete', 'partial', 'absent'):
        where.append(f'{D_EXPR}=%s')
        args += [collect.FULL_SESSIONS, req['daily']]
    sql_where = ' WHERE ' + ' AND '.join(where) if where else ''
    order = SORTS.get(req.get('sort'), 'r.name') + (' DESC' if req.get('dir') == 'desc' else ' ASC')
    page = max(1, int(req.get('page') or 1))
    frm = """FROM catalogue_raw r LEFT JOIN listings l ON l.mic=r.mic AND l.symbol=LEFT(r.symbol,24) LEFT JOIN latest_prices p ON p.listing_id=l.id
             LEFT JOIN series_state s ON s.listing_id=l.id LEFT JOIN (SELECT DISTINCT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL) h ON h.listing_id=l.id"""
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) n FROM catalogue_raw')
        raw_total = cur.fetchone()['n']
        cur.execute(f'SELECT COUNT(*) n {frm}{sql_where}', args)
        total = cur.fetchone()['n']
        cur.execute(f"""SELECT r.kind, r.mic, r.symbol, r.isin, r.name, r.country, r.category, r.removed_step, r.removed_reason, l.id lid, l.status, l.excluded_reason, l.is_primary,
                               p.price, p.currency pcur, p.price_time, p.quote_at, p.avg_volume_3m, s.closes_count, s.last_close_date, {Y_EXPR} y_state, {FINAL_EXPR} in_final,
                               h.listing_id IS NOT NULL held, {D_EXPR} d_state
                        {frm}{sql_where} ORDER BY {order}, r.id LIMIT 50 OFFSET %s""", [collect.FULL_SESSIONS] + args + [(page - 1) * 50])
        rows = cur.fetchall()
        info_done = bool(settings.get(conn, 'last_stats', {}).get('yahoo_info'))
    for r in rows:
        r['fdb_state'] = 'kept' if r['removed_step'] is None else 'removed'
        reason = None
        if r['removed_step']:
            reason = {'stage': 'FinanceDatabase', 'rule': FDB_STEP.get(r['removed_step'], r['removed_step']), 'detail': r['removed_reason']}
        elif r['y_state'] == 'removed':
            reason = {'stage': 'Yahoo Finance', 'rule': 'Filtre Yahoo', 'detail': r['excluded_reason']}
        elif r['y_state'] == 'secondary':
            reason = {'stage': 'Cotation secondaire', 'rule': 'Une cotation principale par produit', 'detail': 'le produit est suivi sur une autre place'}
        elif r['y_state'] == 'pending':
            reason = {'stage': 'En attente', 'rule': None, 'detail': 'informations Yahoo non reçues' if r['quote_at'] is None else 'filtrage Yahoo à lancer'}
        r['reason'] = reason
        r['in_final'], r['held'] = bool(r['in_final']), bool(r['held'])
        r['intraday_state'] = _intraday_status(conn, r['mic'], r['lid'], now) if r['in_final'] and r['lid'] else 'na'
        r['issue'] = None
        if r['y_state'] == 'pending' and r['quote_at'] is None and info_done:
            r['issue'] = 'Yahoo n’a renvoyé aucune information lors du dernier import'
        elif r['in_final'] and r['d_state'] == 'absent':
            r['issue'] = 'Aucun historique quotidien reçu : lancez « Importer / mettre à jour les historiques »'
        for k in ('price_time', 'quote_at', 'last_close_date'):
            r[k] = _iso(r[k])
        r['price'] = None if r['price'] is None else float(r['price'])
        r['in_fdb_universe'] = r['removed_step'] is None
    return {'total': total, 'raw_total': raw_total, 'page': page, 'pages': max(1, -(-total // 50)), 'rows': rows, 'full': collect.FULL_SESSIONS,
            'places': [r['mic'] for r in _distinct_mics(conn)]}


def _distinct_mics(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT mic FROM catalogue_raw WHERE mic<>'' GROUP BY mic ORDER BY COUNT(*) DESC LIMIT 200")
        return cur.fetchall()
