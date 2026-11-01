#!/bin/bash
# Essai ISOLÉ du correctif « motifs des ruptures de cours + revérification bornée des splits » sur l'hébergement, AVANT toute mise en production.
# Isolation : copie du code dans un dossier à part ; base SÉPARÉE (le nom doit contenir « sandbox » ou « test », refus sinon) remplie par une COPIE (mariadb-dump --single-transaction) de la production,
# qui n'est que LUE. Seule la base d'essai est modifiée (migration, revérifications). Les tables financières de la production sont vérifiées par somme de contrôle avant et après.
# Réseau : au plus RECHECK_LIMIT (30) requêtes de lecture vers Yahoo (events.splits), pour observer le vrai comportement de la revérification ; rien n'est écrit chez Yahoo ni en production.
# Variables : JIGO_DB_* (base d'essai) ; JIGO_SOURCE_NAME/USER/PASSWORD (production, lecture) ; JIGO_PY ; SANDBOX_BASE_DIR (copie de l'ancien code, pour comparer).
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${JIGO_PY:-python3}"
fail=""; ok=""
step() { local name="$1"; shift; echo "── $name"; if "$@"; then ok="$ok | $name"; else fail="$fail | $name"; fi; }
for v in JIGO_DB_HOST JIGO_DB_NAME JIGO_DB_USER JIGO_DB_PASSWORD JIGO_SOURCE_NAME SANDBOX_BASE_DIR; do [ -n "${!v:-}" ] || { echo "Variable $v manquante."; exit 2; }; done
case "$JIGO_DB_NAME" in *sandbox*|*test*) ;; *) echo "REFUS : la base « $JIGO_DB_NAME » ne contient ni « sandbox » ni « test »."; exit 2;; esac
[ "$JIGO_SOURCE_NAME" != "$JIGO_DB_NAME" ] || { echo "REFUS : source et destination identiques."; exit 2; }
case "$PWD" in */public_html*|*/jigobourso-v2) echo "REFUS : lancez ce script depuis la copie, pas depuis le dossier du site ($PWD)."; exit 2;; esac
export JIGO_DB_PORT="${JIGO_DB_PORT:-3306}" PYTHONPATH="$PWD" JIGO_ENV_FILE=/nonexistent
SQL() { MYSQL_PWD="$JIGO_DB_PASSWORD" mariadb -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"$JIGO_DB_USER" "$JIGO_DB_NAME" "$@"; }
SRC() { MYSQL_PWD="${JIGO_SOURCE_PASSWORD:-$JIGO_DB_PASSWORD}" mariadb -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"${JIGO_SOURCE_USER:-$JIGO_DB_USER}" "$JIGO_SOURCE_NAME" "$@"; }
FIN="portfolios portfolio_transactions users corporate_events split_log position_levels"
echo "Copie testée : $PWD · base d'essai : $JIGO_DB_NAME · ancien code : $SANDBOX_BASE_DIR · python : $PY · $($PY --version 2>&1)"

# ── 0. somme de contrôle des tables financières de la production, AVANT
before=$(SRC -N -e "CHECKSUM TABLE ${FIN// /, }" | tr '\t' ' ' | tr '\n' ';')
echo "production (avant) : $before"
nsplit=$(SRC -N -e 'SELECT COUNT(*) FROM split_log'); nreal=$(SRC -N -e "SELECT COUNT(*) FROM split_log WHERE status='real_move'"); echo "production : split_log $nsplit lignes dont real_move $nreal"

# ── 1. copie de la production dans la base d'essai (la base d'essai est vidée avant : son nom a été contrôlé)
echo "── 1. copie de la production (lecture seule) vers la base d'essai"
tables=$(SQL -N -e 'SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE()') || { echo "Connexion à la base d'essai impossible."; exit 2; }
if [ -n "$tables" ]; then { echo 'SET FOREIGN_KEY_CHECKS=0;'; for t in $tables; do echo "DROP TABLE IF EXISTS \`$t\`;"; done; } | SQL; fi
MYSQL_PWD="${JIGO_SOURCE_PASSWORD:-$JIGO_DB_PASSWORD}" mariadb-dump -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"${JIGO_SOURCE_USER:-$JIGO_DB_USER}" --single-transaction --quick --skip-lock-tables "$JIGO_SOURCE_NAME" \
  | sed -E 's/DEFINER=`[^`]*`@`[^`]*`//g' | SQL && ok="$ok | 1 copie" || { fail="$fail | 1 copie"; echo "Copie impossible : arrêt."; exit 1; }
echo "copie : $(SQL -N -e 'SELECT COUNT(*) FROM listings') cotations, split_log $(SQL -N -e 'SELECT COUNT(*) FROM split_log') lignes"

# ── 2. migration sur la copie (chemin réel de mise à niveau)
before_rows=$(SQL -N -e 'SELECT COUNT(*) FROM split_log')
step "2a. migrations en attente" $PY scripts/migrate.py --pending
step "2b. application" $PY scripts/migrate.py --apply
after_rows=$(SQL -N -e 'SELECT COUNT(*) FROM split_log')
step "2c. colonnes checks et recheck_after présentes, aucune ligne perdue ($before_rows -> $after_rows)" bash -c "[ '$before_rows' = '$after_rows' ] && [ \"\$(MYSQL_PWD='$JIGO_DB_PASSWORD' mariadb -h'$JIGO_DB_HOST' -P'$JIGO_DB_PORT' -u'$JIGO_DB_USER' '$JIGO_DB_NAME' -N -e \"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='split_log' AND column_name IN ('checks','recheck_after')\")\" = 2 ]"
step "2d. relancer la migration ne fait rien" bash -c "$PY scripts/migrate.py --pending | grep -c . | grep -qx 0"

# ── 3. motifs et verdicts : ancien code contre nouveau code, sur les données réelles copiées
export SANDBOX_NOW="$(date -u +%Y-%m-%dT%H:%M:%S)"
OLD=/tmp/sandbox_old_verdicts.json; NEW=/tmp/sandbox_new_verdicts.json
step "3a. verdicts avec l'ANCIEN code" bash -c "cd '$SANDBOX_BASE_DIR' && PYTHONPATH='$SANDBOX_BASE_DIR' $PY '$PWD/scripts/sandbox_splits_dump.py' $OLD"
step "3b. verdicts avec le NOUVEAU code" $PY scripts/sandbox_splits_dump.py $NEW
step "3c. seuls les motifs « calendar » des ruptures changent (aucun statut, rang, score ni critère)" $PY scripts/sandbox_splits_compare.py $OLD $NEW

# ── 4. revérification bornée avec le vrai Yahoo (lecture), sur la copie
cat > /tmp/sandbox_recheck.py <<'PYEOF'
import datetime
from engine.market import splits
from engine.market.yahoo import YahooClient
from engine.shared.db import connect
conn = connect()
now = datetime.datetime.utcnow()
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) n FROM split_log WHERE status='real_move' AND event_date >= %s", (now.date() - datetime.timedelta(days=splits.RECHECK_WINDOW_DAYS),))
    due = cur.fetchone()['n']
print('sauts real_move de moins de', splits.RECHECK_WINDOW_DAYS, 'jours :', due)
client = YahooClient()
calls = []
real = client.splits
client.splits = lambda s, *a, **k: (calls.append(s), real(s, *a, **k))[1]
r1 = splits.recheck(conn, client, now)
print('1er passage :', r1, '· requêtes Yahoo :', len(calls))
assert len(calls) <= splits.RECHECK_LIMIT, 'plus de requêtes que la limite'
n1 = len(calls)
r2 = splits.recheck(conn, client, now)
print('2e passage immédiat :', r2, '· requêtes supplémentaires :', len(calls) - n1)
with conn.cursor() as cur:
    cur.execute("SELECT s.listing_id, l.symbol, s.event_date, s.status, s.checks, s.recheck_after FROM split_log s JOIN listings l ON l.id=s.listing_id WHERE s.status='confirmed' AND s.checks > 1")
    late = cur.fetchall()
    cur.execute("SELECT checks, COUNT(*) n FROM split_log WHERE status='real_move' GROUP BY checks")
    dist = cur.fetchall()
print('confirmés tardivement :', [(x['symbol'], str(x['event_date'])) for x in late])
print('real_move par nombre de réponses :', {x['checks']: x['n'] for x in dist})
PYEOF
step "4. revérification (limite 30 requêtes, 2e passage sans requête)" $PY /tmp/sandbox_recheck.py

# ── 5. le site lui-même (PHP, pont vers le moteur)
step "5a. syntaxe PHP" bash -c "find app -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null"
step "5b. pont PHP vers le moteur (Explorer, fiche, Suivi, profils)" bash -c "JIGO_ENGINE_ROOT='$PWD' JIGO_PYTHON='$PY' php scripts/verify_php_bridge.php"

# ── 6. la production n'a pas bougé
after=$(SRC -N -e "CHECKSUM TABLE ${FIN// /, }" | tr '\t' ' ' | tr '\n' ';')
echo "production (après)  : $after"
step "6. tables financières de la PRODUCTION inchangées (somme de contrôle avant = après)" bash -c "[ '$before' = '$after' ]"
echo; echo "══ BILAN"; echo "réussi :${ok:- aucun}"; echo "échec  :${fail:- aucun}"
echo "Base d'essai : $JIGO_DB_NAME. La production n'a pas été modifiée ; rien n'a été poussé sur la branche principale ni déployé."
[ -z "$fail" ]
