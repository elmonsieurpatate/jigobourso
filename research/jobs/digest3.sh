#!/bin/bash
# État de l'analyse « rank » et résumé si elle est terminée (lecture seule).
R="$1/resultats"
echo "--- fin du journal"; tail -6 "$1/analyses.log"
echo "--- fichiers"; ls -la "$R"
echo "--- processus"; pgrep -fa research_analyses | head -2
[ -f "$R/rank.json" ] && { echo; echo "######## rank"; python3 scripts/research_digest.py "$R" rank; }
