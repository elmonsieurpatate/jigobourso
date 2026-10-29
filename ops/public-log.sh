#!/usr/bin/env bash
# Filtre un journal de déploiement avant publication (journal d'Actions et branche deployment-status, publics si le dépôt l'est).
# Garde les titres d'étapes et les verdicts ; retire tout ce qui décrit les données (nombres de transactions ou de lignes, tailles, noms de sauvegardes,
# versions logicielles, anomalies). Usage : ops/public-log.sh < journal > journal-public
set -euo pipefail
sed -E 's/^(Retour arrière terminé) : .*/\1/' \
  | grep -iE '^(== |site OK|Déploiement terminé|Retour arrière terminé|PHP valide|moteur importable|code restauré|.*(échec|erreur|refus|interdit|impossible|manquant)\b)' \
  | grep -viE 'transaction|portefeuille|anomalie|sauvegarde|\.sql|\.tgz|Mo\b|Go\b|python [0-9]|php [0-9]|mariadb|empreinte|/home/' \
  | cut -c1-160 | tail -n 60
exit 0
