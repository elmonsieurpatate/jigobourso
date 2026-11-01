#!/bin/bash
# Score appris (research/PROTOCOLE_APPRENTISSAGE.md), lecture seule sur le panel. Résultats : out/resultats/apprentissage.{md,json},
# copie du résumé dans un dossier non servi du site (la réécriture vers v2/ le rend inaccessible par le web) pour le lire avec l'API Hostinger.
OUT="$1"; mkdir -p "$OUT/resultats"
LIRE="$HOME/domains/jigobourso.turnjoy.dev/public_html/.recherche-ml"; mkdir -p "$LIRE"
PANEL="$OUT/panel/panel.pkl.gz"
{ echo "commit $(basename "$PWD") · $(date -u +%FT%TZ) · $(python3 --version 2>&1)"; ls -la "$PANEL" 2>&1; } > "$LIRE/etat.txt"
[ -f "$PANEL" ] || { echo "panel absent : $PANEL" >> "$LIRE/etat.txt"; exit 1; }
START=$(date +%s)
python3 scripts/research_ml.py --panel "$PANEL" --out "$OUT/resultats/apprentissage.md" --json "$OUT/resultats/apprentissage.json" > /dev/null 2> "$OUT/apprentissage.log"
echo "code $? · $(( $(date +%s) - START )) s" >> "$LIRE/etat.txt"; tail -5 "$OUT/apprentissage.log" >> "$LIRE/etat.txt"
cp -f "$OUT/resultats/apprentissage.md" "$LIRE/" 2>/dev/null; echo FIN >> "$LIRE/etat.txt"
