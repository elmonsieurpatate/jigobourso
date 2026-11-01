#!/bin/bash
# Complément de l'inventaire : (1) ajoute la colonne « category » à universe.csv de l'EXPORT de recherche (aucun appel Yahoo, base lue en lecture seule), (2) relance l'inventaire étendu avec le catalogue.
# Aucune écriture en base, rien dans le dossier du site. Le fichier d'environnement est seulement chargé en mémoire, jamais affiché.
OUT="${1:?dossier}"
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
H="$HOME/tmp-history-long"
PY="$SITE/.venv/bin/python"; [ -x "$PY" ] || PY=python3
set -a; . "$SITE/private/env"; set +a
nice -n 10 "$PY" scripts/export_history.py --out "$H" --update-universe
nice -n 10 "$PY" scripts/inventory_extended.py "$H" --db --out "$OUT/inventaire_etendu.md"
