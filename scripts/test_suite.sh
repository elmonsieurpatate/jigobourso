#!/usr/bin/env bash
# Les tests sautés ne constituent pas une validation, sur PR comme sur main.
# Usage : scripts/test_suite.sh fast|integ [i/n]
#   i/n (integ seulement) : exécute le bloc i sur n. Chaque fichier de test est dans un seul bloc ; l'union des blocs est la suite complète (vérifié ici : un fichier oublié fait échouer).
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in fast|integ) suite=$1 ;; *) echo 'Usage: scripts/test_suite.sh fast|integ [i/n]' >&2; exit 2 ;; esac
targets=("tests/$suite")
if [ -n "${2:-}" ]; then
  [ "$suite" = integ ] || { echo 'Le découpage en blocs ne concerne que la suite integ' >&2; exit 2; }
  shard=${2%/*}; count=${2#*/}
  [[ "$shard" =~ ^[0-9]+$ && "$count" =~ ^[0-9]+$ && "$shard" -ge 1 && "$shard" -le "$count" ]] || { echo "Bloc invalide : $2 (attendu i/n)" >&2; exit 2; }
  mapfile -t targets < <(python scripts/integ_shards.py "$shard" "$count")
  [ "${#targets[@]}" -gt 0 ] || { echo "Bloc $2 vide" >&2; exit 2; }
fi
log=$(mktemp)
trap 'rm -f "$log"' EXIT
timeout 240s python -m pytest "${targets[@]}" -q --tb=line -rsfE | tee "$log"
if grep -qE '^SKIPPED|[0-9]+ skipped' "$log"; then
  echo "Échec : la suite $suite contient des tests sautés" >&2
  exit 1
fi
