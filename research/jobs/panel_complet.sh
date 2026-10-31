#!/bin/bash
# Panel complet (3000 titres), lots de 100, reprenable ; puis fusion. Synchrone (quelques minutes).
OUT="$1/panel"; mkdir -p "$OUT"
python3 scripts/research_panel.py build --csv-dir "$HOME/tmp-history-long" --out "$OUT" --batch 100 >> "$1/panel-build.log" 2>&1
python3 scripts/research_panel.py merge --out "$OUT" >> "$1/panel-build.log" 2>&1
tail -4 "$1/panel-build.log"; ls -la "$OUT" | tail -4
