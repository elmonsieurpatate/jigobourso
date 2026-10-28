"""Reprise des données utilisateur de l'ancien Jigobourso vers la base V2 cible (variables JIGO_DB_*).
    python scripts/migrate_legacy.py migration/private/user_data.json
Lit un export déjà fait en lecture seule (scripts/export_user_data.py). N'écrit que dans la base V2 désignée ; refuse si elle contient déjà des comptes."""
import json, sys
sys.path.insert(0, '.')
from engine.shared.db import connect
from engine.migration.legacy import migrate, verify

data = json.load(open(sys.argv[1]))
conn = connect()
report = migrate(conn, data)
problems = verify(conn, data)
print(json.dumps(report, ensure_ascii=False, indent=1))
print('CONTRÔLE :', 'conforme à l’export' if not problems else problems)
sys.exit(1 if problems else 0)
