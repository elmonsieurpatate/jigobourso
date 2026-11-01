#!/bin/bash
# Audit LECTURE SEULE du moteur de production (entonnoir, verdicts, négociabilité, cohérence de l'Explorer, ruptures). Rapport : <out>/audit_production.md
OUT="${1:?dossier}"
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
PY="$SITE/.venv/bin/python"; [ -x "$PY" ] || PY=python3
set -a; . "$SITE/private/env"; set +a
nice -n 10 "$PY" scripts/audit_production.py | tee "$OUT/audit_production.md"
