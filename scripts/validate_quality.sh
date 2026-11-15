#!/usr/bin/env bash
# Même barrière de qualité sur PR et main ; aucun secret ni accès à la production.
set -euo pipefail
cd "$(dirname "$0")/.."
scripts/lint_php.sh
python scripts/migrate.py --check
python -m compileall -q engine scripts
for file in app/public/assets/*.js tests/e2e/*.cjs; do node --check "$file"; done
python -m ruff check .
python -m ruff format --check engine tests scripts
npx --no-install prettier --check 'app/public/assets/*.js' 'app/styles/**/*.css'
python scripts/build_styles.py --check
python scripts/check_halo_css.py
