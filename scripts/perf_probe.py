"""Mesures de performance sur un volume synthétique, base jetable UNIQUEMENT (jigobourso_perf sur 127.0.0.1:33307).

  python scripts/perf_probe.py [--titles 3000] [--days 400]

Phases : semis (SQL), calcul nocturne, puis commandes du moteur (Python lancé comme par PHP, JSON sur stdin) à froid et à chaud :
démarrage Python (import), appel total, taille du JSON. Affiche un JSON ; docs/PERFORMANCE.md en reprend les chiffres. Jamais la production : refuse
toute autre cible. Données synthétiques : ne prouvent rien sur l'hébergement réel.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if not (os.environ.get('JIGO_TEST_DATABASE') == '1' and os.environ.get('JIGO_DB_HOST') == '127.0.0.1' and os.environ.get('JIGO_DB_PORT') == '33307'
        and os.environ.get('JIGO_DB_NAME') == 'jigobourso_perf'):
    sys.exit('refusé : base jetable jigobourso_perf (127.0.0.1:33307) uniquement')
from engine.shared.db import connect  # noqa: E402


def seed(c, titles, days):
    dates, d = [], dt.date.today() - dt.timedelta(days=1)
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d)
        d -= dt.timedelta(days=1)
    dates.reverse()
    mics = ('XPAR', 'XETR', 'XAMS', 'XNYS', 'XNAS', 'XLON')
    with c.cursor() as q:
        for start in range(1, titles + 1, 500):
            ids = range(start, min(start + 500, titles + 1))
            q.executemany('INSERT INTO instruments(id,group_key,kind,name,country) VALUES (%s,%s,%s,%s,%s)',
                          [(i, 'perf:%d' % i, 'etf' if i % 5 == 0 else 'equity', 'Titre synthétique %d' % i, 'France') for i in ids])
            q.executemany("INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,is_primary) VALUES (%s,%s,%s,%s,'EUR','selected',1)",
                          [(i, i, mics[i % len(mics)], 'PERF%d' % i) for i in ids])
            q.executemany('INSERT INTO daily_prices(listing_id,price_date,close_px) VALUES (%s,%s,%s)',
                          [(i, day, round(10 * (1 + 0.0004 * ((i % 17) - 5)) ** k * (1 + 0.01 * ((k * i) % 7 - 3)), 6)) for i in ids for k, day in enumerate(dates)])
            q.executemany("INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m,quote_at) VALUES (%s,%s,NOW(),'quote','EUR',100000,NOW())",
                          [(i, 10) for i in ids])
            c.commit()


def engine(cmd, request):
    import resource
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.perf_counter()
    out = subprocess.run([sys.executable, '-m', 'engine.cli', cmd], input=json.dumps(request), capture_output=True, text=True, cwd=ROOT, timeout=600)
    total = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return dict(command=cmd, seconds=round(total, 2), json_kb=round(len(out.stdout) / 1024, 1), peak_rss_mb=round(peak / 1024) if peak > before else None,
                ok=out.returncode == 0, error=(out.stderr or '')[-200:] if out.returncode else None)


def breakdown(cmd, request):
    """Même appel dans le processus : temps SQL (toutes requêtes), sérialisation JSON, reste = calcul Python (dont cache)."""
    import pymysql.cursors
    from engine import cli
    spent = {'sql': 0.0, 'queries': 0}
    original = pymysql.cursors.Cursor.execute

    def timed(self, *a, **k):
        t = time.perf_counter()
        try:
            return original(self, *a, **k)
        finally:
            spent['sql'] += time.perf_counter() - t; spent['queries'] += 1
    pymysql.cursors.Cursor.execute = timed
    try:
        saved_stdin, saved_stdout = sys.stdin, sys.stdout
        import io
        sys.stdin = io.StringIO(json.dumps(request)); buf = io.StringIO(); sys.stdout = buf
        t = time.perf_counter()
        try:
            cli.main([cmd])
        finally:
            sys.stdin, sys.stdout = saved_stdin, saved_stdout
        total = time.perf_counter() - t
    finally:
        pymysql.cursors.Cursor.execute = original
    t = time.perf_counter(); json.loads(buf.getvalue()); parse = time.perf_counter() - t
    return dict(total=round(total, 2), sql=round(spent['sql'], 2), queries=spent['queries'], python_and_serialisation=round(total - spent['sql'], 2), client_json_parse=round(parse, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--titles', type=int, default=3000)
    ap.add_argument('--days', type=int, default=400)
    args = ap.parse_args()
    from tests.dbutil import reset_data
    from engine.analytics.series.compute import compute_all
    c = connect()
    reset_data(c)
    result = {'titles': args.titles, 'days': args.days}
    t = time.perf_counter(); seed(c, args.titles, args.days); result['seed_seconds'] = round(time.perf_counter() - t, 1)
    t = time.perf_counter(); compute_all(c, dt.datetime.now(dt.timezone.utc)); result['nightly_compute_seconds'] = round(time.perf_counter() - t, 1)
    with c.cursor() as q:
        q.execute('SELECT COUNT(*) n FROM daily_prices'); result['daily_rows'] = q.fetchone()['n']
        q.execute('SELECT COUNT(*) n FROM strategy_metrics'); result['metric_rows'] = q.fetchone()['n']
    c.close()
    t = time.perf_counter(); subprocess.run([sys.executable, '-c', 'import engine.cli'], cwd=ROOT, check=True); result['python_import_seconds'] = round(time.perf_counter() - t, 2)
    runs = []
    for label, cmd, req in (('explorer', 'explore', {'config': 'regular', 'view': {}}),
                            ('explorer page 25', 'explore', {'config': 'regular', 'view': {'limit': 25}}),
                            ('classement', 'ranking-table', {'ct_id': 'fast', 'user_id': 0, 'spec': None, 'include_curves': True}),
                            ('classement sans courbes', 'ranking-table', {'ct_id': 'fast', 'user_id': 0, 'spec': None, 'include_curves': False}),
                            ('fiche titre', 'sheet', {'listing_id': 1, 'config': 'regular', 'view': {}, 'fetch_profile': False})):
        cold = engine(cmd, req); hot = engine(cmd, req)
        runs.append(dict(scenario=label, cold=cold, hot=hot, hot_breakdown=breakdown(cmd, req)))
    result['scenarios'] = runs
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
