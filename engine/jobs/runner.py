"""Journal des traitements : un traitement = une ligne de `jobs`, avertissements/erreurs dans `job_logs`.
Un traitement interrompu (processus tué) est marqué « interrupted » au démarrage suivant ; deux traitements du même type ne se chevauchent pas."""
import datetime
import time
import traceback

from engine.market.yahoo import RateLimited


def _now():
    return datetime.datetime.utcnow().replace(microsecond=0)


def recover_interrupted(conn, stale_minutes=180):
    with conn.cursor() as cur:
        cur.execute("UPDATE jobs SET status='interrupted', finished_at=%s WHERE status='running' AND started_at < %s",
                    (_now(), _now() - datetime.timedelta(minutes=stale_minutes)))
    conn.commit()


def run_job(conn, job_type, fn, trigger='cron'):
    """Exécute fn(log) -> (items_ok, items_error, résumé). Refuse de démarrer si le même type est déjà en cours."""
    recover_interrupted(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM jobs WHERE job_type=%s AND status='running'", (job_type,))
        if cur.fetchone():
            return None
        cur.execute("SELECT id FROM jobs WHERE job_type=%s AND status='queued' ORDER BY id LIMIT 1", (job_type,))
        queued = cur.fetchone()
        if queued:      # demande faite depuis l'administration : on reprend la ligne
            cur.execute("UPDATE jobs SET status='running', started_at=%s WHERE id=%s", (_now(), queued['id']))
            job_id = queued['id']
        else:
            cur.execute("INSERT INTO jobs(job_type,trigger_by,status,started_at) VALUES (%s,%s,'running',%s)", (job_type, trigger, _now()))
            job_id = cur.lastrowid
    conn.commit()

    def log(level, message):
        with conn.cursor() as cur:
            cur.execute('INSERT INTO job_logs(job_id,level,message,logged_at) VALUES (%s,%s,%s,%s)', (job_id, level, str(message)[:400], _now()))
        conn.commit()

    steps = []

    def step(name, fn, detail=None):
        """Exécute une étape du traitement en la chronométrant (table job_steps) ; `detail` peut être une fonction du résultat."""
        t0, started = time.monotonic(), _now()
        result = fn()
        d = detail(result) if callable(detail) else detail
        steps.append(name)
        with conn.cursor() as cur:
            cur.execute('INSERT INTO job_steps(job_id,seq,name,started_at,duration_ms,detail) VALUES (%s,%s,%s,%s,%s,%s)',
                        (job_id, len(steps), name[:80], started, int((time.monotonic() - t0) * 1000), None if d is None else str(d)[:300]))
        conn.commit()
        return result
    def progress(text):
        """Avancement visible dans l'administration pendant l'exécution (remplacé par le résumé final)."""
        with conn.cursor() as cur:
            cur.execute('UPDATE jobs SET summary=%s WHERE id=%s', (str(text)[:500], job_id))
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
        log('error', traceback.format_exc()[-380:])
        conn.rollback()
    with conn.cursor() as cur:
        cur.execute('UPDATE jobs SET status=%s, finished_at=%s, items_ok=%s, items_error=%s, summary=%s WHERE id=%s',
                    (status, _now(), ok, errors, (summary or '')[:500], job_id))
    conn.commit()
    return job_id
