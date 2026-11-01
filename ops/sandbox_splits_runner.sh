#!/bin/bash
# Lance l'essai isolé du correctif des splits (scripts/sandbox_splits.sh) sur l'hébergement, EN ARRIÈRE-PLAN, pour un commit donné et l'ancien commit de référence.
#   bash sandbox_splits_runner.sh <commit_a_tester> <commit_de_reference> <etiquette>      lance l'essai UNE seule fois par étiquette (téléchargement des deux copies du code dans ~/tmp-backtest/splits-test)
#   bash sandbox_splits_runner.sh <commit_a_tester> lecture <lignes> <etiquette>           affiche la fin du journal
# Le mot de passe de la base d'essai est lu dans ~/tmp-backtest/.sandbox_pw (créé à part, jamais dans le dépôt). La production n'est que LUE.
set -u
SHA="${1:?commit}"; BASE="$HOME/tmp-backtest/splits-test"; DIR="$BASE/$SHA"
mkdir -p "$BASE"
if [ "${2:-}" = "lecture" ]; then tail -n "${3:-80}" "$BASE/$SHA-${4:-r1}.log" 2>/dev/null; exit 0; fi
REF="${2:?commit de référence}"; REFDIR="$BASE/ref-$REF"; LOG="$BASE/$SHA-${3:-r1}.log"
[ -e "$LOG" ] && { echo "déjà lancé (étiquette ${3:-r1}) : $LOG"; exit 0; }
pgrep -f "scripts/sandbox_splits.sh" > /dev/null && { echo "un essai est déjà en cours"; exit 0; }
for pair in "$SHA:$DIR" "$REF:$REFDIR"; do
  s="${pair%%:*}"; d="${pair#*:}"; mkdir -p "$d"
  [ -f "$d/.ok" ] || { curl -fsSL "https://codeload.github.com/elmonsieurpatate/jigobourso/tar.gz/$s" | tar -xz --strip-components=1 -C "$d" && touch "$d/.ok"; } || { echo "téléchargement impossible ($s)"; exit 1; }
done
PROD="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
(
  set -a; . "$PROD/private/env"; set +a
  export JIGO_SOURCE_NAME="$JIGO_DB_NAME" JIGO_SOURCE_USER="$JIGO_DB_USER" JIGO_SOURCE_PASSWORD="$JIGO_DB_PASSWORD"
  export JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=3306 JIGO_DB_NAME=u381524662_sandbox JIGO_DB_USER=u381524662_sandbox JIGO_DB_PASSWORD="$(cat "$HOME/tmp-backtest/.sandbox_pw")"
  export JIGO_PY="$PROD/.venv/bin/python" SANDBOX_BASE_DIR="$REFDIR"
  cd "$DIR" && nohup bash scripts/sandbox_splits.sh > "$LOG" 2>&1 &
)
echo "essai lancé pour $SHA contre $REF (journal : $LOG)"
