#!/usr/bin/env bash
# Répétition LOCALE de ops/deploy.sh : le vrai script tourne contre un faux « serveur » (dossier temporaire + base jetable), ssh et rsync exécutés en local.
# Usage : scripts/rehearse_deploy.sh <scénario> [commit_en_place]
#   ok          déploiement normal (code en place = commit_en_place, défaut : parent de 25d9194, ancien emplacement des modules)
#   fail        échec forcé après transfert : le code doit être restauré
#   fail-deps   idem avec un requirements.txt modifié : code ET dépendances doivent être restaurés
#   diagnostic  lecture seule
# Prérequis : base jetable locale (scripts/local_db.sh start) contenant la base jigobourso_rehearsal (copie d'une base de développement), rsync, php, mariadb-dump.
# Ne touche ni la production ni la base de développement. Le dépôt n'est jamais modifié (le script tourne sur une copie des fichiers suivis).
set -euo pipefail
scenario=${1:?scénario}; inplace=${2:-25d9194^}
here=$(cd "$(dirname "$0")/.." && pwd)
R=${REHEARSAL_DIR:-/tmp/jigo-rehearsal}
DB=(-h127.0.0.1 -P33307 -uroot -plocal-test-only)
rm -rf "$R"; mkdir -p "$R"/{bin,home,tmp,repo,domain/jigobourso-v2/{private,logs,data}}
domain=$R/domain; root=$domain/jigobourso-v2
# 1. code en place (ancienne version) et venv propre
git -C "$here" archive "$inplace" app engine db docs scripts README.md requirements.txt | tar -x -C "$root"
python3 -m venv "$root/.venv" && "$root/.venv/bin/pip" install -q -r "$root/requirements.txt"
sha256sum "$root/requirements.txt" | cut -d' ' -f1 > "$root/.requirements.sha"
ln -s ../jigobourso-v2/app/public "$domain/public_html_v2"; mkdir -p "$domain/public_html"; ln -s ../jigobourso-v2/app/public "$domain/public_html/v2"
printf 'JIGO_DB_HOST=127.0.0.1\nJIGO_DB_PORT=33307\nJIGO_DB_NAME=jigobourso_rehearsal\nJIGO_DB_USER=root\nJIGO_DB_PASSWORD=local-test-only\nJIGO_PYTHON=%s\nJIGO_ENGINE_ROOT=%s\n' "$root/.venv/bin/python" "$root" > "$root/private/env"
echo rehearsal-key > "$root/private/cron.key"
# 2. ssh factice : exécute la commande en local (les options sont ignorées, l'entrée standard est transmise)
cat > "$R/bin/ssh" <<'SSH'
#!/usr/bin/env bash
while [ $# -gt 0 ]; do
  case "$1" in
    -O) exit 0 ;;
    -F|-p|-i|-o|-l) shift 2 ;;
    -*) shift ;;
    *) shift; break ;;                      # l'hôte
  esac
done
[ $# -gt 0 ] || exit 0
exec bash -c "$*"
SSH
chmod +x "$R/bin/ssh"
php8=$(command -v php8.3 || command -v php8.2 || command -v php8.4 || true); printf '#!/bin/sh\ncat > /dev/null\n' > "$R/bin/sendmail"; chmod +x "$R/bin/sendmail"      # le contrôle des comptes envoie un mail test : accepté sans rien envoyer
[ -n "$php8" ] && printf '#!/bin/sh\nexec %s -d sendmail_path="%s -t -i" "$@"\n' "$php8" "$R/bin/sendmail" > "$R/bin/php" && chmod +x "$R/bin/php"      # le serveur est en PHP 8.2 ; le php du PATH local peut être en 7.4
# 3. copie de travail du dépôt à déployer ; le scénario d'échec y est injecté
(cd "$here" && git ls-files -z | tar --null -T - -cf -) | tar -x -C "$R/repo"      # arbre de travail (fichiers suivis), modifications non commitées comprises
case "$scenario" in
  fail) echo "def broken(:" >> "$R/repo/engine/cli.py" ;;
  fail-deps) echo "def broken(:" >> "$R/repo/engine/cli.py"; printf 'six>=1.16,<2\n' >> "$R/repo/requirements.txt" ;;
  ok|diagnostic) ;;
  *) echo "scénario inconnu" >&2; exit 2 ;;
esac
# 4. exécution
export PATH="$R/bin:$PATH" HOME="$R/home" RUNNER_TEMP="$R/tmp" GITHUB_SHA=rehearsal$(date +%s)
mkdir -p "$RUNNER_TEMP/jigobourso-ssh"; : > "$RUNNER_TEMP/jigobourso-ssh/key"; : > "$RUNNER_TEMP/jigobourso-ssh/known_hosts"
export JIGO_DEPLOY_DOMAIN="$domain" JIGO_DEPLOY_SANDBOX=1 JIGO_DEPLOY_VALIDATION=${JIGO_DEPLOY_VALIDATION:-full}
cd "$R/repo"
op=deploy; [ "$scenario" = diagnostic ] && op=diagnostic
set +e; bash ops/deploy.sh "$op" 2>&1 | tee "$R/deploy.log"; rc=${PIPESTATUS[0]}; set -e
echo "== code retour du déploiement : $rc"
echo "== .deployed :"; cat "$root/.deployed" 2>/dev/null || echo absent
echo "== dépendances :"; "$root/.venv/bin/python" -m pip list 2>/dev/null | grep -i "^six " || echo "six absent"
exit "$rc"
