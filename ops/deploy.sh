#!/usr/bin/env bash
# Déploiement Jigobourso V2 sur Hostinger (appelé par .github/workflows/deploy.yml).
#   diagnostic : contrôles en lecture seule
#   deploy     : sauvegarde du code, transfert, dépendances, migrations additives, contrôles ; ÉCHEC = retour arrière automatique du code
#   rollback   : restaure la dernière sauvegarde du code (ou ROLLBACK_BACKUP=<fichier>)
# Garanties : seuls app/ engine/ db/ docs/ scripts/ README.md requirements.txt sont transmis ; private/ data/ logs/ .venv (base, clés, cron, portefeuilles)
# ne sont ni listés, ni écrasés, ni supprimés. Aucune migration destructive : voir db/migrations/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."
operation=${1:-diagnostic}
case "$operation" in diagnostic|deploy|rollback) ;; *) exit 2 ;; esac
sha=${GITHUB_SHA:-local}
version=$(date -u +%Y%m%d%H%M)
ssh_opts=(-F /dev/null -p 65002 -i "$RUNNER_TEMP/jigobourso-ssh/key"
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$RUNNER_TEMP/jigobourso-ssh/known_hosts"
  -o ConnectTimeout=20 -o ConnectionAttempts=3 -o HostKeyAlgorithms=ssh-ed25519)
remote=u381524662@147.79.103.168
domain=/home/u381524662/domains/jigobourso.turnjoy.dev
root=$domain/jigobourso-v2
backups=$domain/.jigobourso-v2-code-backups
base=https://jigobourso.turnjoy.dev
remote_sh() { ssh "${ssh_opts[@]}" "$remote" "$@"; }

public_check() {                                  # accueil servi avec la bonne version (si fournie), API qui répond
  local expect=${1:-} code me
  code=$(curl -s -o "$RUNNER_TEMP/index.html" -w '%{http_code}' "$base/")
  test "$code" = 200 || { echo "page d'accueil : HTTP $code" >&2; return 4; }
  if [ -n "$expect" ]; then grep -q "?v=$expect" "$RUNNER_TEMP/index.html" || { echo "la page servie n'a pas la version attendue ($expect)" >&2; return 4; }; fi
  me=$(curl -s -o /dev/null -w '%{http_code}' "$base/api/auth/me")
  case "$me" in 200|401) ;; *) echo "api/auth/me : HTTP $me" >&2; return 4 ;; esac
  echo "site OK : accueil 200${expect:+, version $expect servie}, API répond ($me)"
}

restore_code() {                                  # restaure le code depuis une sauvegarde (nom de fichier dans $backups) ; données et secrets intouchés
  remote_sh "ROOT=$root BACKUPS=$backups FILE=$1 bash -s" <<'REMOTE'
set -euo pipefail
test -f "$BACKUPS/$FILE"
tmp=$(mktemp -d "$BACKUPS/restore.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
tar xzf "$BACKUPS/$FILE" -C "$tmp"
cd "$tmp/jigobourso-v2"
rsync -rlt --delete --exclude=__pycache__ app engine db docs scripts README.md requirements.txt "$ROOT/"
"$ROOT/.venv/bin/python" -c "import sys; sys.path.insert(0, '$ROOT'); import engine.cli" && echo "moteur importable après restauration"
echo "code restauré depuis $FILE"
REMOTE
}

echo "== Contrôles du serveur (lecture seule)"
remote_sh "ROOT=$root DOMAIN=$domain bash -s" <<'REMOTE'
set -euo pipefail
test "$(realpath -e "$ROOT")" = "$ROOT"
test -f "$ROOT/private/env" && test -f "$ROOT/private/cron.key" && echo "private/ présent (non lu)"
test -x "$ROOT/.venv/bin/python" && "$ROOT/.venv/bin/python" --version
test "$(readlink "$DOMAIN/public_html/v2")" = "../jigobourso-v2/app/public" && echo "public_html/v2 -> app/public OK"
php --version | head -1
command -v rsync mariadb-dump > /dev/null && echo "rsync et mariadb-dump OK"
df -h "$DOMAIN" | tail -1
REMOTE

if [ "$operation" = diagnostic ]; then echo "Diagnostic terminé : rien modifié."; exit 0; fi

if [ "$operation" = rollback ]; then
  file=${ROLLBACK_BACKUP:-$(remote_sh "ls -1t $backups/code-*.tgz | head -1 | xargs -n1 basename")}
  echo "== Retour arrière du code vers $file"
  restore_code "$file"
  public_check
  echo "Retour arrière terminé : $file"
  exit 0
fi

echo "== Contrôle des fichiers SQL : ajouts seulement"
if grep -qiE '^\s*(drop|truncate|delete|alter|rename|update|insert|replace)\b' db/schema.sql; then
  echo "db/schema.sql contient une instruction non additive : déploiement refusé" >&2; exit 3
fi
python3 scripts/migrate.py --check

echo "== Version des pages : ?v=$version"
sed -i -E "s/(assets\/[a-z0-9_.-]+\.(js|css))\?v=[0-9]+/\1?v=$version/g" app/public/*.html

echo "== Sauvegarde du code distant (garde les 5 dernières)"
backup=$(remote_sh "ROOT=$root DOMAIN=$domain BACKUPS=$backups SHA=$sha bash -s" <<'REMOTE'
set -euo pipefail
install -d -m 700 "$BACKUPS"
cd "$DOMAIN"
name="code-$(date -u +%Y%m%d%H%M%S)-${SHA:0:8}.tgz"
tar czf "$BACKUPS/$name" --exclude=.venv --exclude=data --exclude=logs --exclude=private jigobourso-v2
tar tzf "$BACKUPS/$name" > /dev/null
ls -1t "$BACKUPS"/code-*.tgz | tail -n +6 | xargs -r rm -f
echo "$name"
REMOTE
)
echo "sauvegarde : $backup"

set +e
(
  set -euo pipefail
  echo "== Transfert du code"
  rsync -rlt --delete --exclude=__pycache__ --exclude=.venv --exclude=private --exclude=data --exclude=logs \
    -e "ssh ${ssh_opts[*]}" \
    app engine db docs scripts README.md requirements.txt "$remote:$root/"

  echo "== Dépendances Python, migrations de schéma, contrôles"
  remote_sh "ROOT=$root BACKUPS=$backups SHA=$sha VERSION=$version bash -s" <<'REMOTE'
set -euo pipefail
cd "$ROOT"
want=$(sha256sum requirements.txt | cut -d' ' -f1)
have=$(cat .requirements.sha 2>/dev/null || true)
site=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
if [ "$have" = "$want" ]; then
  echo "dépendances Python inchangées"
elif [ -z "$have" ]; then
  .venv/bin/python -c "import pymysql" && printf '%s\n' "$want" > .requirements.sha && echo "dépendances Python existantes validées (première exécution)"
else
  tar czf "$BACKUPS/site-packages-$(date -u +%Y%m%d%H%M%S).tgz" -C "$site" . && echo "sauvegarde du venv faite"
  ls -1t "$BACKUPS"/site-packages-*.tgz | tail -n +4 | xargs -r rm -f
  if .venv/bin/python -m pip --version > /dev/null 2>&1; then
    .venv/bin/python -m pip install --quiet --upgrade -r requirements.txt
  else
    # le venv de production n'a pas pip (ensurepip indisponible) : le pip du système installe dans le venv
    python3 -m pip install --quiet --upgrade --target "$site" -r requirements.txt
  fi
  .venv/bin/python -c "import pymysql" && printf '%s\n' "$want" > .requirements.sha && echo "dépendances Python mises à jour"
fi
set -a; . ./private/env; set +a
export MYSQL_PWD="$JIGO_DB_PASSWORD" PYTHONPATH="$ROOT"
# tables : créées seulement si absentes (aucune existante n'est modifiée) ; vues : redéfinies (aucune donnée)
sed -E 's/^CREATE TABLE ([a-z_]+)/CREATE TABLE IF NOT EXISTS \1/; s/^CREATE VIEW /CREATE OR REPLACE VIEW /' db/schema.sql \
  | mariadb -h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}" -u"$JIGO_DB_USER" "$JIGO_DB_NAME"
echo "schéma de base appliqué (tables manquantes créées, vues redéfinies)"
todo=$(.venv/bin/python scripts/migrate.py --pending)
if [ -n "$todo" ]; then
  echo "migrations en attente : $(echo "$todo" | tr '\n' ' ')"
  dump="$BACKUPS/db-$(date -u +%Y%m%d%H%M%S).sql.gz"
  mariadb-dump -h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}" -u"$JIGO_DB_USER" --single-transaction --quick "$JIGO_DB_NAME" | gzip > "$dump"
  gzip -t "$dump" && echo "sauvegarde de la base : $(basename "$dump") ($(du -h "$dump" | cut -f1))"
  chmod 600 "$dump"
  ls -1t "$BACKUPS"/db-*.sql.gz | tail -n +4 | xargs -r rm -f
  .venv/bin/python scripts/migrate.py --apply
else
  echo "aucune migration en attente"
fi
.venv/bin/python -c "import engine.cli" && echo "moteur importable"
find app scripts -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null && echo "PHP valide"
REMOTE

  echo "== Vérification publique"
  public_check "$version"
)
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  echo "ÉCHEC du déploiement (code $rc) : retour arrière automatique du code vers $backup" >&2
  restore_code "$backup" || { echo "RETOUR ARRIÈRE ÉCHOUÉ : restaurer à la main $backup (opération rollback du workflow)" >&2; exit 5; }
  public_check || true
  echo "Code restauré ; les données et la base n'ont pas été touchées (les migrations déjà appliquées sont additives)." >&2
  exit "$rc"
fi

remote_sh "ROOT=$root SHA=$sha VERSION=$version bash -s" <<'REMOTE'
printf 'commit=%s\nversion=%s\ndate=%s\n' "$SHA" "$VERSION" "$(date -u +%FT%TZ)" > "$ROOT/.deployed"
REMOTE
echo "Déploiement terminé : $sha"
