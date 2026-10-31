#!/bin/bash
# Résumé texte des résultats déjà produits (lecture seule).
R="$1/resultats"
tail -3 "$1/analyses.log"
for a in risk horizons candidates; do [ -f "$R/$a.json" ] && { echo; echo "######## $a"; python3 scripts/research_digest.py "$R" $a; }; done
