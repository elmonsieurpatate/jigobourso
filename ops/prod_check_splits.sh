#!/bin/bash
# Vérification LECTURE SEULE après déploiement du correctif des ruptures/splits : version, migration, revérification, motifs affichés.
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
set -a; . "$SITE/private/env"; set +a
cd "$SITE" && cat .deployed 2>/dev/null | head -2
PYTHONPATH="$SITE" "$SITE/.venv/bin/python" - <<'PY' 2>&1 | grep -v "Warning\|align"
import collections, datetime
from engine.shared.db import connect
from engine.market import splits
from engine.analytics import service, strategy
c = connect()
with c.cursor() as cur:
    cur.execute('SET SESSION TRANSACTION READ ONLY')
    cur.execute("SELECT name FROM schema_migrations WHERE name LIKE '20261102%'"); print('migration enregistrée :', [r['name'] for r in cur.fetchall()])
    cur.execute("SHOW COLUMNS FROM split_log"); print('colonnes split_log :', [r['Field'] for r in cur.fetchall()][-3:])
    cur.execute("SELECT status, checks, COUNT(*) n FROM split_log GROUP BY status, checks ORDER BY status, checks"); print('split_log par statut et nombre de réponses :', [(r['status'], r['checks'], r['n']) for r in cur.fetchall()])
    cur.execute("SELECT COUNT(*) n FROM split_log WHERE recheck_after IS NOT NULL"); print('sauts avec revérification planifiée :', cur.fetchone()['n'])
print('revérification disponible dans le code déployé :', hasattr(splits, 'recheck'), '· colonnes présentes :', splits.has_recheck(c))
cnt = collections.Counter()
for name in ('momentum', 'momentum12'):
    for v in service.judge_universe(c, strategy.validate(strategy.preset(name))):
        for r in v['reasons']:
            if r['criterion'] == 'data' and r['result'] == 'missing':
                cnt[(name, r['metric'])] += 1
print('motifs de données manquantes (momentum / momentum12) :', dict(cnt))
bad = sum(1 for name in ('momentum', 'momentum12') for v in service.judge_universe(c, strategy.validate(strategy.preset(name)))
          if v['row']['quality'] == 'break' and v['row'].get('break_age') is not None and v['row']['break_age'] < (126 if name == 'momentum' else 252)
          and any(r['criterion'] == 'data' and r['metric'] == 'calendar' for r in v['reasons']))
print('titres en rupture encore expliqués par « calendar » :', bad)
PY
