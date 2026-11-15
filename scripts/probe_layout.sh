#!/usr/bin/env bash
# Lance la sonde de mise en page sur la base jetable jigobourso_it (jamais la base locale ni la production). Arguments passés à probe_layout.cjs.
# Prérequis : `make db-reset`, PLAYWRIGHT_MODULE et JIGO_CHROMIUM.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH" JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT="${JIGO_DB_PORT:-33307}" JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only
export JIGO_PYTHON="$(command -v python)" JIGO_ENGINE_ROOT="$PWD" PYTHONPATH="$PWD"
: "${PLAYWRIGHT_MODULE:?}" "${JIGO_CHROMIUM:?}"
export JIGO_TEST_MAIL_DIR="$(mktemp -d)"; chmod 700 "$JIGO_TEST_MAIL_DIR"
python tests/seeds/account_seed.py > /dev/null
php scripts/create_user.php review_user review-local-password --admin --email=review@example.test > /dev/null
python tests/seeds/etf_seed.py > /dev/null
php -S 127.0.0.1:18089 -t app/public > /dev/null 2>&1 & pid=$!
trap 'kill $pid 2>/dev/null' EXIT
for _ in $(seq 50); do curl -sf -o /dev/null http://127.0.0.1:18089/login.html && break; sleep .2; done
USER_NAME=review_user PASS=review-local-password node "${PROBE:-scripts/probe_layout.cjs}" "$@"
