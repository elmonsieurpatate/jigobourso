#!/bin/bash
# Expérience Ridge, mode final (actions, lecture seule). Rapport : <out>/ridge_final.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_ridge.py final "$HOME/tmp-history-long" --out "$OUT"
