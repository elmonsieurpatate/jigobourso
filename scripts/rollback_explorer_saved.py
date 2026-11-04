"""Explicit rollback of the Explorer-only additive table; refuses any saved data.

Run only during a reviewed rollback: python scripts/rollback_explorer_saved.py --empty-only
No collection, portfolio or old saved-search table is modified.
"""
import sys
import os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.shared.db import connect


def rollback(conn):
    from scripts.migrate import ensure_table
    ensure_table(conn)
    with conn.cursor() as q:
        # Lock out concurrent library writes between the safety check and DDL.
        q.execute('LOCK TABLES explorer_saved WRITE')
        try:
            q.execute('SELECT COUNT(*) n FROM explorer_saved')
            if q.fetchone()['n']:
                raise ValueError('Rollback refusé : exporter et conserver les sauvegardes avant toute suppression de table')
            q.execute('DROP TABLE explorer_saved')
        finally:
            q.execute('UNLOCK TABLES')
        q.execute("DELETE FROM schema_migrations WHERE name='20261104_explorer_saved.sql'")
    conn.commit()


if __name__=='__main__':
    if sys.argv[1:]!=['--empty-only']:raise SystemExit(__doc__)
    conn=connect()
    try:rollback(conn)
    finally:conn.close()
