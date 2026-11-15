#!/usr/bin/env bash
# Réconcilie le venv et requirements.txt, même si le manifeste n'a pas changé.
# La sauvegarde marquée reste disponible jusqu'à la réussite de toute la livraison.
set -euo pipefail
ROOT=${1:?racine du site}
BACKUPS=${2:?dossier de sauvegarde}
cd "$ROOT"
want=$(sha256sum requirements.txt | cut -d' ' -f1)
have=$(cat .requirements.sha 2>/dev/null || true)
site=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
if [ "$have" = "$want" ] && .venv/bin/python scripts/check_env.py > /dev/null 2>&1; then
  echo "dépendances Python inchangées"
elif [ -z "$have" ] && .venv/bin/python scripts/check_env.py > /dev/null 2>&1; then
  .venv/bin/python -c "import pymysql" || { echo "dépendances Python inutilisables" >&2; exit 1; }
  printf '%s\n' "$want" > .requirements.sha; echo "dépendances Python existantes validées (première exécution)"
else
  backup="site-packages-$(date -u +%Y%m%d%H%M%S).tgz"
  tar czf "$BACKUPS/$backup" -C "$site" . || { echo "sauvegarde du venv impossible : mise à jour refusée" >&2; exit 1; }
  printf '%s\n' "$backup" > .deployment-venv-backup
  echo "sauvegarde du venv faite"
  ls -1t "$BACKUPS"/site-packages-*.tgz | tail -n +4 | xargs -r rm -f
  if .venv/bin/python -m pip --version > /dev/null 2>&1; then
    .venv/bin/python -m pip install --quiet --upgrade -r requirements.txt
  else
    # le venv de production n'a pas pip (ensurepip indisponible) : le pip du système installe dans le venv
    python3 -m pip install --quiet --upgrade --target "$site" -r requirements.txt
  fi
  .venv/bin/python -c "import pymysql" || { echo "dépendances Python inutilisables après mise à jour" >&2; exit 1; }
  .venv/bin/python scripts/check_env.py > /dev/null 2>&1 || { echo "Erreur : dépendances toujours non conformes après installation" >&2; exit 1; }
  printf '%s\n' "$want" > .requirements.sha; echo "dépendances Python mises à jour"
fi
