#!/usr/bin/env bash
# Empreinte du code qui PRODUIT les données dérivées (engine/, db/), exécutée depuis la racine du déploiement.
# Elle décide si un recalcul est nécessaire après une livraison (ops/deploy.sh). Les fichiers ci-dessous ne font qu'AFFICHER
# (lecture seule) : les exclure évite un recalcul pour une retouche d'affichage. Source unique : tests/fast/test_environment.py la contrôle.
# Envoyée aussi par l'entrée standard au serveur pour l'empreinte « avant » (l'ancien code n'a pas ce fichier) : aucune dépendance au dépôt.
cd "${1:-.}"
find engine db -type f ! -name '*.pyc' \
  ! -path engine/analytics/admin/service.py \
  ! -path engine/analytics/explorer/universe_verdicts.py \
  ! -path engine/analytics/admin/title_sheet.py \
  ! -path engine/analytics/market_views/market_facts.py \
  ! -path engine/analytics/series/signals.py \
  | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -c1-16
