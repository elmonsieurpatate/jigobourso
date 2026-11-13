#!/usr/bin/env bash
# Point d'entrée unique des parcours navigateur de la CI (financial, strategies-ui, account-navigation) sur la base jetable jigobourso_it.
# Prérequis : `make db-reset`, playwright-core (PLAYWRIGHT_MODULE) et un Chromium (JIGO_CHROMIUM). Même enchaînement que .github/workflows/deploy.yml.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH" JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT="${JIGO_DB_PORT:-33307}" JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only
export JIGO_PYTHON="$(command -v python)" JIGO_ENGINE_ROOT="$PWD" PYTHONPATH="$PWD"
: "${PLAYWRIGHT_MODULE:?chemin de playwright-core}" "${JIGO_CHROMIUM:?chemin de Chromium}"
export JIGO_TEST_MAIL_DIR="${JIGO_TEST_MAIL_DIR:-$(mktemp -d)}"; chmod 700 "$JIGO_TEST_MAIL_DIR"
python tests/e2e/account_seed.py > /dev/null
php scripts/create_user.php review_user review-local-password --admin --email=review@example.test > /dev/null
php scripts/create_user.php plain_user plain-local-password --email=plain@example.test > /dev/null
python tests/e2e/etf_seed.py > /dev/null
php -S 127.0.0.1:18089 -t app/public > /dev/null 2>&1 & pid=$!
trap 'kill $pid 2>/dev/null' EXIT
for _ in $(seq 50); do curl -sf -o /dev/null http://127.0.0.1:18089/login.html && break; sleep .2; done
node tests/e2e/financial.cjs > /dev/null
timeout 240s node tests/e2e/strategies-ui.cjs > /dev/null      # avant account-navigation : celui-ci provoque des échecs de connexion volontaires
timeout 180s node tests/e2e/account-navigation.cjs > /dev/null
echo "e2e navigateur : OK"
