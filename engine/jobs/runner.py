"""Journal des traitements : un traitement = une ligne de `jobs`, avertissements/erreurs dans `job_logs`.
Un traitement interrompu (processus tué) est marqué « interrupted » au démarrage suivant ; deux traitements du même type ne se chevauchent pas."""
import datetime
import time
import traceback

from engine.market.yahoo import RateLimited
from engine.shared.db import ensure


def _now():
    """UTC naïf (comme toutes les colonnes DATETIME du schéma : `jobs.started_at`, `updated_at`…), sans `datetime.utcnow()` déprécié."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)


# Durée au-delà de laquelle un traitement « en cours » est considéré mort (processus tué, hébergeur, panne) et libère son verrou.
# Les traitements du cron ont une durée bornée : un verrou resté posé ne doit jamais bloquer le rattrapage pendant des heures.
STALE_MINUTES = {'catchup': 8, 'maintenance': 45, 'metrics': 45, 'etf': 45}
STALE_PREFIX = (('intraday:', 20), ('daily:', 45))
COMPUTE = ('maintenance', 'metrics', 'etf')     # écrivent les mêmes tables dérivées : jamais deux en même temps (même verrou), qu'ils viennent du cron ou d'une demande explicite
LOG_DETAIL_MAX = 8000          # taille maximale du texte complet d'un journal (`job_logs.detail`) ; `message` est tronqué à 400
STALE_DEFAULT = 180            # traitements manuels de l'administration (import, filtres, historiques)


def stale_minutes(job_type):
    if job_type in STALE_MINUTES:
        return STALE_MINUTES[job_type]
    return next((m for prefix, m in STALE_PREFIX if job_type.startswith(prefix)), STALE_DEFAULT)


def recover_interrupted(conn):
    """Marque « interrupted » les traitements restés « running » trop longtemps pour leur type (libère le verrou)."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, job_type, COALESCE(updated_at, started_at) AS beat FROM jobs WHERE status='running'")
        running = cur.fetchall()
        for j in running:
            if j['beat'] < _now() - datetime.timedelta(minutes=stale_minutes(j['job_type'])):
                cur.execute("UPDATE jobs SET status='interrupted', finished_at=%s, summary=LEFT(CONCAT('interrompu (processus arrêté) · ', COALESCE(summary, '')), 500) WHERE id=%s", (_now(), j['id']))
    conn.commit()


def run_job(conn, job_type, fn, trigger='cron'):
    """Exécute fn(log) -> (items_ok, items_error, résumé). Refuse de démarrer si le même type est déjà en cours."""
    recover_interrupted(conn)
    # Verrou nommé le temps de « vérifier puis créer » : deux processus simultanés (cron + test depuis l'administration) ne démarrent pas le même type.
    group = COMPUTE if job_type in COMPUTE else (job_type,)
    lock = 'jigo:job:' + ('compute' if job_type in COMPUTE else job_type)
    with conn.cursor() as cur:
        cur.execute('SELECT GET_LOCK(%s, 0) AS got', (lock,))
        if not cur.fetchone()['got']:
            return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM jobs WHERE job_type IN %s AND status='running'", (group,))
            if cur.fetchone():
                return None
            cur.execute("SELECT id FROM jobs WHERE job_type=%s AND status='queued' ORDER BY id LIMIT 1", (job_type,))
            queued = cur.fetchone()
            if queued:      # demande faite depuis l'administration : on reprend la ligne
                cur.execute("UPDATE jobs SET status='running', started_at=%s, updated_at=%s WHERE id=%s", (_now(), _now(), queued['id']))
                job_id = queued['id']
            else:
                cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at,updated_at) VALUES (%s,%s,'running',%s,%s)", (job_type, trigger, _now(), _now()))
                job_id = cur.lastrowid
        conn.commit()
    finally:
        with conn.cursor() as cur:
            cur.execute('SELECT RELEASE_LOCK(%s)', (lock,))

    def beat():
        """Battement : un traitement long mais vivant n'est jamais jugé périmé (le seuil s'applique au dernier battement, pas au démarrage)."""
        with conn.cursor() as cur:
            cur.execute('UPDATE jobs SET updated_at=%s WHERE id=%s', (_now(), job_id))

    def log(level, message):
        ensure(conn)
        text = str(message)
        with conn.cursor() as cur:       # `message` reste court (liste de l'administration) ; le texte complet (trace) va dans `detail`
            cur.execute('INSERT INTO job_logs(job_id,level,message,detail,logged_at) VALUES (%s,%s,%s,%s,%s)',
                        (job_id, level, text[:400], text[:LOG_DETAIL_MAX] if len(text) > 400 else None, _now()))
        beat()
        conn.commit()

    steps = []

    def step(name, fn, detail=None):
        """Exécute une étape du traitement en la chronométrant (table job_steps) ; `detail` peut être une fonction du résultat."""
        ensure(conn)
        t0, started = time.monotonic(), _now()
        result = fn()
        d = detail(result) if callable(detail) else detail
        steps.append(name)
        ensure(conn)
        with conn.cursor() as cur:
            cur.execute('INSERT INTO job_steps(job_id,seq,name,started_at,duration_ms,detail) VALUES (%s,%s,%s,%s,%s,%s)',
                        (job_id, len(steps), name[:80], started, int((time.monotonic() - t0) * 1000), None if d is None else str(d)[:300]))
        beat()
        conn.commit()
        return result

    def progress(text):
        """Avancement visible dans l'administration pendant l'exécution (remplacé par le résumé final)."""
        with conn.cursor() as cur:
            cur.execute('UPDATE jobs SET summary=%s, updated_at=%s WHERE id=%s', (str(text)[:500], _now(), job_id))
        conn.commit()
    log.job_id, log.step, log.progress = job_id, step, progress
    status, ok, errors, summary = 'completed', None, 0, None
    try:
        ok, errors, summary = fn(log)
        if errors:
            status = 'completed_with_errors'
    except RateLimited as e:
        status, summary = 'paused', f'Yahoo 429, reprise au prochain passage (Retry-After {e.retry_after})'
        log('warning', summary)
    except Exception as e:
        status, summary = 'failed', f'{type(e).__name__}: {e}'
        trace = traceback.format_exc()[-LOG_DETAIL_MAX:]
        ensure(conn)                               # le statut final s'écrit toujours : jamais sur une connexion que l'erreur a fermée
        conn.rollback()
        log('error', trace)
    ensure(conn)
    with conn.cursor() as cur:
        cur.execute('UPDATE jobs SET status=%s, finished_at=%s, items_ok=%s, items_error=%s, summary=%s WHERE id=%s',
                    (status, _now(), ok, errors, (summary or '')[:500], job_id))
    conn.commit()
    return job_id
