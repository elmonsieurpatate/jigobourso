#!/bin/bash
# Diagnostic du nettoyage des mouvements extrêmes (actions, lecture seule, aucun entraînement). Rapport : <out>/nettoyage.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_cleaning.py "$HOME/tmp-history-long" --out "$OUT/nettoyage.md"
