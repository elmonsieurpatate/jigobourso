"""Point d'entrée du moteur : python -m engine.cli <commande>   (job | tick | metrics | …)."""
import argparse
import json
import subprocess
import sys

from engine.shared.db import connect


def _admin_commands():
    from engine.analytics import adminsvc, funnel
    from engine.jobs import schedule, tasks
    from engine.shared import settings

    def stage(r):
        if r.get('stage') not in ('catalogue', 'yahoo'):
            raise ValueError('Étape inconnue')
        return r['stage']

    def sched_save(conn, r):
        settings.put(conn, 'schedule', schedule.normalize(r))
        return schedule.state(conn)

    def check(conn, r):
        tasks.precheck(conn, r.get('name'))
        return {'ok': True}
    return {
        'fdb-state': lambda conn, r: adminsvc.fdb_state(conn),
        'yahoo-state': lambda conn, r: adminsvc.yahoo_state(conn),
        'titles': adminsvc.titles,
        'rules-save': lambda conn, r: adminsvc.rules_save(conn, r.get('level'), r.get('config')),
        'rules-reset': lambda conn, r: adminsvc.rules_reset(conn, r.get('level')),
        'funnel': lambda conn, r: funnel.last_run(conn, stage(r)),
        'funnel-items': lambda conn, r: funnel.items(conn, r.get('stage'), r.get('step'), r.get('q', ''), r.get('kind', ''), r.get('mic', ''), r.get('page', 1)),
        'funnel-explain': lambda conn, r: funnel.explain(conn, r.get('q', '')),
        'schedule-get': lambda conn, r: schedule.state(conn),
        'schedule-save': sched_save,
        'job-check': check,
        'jobs-list': adminsvc.jobs_list,
        'job-detail': lambda conn, r: adminsvc.job_detail(conn, int(r['id'])),
    }


ADMIN = {}


def serve(cmd):
    """Commandes appelées par PHP : JSON en entrée, JSON en sortie, code 2 + {"error"} en cas de demande invalide."""
    import decimal
    import datetime as dt
    from engine.analytics import service, strategy, tracking

    def plain(o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (dt.datetime, dt.date)):
            return o.isoformat(sep=' ') if isinstance(o, dt.datetime) else o.isoformat()
        raise TypeError(type(o).__name__)
    ADMIN.update(_admin_commands())
    try:
        request = json.load(sys.stdin)
        if cmd == 'presets':
            result = {'presets': {name: strategy.preset(name) for name in strategy.PRESETS}, 'labels': strategy.LABELS,
                      'slope_levels': strategy.SLOPE_LEVELS, 'r2_levels': strategy.R2_LEVELS, 'rank_modes': list(strategy.RANK_MODES)}
        elif cmd == 'intraday':
            from engine.market import intraday
            from engine.market.yahoo import YahooClient
            result = intraday.view(connect(), int(request['listing_id']), client=YahooClient() if request.get('fetch', True) else None)
        elif cmd == 'etf-portfolio':
            from .analytics import etf
            result = etf.portfolio(connect(), request.get('positions', []))
        elif cmd == 'overview':
            from .analytics import overview
            result = overview.data_overview(connect())
        elif cmd == 'suivi':
            result = tracking.summary(connect())
        elif cmd in ADMIN:
            result = ADMIN[cmd](connect(), request)
        elif cmd == 'validate-config':
            result = strategy.validate(request)
        else:
            conn = connect()
            result = service.explore(conn, request) if cmd == 'explore' else service.instrument_sheet(conn, request)
        print(json.dumps(result, default=plain, ensure_ascii=False, allow_nan=False))
        return 0
    except ValueError as e:                                 # demande invalide : message écrit pour l'utilisateur
        print(json.dumps({'error': str(e)}, ensure_ascii=False))
        return 2
    except (KeyError, TypeError) as e:                      # forme de requête inattendue : le détail va dans le journal, pas vers le client
        print(f'{type(e).__name__}: {e}', file=sys.stderr)
        print(json.dumps({'error': f'Champ manquant : {e.args[0]}' if isinstance(e, KeyError) and e.args and isinstance(e.args[0], str) else 'Requête invalide'}, ensure_ascii=False))
        return 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog='engine')
    sub = ap.add_subparsers(dest='cmd', required=True)
    cat = sub.add_parser('catalogue', help='charger le catalogue depuis un clone FinanceDatabase')
    cat.add_argument('--source', required=True, help='dossier du clone (contient database/)')
    tick = sub.add_parser('tick', help='passage du cron (historiques du catalogue final)')
    tick.add_argument('--trigger', default='cron', choices=('cron', 'admin'))
    job = sub.add_parser('job', help='exécuter un traitement ou une chaîne (lancé depuis l’administration)')
    job.add_argument('--name', required=True)
    job.add_argument('--trigger', default='admin', choices=('admin', 'cron', 'system'))
    sub.add_parser('metrics', help='recalculer les mesures de stratégie')
    sub.add_parser('etf', help='recalculer la similarité des ETF (indépendant des mesures)')
    back = sub.add_parser('suivi-backfill', help='reconstituer les classements des dernières séances (origine « reconstitué »)')
    back.add_argument('--sessions', type=int, default=30)
    for name in ('fdb-state', 'yahoo-state', 'titles', 'rules-save', 'rules-reset', 'funnel', 'funnel-items', 'funnel-explain', 'schedule-get', 'schedule-save', 'job-check', 'jobs-list', 'job-detail'):
        sub.add_parser(name, help='administration (JSON sur stdin)')
    for name, text in (('explore', 'Explorer : classement et recherche (JSON sur stdin)'), ('sheet', 'fiche d’un titre (JSON sur stdin)'),
                       ('validate-config', 'valider une configuration de stratégie (JSON sur stdin)'),
                       ('etf-portfolio', 'Expositions connues et similarité du portefeuille'), ('presets', 'les quatre stratégies de départ'), ('suivi', 'statistiques de la page Suivi'), ('overview', 'vue d’ensemble des données (sources, fraîcheur, couverture)'), ('intraday', 'deux dernières séances en barres de 15 minutes (JSON sur stdin)')):
        sub.add_parser(name, help=text)
    args = ap.parse_args(argv)
    if args.cmd in ('fdb-state', 'yahoo-state', 'titles', 'rules-save', 'rules-reset', 'funnel', 'funnel-items', 'funnel-explain', 'schedule-get', 'schedule-save', 'job-check', 'jobs-list', 'job-detail', 'explore', 'sheet', 'validate-config', 'presets', 'suivi', 'intraday', 'overview', 'etf-portfolio'):
        return serve(args.cmd)
    if args.cmd == 'catalogue':
        from engine.catalogue.loader import load
        commit = subprocess.run(['git', '-C', args.source, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or '0' * 40
        conn = connect()
        print(json.dumps(load(conn, args.source, commit), ensure_ascii=False))
    else:
        from engine.jobs import tasks
        from engine.jobs.runner import run_job
        from engine.market import hours
        from engine.market.yahoo import YahooClient
        conn = connect()
        now = hours.utcnow()
        if args.cmd == 'tick':
            try:
                print(json.dumps([(k, m, j) for k, m, j in tasks.tick(conn, YahooClient(), now, args.trigger)]))
            except Exception as e:                                          # noqa: BLE001 : visible dans l'administration, puis remonte vers logs/cron.log
                if args.trigger == 'cron':
                    from engine.jobs import schedule
                    conn.rollback()
                    schedule.record_error(conn, now, 'passage', e)
                raise
        elif args.cmd == 'job':
            print(tasks.run_manual(conn, YahooClient(), args.name, now, args.trigger))
        elif args.cmd == 'suivi-backfill':
            from engine.analytics import tracking
            print(tracking.backfill(conn, args.sessions, log=lambda m: print(m, file=sys.stderr)), tracking.update_outcomes(conn))
        elif args.cmd == 'metrics':
            from engine.analytics import compute
            print(compute.compute_all(conn, now))
        elif args.cmd == 'etf':
            from engine.analytics import etf
            print(etf.build(conn, now))
    return 0


if __name__ == '__main__':
    sys.exit(main())
