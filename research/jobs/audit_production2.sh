#!/bin/bash
# Audit LECTURE SEULE n°2 : ruptures en production, exemples de critères, rotation réelle, actions sans cotation (+ sondage Yahoo de 60 symboles, rien n'est enregistré), « Hausse calme ». Rapport : <out>/audit_production2.md
OUT="${1:?dossier}"
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
PY="$SITE/.venv/bin/python"; [ -x "$PY" ] || PY=python3
set -a; . "$SITE/private/env"; set +a
nice -n 10 "$PY" scripts/audit_production2.py --probe 60 | tee "$OUT/audit_production2.md"
