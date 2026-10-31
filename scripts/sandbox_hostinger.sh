#!/bin/bash
# Essai ISOLÉ des stratégies « Momentum 6 mois » et « Momentum 12 mois » sur l'hébergement, AVANT toute mise en production.
#
# Isolation : (1) le code testé est une COPIE dans un dossier à part, jamais le dossier du site ; (2) la base utilisée est une base SÉPARÉE dont le nom doit contenir « sandbox » ou « test »
# (refus sinon) ; (3) la production n'est que LUE (mariadb-dump --single-transaction) ; (4) aucun appel Yahoo (calculs sur les clôtures déjà en base) ; (5) aucun cron ; le seul serveur lancé
# écoute sur 127.0.0.1 (port d'essai) et s'arrête à la fin.
#
# Variables : JIGO_DB_HOST JIGO_DB_PORT JIGO_DB_NAME(sandbox) JIGO_DB_USER JIGO_DB_PASSWORD ; facultatif JIGO_SOURCE_NAME JIGO_SOURCE_USER JIGO_SOURCE_PASSWORD (copie des données de production) ;
# JIGO_PY (python du site, utilisé en lecture seule). Usage, depuis la copie : bash scripts/sandbox_hostinger.sh
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${JIGO_PY:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"
fail=""; ok=""
step() { local name="$1"; shift; echo "── $name"; if "$@"; then ok="$ok | $name"; else fail="$fail | $name"; fi; }

for v in JIGO_DB_HOST JIGO_DB_NAME JIGO_DB_USER JIGO_DB_PASSWORD; do [ -n "${!v:-}" ] || { echo "Variable $v manquante (voir l'en-tête du script)."; exit 2; }; done
case "$JIGO_DB_NAME" in *sandbox*|*test*) ;; *) echo "REFUS : la base « $JIGO_DB_NAME » ne contient ni « sandbox » ni « test »."; exit 2;; esac
if [ -n "${JIGO_SOURCE_NAME:-}" ] && [ "$JIGO_SOURCE_NAME" = "$JIGO_DB_NAME" ]; then echo "REFUS : source et destination identiques."; exit 2; fi
case "$PWD" in */public_html*|*/jigobourso-v2) echo "REFUS : lancez ce script depuis la copie, pas depuis le dossier du site ($PWD)."; exit 2;; esac
export JIGO_DB_PORT="${JIGO_DB_PORT:-3306}" PYTHONPATH="$PWD" JIGO_ENV_FILE=/nonexistent
SQL() { MYSQL_PWD="$JIGO_DB_PASSWORD" mariadb -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"$JIGO_DB_USER" "$JIGO_DB_NAME" "$@"; }
echo "Copie testée : $PWD · base d'essai : $JIGO_DB_NAME · python : $PY"

tables=$(SQL -N -e 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()') || { echo "Connexion à la base d'essai impossible."; exit 2; }

# ── 1. contenu de la base d'essai
if [ "$tables" -eq 0 ]; then
  if [ -n "${JIGO_SOURCE_NAME:-}" ]; then
    echo "── 1. copie des données de production (lecture seule) vers la base d'essai"
    MYSQL_PWD="${JIGO_SOURCE_PASSWORD:-$JIGO_DB_PASSWORD}" mariadb-dump -h"$JIGO_DB_HOST" -P"$JIGO_DB_PORT" -u"${JIGO_SOURCE_USER:-$JIGO_DB_USER}" --single-transaction --quick --skip-lock-tables "$JIGO_SOURCE_NAME" \
      | sed -E 's/DEFINER=`[^`]*`@`[^`]*`//g' | SQL \
      && ok="$ok | 1 copie" || { fail="$fail | 1 copie"; echo "Copie impossible : arrêt."; exit 1; }
  else
    step "1. schéma neuf (db/schema.sql) + migrations marquées" bash -c "SQL() { MYSQL_PWD='$JIGO_DB_PASSWORD' mariadb -h'$JIGO_DB_HOST' -P'$JIGO_DB_PORT' -u'$JIGO_DB_USER' '$JIGO_DB_NAME' \"\$@\"; }; SQL < db/schema.sql && $PY scripts/migrate.py --record-all"
  fi
else
  echo "La base d'essai contient déjà $tables tables : réutilisée telle quelle."
fi

# ── 2. migrations (chemin de mise à niveau réel : colonnes ajoutées sans rien perdre)
before=$(SQL -N -e 'SELECT COUNT(*) FROM series_state' 2>/dev/null || echo 0)
step "2a. migrations en attente" $PY scripts/migrate.py --pending
step "2b. application des migrations" $PY scripts/migrate.py --apply
after=$(SQL -N -e 'SELECT COUNT(*) FROM series_state' 2>/dev/null || echo 0)
step "2c. colonnes momentum_6m et momentum_12m présentes, aucune ligne perdue ($before -> $after)" bash -c "[ '$before' = '$after' ] && [ \"\$(MYSQL_PWD='$JIGO_DB_PASSWORD' mariadb -h'$JIGO_DB_HOST' -P'$JIGO_DB_PORT' -u'$JIGO_DB_USER' '$JIGO_DB_NAME' -N -e \"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='series_state' AND column_name IN ('momentum_6m','momentum_12m')\")\" = 2 ]"

# ── 3. calcul des indicateurs (clôtures déjà en base, aucun réseau)
step "3. recalcul des indicateurs (engine.cli metrics)" nice -n 10 $PY -m engine.cli metrics

# ── 3b. reconstitution du suivi sur les dernières séances (INSERT IGNORE : n'écrase aucun instantané existant) pour que le Suivi montre les deux stratégies à 21 et 63 séances
step "3b. reconstitution du suivi (75 séances) et résultats à 21 et 63 séances" nice -n 15 $PY -m engine.cli suivi-backfill --sessions 75

# ── 4. contrôles de cohérence et classements (lecture seule)
step "4. valeurs stockées, cohérence avec la formule des tests, classements" $PY scripts/verify_momentum_release.py

check() { printf '%s' "$2" | $PY -m engine.cli "$1" | $PY -c "import json,sys; d=json.load(sys.stdin); $3"; }
step "4b. presets : 6 stratégies, 4 inchangées, deux momentums à l'essai" check presets '{}' "assert list(d['presets'])==['regular','fast','recovery','low_volatility','momentum','momentum12'] and d['experimental']==['momentum','momentum12']; print('ok')"
step "4c. Suivi lisible (horizons 1, 3, 5, 21, 63)" check suivi '{}' "assert d['horizons']==[1,3,5,21,63], d.get('horizons'); print('ok')"
step "4d. syntaxe PHP du site" bash -c "find app -name '*.php' -print0 | xargs -0 -n1 php -l > /dev/null"

# ── 5. PHP + API sur un serveur local isolé (base d'essai, compte d'essai créé DANS la base d'essai seulement)
api_check() {
  local port=18090 jar; jar=$(mktemp); local pw='Sandbox-only-pass-2026'
  export JIGO_ENGINE_ROOT="$PWD" JIGO_PYTHON="$PY"
  php scripts/create_user.php sandbox_user "$pw" --admin --email=sandbox@example.test > /dev/null || return 1
  php -S 127.0.0.1:$port -t app/public > /tmp/jigo-sandbox-php.log 2>&1 &
  local pid=$!; local rc=0 api="http://127.0.0.1:$port/api.php?r="
  for _ in $(seq 1 30); do curl -s -o /dev/null "${api}auth/me" && break; sleep 1; done
  echo "serveur d'essai : $(curl -s -o /dev/null -w 'HTTP %{http_code}' "${api}auth/me")"
  curl -sS -c "$jar" -H 'Content-Type: application/json' -d "{\"username\":\"sandbox_user\",\"password\":\"$pw\"}" "${api}auth/login" | $PY -c "import json,sys; raw=sys.stdin.read(); d=json.loads(raw) if raw.strip() else {}; assert d.get('user'), raw[:300]" || rc=1
  for p in momentum momentum12 regular; do
    curl -s -b "$jar" -H 'Content-Type: application/json' -d "{\"config\":\"$p\",\"view\":{\"status\":\"retained\",\"kind\":\"equity\",\"page_size\":20}}" "${api}explore" \
      | $PY -c "import json,sys; d=json.load(sys.stdin); r=d['rows']; assert d['config']['name']=='$p' and r, d.get('error'); print('$p', d['total'], 'retenus ; premier :', r[0]['symbol'], r[0].get('momentum'))" || rc=1
  done
  id=$(curl -s -b "$jar" -H 'Content-Type: application/json' -d '{"config":"momentum12","view":{"status":"retained","kind":"equity","page_size":1}}' "${api}explore" | $PY -c "import json,sys; print(json.load(sys.stdin)['rows'][0]['id'])")
  curl -s -b "$jar" -H 'Content-Type: application/json' -d "{\"id\":$id,\"config\":$(curl -s -b "$jar" "${api}strategy/presets" | $PY -c "import json,sys; print(json.dumps(json.load(sys.stdin)['presets']['momentum12']))")}" "${api}sheet" \
    | $PY -c "import json,sys; d=json.load(sys.stdin); assert d['strategy']['experimental'] and d['strategy']['ranking']=='momentum12' and d['state']['momentum_12m'] is not None, d.get('error'); print('fiche ok :', d['state']['momentum_12m'])" || rc=1
  curl -s -b "$jar" "${api}suivi" | $PY -c "
import json,sys
d=json.load(sys.stdin)
assert d['horizons']==[1,3,5,21,63] and 'momentum' in d['presets'] and 'momentum12' in d['presets'], list(d.get('presets', {}))
for p in ('momentum','momentum12'):
    g=d['presets'][p]['groups']['equity']
    print('suivi', p, {h: (g[h]['n'] if g.get(h) else None) for h in ('21','63')})
    assert g.get('21') and g['21']['n']>0, p
" || rc=1
  curl -s -b "$jar" "${api}strategy/presets" | $PY -c "import json,sys; d=json.load(sys.stdin); assert list(d['presets'])[-2:]==['momentum','momentum12']; print('presets ok')" || rc=1
  [ $rc -eq 0 ] || { echo "-- journal du serveur d'essai :"; tail -n 8 /tmp/jigo-sandbox-php.log | cut -c1-240; }
  kill $pid 2>/dev/null; rm -f "$jar"
  return $rc
}
step "5. PHP + API (serveur local isolé) : Explorer, fiche, Suivi, profils" api_check
echo
echo "══ BILAN"
echo "réussi :${ok:- aucun}"
echo "échec  :${fail:- aucun}"
echo "Base d'essai : $JIGO_DB_NAME (la production n'a pas été modifiée). Rien n'a été poussé sur la branche principale ni déployé."
[ -z "$fail" ]
