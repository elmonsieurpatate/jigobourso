#!/bin/bash
# Lance l'essai isolé (scripts/sandbox_hostinger.sh) sur l'hébergement, pour un commit donné de GitHub, EN ARRIÈRE-PLAN. Appelé par une tâche planifiée temporaire.
#   bash sandbox_runner.sh <commit> [lecture]    sans « lecture » : télécharge le commit dans ~/tmp-backtest/momentum-test/<commit> et lance l'essai ; avec « lecture » : affiche la fin du journal.
# Le mot de passe de la base d'essai est lu dans ~/tmp-backtest/.sandbox_pw (créé à part, jamais dans le dépôt). La base de production n'est que LUE (copie).
set -u
SHA="${1:?commit}"; BASE="$HOME/tmp-backtest/momentum-test"; DIR="$BASE/$SHA"; LOG="$BASE/$SHA.log"
mkdir -p "$BASE"
if [ "${2:-}" = "lecture" ]; then tail -n "${3:-60}" "$LOG" 2>/dev/null; pgrep -fa sandbox_hostinger | head -2; exit 0; fi
if [ "${2:-}" != "pont" ] && pgrep -f "sandbox_hostinger.sh" > /dev/null; then echo "un essai est déjà en cours"; exit 0; fi
mkdir -p "$DIR"
[ -f "$DIR/.ok" ] || { curl -fsSL "https://codeload.github.com/elmonsieurpatate/jigobourso/tar.gz/$SHA" | tar -xz --strip-components=1 -C "$DIR" && touch "$DIR/.ok"; } || { echo "téléchargement impossible"; exit 1; }
PROD="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
(
  set -a; . "$PROD/private/env"; set +a
  export JIGO_SOURCE_NAME="$JIGO_DB_NAME" JIGO_SOURCE_USER="$JIGO_DB_USER" JIGO_SOURCE_PASSWORD="$JIGO_DB_PASSWORD"
  export JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=3306 JIGO_DB_NAME=u381524662_sandbox JIGO_DB_USER=u381524662_sandbox JIGO_DB_PASSWORD="$(cat "$HOME/tmp-backtest/.sandbox_pw")"
  export JIGO_PY="$PROD/.venv/bin/python"
  [ "${2:-}" = "pont" ] && export JIGO_ONLY_BRIDGE=1
  cd "$DIR" && nohup bash scripts/sandbox_hostinger.sh > "$LOG" 2>&1 &
)
echo "essai lancé pour $SHA (journal : $LOG)"
