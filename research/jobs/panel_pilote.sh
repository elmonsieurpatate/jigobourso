#!/bin/bash
# Pilote : 300 titres tirés au hasard, pour mesurer la durée avant le calcul complet.
OUT="$1/panel-pilote"; mkdir -p "$OUT"
( time python3 scripts/research_panel.py build --csv-dir "$HOME/tmp-history-long" --out "$OUT" --sample 300 --batch 100 ) > "$1/panel-pilote.log" 2>&1
tail -5 "$1/panel-pilote.log"
