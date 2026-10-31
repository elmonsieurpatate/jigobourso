#!/bin/bash
OUT="$1"; mkdir -p "$OUT/resultats"
( time python3 scripts/research_analyses.py risk --panel "$OUT/panel/panel.pkl.gz" --universe "$HOME/tmp-history-long/universe.csv" --out "$OUT/resultats" ) >> "$OUT/analyses.log" 2>&1
tail -6 "$OUT/analyses.log"; ls -la "$OUT/resultats" | tail -8
