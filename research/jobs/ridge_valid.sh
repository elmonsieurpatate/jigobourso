#!/bin/bash
# Expérience Ridge, mode valid (actions, lecture seule). Rapport : <out>/ridge_valid.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_ridge.py valid "$HOME/tmp-history-long" --out "$OUT"
