#!/bin/bash
# Tâche de recherche exécutée sur l'hébergement par un cron temporaire. LECTURE SEULE sur les historiques exportés ; aucune écriture en base ; rien dans le dossier du site.
# Récupère le dépôt au commit demandé dans ~/tmp-backtest/research/<commit>, puis lance la commande de research/jobs/<nom>.sh.
set -u
COMMIT="${1:?commit}"; JOB="${2:?nom}"
BASE="$HOME/tmp-backtest/research"; DIR="$BASE/$COMMIT"
mkdir -p "$DIR" "$BASE/out"
[ -f "$DIR/.ok" ] || { curl -fsSL "https://codeload.github.com/elmonsieurpatate/jigobourso/tar.gz/$COMMIT" | tar -xz --strip-components=1 -C "$DIR" && touch "$DIR/.ok"; } || { echo "téléchargement impossible"; exit 1; }
cd "$DIR" && export PYTHONPATH="$DIR" && echo "commit $COMMIT · tâche $JOB · $(python3 --version)" && nice -n 10 bash "research/jobs/$JOB.sh" "$BASE/out"
