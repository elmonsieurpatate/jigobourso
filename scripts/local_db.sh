#!/bin/bash
# MariaDB jetable pour les tests d'intégration : start | stop | reset | status.  Port 33306, base jigobourso_v2, jamais la production.
set -euo pipefail
DIR="${JIGO_LOCAL_DB_DIR:-/tmp/jigobourso-v2-localdb}"; PORT=33307; PASS=local-test-only
case "${1:-status}" in
  start)
    if mariadb -h127.0.0.1 -P$PORT -uroot -p$PASS -e 'SELECT 1' >/dev/null 2>&1; then echo "déjà démarré"; exit 0; fi
    rm -rf "$DIR"; mkdir -p "$DIR/data"
    mariadb-install-db --datadir="$DIR/data" --auth-root-authentication-method=normal --skip-test-db >/dev/null 2>&1
    nohup mariadbd --no-defaults --datadir="$DIR/data" --port=$PORT --bind-address=127.0.0.1 --socket="$DIR/sock" \
      --pid-file="$DIR/pid" --skip-name-resolve --innodb-buffer-pool-size=64M --innodb-flush-log-at-trx-commit=0 \
      --innodb-doublewrite=0 --skip-log-bin --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci \
      >"$DIR/log" 2>&1 &
    for _ in $(seq 1 60); do
      mariadb --socket="$DIR/sock" -uroot -e 'SELECT 1' >/dev/null 2>&1 && break; sleep 0.5
    done
    mariadb --socket="$DIR/sock" -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$PASS'; CREATE OR REPLACE USER 'root'@'127.0.0.1' IDENTIFIED VIA mysql_native_password USING PASSWORD('$PASS'); GRANT ALL ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; CREATE DATABASE IF NOT EXISTS jigobourso_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; FLUSH PRIVILEGES;"
    echo "MariaDB jetable prêt sur 127.0.0.1:$PORT";;
  stop)
    [ -f "$DIR/pid" ] && kill "$(cat "$DIR/pid")" 2>/dev/null || true
    for _ in $(seq 1 20); do [ -f "$DIR/pid" ] || break; sleep 0.5; done
    rm -rf "$DIR"; echo arrêté;;
  reset) mariadb -h127.0.0.1 -P$PORT -uroot -p$PASS -e 'DROP DATABASE IF EXISTS jigobourso_v2; CREATE DATABASE jigobourso_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'; echo "base remise à zéro";;
  status) mariadb -h127.0.0.1 -P$PORT -uroot -p$PASS -e 'SELECT VERSION()' 2>/dev/null || echo arrêté;;
esac
