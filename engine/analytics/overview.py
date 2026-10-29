"""Vue d'ensemble des données pour la page « Données » : d'où viennent-elles, quand ont-elles été collectées, qu'est-ce qui est couvert."""
from engine.catalogue.rules import MARKETS
from engine.market import hours


def _iso(v):
    return v.isoformat(sep=' ') if hasattr(v, 'isoformat') else v


def data_overview(conn):
    now = hours.utcnow()
    with conn.cursor() as cur:
        cur.execute('SELECT source_commit, loaded_at, rows_read, rows_kept FROM catalogue_loads ORDER BY id DESC LIMIT 1')
        cat = cur.fetchone()
        cur.execute("SELECT i.kind, l.status, COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id GROUP BY i.kind, l.status")
        listings = {}
        for r in cur.fetchall():
            listings.setdefault(r['kind'], {})[r['status']] = r['n']
        cur.execute("SELECT COUNT(*) n FROM listings WHERE status='selected' AND is_primary=1")
        recommendable = cur.fetchone()['n']
        cur.execute("""SELECT l.mic, COUNT(*) followed, MAX(s.last_close_date) last_close,
                              SUM(s.quality='ok') ok,
                              SUM(s.quality='incomplete') incomplete,
                              SUM(s.quality='calendar_unknown') calendar_unknown,
                              SUM(s.quality='stale') stale, SUM(s.quality='insufficient') insufficient,
                              SUM(s.quality='break') broken, SUM(s.coverage_252=1) full_year, MAX(p.price_time) last_price
                       FROM v_collect_set c JOIN listings l ON l.id=c.listing_id LEFT JOIN series_state s ON s.listing_id=l.id LEFT JOIN latest_prices p ON p.listing_id=l.id
                       GROUP BY l.mic ORDER BY followed DESC""")
        places = cur.fetchall()
        cur.execute("""SELECT SUBSTRING_INDEX(job_type, ':', 1) kind, SUBSTRING_INDEX(job_type, ':', -1) mic, MAX(COALESCE(finished_at, started_at)) t FROM jobs
                       WHERE (job_type LIKE 'daily:%' OR job_type LIKE 'intraday:%') AND status IN ('completed','completed_with_errors') GROUP BY job_type""")
        last = {}
        for r in cur.fetchall():
            last.setdefault(r['mic'], {})[r['kind']] = _iso(r['t'])
        cur.execute("SELECT MAX(COALESCE(finished_at, started_at)) t FROM jobs WHERE job_type IN ('maintenance','history','nightly') AND status IN ('completed','completed_with_errors')")
        nightly = cur.fetchone()['t']
        cur.execute('SELECT MAX(computed_at) t FROM series_state')
        computed = cur.fetchone()['t']
        cur.execute('SELECT MAX(rate_date) d, COUNT(DISTINCT currency) n FROM fx_rates')
        fx = cur.fetchone()
        cur.execute('SELECT COUNT(*) n, MIN(price_date) a, MAX(price_date) b FROM daily_prices')
        daily = cur.fetchone()
        cur.execute('SELECT COUNT(*) n, MAX(slot_start) t FROM intraday_prices')
        intra = cur.fetchone()
    out = []
    for p in places:
        mic = p['mic']
        out.append({'mic': mic, 'market': MARKETS.get(mic, mic), 'followed': p['followed'], 'last_close': p['last_close'].isoformat() if p['last_close'] else None,
                    'ok': int(p['ok'] or 0), 'incomplete': int(p['incomplete'] or 0), 'calendar_unknown': int(p['calendar_unknown'] or 0),
                    'stale': int(p['stale'] or 0), 'insufficient': int(p['insufficient'] or 0), 'broken': int(p['broken'] or 0), 'full_year': int(p['full_year'] or 0),
                    'last_price': _iso(p['last_price']), 'last_daily_collect': (last.get(mic) or {}).get('daily'), 'last_intraday_collect': (last.get(mic) or {}).get('intraday'),
                    'open': mic in hours.HOURS and hours.is_open(mic, now), 'tz': hours.HOURS[mic][0] if mic in hours.HOURS else None})
    return {'catalogue': {'source': 'FinanceDatabase', 'url': 'https://github.com/JerBouma/FinanceDatabase', 'commit': cat['source_commit'][:8] if cat else None,
                          'loaded_at': _iso(cat['loaded_at']) if cat else None, 'rows_read': cat['rows_read'] if cat else None, 'rows_kept': cat['rows_kept'] if cat else None,
                          'listings': listings, 'recommendable': recommendable},
            'prices': {'source': 'Yahoo Finance', 'daily_rows': daily['n'], 'daily_from': daily['a'].isoformat() if daily['a'] else None, 'daily_to': daily['b'].isoformat() if daily['b'] else None,
                       'intraday_rows': intra['n'], 'intraday_last': _iso(intra['t']), 'fx_date': fx['d'].isoformat() if fx['d'] else None, 'fx_currencies': fx['n'],
                       'last_nightly': _iso(nightly), 'last_computed': _iso(computed)},
            'places': out, 'now_utc': now.replace(tzinfo=None).isoformat(sep=' ')}
