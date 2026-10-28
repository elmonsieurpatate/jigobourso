# Niveau 1 : make fast (sans base ni réseau). Niveau 2 : make integ (base jetable jigobourso_it, jamais la production).
# La base jigobourso_v2 (données réelles de développement) n'est jamais touchée par les tests.
PY = $(CURDIR)/.venv/bin/python
SQLROOT = mariadb -h127.0.0.1 -P33307 -uroot -plocal-test-only
DBENV = JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=33307 JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only

.PHONY: fast integ db-reset dev-db
fast:
	$(PY) -m pytest tests/fast -q
db-reset:
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_it; CREATE DATABASE jigobourso_it CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_it < db/schema.sql
integ: db-reset
	$(DBENV) $(PY) -m pytest tests/integ -q
dev-db:   ## base de développement avec données réelles : schéma seulement (puis catalogue, scripts/bootstrap_real.py)
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_v2; CREATE DATABASE jigobourso_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_v2 < db/schema.sql
