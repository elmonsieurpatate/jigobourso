#!/bin/bash
# Inventaire étendu des historiques exportés (lecture seule, aucun entraînement). Rapport : <out>/inventaire_etendu.md
OUT="${1:?dossier}"
H="$HOME/tmp-history-long"
nice -n 10 python3 scripts/inventory_extended.py "$H" --db --out "$OUT/inventaire_etendu.md"
