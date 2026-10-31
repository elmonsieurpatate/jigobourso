#!/bin/bash
# Essai ISOLÉ du « Momentum 6 mois » sur l'hébergement, AVANT tout push GitHub ou déploiement.
#
# Isolation : (1) le code testé est une COPIE dans un dossier à part (~/jigo-sandbox), jamais le dossier du site ; (2) la base utilisée est une base SÉPARÉE dont le nom doit
# contenir « sandbox » ou « test » (refus sinon) ; (3) aucune écriture dans la base de production : elle n'est que LUE (dump) si vous fournissez JIGO_SOURCE_* ; (4) aucun appel Yahoo
# (seulement des calculs sur les clôtures déjà en base) ; (5) aucun cron, aucun serveur public.
#
# Variables (la base d'essai, à créer dans hPanel > Bases de données MySQL, p. ex. u123_sandbox) :
#   JIGO_DB_HOST=127.0.0.1  JIGO_DB_PORT=3306  JIGO_DB_NAME=...sandbox  JIGO_DB_USER=...  JIGO_DB_PASSWORD=...
# Facultatif, pour essayer sur une COPIE des vraies données (chemin de mise à niveau réel : ancien schéma -> migration) :
#   JIGO_SOURCE_NAME  JIGO_SOURCE_USER  JIGO_SOURCE_PASSWORD   (lecture seule, mariadb-dump --single-transaction)
# Python : JIGO_PY (défaut : .venv/bin/python s'il existe, sinon python3). Usage, depuis le dossier de la copie : bash scripts/sandbox_hostinger.sh
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${JIGO_PY:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"
fail=""; ok=""
note() { echo "   → $*"; }
step() { local name="$1"; shift; echo "── $name"; if "$@"; then ok="$ok | $name"; else fail="$fail | $name"; fi; }

# ── garde-fous
for v in JIGO_DB_HOST JIGO_DB_NAME JIGO_DB_USER JIGO_DB_PASSWORD; do [ -n "${!v:-}" ] || { echo "Variable $v manquante (voir l'en-tête du script)."; exit 2; }; done
case "$JIGO_DB_NAME" in *sandbox*|*test*) ;; *) echo "REFUS : la base « $JIGO_DB_NAME » ne contient ni « sandbox » ni « test »."; exit 2;; esac
if [ -n "${JIGO_SOURCE_NAME:-}" ] && [ "$JIGO_SOURCE_NAME" = "$JIGO_DB_NAME" ]; then echo "REFUS : source et destination identiques."; exit 2; fi
case "$PWD" in */public_html*|*/domains/*) echo "REFUS : lancez ce script depuis la copie (~/jigo-sandbox), pas depuis le dossier du site ($PWD)."; exit 2;; esac
export JIGO_DB_PORT="${JIGO_DB_PORT:-3306}"
SQL() { mariadb -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"$JIGO_DB_USER" -p"$JIGO_DB_PASSWORD" "$JIGO_DB_NAME" "$@"; }
export PYTHONPATH="$PWD"
echo "Copie testée : $PWD · base d'essai : $JIGO_DB_NAME · python : $PY"

tables=$(SQL -N -e 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()') || { echo "Connexion à la base d'essai impossible."; exit 2; }

# ── 1. contenu de la base d'essai
if [ "$tables" -eq 0 ]; then
  if [ -n "${JIGO_SOURCE_NAME:-}" ]; then
    echo "── 1. copie des données de production (lecture seule) vers la base d'essai"
    mariadb-dump -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"${JIGO_SOURCE_USER:-$JIGO_DB_USER}" -p"${JIGO_SOURCE_PASSWORD:-$JIGO_DB_PASSWORD}" --single-transaction --skip-lock-tables --routines=false "$JIGO_SOURCE_NAME" | SQL \
      && ok="$ok | 1 copie" || { fail="$fail | 1 copie"; echo "Copie impossible : arrêt."; exit 1; }
    COPY=1
  else
    step "1. schéma neuf (db/schema.sql) + migrations marquées" bash -c "SQL() { mariadb -h'$JIGO_DB_HOST' -P'$JIGO_DB_PORT' -u'$JIGO_DB_USER' -p'$JIGO_DB_PASSWORD' '$JIGO_DB_NAME' \"\$@\"; }; SQL < db/schema.sql && $PY scripts/migrate.py --record-all"
    COPY=0
  fi
else
  note "La base d'essai contient déjà $tables tables : on la réutilise telle quelle (vide-la dans hPanel pour repartir de zéro)."
  COPY=1
fi

# ── 2. migration (chemin de mise à niveau : la colonne momentum_6m doit être AJOUTÉE sans rien perdre)
before=$(SQL -N -e 'SELECT COUNT(*) FROM series_state' 2>/dev/null || echo 0)
step "2a. migrations en attente" $PY scripts/migrate.py --pending
step "2b. application des migrations" $PY scripts/migrate.py --apply
after=$(SQL -N -e 'SELECT COUNT(*) FROM series_state' 2>/dev/null || echo 0)
step "2c. colonne momentum_6m présente, aucune ligne perdue ($before -> $after)" bash -c "[ '$before' = '$after' ] && [ \"\$(mariadb -h'$JIGO_DB_HOST' -P'$JIGO_DB_PORT' -u'$JIGO_DB_USER' -p'$JIGO_DB_PASSWORD' '$JIGO_DB_NAME' -N -e \"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='series_state' AND column_name='momentum_6m'\")\" = 1 ]"

# ── 3. calcul des mesures (clôtures déjà en base, aucun réseau)
step "3. recalcul des mesures (engine.cli metrics)" $PY -m engine.cli metrics

# ── 4. contrôles du résultat
echo "── 4. contrôles"
SQL -t -e "SELECT COUNT(*) AS lignes, SUM(momentum_6m IS NOT NULL) AS momentum_calcule, SUM(momentum_6m IS NULL) AS non_evaluable, ROUND(MIN(momentum_6m),1) AS min_pct, ROUND(MAX(momentum_6m),1) AS max_pct FROM series_state"
ok_count=$(SQL -N -e "SELECT SUM(momentum_6m IS NOT NULL) FROM series_state" 2>/dev/null || echo 0)
step "4a. des valeurs Momentum existent (${ok_count:-0})" bash -c "[ '${ok_count:-0}' != 'NULL' ] && [ '${ok_count:-0}' -gt 0 ]"

check() {   # check <commande> <json> <script python de contrôle lisant « d »>
  printf '%s' "$2" | $PY -m engine.cli "$1" | $PY -c "import json,sys; d=json.load(sys.stdin); $3"
}
step "4b. presets : 5 stratégies, 4 inchangées, momentum expérimentale" check presets '{}' "assert list(d['presets'])==['regular','fast','recovery','low_volatility','momentum'] and d['experimental']==['momentum']; print('ok')"
step "4c. Explorer (momentum, négociabilité conservée)" check explore '{"config":"momentum","view":{"status":"retained","kind":"equity","page_size":20}}' "r=d['rows']; assert d['config']['name']=='momentum' and r; print(len(r),'lignes ; premiers :',[(x.get('symbol'),x.get('momentum')) for x in r[:3]])"
step "4d. Explorer : les 4 autres stratégies répondent encore" bash -c "for n in regular fast recovery low_volatility; do printf '{\"config\":\"%s\",\"view\":{\"page_size\":5}}' \$n | $PY -m engine.cli explore | $PY -c 'import json,sys; d=json.load(sys.stdin); assert \"error\" not in d' || exit 1; done"
step "4e. Suivi lisible (horizons 1, 3, 5, 21, 63)" check suivi '{}' "assert d['horizons']==[1,3,5,21,63], d.get('horizons'); print('ok')"
step "4f. syntaxe PHP du site" bash -c "find app -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null"
echo
echo "══ BILAN"
echo "réussi :${ok:- aucun}"
echo "échec  :${fail:- aucun}"
echo "Base d'essai : $JIGO_DB_NAME (la production n'a pas été modifiée). Rien n'a été poussé sur GitHub ni déployé."
[ -z "$fail" ]
