#!/usr/bin/env bash
# Déploiement Jigobourso V2 sur Hostinger (appelé par .github/workflows/deploy.yml, jamais par un humain en prod).
# Garanties : seuls app/ engine/ db/ docs/ scripts/ README.md requirements.txt sont transmis ; private/ data/ logs/ .venv
# (base, clés, cron, portefeuilles) ne sont ni listés, ni écrasés, ni supprimés. Le schéma SQL n'est appliqué que s'il est purement additif.
set -euo pipefail
cd "$(dirname "$0")/.."
operation=${1:-diagnostic}
case "$operation" in diagnostic|deploy) ;; *) exit 2 ;; esac
sha=${GITHUB_SHA:-local}
version=$(date -u +%Y%m%d%H%M)
ssh_opts=(-F /dev/null -p 65002 -i "$RUNNER_TEMP/jigobourso-ssh/key"
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$RUNNER_TEMP/jigobourso-ssh/known_hosts"
  -o ConnectTimeout=20 -o ConnectionAttempts=3 -o HostKeyAlgorithms=ssh-ed25519)
remote=u381524662@147.79.103.168
domain=/home/u381524662/domains/jigobourso.turnjoy.dev
root=$domain/jigobourso-v2

echo "== Contrôles du serveur (lecture seule)"
ssh "${ssh_opts[@]}" "$remote" "ROOT=$root DOMAIN=$domain bash -s" <<'REMOTE'
set -euo pipefail
test "$(realpath -e "$ROOT")" = "$ROOT"
test -f "$ROOT/private/env" && test -f "$ROOT/private/cron.key" && echo "private/ présent (non lu)"
test -x "$ROOT/.venv/bin/python" && "$ROOT/.venv/bin/python" --version
test "$(readlink "$DOMAIN/public_html/v2")" = "../jigobourso-v2/app/public" && echo "public_html/v2 -> app/public OK"
php --version | head -1
command -v rsync > /dev/null && echo "rsync OK"
df -h "$DOMAIN" | tail -1
REMOTE
if [ "$operation" = diagnostic ]; then echo "Diagnostic terminé : rien modifié."; exit 0; fi

echo "== Contrôle du schéma : additif seulement"
if grep -qiE '^\s*(drop|truncate|delete|alter|rename|update|insert|replace)\b' db/schema.sql; then
  echo "db/schema.sql contient une instruction non additive : déploiement refusé, migration à faire à part avec sauvegarde" >&2
  exit 3
fi

echo "== Version des pages : ?v=$version"
sed -i -E "s/(assets\/[a-z0-9_.-]+\.(js|css))\?v=[0-9]+/\1?v=$version/g" app/public/*.html

echo "== Sauvegarde du code distant (garde les 5 dernières)"
ssh "${ssh_opts[@]}" "$remote" "ROOT=$root DOMAIN=$domain SHA=$sha bash -s" <<'REMOTE'
set -euo pipefail
dir=$DOMAIN/.jigobourso-v2-code-backups
install -d -m 700 "$dir"
cd "$DOMAIN"
tar czf "$dir/code-$(date -u +%Y%m%d%H%M%S)-${SHA:0:8}.tgz" --exclude=.venv --exclude=data --exclude=logs --exclude=private jigobourso-v2
ls -1t "$dir"/code-*.tgz | tail -n +6 | xargs -r rm -f
ls -1t "$dir"/code-*.tgz | head -1
REMOTE

echo "== Transfert du code"
rsync -rlt --delete --exclude=__pycache__ --exclude=.venv --exclude=private --exclude=data --exclude=logs \
  -e "ssh ${ssh_opts[*]}" \
  app engine db docs scripts README.md requirements.txt "$remote:$root/"

echo "== Dépendances, schéma additif, contrôles"
ssh "${ssh_opts[@]}" "$remote" "ROOT=$root SHA=$sha VERSION=$version bash -s" <<'REMOTE'
set -euo pipefail
cd "$ROOT"
want=$(sha256sum requirements.txt | cut -d' ' -f1)
have=$(cat .requirements.sha 2>/dev/null || true)
if [ "$have" = "$want" ]; then
  echo "dépendances Python inchangées"
elif [ -z "$have" ]; then
  # première exécution : le venv a été installé à la main (sans pip) ; on vérifie seulement que le nécessaire s'importe
  .venv/bin/python -c "import pymysql" && printf '%s\n' "$want" > .requirements.sha && echo "dépendances Python existantes validées"
elif .venv/bin/python -m pip --version > /dev/null 2>&1; then
  .venv/bin/python -m pip install --quiet -r requirements.txt && printf '%s\n' "$want" > .requirements.sha && echo "dépendances Python mises à jour"
else
  echo "requirements.txt a changé mais le venv n'a pas pip : installation manuelle nécessaire" >&2; exit 5
fi
set -a; . ./private/env; set +a
export MYSQL_PWD="$JIGO_DB_PASSWORD"
# tables : créées seulement si absentes (aucune existante n'est modifiée) ; vues : redéfinies (aucune donnée)
sed -E 's/^CREATE TABLE ([a-z_]+)/CREATE TABLE IF NOT EXISTS \1/; s/^CREATE VIEW /CREATE OR REPLACE VIEW /' db/schema.sql \
  | mariadb -h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}" -u"$JIGO_DB_USER" "$JIGO_DB_NAME"
echo "schéma additif appliqué (tables manquantes créées, vues redéfinies)"
.venv/bin/python -c "import engine.cli" && echo "moteur importable"
find app scripts -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null && echo "PHP valide"
printf 'commit=%s\nversion=%s\ndate=%s\n' "$SHA" "$VERSION" "$(date -u +%FT%TZ)" > .deployed
REMOTE

echo "== Vérification publique"
base=https://jigobourso.turnjoy.dev
code=$(curl -s -o "$RUNNER_TEMP/index.html" -w '%{http_code}' "$base/")
test "$code" = 200 || { echo "page d'accueil : HTTP $code" >&2; exit 4; }
grep -q "?v=$version" "$RUNNER_TEMP/index.html" || { echo "la page servie n'a pas la version déployée ($version)" >&2; exit 4; }
me=$(curl -s -o /dev/null -w '%{http_code}' "$base/api/auth/me")
case "$me" in 200|401) ;; *) echo "api/auth/me : HTTP $me" >&2; exit 4 ;; esac
echo "site OK : accueil 200, version $version servie, API répond ($me)"
echo "Déploiement terminé : $sha"
