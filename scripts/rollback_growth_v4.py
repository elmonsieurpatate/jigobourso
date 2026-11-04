"""Optional additive-schema rollback. Refuses any lifecycle or admin data.

Normal rollback restores code and leaves this harmless metadata table intact.
Never run on a real database without explicit authorization and backup.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def rollback(conn):
    with conn.cursor() as q:
        q.execute('LOCK TABLES explorer_states WRITE,settings WRITE')
        try:
            q.execute('SELECT COUNT(*) n FROM explorer_states')
            if q.fetchone()['n']:raise ValueError('États de stratégies présents : exportez et conservez les données ; retour arrière refusé')
            q.execute("SELECT COUNT(*) n FROM settings WHERE name='explorer_growth'")
            if q.fetchone()['n']:raise ValueError('Réglages V4 présents : retour arrière de schéma refusé')
            q.execute('DROP TABLE explorer_states')
        finally:q.execute('UNLOCK TABLES')
        q.execute("SHOW TABLES LIKE 'schema_migrations'")
        if q.fetchone():q.execute("DELETE FROM schema_migrations WHERE name='20261105_explorer_states.sql'")
    conn.commit()


if __name__=='__main__':
    if sys.argv[1:]!=['--empty-only']:raise SystemExit('Usage : rollback_growth_v4.py --empty-only (refus si données présentes)')
    from engine.shared.db import connect
    conn=connect()
    try:rollback(conn)
    finally:conn.close()
