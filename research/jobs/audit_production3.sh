#!/bin/bash
# Audit LECTURE SEULE n°3 : ruptures de cours et circuit de vérification des splits. Rapport : <out>/audit_production3.md
OUT="${1:?dossier}"
SITE="$HOME/domains/jigobourso.turnjoy.dev/jigobourso-v2"
PY="$SITE/.venv/bin/python"; [ -x "$PY" ] || PY=python3
set -a; . "$SITE/private/env"; set +a
nice -n 10 "$PY" scripts/audit_production3.py | tee "$OUT/audit_production3.md"
