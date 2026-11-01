#!/bin/bash
# Rejeu descriptif des six profils de Jigobourso (moteur de production) sur les mêmes dates et le même univers que Ridge. Lecture seule. Rapport : <out>/profils_valid.md
OUT="${1:?dossier}"
nice -n 10 python3 scripts/research_profiles.py "$HOME/tmp-history-long" --out "$OUT"
