"""Cron : ce qu'il fait (uniquement l'entretien des historiques du catalogue final) et s'il fonctionne VRAIMENT.

Le déclencheur est externe : une tâche cron de l'hébergeur appelle `tick` (toutes les 5 minutes en production, mesuré ; la fréquence réelle est mesurée, pas supposée). Ce module distingue :
  - la configuration prévue (activation, intervalle) ;
  - l'observé : le dernier passage RÉEL du cron (battement écrit par `tick` quand c'est le cron qui l'appelle) et les exécutions réelles dans `jobs`.
Il ne prétend jamais connaître une cause qu'il ne peut pas voir : si le cron ne passe pas, il le dit et indique ce qu'il ne peut pas diagnostiquer.
"""
import datetime
from zoneinfo import ZoneInfo

from engine.market import catchup, collect, hours
from engine.shared import settings

TASKS = (
    {'id': 'daily', 'label': 'Historique quotidien', 'prefix': 'daily:', 'stats': 'daily',
     'help': 'Après la clôture officielle de chaque place : récupère les séances manquantes (jamais ce qui est déjà en base, 400 séances conservées), complète les trous, puis recalcule les indicateurs.',
     'params': {}},
    {'id': 'intraday', 'label': 'Barres de 15 minutes', 'prefix': 'intraday:', 'stats': 'intraday',
     'help': 'Pendant la séance de chaque place (+ 30 min après la clôture) : ne télécharge que les barres manquantes ou à actualiser des deux dernières séances (les séances plus anciennes, jusqu’à la rétention, sont rattrapées automatiquement).',
     'params': {'interval_minutes': {'label': 'Intervalle minimal entre deux collectes d’une place (min)', 'default': 15, 'min': 5, 'max': 120}}},
)
BY_ID = {t['id']: t for t in TASKS}
CRON_EXPECTED_MINUTES = 5
RECENT_PASSES = 12          # derniers passages du cron conservés pour mesurer la fréquence réelle
STUCK_MINUTES = 90


def default_config():
    cfg = {'cron_interval_minutes': CRON_EXPECTED_MINUTES}
    for t in TASKS:
        cfg[t['id']] = {'enabled': True}
        for k, spec in t['params'].items():
            cfg[t['id']][k] = spec['default']
    return cfg


def normalize(config):
    cfg = default_config()
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError('Planification invalide')
    if 'cron_interval_minutes' in config:
        v = config['cron_interval_minutes']
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 60:
            raise ValueError('Intervalle d’appel du cron : 1 à 60 minutes')
        cfg['cron_interval_minutes'] = v
    for tid, given in config.items():
        if tid in ('cron_interval_minutes', 'nightly', 'catalogue'):        # anciens réglages : le cron ne construit plus le catalogue
            continue
        if tid not in BY_ID or not isinstance(given, dict):
            raise ValueError(f'Tâche inconnue : {tid}')
        if 'enabled' in given:
            if type(given['enabled']) is not bool:
                raise ValueError('Activation invalide')
            cfg[tid]['enabled'] = given['enabled']
        for k, spec in BY_ID[tid]['params'].items():
            if k in given:
                v = given[k]
                if isinstance(v, bool) or not isinstance(v, int) or not spec['min'] <= v <= spec['max']:
                    raise ValueError(f'{spec["label"]} : entre {spec["min"]} et {spec["max"]}')
                cfg[tid][k] = v
    return cfg


def get(conn):
    return normalize(settings.get(conn, 'schedule', {}))


def _iso(v):
    return v.isoformat(sep=' ') if hasattr(v, 'isoformat') else v


def beat(conn, now, trigger='cron', done=None, duration=None):
    """Battement. Seul un passage du CRON compte comme preuve de fonctionnement ; un test manuel est noté à part.
    Le premier battement d'un passage (done=None) s'ajoute à la liste des derniers passages, qui sert à mesurer la fréquence réelle."""
    key = 'cron_heartbeat' if trigger == 'cron' else 'cron_test'
    prev = settings.get(conn, key, {})
    at = now.replace(tzinfo=None, microsecond=0).isoformat(sep=' ')
    data = {'at': at, 'trigger': trigger, 'done': done if done is not None else prev.get('done'), 'duration_s': duration}
    if trigger == 'cron':
        recent = list(prev.get('recent') or [])
        if done is None and (not recent or recent[-1] != at):
            recent.append(at)
        data['recent'] = recent[-RECENT_PASSES:]
    settings.put(conn, key, data)


def measured_interval(recent):
    """Écart médian (minutes) entre les derniers passages du cron ; None tant que moins de 3 passages sont connus."""
    pts = []
    for v in recent or []:
        try:
            pts.append(datetime.datetime.fromisoformat(v))
        except ValueError:
            pass
    gaps = sorted((b - a).total_seconds() / 60 for a, b in zip(pts, pts[1:]) if b > a)
    if len(gaps) < 2:
        return None
    mid = len(gaps) // 2
    return round(gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2, 1)


def record_error(conn, now, where, exc):
    """Erreur d'un passage du cron survenue hors d'un traitement (base, planification, import) : conservée pour l'administration (50 dernières)."""
    errs = settings.get(conn, 'cron_errors', [])
    errs.insert(0, {'at': now.replace(tzinfo=None, microsecond=0).isoformat(sep=' '), 'where': where, 'message': f'{type(exc).__name__}: {exc}'[:300]})
    settings.put(conn, 'cron_errors', errs[:50])


def cron_errors(conn, naive, days=7, limit=40):
    """Tout ce qui a mal tourné pour le cron sur `days` jours : avertissements et erreurs des traitements automatiques, traitements en échec / en pause /
    interrompus, erreurs du passage lui-même. Liste vide = aucune erreur enregistrée (et non « inconnu »)."""
    since = naive - datetime.timedelta(days=days)
    out = []
    with conn.cursor() as cur:
        cur.execute("""SELECT l.level, l.message, l.logged_at, j.job_type, j.id job_id FROM job_logs l JOIN jobs j ON j.id=l.job_id
                       WHERE j.trigger_by='cron' AND l.level IN ('warning','error') AND l.logged_at >= %s ORDER BY l.id DESC LIMIT %s""", (since, limit))
        out += [{'level': r['level'], 'message': r['message'], 'at': _iso(r['logged_at']), 'source': 'traitement', 'job_type': r['job_type'], 'job_id': r['job_id']} for r in cur.fetchall()]
        cur.execute("""SELECT id, job_type, status, started_at, summary FROM jobs WHERE trigger_by='cron' AND status IN ('failed','paused','interrupted') AND started_at >= %s
                       ORDER BY id DESC LIMIT %s""", (since, limit))
        out += [{'level': 'error' if r['status'] != 'paused' else 'warning', 'message': f'{ {"failed": "Échec", "paused": "En pause", "interrupted": "Interrompu"}[r["status"]] } : {r["summary"] or ""}',
                 'at': _iso(r['started_at']), 'source': 'traitement', 'job_type': r['job_type'], 'job_id': r['id']} for r in cur.fetchall()]
    out += [{'level': 'error', 'message': e['message'], 'at': e['at'], 'source': 'passage du cron', 'job_type': e['where'], 'job_id': None}
            for e in settings.get(conn, 'cron_errors', []) if e['at'] >= _iso(since)]
    out.sort(key=lambda e: e['at'], reverse=True)
    return out[:limit]


def _next_settle(mic, now):
    tz, _, closes = hours.spec(mic)
    day = now.astimezone(ZoneInfo(tz)).date()
    for _ in range(8):
        if day.weekday() < 5:
            end = datetime.datetime.combine(day, closes, ZoneInfo(tz)) + datetime.timedelta(minutes=hours.SETTLE_MINUTES)
            if end > now:
                return end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        day += datetime.timedelta(days=1)


def _next_open(mic, now):
    cand = now
    for _ in range(8 * 24 * 4):
        if hours.is_open(mic, cand):
            return cand.replace(tzinfo=None)
        cand += datetime.timedelta(minutes=15)


def _last_jobs(conn, prefix):
    with conn.cursor() as cur:
        cur.execute("""SELECT id, job_type, trigger_by, status, started_at, finished_at, items_ok, items_error, summary, TIMESTAMPDIFF(SECOND, started_at, finished_at) secs
                       FROM jobs WHERE job_type LIKE %s ORDER BY id DESC LIMIT 60""", (prefix + '%',))
        return cur.fetchall()


def _job(r):
    return {'id': r['id'], 'job_type': r['job_type'], 'status': r['status'], 'started_at': _iso(r['started_at']), 'finished_at': _iso(r['finished_at']), 'duration_s': r['secs'],
            'items_ok': r['items_ok'], 'items_error': r['items_error'], 'summary': r['summary'], 'trigger': r['trigger_by']}


def state(conn, now=None):
    now = (now or hours.utcnow())
    naive = now.replace(tzinfo=None)
    now = now if now.tzinfo else now.replace(tzinfo=datetime.timezone.utc)
    cfg = get(conn)
    hb, test = settings.get(conn, 'cron_heartbeat', {}), settings.get(conn, 'cron_test', {})
    stats = settings.get(conn, 'last_stats', {})
    expected = cfg['cron_interval_minutes']
    last_beat = datetime.datetime.fromisoformat(hb['at']) if hb.get('at') else None
    age = (naive - last_beat).total_seconds() / 60 if last_beat else None
    with conn.cursor() as cur:
        cur.execute("SELECT id, job_type, started_at, TIMESTAMPDIFF(MINUTE, started_at, %s) mins FROM jobs WHERE status='running' AND started_at < %s", (naive, naive - datetime.timedelta(minutes=STUCK_MINUTES)))
        stuck = cur.fetchall()
        cur.execute("SELECT DISTINCT mic FROM v_collect_set")
        mics = [r['mic'] for r in cur.fetchall()]
    diagnosis = []
    if last_beat is None:
        cron = {'state': 'never', 'observed': False, 'label': 'Non observé'}
        diagnosis.append('Aucun passage du cron n’a jamais été enregistré : la tâche planifiée de l’hébergeur n’est pas installée, ou elle n’atteint pas le site (adresse ou clé incorrecte). Le système ne peut pas voir lequel de ces cas.')
    elif age <= expected * 2.5:
        cron = {'state': 'ok', 'observed': True, 'label': 'Observé'}
    else:
        cron = {'state': 'late', 'observed': True, 'label': 'Ne répond plus'}
        diagnosis.append(f'Dernier passage il y a {age / 60:.1f} h alors qu’un passage est attendu toutes les {expected} min. Le cron ne se déclenche plus (tâche arrêtée ou supprimée chez l’hébergeur, adresse ou clé modifiée) : le système ne peut pas savoir laquelle de ces causes.' if age > 120
                         else f'Dernier passage il y a {age:.0f} min alors qu’un passage est attendu toutes les {expected} min : retard ou arrêt du cron (cause non observable).')
    measured = measured_interval(hb.get('recent'))
    if measured is not None and abs(measured - expected) > max(2, 0.3 * expected):
        diagnosis.append(f'Fréquence observée : un passage toutes les {measured:g} min, alors que la planification attend {expected} min. Corrigez la valeur ici ou la tâche chez l’hébergeur.')
    for s in stuck:
        diagnosis.append(f'Verrou possible : le traitement « {s["job_type"]} » (n° {s["id"]}) est « en cours » depuis {s["mins"]} min. Un traitement du même type ne redémarre pas tant que celui-ci n’est pas terminé ; au-delà de 3 h il est marqué « interrompu » au passage suivant.')
    for t in TASKS:
        if not cfg[t['id']]['enabled']:
            diagnosis.append(f'La tâche « {t["label"]} » est désactivée dans la planification : le passage du cron l’ignore.')
    tasks = []
    for t in TASKS:
        c = cfg[t['id']]
        rows = _last_jobs(conn, t['prefix'])
        last = rows[0] if rows else None
        last_ok = next((r for r in rows if r['status'] in ('completed', 'completed_with_errors')), None)
        running = next((r for r in rows if r['status'] == 'running'), None)
        done = [r for r in rows if r['secs'] is not None and r['status'] in ('completed', 'completed_with_errors')][:20]
        if t['id'] == 'daily':
            nxt = min((x for x in (_next_settle(m, now) for m in mics) if x), default=None)
        else:
            opens = [m for m in mics if hours.known(m) and hours.is_open(m, now)]
            nxt = (naive + datetime.timedelta(minutes=expected)) if opens else min((x for x in (_next_open(m, now) for m in mics if hours.known(m)) if x), default=None)
        if not c['enabled']:
            st, why = 'inactive', 'Désactivée.'
        elif running and (naive - running['started_at']).total_seconds() < STUCK_MINUTES * 60:
            st, why = 'running', 'Exécution en cours.'
        elif last is None:
            st, why = 'never', 'Jamais exécutée.' + (' Le cron n’a jamais été observé.' if cron['state'] == 'never' else '')
        elif last['status'] in ('failed', 'interrupted'):
            st, why = 'error', f'Dernière exécution en échec : {last["summary"] or last["status"]}'
        elif cron['state'] == 'late':
            st, why = 'late', 'Le cron ne passe plus : aucune nouvelle exécution.'
        elif t['id'] == 'daily' and last_ok and (naive - (last_ok['finished_at'] or last_ok['started_at'])).total_seconds() > 30 * 3600 and any(m for m in mics if collect.latest_settled(m, now) > (last_ok['started_at'].date())):
            st, why = 'late', 'Une clôture publiée n’a pas encore été collectée.'
        else:
            st, why = 'ok', 'Fonctionne comme prévu.' if last_ok else 'Dernière exécution incomplète.'
        tasks.append({'id': t['id'], 'label': t['label'], 'help': t['help'], 'enabled': c['enabled'], 'params': {k: {'value': c[k], **spec} for k, spec in t['params'].items()},
                      'state': st, 'state_detail': why, 'last': _job(last) if last else None, 'last_ok': _job(last_ok) if last_ok else None,
                      'avg_duration_s': sum(r['secs'] for r in done) / len(done) if done else None, 'next': _iso(nxt) if nxt else None, 'stats': stats.get(t['stats']),
                      'recent': [_job(r) for r in rows[:5]]})
    with conn.cursor() as cur:
        cur.execute("SELECT id, status, started_at, finished_at, summary, TIMESTAMPDIFF(SECOND, started_at, finished_at) secs FROM jobs WHERE job_type='maintenance' ORDER BY id DESC LIMIT 1")
        maint = cur.fetchone()
    cron.update({'last_at': hb.get('at'), 'last_done': hb.get('done'), 'last_duration_s': hb.get('duration_s'), 'expected_minutes': expected, 'measured_minutes': measured, 'passes_seen': len(hb.get('recent') or []), 'age_minutes': age,
                 'next_at': _iso(last_beat + datetime.timedelta(minutes=measured or expected)) if last_beat else None, 'last_test': test or None})
    errors = cron_errors(conn, naive)
    catch = catchup.status(conn, naive)
    if catch['unrecoverable']:
        diagnosis.append(f'{len(catch["unrecoverable"])} séance(s) de barres de 15 minutes n’ont pas pu être complétées : Yahoo ne les fournit pas (voir « Rattrapage automatique »).')
    return {'cron': cron, 'catchup': catch, 'diagnosis': diagnosis, 'tasks': tasks, 'errors': errors, 'config': cfg, 'now_utc': naive.isoformat(sep=' '),
            'maintenance': None if not maint else {'id': maint['id'], 'status': maint['status'], 'started_at': _iso(maint['started_at']), 'duration_s': maint['secs'], 'summary': maint['summary']}}
