#!/bin/bash
# Extension du diagnostic des ruptures de cours (hausses/baisses, CVaR, nature des ruptures, liste à vérifier, part retenue par année). Lecture seule. Rapport : <out>/diagnostic_ruptures.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_diagnostics2.py "$HOME/tmp-history-long" --out "$OUT"
