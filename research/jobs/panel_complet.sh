#!/bin/bash
# Panel complet (3000 titres), par lots de 100, reprenable. Lancé en arrière-plan : relancer la tâche reprend où le calcul s'est arrêté.
OUT="$1/panel"; mkdir -p "$OUT"
nohup nice -n 15 python3 scripts/research_panel.py build --csv-dir "$HOME/tmp-history-long" --out "$OUT" --batch 100 >> "$1/panel-build.log" 2>&1 &
echo "lancé (pid $!)"
