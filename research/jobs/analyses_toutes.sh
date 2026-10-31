#!/bin/bash
# Les six analyses l'une après l'autre, en arrière-plan (pas de limite de 30 min du cron). Journal : out/analyses.log ; résultats : out/resultats/*.json|md.
OUT="$1"; mkdir -p "$OUT/resultats"
nohup nice -n 10 bash -c "for a in risk horizons candidates deciles ic rank; do echo \"== \$a \$(date +%T)\" >> \"$OUT/analyses.log\"; python3 scripts/research_analyses.py \$a --panel \"$OUT/panel/panel.pkl.gz\" --universe \"$HOME/tmp-history-long/universe.csv\" --out \"$OUT/resultats\" >> \"$OUT/analyses.log\" 2>&1; done; echo FIN >> \"$OUT/analyses.log\"" > /dev/null 2>&1 &
echo "lancé"
