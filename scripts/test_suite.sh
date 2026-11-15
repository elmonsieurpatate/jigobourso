#!/usr/bin/env bash
# Les tests sautés ne constituent pas une validation, sur PR comme sur main.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in fast|integ) suite=$1 ;; *) echo 'Usage: scripts/test_suite.sh fast|integ' >&2; exit 2 ;; esac
log=$(mktemp)
trap 'rm -f "$log"' EXIT
timeout 240s python -m pytest "tests/$suite" -q --tb=line -rsfE | tee "$log"
if grep -qE '^SKIPPED|[0-9]+ skipped' "$log"; then
  echo "Échec : la suite $suite contient des tests sautés" >&2
  exit 1
fi
