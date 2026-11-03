"""Prepare a release through the normal derived-metrics job; never edit source prices or user data."""
import time
from engine.shared.db import connect
from engine.jobs import tasks
from scripts.verify_financial_release import run as verify


def refresh_metrics():
    conn=connect()
    try:
        # Standard compute-job locks also serialize this request with normal maintenance.
        job=None
        for attempt in range(5):
            job=tasks.run_manual(conn,None,'metrics',trigger='system')
            if job is not None:break
            if attempt<4:time.sleep(15)
        if job is None:raise RuntimeError('Erreur préparation financière : calcul dérivé déjà occupé')
        with conn.cursor() as q:
            q.execute('SELECT status FROM jobs WHERE id=%s',(job,));state=q.fetchone()['status']
        if state!='completed':raise RuntimeError('Erreur préparation financière : recalcul dérivé non terminé')
    finally:conn.close()


def prepare(check=verify,refresh=refresh_metrics):
    try:
        check()
        return
    except AssertionError:
        print('== Actualisation des indicateurs dérivés par le traitement existant',flush=True)
    refresh()
    # Same read-only check, same windows and tolerance. Any remaining mismatch aborts deployment.
    check()
    print('== Contrôle financier strict validé après actualisation',flush=True)


if __name__=='__main__':prepare()
