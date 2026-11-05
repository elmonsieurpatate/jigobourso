#!/usr/bin/env bash
# Entirely disposable MariaDB, Unix socket only. Never uses the configured application DB.
set -euo pipefail
cd "$(dirname "$0")/.."
secondary_run=$(mktemp -d "${TMPDIR:-/tmp}/jigo-secondary-tests.XXXXXX")
secondary_db_pid=''
secondary_web_pid=''
cleanup_secondary() {
  if [ -n "$secondary_web_pid" ]; then
    for secondary_child in $(pgrep -P "$secondary_web_pid" || true); do kill "$secondary_child" 2>/dev/null || true; done
    kill "$secondary_web_pid" 2>/dev/null || true
  fi
  if [ -n "$secondary_db_pid" ]; then kill "$secondary_db_pid" 2>/dev/null || true; fi
}
trap cleanup_secondary EXIT
mkdir "$secondary_run/db"
mariadb-install-db --no-defaults --datadir="$secondary_run/db" --auth-root-authentication-method=normal --skip-test-db >"$secondary_run/install.log" 2>&1
mariadbd --no-defaults --datadir="$secondary_run/db" --socket="$secondary_run/db.sock" --skip-networking --pid-file="$secondary_run/db.pid" --innodb-buffer-pool-size=64M --skip-log-bin >"$secondary_run/mariadb.log" 2>&1 &
secondary_db_pid=$!
for _ in $(seq 1 100); do
  if mariadb --no-defaults --socket="$secondary_run/db.sock" -uroot -e 'SELECT 1' >/dev/null 2>&1; then break; fi
  sleep .1
done
mariadb --no-defaults --socket="$secondary_run/db.sock" -uroot -e "CREATE DATABASE jigobourso_filters_it CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; ALTER USER 'root'@'localhost' IDENTIFIED BY 'filters-local-only';"
export JIGO_DB_SOCKET="$secondary_run/db.sock" JIGO_DB_HOST=127.0.0.1 JIGO_DB_NAME=jigobourso_filters_it JIGO_DB_USER=root JIGO_DB_PASSWORD=filters-local-only JIGO_TEST_DATABASE=1 JIGO_ENV_FILE=/dev/null JIGO_PYTHON=/no-financial-engine
MYSQL_PWD=filters-local-only mariadb --no-defaults --socket="$secondary_run/db.sock" -uroot jigobourso_filters_it < db/schema.sql
php tests/e2e/secondary-persistence.php seed
php tests/e2e/secondary-persistence.php | tee "$secondary_run/php-results.txt"
php tests/e2e/secondary-metadata-persistence.php | tee "$secondary_run/metadata-results.txt"
secondary_port=$(python3 - <<'PY'
import socket
with socket.socket() as server:
    server.bind(('127.0.0.1',0))
    print(server.getsockname()[1])
PY
)
PHP_CLI_SERVER_WORKERS=4 php -S "127.0.0.1:$secondary_port" -t app/public >"$secondary_run/php-server.log" 2>&1 &
secondary_web_pid=$!
for _ in $(seq 1 50); do
  if curl --noproxy '*' -fsS "http://127.0.0.1:$secondary_port/login.html" >/dev/null 2>&1; then break; fi
  sleep .1
done
BASE="http://127.0.0.1:$secondary_port" AUDIT_OUT="$secondary_run/browser" node tests/e2e/secondary-persistence-browser.cjs | tee "$secondary_run/browser-results.txt"
BASE="http://127.0.0.1:$secondary_port" AUDIT_OUT="$secondary_run/mobile" node tests/e2e/classement-test-mobile.cjs
printf 'Rapports et captures de validation : %s\n' "$secondary_run"
