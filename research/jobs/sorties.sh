#!/bin/bash
# Règles de sortie (research/PROTOCOLE_SORTIES.md), lecture seule, en arrière-plan (pas de limite de durée du cron).
# Résumé copié dans un dossier non servi du site (réécriture vers v2/) pour le lire avec l'API Hostinger.
OUT="$1"; mkdir -p "$OUT/resultats"
LIRE="$HOME/domains/jigobourso.turnjoy.dev/public_html/.recherche-ml"; mkdir -p "$LIRE"
echo "commit $(basename "$PWD") · début $(date -u +%FT%TZ) · $(python3 --version 2>&1)" > "$LIRE/sorties-etat.txt"
nohup nice -n 10 bash -c "S=\$(date +%s); python3 scripts/research_exits.py --panel '$OUT/panel/panel.pkl.gz' --csv-dir '$HOME/tmp-history-long' --out '$OUT/resultats/sorties.md' --json '$OUT/resultats/sorties.json' > /dev/null 2> '$OUT/sorties.log'; echo \"code \$? · \$(( \$(date +%s) - S )) s\" >> '$LIRE/sorties-etat.txt'; tail -5 '$OUT/sorties.log' >> '$LIRE/sorties-etat.txt'; cp -f '$OUT/resultats/sorties.md' '$LIRE/' 2>/dev/null; echo FIN >> '$LIRE/sorties-etat.txt'" > /dev/null 2>&1 &
echo "lancé"
