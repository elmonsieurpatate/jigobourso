#!/usr/bin/env bash
# Réconcilie le venv et requirements.txt, même si le manifeste n'a pas changé.
# La sauvegarde marquée reste disponible jusqu'à la réussite de toute la livraison.
set -euo pipefail
ROOT=${1:?racine du site}
BACKUPS=${2:?dossier de sauvegarde}
cd "$ROOT"
check_runtime() {
  local report status
  report=$(mktemp)
  status=0
  .venv/bin/python scripts/check_env.py > "$report" 2>&1 || status=$?
  if [ "$status" -ne 0 ]; then
    echo "Erreur contrôle environnement : code $status"
    # Aucun chemin, version, message d'exception ou paramètre privé publié.
    { grep -oE 'ÉCART (PyMySQL|numpy|pandas|exchange_calendars|engine.cli)' "$report" || true; } | sort -u | sed 's/^ÉCART /Erreur dépendance : /'
    { grep -oE '(ModuleNotFoundError|ImportError|NameError|TypeError|UnicodeEncodeError|PermissionError|SyntaxError):' "$report" || true; } | sort -u | sed 's/^/Erreur contrôle : /'
    if grep -q "can't open file" "$report"; then echo "Erreur contrôle : fichier inaccessible"; fi
  fi
  rm -f "$report"
  if [ "$status" -ge 128 ]; then
    echo "Erreur : contrôle interrompu, réinstallation non tentée" >&2
    exit "$status"
  fi
  return "$status"
}
want=$(sha256sum requirements.txt | cut -d' ' -f1)
have=$(cat .requirements.sha 2>/dev/null || true)
site=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
if [ "$have" = "$want" ] && check_runtime; then
  echo "dépendances Python inchangées"
elif [ -z "$have" ] && check_runtime; then
  .venv/bin/python -c "import pymysql" || { echo "dépendances Python inutilisables" >&2; exit 1; }
  printf '%s\n' "$want" > .requirements.sha; echo "dépendances Python existantes validées (première exécution)"
else
  if [ -n "${CODE_BACKUP:-}" ] && [ -f "$BACKUPS/$CODE_BACKUP.venv" ]; then
    backup=$(cat "$BACKUPS/$CODE_BACKUP.venv")
    test -f "$BACKUPS/$backup" || { echo "Erreur : environnement de retour arrière absent" >&2; exit 1; }
  else
    backup="site-packages-$(date -u +%Y%m%d%H%M%S).tgz"
    tar czf "$BACKUPS/$backup" -C "$site" . || { echo "sauvegarde du venv impossible : mise à jour refusée" >&2; exit 1; }
  fi
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
  check_runtime || { echo "Erreur : dépendances toujours non conformes après installation" >&2; exit 1; }
  printf '%s\n' "$want" > .requirements.sha; echo "dépendances Python mises à jour"
fi
