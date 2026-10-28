"""Connexion MariaDB. Configuration par variables d'environnement JIGO_DB_* ; aucun identifiant dans le code."""
import os
import pymysql
import pymysql.cursors


def connect():
    env = os.environ
    for name in ('JIGO_DB_HOST', 'JIGO_DB_NAME', 'JIGO_DB_USER', 'JIGO_DB_PASSWORD'):
        if not env.get(name):
            raise RuntimeError(f'Variable {name} absente')
    return pymysql.connect(host=env['JIGO_DB_HOST'], port=int(env.get('JIGO_DB_PORT', '3306')), user=env['JIGO_DB_USER'],
                           password=env['JIGO_DB_PASSWORD'], database=env['JIGO_DB_NAME'], charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False)
