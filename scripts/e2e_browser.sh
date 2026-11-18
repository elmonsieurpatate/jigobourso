#!/usr/bin/env bash
# Point d'entrée unique des parcours navigateur actifs de la CI sur la base jetable jigobourso_it.
# Prérequis : `make db-reset`, playwright-core (PLAYWRIGHT_MODULE) et un Chromium (JIGO_CHROMIUM). Même enchaînement que .github/workflows/ci.yml.
# Usage : scripts/e2e_browser.sh [core|pages|plan|portfolio|all]  (défaut : all, en série comme avant).
# Les quatre groupes sont indépendants (core et pages partagent les mêmes graines, créées par chacun sur sa base ; aucun ne dépend de l'état laissé par l'autre) : plan et portfolio repartent d'une base remise à zéro par leur propre graine (tests/dbutil.reset_data) et créent leurs utilisateurs ;
# la CI les lance donc en parallèle, chacun sur sa propre base jetable. `all` reste l'enchaînement historique.
set -euo pipefail
cd "$(dirname "$0")/.."
group=${1:-all}
case "$group" in core|pages|plan|portfolio|all) ;; *) echo 'Usage: scripts/e2e_browser.sh [core|pages|plan|portfolio|all]' >&2; exit 2 ;; esac
want() { [ "$group" = all ] || [ "$group" = "$1" ]; }
export PATH="$PWD/.venv/bin:$PATH" JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT="${JIGO_DB_PORT:-33307}" JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only
export JIGO_PYTHON="$(command -v python)" JIGO_ENGINE_ROOT="$PWD" PYTHONPATH="$PWD"
: "${PLAYWRIGHT_MODULE:?chemin de playwright-core}" "${JIGO_CHROMIUM:?chemin de Chromium}"
export JIGO_TEST_MAIL_DIR="${JIGO_TEST_MAIL_DIR:-$(mktemp -d)}"; install -d -m 700 "$JIGO_TEST_MAIL_DIR"
if want core || want pages; then
  python tests/seeds/account_seed.py > /dev/null
  php scripts/create_user.php review_user review-local-password --admin --email=review@example.test > /dev/null
  php scripts/create_user.php plain_user plain-local-password --email=plain@example.test > /dev/null
  python tests/seeds/etf_seed.py > /dev/null
fi
php -S 127.0.0.1:18089 -t app/public > /dev/null 2>&1 & pid=$!
out=${JIGO_E2E_RESULTS:-$(mktemp -d)}
mkdir -p "$out"
trap 'kill $pid 2>/dev/null' EXIT
for _ in $(seq 50); do curl -sf -o /dev/null http://127.0.0.1:18089/login.html && break; sleep .2; done
run() { local name=$1; shift; echo "Recette : $name"; "$@" > "$out/$name.log" 2>&1 || { echo "ÉCHEC $name :"; tail -c 1500 "$out/$name.log"; exit 1; }; }
if want core; then
run visual make visual
php scripts/create_user.php filters-owner personal-filters-local-only > /dev/null
php scripts/create_user.php filters-other personal-filters-local-only > /dev/null
php scripts/create_user.php filters-admin personal-filters-local-only --admin > /dev/null
export BASE=http://127.0.0.1:18089
run personal-filters timeout 120s node tests/e2e/personal-filters.cjs
run scores-preview timeout 120s node tests/e2e/scores-preview.cjs
run financial timeout 180s node tests/e2e/financial.cjs
fi
if want pages; then
export BASE=http://127.0.0.1:18089
run catalogue-search node tests/e2e/catalogue-search.cjs
run explorer-hidden-search node tests/e2e/explorer-hidden-search.cjs
run keyboard node tests/e2e/keyboard.cjs
run title-layout node tests/e2e/title-layout.cjs
run admin-title-history node tests/e2e/admin-title-history.cjs
run strategies-ui timeout 240s node tests/e2e/strategies-ui.cjs      # avant account-navigation : celui-ci provoque des échecs de connexion volontaires
run account-navigation timeout 180s node tests/e2e/account-navigation.cjs
fi
# Chaque groupe métier réinitialise explicitement la même base jetable, en série.
# BASE évite les ports historiques différents des scripts de recette.
export BASE=http://127.0.0.1:18089
if want plan; then
run plan-seed python tests/seeds/plan_suivi_seed.py
run plan-suivi timeout 240s node tests/e2e/plan-suivi.cjs
run split-seed python tests/seeds/split_review_seed.py
php scripts/create_user.php split-admin split-review-local-only --admin > /dev/null
php scripts/create_user.php split-user split-review-local-only > /dev/null
run split-reviews timeout 120s node tests/e2e/split-reviews.cjs
fi
if want portfolio; then
run portfolio-seed python tests/seeds/portfolio_audit_seed.py
run portfolio-v5 timeout 240s node tests/e2e/portfolio-v5.cjs
fi
echo "e2e navigateur ($group) : OK"
