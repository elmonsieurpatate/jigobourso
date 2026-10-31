#!/bin/bash
# État d'avancement : fin du journal et fichiers produits.
tail -4 "$1/panel-build.log" 2>/dev/null; ls "$1/panel" 2>/dev/null | tail -3; ls "$1/panel" 2>/dev/null | wc -l; pgrep -fa research_ | head -3; du -sh "$1" | tail -1
