"""Copie `saved_searches` et `saved_presets` vers `explorer_saved` (kind='search'), à lancer UNE fois en production avant de supprimer les deux anciennes tables.

  python scripts/oneshot/migrate_saved_to_explorer.py            simulation (rien n'est écrit)
  python scripts/oneshot/migrate_saved_to_explorer.py --go       copie (idempotent : une ligne déjà présente sous le même nom est laissée telle quelle)

Ensuite, à la main et avec sauvegarde : DROP TABLE saved_presets, saved_searches (les migrations de db/migrations/ n'ont pas le droit de supprimer).
Connexion : variables JIGO_DB_* (comme le moteur).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from engine.shared.db import connect  # noqa: E402


def payload(config, view):
    return json.dumps({'schema': 4, 'config': json.loads(config) if isinstance(config, (str, bytes)) else config,
                       'universe': (json.loads(view) if isinstance(view, (str, bytes)) else view) or {}}, ensure_ascii=False)


def main(go):
    conn = connect()
    added = skipped = 0
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT user_id, name, config, view, created_at, updated_at FROM saved_searches')
            items = [(r['user_id'], r['name'], payload(r['config'], r['view']), r['created_at'], r['updated_at']) for r in cur.fetchall()]
            cur.execute('SELECT user_id, preset, config, view, updated_at FROM saved_presets')
            items += [(r['user_id'], f"{r['preset']} (réglage personnel)"[:80], payload(r['config'], r['view']), r['updated_at'], r['updated_at']) for r in cur.fetchall()]
            for uid, name, body, created, updated in items:
                cur.execute("SELECT 1 FROM explorer_saved WHERE user_id=%s AND kind='search' AND name=%s", (uid, name))
                if cur.fetchone():
                    skipped += 1
                    continue
                added += 1
                if go:
                    cur.execute("INSERT INTO explorer_saved(user_id, kind, name, payload, active, created_at, updated_at) VALUES (%s,'search',%s,%s,1,%s,%s)", (uid, name, body, created, updated))
        if go:
            conn.commit()
    finally:
        conn.close()
    print(f"{'copiées' if go else 'à copier'} : {added} ; déjà présentes : {skipped}" + ('' if go else ' (simulation, relancer avec --go)'))


if __name__ == '__main__':
    main('--go' in sys.argv)
