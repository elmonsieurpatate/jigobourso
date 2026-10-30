"""Connexion MariaDB. Configuration par variables d'environnement JIGO_DB_* ; aucun identifiant dans le code.

Règle d'hébergement : MariaDB ferme une connexion restée inactive plus de 20 s (wait_timeout). Une connexion n'est donc jamais supposée vivante après un calcul
ou une attente réseau : `ensure(conn)` la rétablit, et se place aux frontières de phase (début d'étape, avant une écriture), jamais au milieu d'une transaction."""
import os
import pymysql
import pymysql.cursors


def connect():
    env = os.environ
    socket = env.get('JIGO_DB_SOCKET')          # base de test locale (sans réseau) ; absent en production
    for name in ('JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD') + (() if socket else ('JIGO_DB_HOST',)):
        if not env.get(name):
            raise RuntimeError(f'Variable {name} absente')
    where = {'unix_socket': socket} if socket else {'host': env['JIGO_DB_HOST'], 'port': int(env.get('JIGO_DB_PORT', '3306'))}
    return pymysql.connect(user=env['JIGO_DB_USER'], password=env['JIGO_DB_PASSWORD'], database=env['JIGO_DB_NAME'], charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False, connect_timeout=10, read_timeout=900, write_timeout=900, **where)


def ensure(conn):
    """Rétablit la connexion si le serveur l'a fermée (le même objet reste utilisable). À appeler hors transaction."""
    try:
        conn.ping(reconnect=False)
    except pymysql.err.Error:
        conn.connect()
