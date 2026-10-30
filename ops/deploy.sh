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
  -o ConnectTimeout=20 -o ConnectionAttempts=3 -o HostKeyAlgorithms=ssh-ed25519
  -o ServerAliveInterval=15 -o ServerAliveCountMax=8
  # Une seule connexion SSH réutilisée par tous les appels (et rsync) : l'hébergement mutualisé refuse ou coupe les connexions répétées (code 255).
  -o ControlMaster=auto -o ControlPath="$RUNNER_TEMP/jcm-%C" -o ControlPersist=900)
remote=u381524662@147.79.103.168
# Paramètres de la production ; JIGO_DEPLOY_DOMAIN / JIGO_DEPLOY_BASE / JIGO_DEPLOY_SANDBOX ne servent qu'aux essais sur une copie isolée (sans site public).
domain=${JIGO_DEPLOY_DOMAIN:-/home/u381524662/domains/jigobourso.turnjoy.dev}
root=$domain/jigobourso-v2
backups=$domain/.jigobourso-v2-code-backups
base=${JIGO_DEPLOY_BASE:-https://jigobourso.turnjoy.dev}
sandbox=${JIGO_DEPLOY_SANDBOX:-}
remote_sh() { ssh "${ssh_opts[@]}" "$remote" "$@"; }
trap 'ssh "${ssh_opts[@]}" -O exit "$remote" > /dev/null 2>&1 || true' EXIT

public_check() {                                  # accueil servi avec la bonne version (si fournie), API qui répond
  local expect=${1:-} code me
  if [ -n "$sandbox" ]; then                      # essai isolé : pas de HTTP, la version est lue dans la page du dossier de test
    remote_sh "grep -q '?v=$expect' $root/app/public/index.html" || { echo "la page n'a pas la version attendue ($expect)" >&2; return 4; }
    echo "essai isolé : version ${expect:-?} présente dans la page"; return 0
  fi
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
# Lecture seule : identifiant de la version en place.
if [ -f "$ROOT/.deployed" ]; then
  sed -nE 's/^commit=([0-9a-f]{40})$/release commit=\1/p' "$ROOT/.deployed"
fi
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

# Preserve financial evidence before any code replacement. Never auto-rewrite legacy transactions.
echo "== Sauvegarde et empreinte des portefeuilles"
remote_sh "ROOT=$root BACKUPS=$backups bash -s" <<'REMOTE'
set -euo pipefail
cd "$ROOT"
set -a; . ./private/env; set +a
export MYSQL_PWD="$JIGO_DB_PASSWORD"
dbconn=(-u"$JIGO_DB_USER"); if [ -n "${JIGO_DB_SOCKET:-}" ]; then dbconn+=(--protocol=socket --socket="$JIGO_DB_SOCKET"); else dbconn+=(-h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}"); fi   # JIGO_DB_SOCKET : essais isolés uniquement
install -d -m 700 "$BACKUPS"
file="$BACKUPS/financial-$(date -u +%Y%m%d%H%M%S).sql.gz"
mariadb-dump "${dbconn[@]}" --single-transaction --quick "$JIGO_DB_NAME" portfolios portfolio_transactions position_levels | gzip > "$file"
chmod 600 "$file"
gzip -t "$file"
echo "Sauvegarde financière vérifiée : $(basename "$file")"
REMOTE
# Run the new SELECT-only checker against the old deployment to establish the baseline.
remote_sh "cd $root && set -a && . ./private/env && set +a && php" < <(sed "s@__DIR__ . '/../app/lib/db.php'@getcwd() . '/app/lib/db.php'@" scripts/check_financial_integrity.php) > "$RUNNER_TEMP/financial-before.json"
remote_sh "cd $root && set -a && . ./private/env && set +a && php" < scripts/verify_account_release.php > "$RUNNER_TEMP/account-before.json"

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
  phase="transfert du code"
  trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo "Échec déploiement : étape ${phase} (code ${rc})" >&2; fi' EXIT
  echo "== Transfert du code"
  rsync -rlt --delete --exclude=__pycache__ --exclude=.venv --exclude=private --exclude=data --exclude=logs \
    -e "ssh ${ssh_opts[*]}" \
    app engine db docs scripts README.md requirements.txt "$remote:$root/"

  phase="dépendances Python et migration du schéma"
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
dbconn=(-u"$JIGO_DB_USER"); if [ -n "${JIGO_DB_SOCKET:-}" ]; then dbconn+=(--protocol=socket --socket="$JIGO_DB_SOCKET"); else dbconn+=(-h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}"); fi   # JIGO_DB_SOCKET : essais isolés uniquement
# tables : créées seulement si absentes (aucune existante n'est modifiée) ; vues : redéfinies (aucune donnée)
sed -E 's/^CREATE TABLE ([a-z_]+)/CREATE TABLE IF NOT EXISTS \1/; s/^CREATE VIEW /CREATE OR REPLACE VIEW /' db/schema.sql \
  | mariadb "${dbconn[@]}" "$JIGO_DB_NAME"
echo "schéma de base appliqué (tables manquantes créées, vues redéfinies)"
todo=$(.venv/bin/python scripts/migrate.py --pending)
if [ -n "$todo" ]; then
  echo "migrations en attente : $(echo "$todo" | tr '\n' ' ')"
  dump="$BACKUPS/db-$(date -u +%Y%m%d%H%M%S).sql.gz"
  mariadb-dump "${dbconn[@]}" --single-transaction --quick "$JIGO_DB_NAME" | gzip > "$dump"
  gzip -t "$dump" && echo "sauvegarde de la base : $(basename "$dump") ($(du -h "$dump" | cut -f1))"
  chmod 600 "$dump"
  ls -1t "$BACKUPS"/db-*.sql.gz | tail -n +4 | xargs -r rm -f
  .venv/bin/python scripts/migrate.py --apply
else
  echo "aucune migration en attente"
fi
.venv/bin/python -c "import engine.cli" && echo "moteur importable"
# Le déploiement ne recalcule rien : il demande seulement à la maintenance (cron, moins de 5 minutes) de recalculer les données dérivées avec le nouveau code.
.venv/bin/python -c "from engine.shared import settings; from engine.shared.db import connect; c = connect(); settings.put(c, 'maintenance_pending', 'deploy'); c.commit()"
echo "recalcul des données dérivées demandé à la maintenance (aucun calcul pendant le déploiement)"
echo "== Contrôle d'intégrité financière"
php scripts/check_financial_integrity.php > "$ROOT/logs/financial-integrity.json"
chmod 600 "$ROOT/logs/financial-integrity.json"

find app scripts -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null && echo "PHP valide"
REMOTE

  phase="vérification des calculs financiers"
  echo "== Vérification des calculs financiers avec les calendriers de séance"
  remote_sh "cd $root && set -a && . ./private/env && set +a && PYTHONPATH=$root .venv/bin/python scripts/verify_financial_release.py"

  phase="vérification ETF, comptes et intégrité financière"
  echo "== Vérification ETF"
  remote_sh "cd $root && set -a && . ./private/env && set +a && PYTHONPATH=$root .venv/bin/python scripts/verify_etf_release.py" > "$RUNNER_TEMP/etf-report.json"
  echo "== Vérification des comptes et des transactions"
  remote_sh "cd $root && set -a && . ./private/env && set +a && php scripts/check_financial_integrity.php" > "$RUNNER_TEMP/financial-after.json"
  remote_sh "cd $root && set -a && . ./private/env && set +a && JIGO_ACCOUNT_POSTCHECK=1 php scripts/verify_account_release.php" > "$RUNNER_TEMP/account-after.json"
  python3 - <<'ACCOUNTVERIFY'
import json,os
from pathlib import Path
base=Path(os.environ['RUNNER_TEMP'])
a=json.loads((base/'account-before.json').read_text());b=json.loads((base/'account-after.json').read_text())
assert a['users_fingerprint']==b['users_fingerprint'], 'Les comptes existants ont changé pendant la livraison'
print('Comptes et hachages conservés ; contrôle du module de messagerie :',b['mail_transport'])
ACCOUNTVERIFY

  python3 - <<'PYVERIFY'
import json, os
from pathlib import Path
base=Path(os.environ['RUNNER_TEMP'])
before=json.loads((base/'financial-before.json').read_text())
after=json.loads((base/'financial-after.json').read_text())
assert before['fingerprint']==after['fingerprint'], 'Les transactions ont changé pendant la livraison : vérification manuelle requise'
assert before['portfolios']==after['portfolios'], 'Le nombre de portefeuilles a changé'
print('Intégrité : portefeuilles et transactions strictement conservés ;',after['transactions'],'transactions ; anomalies historiques non réécrites :',after['issues'])
PYVERIFY
  phase="vérification publique"
  echo "== Vérification publique"
  public_check "$version"
  if [ -z "$sandbox" ]; then
    for page in login.html recover.html reset.html verify-email.html; do
      test "$(curl -s -o /dev/null -w '%{http_code}' "$base/$page")" = 200 || exit 4
    done
    echo "Pages de connexion, récupération et confirmation : HTTP 200"
  fi
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
