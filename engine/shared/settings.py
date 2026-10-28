"""Accès aux réglages persistants (table `settings`, JSON) et configuration des règles : lecture avec valeurs par défaut, écriture validée."""
import datetime
import hashlib
import json


def get(conn, name, default=None):
    with conn.cursor() as cur:
        cur.execute('SELECT value_json FROM settings WHERE name=%s', (name,))
        row = cur.fetchone()
    return json.loads(row['value_json']) if row else default


def put(conn, name, value):
    with conn.cursor() as cur:
        cur.execute('INSERT INTO settings(name, value_json, updated_at) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE value_json=VALUES(value_json), updated_at=VALUES(updated_at)',
                    (name, json.dumps(value, ensure_ascii=False), datetime.datetime.utcnow().replace(microsecond=0)))
    conn.commit()


def digest(config):
    return hashlib.sha1(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:12]


def catalogue_rules(conn):
    from engine.catalogue import rules
    return rules.normalize(get(conn, 'catalogue_rules', {}))


def prefilter_rules(conn):
    from engine.market import prefilter
    return prefilter.normalize(get(conn, 'prefilter', {}))


def mark_applied(conn, level, config):
    """Mémorise la configuration réellement appliquée par la dernière exécution (pour signaler « modifié, pas encore appliqué »)."""
    applied = get(conn, 'rules_applied', {})
    applied[level] = {'hash': digest(config), 'at': datetime.datetime.utcnow().replace(microsecond=0).isoformat(sep=' ')}
    put(conn, 'rules_applied', applied)
