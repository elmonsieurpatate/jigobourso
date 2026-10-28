#!/bin/bash
# Répétition générale de la bascule, sur une base jetable NEUVE (jigobourso_rehearsal) : rejoue les étapes 2 à 6 de docs/DEPLOIEMENT.md.
# Ne touche ni la production ni la base de développement. Lecture seule côté Yahoo. Usage : scripts/rehearsal.sh [dossier du clone FinanceDatabase, cloné au besoin]
set -uo pipefail
cd "$(dirname "$0")/.."
SRC="${1:-${TMPDIR:-/tmp}/jigo-rehearsal-fd}"
export JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=33307 JIGO_DB_NAME=jigobourso_rehearsal JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only
PY=.venv/bin/python; SQL="mariadb -h127.0.0.1 -P33307 -uroot -plocal-test-only"
step() { local t=$(date +%s) name="$1"; echo "── $name"; shift; "$@"; local rc=$?; echo "   code $rc en $(( $(date +%s) - t )) s"; [ $rc -eq 0 ] || FAILED="$FAILED | $name"; }
FAILED=""
$SQL -e 'DROP DATABASE IF EXISTS jigobourso_rehearsal; CREATE DATABASE jigobourso_rehearsal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci' || exit 1
step "2 schéma" bash -c "$SQL jigobourso_rehearsal < db/schema.sql"
[ -d "$SRC/database" ] || git clone --depth 1 -q https://github.com/JerBouma/FinanceDatabase.git "$SRC"
step "4a catalogue" $PY -m engine.cli catalogue --source "$SRC"
step "4b amorçage (quotes, préfiltre, clôtures)" $PY scripts/bootstrap_real.py
step "5 migration des comptes" $PY scripts/migrate_legacy.py migration/private/user_data.json
step "4c nightly" $PY -m engine.cli nightly
step "4d tick" $PY -m engine.cli tick
step "4e reconstitution du suivi (10 séances)" $PY -m engine.cli suivi-backfill --sessions 10
# mot de passe de test, base de répétition uniquement
HASH=$(php -r 'echo password_hash("rehearsal-only-123", PASSWORD_BCRYPT);')
$SQL jigobourso_rehearsal -e "UPDATE users SET pass_hash='$HASH' WHERE username='jigo'"
echo "── contrôles"
$SQL jigobourso_rehearsal -e "SELECT 'cotations' k, COUNT(*) n FROM listings UNION ALL SELECT 'sélectionnées', COUNT(*) FROM listings WHERE status='selected' UNION ALL SELECT 'clôtures', COUNT(*) FROM daily_prices UNION ALL SELECT 'barres 15 min', COUNT(*) FROM intraday_prices UNION ALL SELECT 'instantanés suivi', COUNT(*) FROM ranking_snapshots UNION ALL SELECT 'transactions', COUNT(*) FROM portfolio_transactions;
  SELECT job_type, status, LEFT(summary, 110) summary FROM jobs ORDER BY id DESC LIMIT 6;
  SELECT ROUND(SUM(data_length + index_length) / 1048576) AS base_mo FROM information_schema.tables WHERE table_schema='jigobourso_rehearsal';"
echo "── site (port 8091) puis parcours e2e"
setsid nohup php -S 127.0.0.1:8091 -t app/public > /dev/null 2>&1 &
sleep 2
BASE=http://127.0.0.1:8091 USER_NAME=jigo PASS=rehearsal-only-123 SHOTS="${SHOTS:-/tmp}" node tests/e2e/smoke.mjs; E2E=$?
pkill -f "php -S 127.0.0.1:8091" || true
echo "── bilan : étapes en échec :${FAILED:- aucune} ; e2e code $E2E"
