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
domain=/home/u381524662/domains/jigobourso.turnjoy.dev
root=$domain/jigobourso-v2
backups=$domain/.jigobourso-v2-code-backups
base=https://jigobourso.turnjoy.dev
remote_sh() { ssh "${ssh_opts[@]}" "$remote" "$@"; }
trap 'ssh "${ssh_opts[@]}" -O exit "$remote" > /dev/null 2>&1 || true' EXIT

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
# Read only: expose a release identifier and only the exception class from a
# failed detached metrics job. Never print the private job log (it can contain
# identifiers and query details).
if [ -f "$ROOT/.deployed" ]; then
  sed -nE 's/^commit=([0-9a-f]{40})$/release commit=\1/p' "$ROOT/.deployed"
fi
log=$(ls -1t "$ROOT"/logs/deploy-metrics-*.log 2>/dev/null | head -1 || true)
if [ -n "$log" ]; then
  error_line=$(grep -E '^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception)(:|$)' "$log" | tail -1 || true)
  error=$(sed -nE 's/^([A-Za-z_][A-Za-z0-9_.]*(Error|Exception))(:.*)?$/\1/p' <<< "$error_line")
  db_code=$(sed -nE 's/^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception): \(([0-9]+),.*/\2/p' <<< "$error_line")
  [ -z "$error" ] || echo "dernier recalcul en échec : type $error${db_code:+, code MariaDB $db_code}"
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
install -d -m 700 "$BACKUPS"
file="$BACKUPS/financial-$(date -u +%Y%m%d%H%M%S).sql.gz"
mariadb-dump -h"$JIGO_DB_HOST" -P"${JIGO_DB_PORT:-3306}" -u"$JIGO_DB_USER" --single-transaction --quick "$JIGO_DB_NAME" portfolios portfolio_transactions position_levels | gzip > "$file"
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

  phase="dépendances Python, migration du schéma et recalcul"
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
# Détacher le recalcul des données dérivées : certaines commandes SSH mutualisées
# interrompent les traitements longs. Le runner attend le code de sortie avant la suite.
token="$SHA-$VERSION"
metrics_log="$ROOT/logs/deploy-metrics-$token.log"
metrics_exit="$ROOT/logs/deploy-metrics-$token.exit"
metrics_pid="$ROOT/logs/deploy-metrics-$token.pid"
rm -f "$metrics_exit" "$metrics_exit.tmp" "$metrics_pid"
# Shared-host SSH servers may terminate every child in the session once the
# channel closes. nohup alone ignores SIGHUP but keeps the SSH session/process
# group; setsid gives this bounded maintenance job its own session as well.
if command -v setsid >/dev/null 2>&1; then
  # --wait keeps the PID we record alive until the detached child exits;
  # without it setsid may fork and the poller mistakes the parent exit for a
  # lost worker before the child has written its status file.
  nohup setsid --wait bash -c 'set +e; cd "$1"; .venv/bin/python -m engine.cli metrics; rc=$?; printf "%s\n" "$rc" > "$2.tmp"; mv "$2.tmp" "$2"; exit 0' _ "$ROOT" "$metrics_exit" > "$metrics_log" 2>&1 < /dev/null &
else
  nohup bash -c 'set +e; cd "$1"; .venv/bin/python -m engine.cli metrics; rc=$?; printf "%s\n" "$rc" > "$2.tmp"; mv "$2.tmp" "$2"; exit 0' _ "$ROOT" "$metrics_exit" > "$metrics_log" 2>&1 < /dev/null &
fi
printf '%s\n' "$!" > "$metrics_pid"
echo "Recalcul analytique lancé en tâche détachée"
echo "== Contrôle d'intégrité financière"
php scripts/check_financial_integrity.php > "$ROOT/logs/financial-integrity.json"
chmod 600 "$ROOT/logs/financial-integrity.json"

find app scripts -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null && echo "PHP valide"
REMOTE

  phase="recalcul analytique sur les historiques existants"
  echo "== Attente du recalcul des mesures et classements"
  metrics_state=""; ssh_errors=0
  for attempt in $(seq 1 120); do
    metrics_state=$(remote_sh "ROOT=$root TOKEN=$sha-$version bash -s" <<'REMOTE' || echo ssh_error
set -euo pipefail
status="$ROOT/logs/deploy-metrics-$TOKEN.exit"
pidfile="$ROOT/logs/deploy-metrics-$TOKEN.pid"
if [ -f "$status" ]; then
  rc=$(cat "$status")
  if [ "$rc" = 0 ]; then
    rm -f "$status" "$pidfile" "$ROOT/logs/deploy-metrics-$TOKEN.log"
    echo done
  else
    echo "failed:$rc"
  fi
elif [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
  echo running
else
  echo missing
fi
REMOTE
)
    case "$metrics_state" in
      done) echo "== Recalcul analytique terminé"; break ;;
      running) sleep 10 ;;
      ssh_error) ssh_errors=$((ssh_errors + 1)); [ "$ssh_errors" -le 10 ] || { echo "Échec de la liaison SSH pendant l'attente du recalcul" >&2; exit 1; }; sleep 15 ;;
      failed:*)
        error_type=$(remote_sh "ROOT=$root TOKEN=$sha-$version bash -s" <<'REMOTE'
set -euo pipefail
log="$ROOT/logs/deploy-metrics-$TOKEN.log"
line=$(grep -E '^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception)(:|$)' "$log" 2>/dev/null | tail -1 || true)
error=$(sed -nE 's/^([A-Za-z_][A-Za-z0-9_.]*(Error|Exception))(:.*)?$/\1/p' <<< "$line")
db_code=$(sed -nE 's/^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception): \(([0-9]+),.*/\2/p' <<< "$line")
printf '%s%s' "$error" "${db_code:+ errno=$db_code}"
REMOTE
)
        echo "Échec du recalcul analytique (code de retour $metrics_state${error_type:+, erreur $error_type})" >&2
        exit 1 ;;
      *) echo "Échec du recalcul analytique (processus terminé sans code de sortie)" >&2; exit 1 ;;
    esac
  done
  if [ "$metrics_state" != done ]; then echo "Échec du recalcul analytique (délai dépassé)" >&2; exit 1; fi

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
  for page in login.html recover.html reset.html verify-email.html; do
    test "$(curl -s -o /dev/null -w '%{http_code}' "$base/$page")" = 200 || exit 4
  done
  echo "Pages de connexion, récupération et confirmation : HTTP 200"
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
