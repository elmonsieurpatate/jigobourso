#!/bin/bash
# Contrôles et calculs APRÈS un déploiement, sur l'hébergement (appelé par une tâche planifiée temporaire).
#   verif    : contrôles en LECTURE SEULE du site public et du moteur en production (aucune écriture).
#   calcul   : recalcul des indicateurs (engine.cli metrics, tâche nocturne habituelle) puis reconstitution du suivi (INSERT IGNORE : n'écrase aucun instantané), en arrière-plan, priorité basse.
#   lecture  : fin du journal du calcul.
set -u
MODE="${1:?verif|calcul|lecture}"
PROD="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"; LOG="$HOME/tmp-backtest/prod-post-deploy.log"; B=https://jigobourso.turnjoy.dev
mkdir -p "$HOME/tmp-backtest"
case "$MODE" in
  verif)
    echo "déployé : $(tr '\n' ' ' < "$PROD/.deployed" | cut -c1-160)"
    page=$(curl -s "$B/"); echo "accueil : $(printf '%s' "$page" | grep -o 'explorer.js?v=[0-9]*' | head -1) · $(curl -s -o /dev/null -w '%{http_code}' "$B/")"
    for f in explorer titre suivi portefeuilles; do echo "$f.js : $(curl -s "$B/assets/$f.js" | grep -c 'momentum12') occurrence(s) de momentum12"; done
    echo "api/auth/me : $(curl -s -o /dev/null -w '%{http_code}' "$B/api/auth/me") (401 attendu sans connexion)"
    for p in login.html recover.html; do echo "$p : $(curl -s -o /dev/null -w '%{http_code}' "$B/$p")"; done
    ( cd "$PROD" && set -a && . ./private/env && set +a && export JIGO_ENGINE_ROOT="$PROD" JIGO_PYTHON="$PROD/.venv/bin/python" PYTHONPATH="$PROD" \
      && echo "── pont PHP → moteur" && php scripts/verify_php_bridge.php && echo "── valeurs et classements" && "$PROD/.venv/bin/python" scripts/verify_momentum_release.py ) 2>&1 | grep -Ev 'FutureWarning|align:'
    ;;
  calcul)
    pgrep -f "engine.cli metrics" > /dev/null && { echo "un calcul est déjà en cours"; exit 0; }
    ( cd "$PROD" && set -a && . ./private/env && set +a && export PYTHONPATH="$PROD" \
      && nohup nice -n 15 bash -c "date -u +%T; $PROD/.venv/bin/python -m engine.cli metrics; date -u +%T; $PROD/.venv/bin/python -m engine.cli suivi-backfill --sessions 75; date -u +%T; echo FIN" > "$LOG" 2>&1 & )
    echo "calcul lancé (journal : $LOG)"
    ;;
  lecture) grep -Ev 'FutureWarning|align:' "$LOG" | tail -n "${2:-20}" | cut -c1-200; pgrep -fa "engine.cli" | head -3 | cut -c1-120 ;;
esac
