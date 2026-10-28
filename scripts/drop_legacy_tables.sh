#!/bin/bash
# Supprime les ANCIENNES tables de la base Hostinger (préfixes jb_, jy_, fd_, fdp_), sauf les 4 petites tables de comptes/portefeuilles.
# Le dump complet est sur le poste : migration/private/backup/prod-db-*.sql.gz (vérifié : gzip -t, 54 tables, « Dump completed »).
# Les tables V2 (sans préfixe) ne sont jamais touchées. Usage : scripts/drop_legacy_tables.sh        (affiche seulement)
#                                                                 scripts/drop_legacy_tables.sh --go   (supprime)
set -euo pipefail
GO="${1:-}"
ssh -o BatchMode=yes -p 65002 u381524662@147.79.103.168 bash -s -- "$GO" <<'REMOTE'
cd domains/jigobourso.turnjoy.dev/jigobourso-v2
set -a; . private/env; set +a
export MYSQL_PWD="$JIGO_DB_PASSWORD"
M="mariadb -h$JIGO_DB_HOST -P$JIGO_DB_PORT -u$JIGO_DB_USER $JIGO_DB_NAME"
KEEP="jb_users|jb_portfolios|jb_portfolio_transactions|jb_positions"
LIST=$($M -N -e "select table_name from information_schema.tables where table_schema=database() and table_name regexp '^(jb_|jy_|fd_|fdp_)' and table_name not regexp '^($KEEP)\$'")
echo "À supprimer : $(echo "$LIST" | wc -l) tables"; echo "$LIST" | tr '\n' ' '; echo
$M -N -e "select concat('Taille avant : ', round(sum(data_length+index_length)/1048576), ' Mo') from information_schema.tables where table_schema=database()"
if [ "$1" != "--go" ]; then echo "(simulation : rien supprimé ; relancer avec --go)"; exit 0; fi
SQL="SET FOREIGN_KEY_CHECKS=0;"; for t in $LIST; do SQL="$SQL DROP TABLE \`$t\`;"; done
$M -e "$SQL SET FOREIGN_KEY_CHECKS=1;"
$M -N -e "select concat('Taille après : ', round(sum(data_length+index_length)/1048576), ' Mo, ', count(*), ' tables') from information_schema.tables where table_schema=database()"
REMOTE
