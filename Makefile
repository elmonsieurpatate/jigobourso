# Niveau 1 : make fast (sans base ni réseau). Niveau 2 : make integ (base jetable jigobourso_it, jamais la production).
# La base jigobourso_v2 (données réelles de développement) n'est jamais touchée par les tests.
PY = $(CURDIR)/.venv/bin/python
SQLROOT = mariadb -h127.0.0.1 -P33307 -uroot -plocal-test-only
DBENV = JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=33307 JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only

.PHONY: e2e fast integ db-reset dev-db lint lint-py lint-php check
# Le code exige PHP >= 8.1 (expression throw, array_is_list) ; le serveur est en 8.2.
PHP ?= $(shell command -v php8.3 || command -v php8.2 || command -v php8.4 || echo php)
fast:
	$(PY) -m pytest tests/fast -q
lint: lint-py lint-php   ## linters : ruff (Python) + php -l (syntaxe PHP)
lint-py:
	$(CURDIR)/.venv/bin/ruff check .
lint-php:
	@git ls-files '*.php' | while read f; do $(PHP) -l "$$f" | grep -v '^No syntax errors' && exit 1; done; echo "php -l : OK ($(PHP))"
check: lint fast   ## filet de sécurité avant tout refactor
db-reset:
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_it; CREATE DATABASE jigobourso_it CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_it < db/schema.sql
# Les tests lancent `python` et `php` nus : on les force vers le venv et vers PHP >= 8.1 (le `php` du PATH peut être en 7.4).
integ: db-reset
	ln -sf $(PHP) $(CURDIR)/.venv/bin/php
	PATH=$(CURDIR)/.venv/bin:$$PATH $(DBENV) $(PY) -m pytest tests/integ -q
e2e: db-reset   ## parcours navigateur de la CI (PLAYWRIGHT_MODULE et JIGO_CHROMIUM requis)
	scripts/e2e_browser.sh
dev-db:   ## base de développement avec données réelles : schéma seulement (puis catalogue, scripts/bootstrap_real.py)
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_v2; CREATE DATABASE jigobourso_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_v2 < db/schema.sql
