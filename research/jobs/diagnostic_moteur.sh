#!/bin/bash
# Diagnostic descriptif du moteur sur l'historique : ruptures de cours, rotation des profils filtrants, négociabilité. Lecture seule. Rapport : <out>/diagnostic_moteur.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_diagnostics.py "$HOME/tmp-history-long" --out "$OUT"
