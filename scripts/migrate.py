"""Migrations de schéma sans perte : applique une seule fois, dans l'ordre, les fichiers de db/migrations/ (voir README.md de ce dossier).

  python scripts/migrate.py --pending       liste les migrations à appliquer (code retour 0)
  python scripts/migrate.py --apply         applique les migrations en attente
  python scripts/migrate.py --record-all    marque toutes les migrations comme déjà incluses (base neuve créée par db/schema.sql)
  python scripts/migrate.py --check         vérifie seulement que les fichiers sont admissibles (CI)
Connexion : variables JIGO_DB_* (comme le moteur).
"""
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'db', 'migrations')
FORBIDDEN = re.compile(r'\b(DROP|TRUNCATE|DELETE|UPDATE|INSERT|RENAME|MODIFY|CHANGE|REPLACE\s+INTO|GRANT|REVOKE)\b', re.I)
ALLOWED_START = re.compile(r'^(CREATE\s+(UNIQUE\s+)?(TABLE\s+IF\s+NOT\s+EXISTS|INDEX|OR\s+REPLACE\s+VIEW)|ALTER\s+TABLE\s+\S+\s+ADD\s+)', re.I)


def statements(sql):
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.S)
    return [s.strip() for s in sql.split(';') if s.strip()]


def check(sql, name='?'):
    """ValueError si le fichier contient autre chose que des ajouts."""
    for st in statements(sql):
        if FORBIDDEN.search(re.sub(r'ON\s+DELETE\s+CASCADE', '', st, flags=re.I)) or not ALLOWED_START.match(st):
            raise ValueError(f'{name} : instruction non admise ({st[:60]!r}…). Seuls les ajouts sont autorisés.')


def files(directory=DIR):
    return sorted(f for f in os.listdir(directory) if f.endswith('.sql')) if os.path.isdir(directory) else []


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR(120) NOT NULL, applied_at DATETIME NOT NULL, PRIMARY KEY (name)) ENGINE=InnoDB')
    conn.commit()


def pending(conn, directory=DIR):
    ensure_table(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT name FROM schema_migrations')
        done = {r['name'] for r in cur.fetchall()}
    return [f for f in files(directory) if f not in done]


def apply(conn, directory=DIR):
    """Applique les migrations en attente. Tout est vérifié AVANT la première exécution. Renvoie la liste appliquée."""
    todo = pending(conn, directory)
    texts = {}
    for f in todo:
        with open(os.path.join(directory, f), encoding='utf-8') as fh:
            texts[f] = fh.read()
        check(texts[f], f)
    for f in todo:
        with conn.cursor() as cur:
            for st in statements(texts[f]):
                cur.execute(st)
            cur.execute('INSERT INTO schema_migrations(name, applied_at) VALUES (%s,%s)', (f, datetime.datetime.utcnow().replace(microsecond=0)))
        conn.commit()
    return todo


def record_all(conn, directory=DIR):
    ensure_table(conn)
    with conn.cursor() as cur:
        for f in files(directory):
            cur.execute('INSERT IGNORE INTO schema_migrations(name, applied_at) VALUES (%s,%s)', (f, datetime.datetime.utcnow().replace(microsecond=0)))
    conn.commit()


def main(argv):
    mode = argv[1] if len(argv) > 1 else ''
    if mode == '--check':
        for f in files():
            with open(os.path.join(DIR, f), encoding='utf-8') as fh:
                check(fh.read(), f)
        print(f'{len(files())} migration(s) admissible(s)')
        return 0
    sys.path.insert(0, ROOT)
    from engine.shared.db import connect
    conn = connect()
    try:
        if mode == '--pending':
            print('\n'.join(pending(conn)))
        elif mode == '--apply':
            done = apply(conn)
            print(f'{len(done)} migration(s) appliquée(s)' + (' : ' + ', '.join(done) if done else ''))
        elif mode == '--record-all':
            record_all(conn)
            print('migrations enregistrées')
        else:
            print(__doc__)
            return 2
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(3)
