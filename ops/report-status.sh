#!/usr/bin/env bash
set -euo pipefail
# Compte rendu minimal (statut, commit, lien du run, fin du journal) sur la branche existante deployment-status.
# Aucun secret, aucune donnée de portefeuille : le journal ne contient que les messages de ops/deploy.sh.
report_dir=$(mktemp -d)
git init -q "$report_dir"
cd "$report_dir"
git config user.name github-actions[bot]
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git remote add origin "https://github.com/$GITHUB_REPOSITORY.git"
auth=$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=http.https://github.com/.extraheader
export GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $auth"
if git fetch -q origin deployment-status; then
  git checkout -q -b deployment-status FETCH_HEAD
else
  git checkout -q --orphan deployment-status
fi
git rm -rq --ignore-unmatch . >/dev/null 2>&1 || true
python3 - <<'PY'
import json, os
from pathlib import Path
Path('status.json').write_text(json.dumps({
 'app': 'jigobourso-v2', 'status': os.environ['STATUS'], 'commit': os.environ['GITHUB_SHA'],
 'run_url': f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
}, indent=2) + '\n')
PY
git add status.json
if [ -f "$RUNNER_TEMP/jigobourso-deploy.log" ]; then
  tail -n 200 "$RUNNER_TEMP/jigobourso-deploy.log" > deployment.log
  git add deployment.log
fi
git commit -qm "Statut du déploiement Jigobourso V2 : $STATUS" --allow-empty
git push -q origin HEAD:deployment-status
