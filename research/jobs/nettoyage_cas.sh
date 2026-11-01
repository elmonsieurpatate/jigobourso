#!/bin/bash
# Justification du nettoyage : cas concrets avant/après et matrice de transition v1 -> v2 (actions, lecture seule). Rapport : <out>/nettoyage_cas.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_cleaning_cases.py "$HOME/tmp-history-long" --out "$OUT/nettoyage_cas.md"
