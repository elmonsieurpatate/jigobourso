# Niveau 1 : make fast (sans base ni réseau). Niveau 2 : make integ (base jetable jigobourso_it, jamais la production).
# La base jigobourso_v2 (données réelles de développement) n'est jamais touchée par les tests.
PY = $(CURDIR)/.venv/bin/python
SQLROOT = mariadb -h127.0.0.1 -P33307 -uroot -plocal-test-only
DBENV = JIGO_TEST_DATABASE=1 JIGO_DB_HOST=127.0.0.1 JIGO_DB_PORT=33307 JIGO_DB_NAME=jigobourso_it JIGO_DB_USER=root JIGO_DB_PASSWORD=local-test-only

.PHONY: js-format js-check visual visual-update css-format css-check release-check e2e fast integ db-reset dev-db lint lint-py lint-php check
# Le code exige PHP >= 8.1 (expression throw, array_is_list) ; le serveur est en 8.2.
PHP ?= $(shell command -v php8.3 || command -v php8.2 || command -v php8.4 || echo php)
fast:
	$(PY) -m pytest tests/fast -q
lint: lint-py lint-php   ## linters : ruff (Python) + php -l (syntaxe PHP)
lint-py:
	$(CURDIR)/.venv/bin/ruff check .
lint-php:
	@PHP=$(PHP) scripts/lint_php.sh
css-format:   ## formate les feuilles CSS (Prettier 3.3.3, config .prettierrc)
	npx --yes prettier@3.3.3 --write 'app/public/assets/*.css'
js-format:   ## formate les scripts JS (Prettier 3.3.3, config .prettierrc)
	npx --yes prettier@3.3.3 --write 'app/public/assets/*.js'
js-check:   ## vérifie le formatage et la syntaxe des scripts JS
	npx --yes prettier@3.3.3 --check 'app/public/assets/*.js'
	@for f in app/public/assets/*.js; do node --check $$f || exit 1; done; echo 'JS : syntaxe OK'
css-check:   ## vérifie formatage + garde-fous Halo
	npx --yes prettier@3.3.3 --check 'app/public/assets/*.css'
	python3 scripts/check_halo_css.py
visual:   ## compare les styles calculés de la galerie à la référence (PLAYWRIGHT_MODULE, JIGO_CHROMIUM requis)
	node tests/visual/galerie.cjs
visual-update:   ## régénère la référence après un changement de design voulu
	node tests/visual/galerie.cjs --update
check: lint fast   ## filet de sécurité avant tout refactor
db-reset:
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_it; CREATE DATABASE jigobourso_it CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_it < db/schema.sql
# Les tests lancent `python` et `php` nus : on les force vers le venv et vers PHP >= 8.1 (le `php` du PATH peut être en 7.4).
integ: db-reset
	ln -sf $(PHP) $(CURDIR)/.venv/bin/php
	PATH=$(CURDIR)/.venv/bin:$$PATH $(DBENV) $(PY) -m pytest $(or $(INTEG_ARGS),tests/integ) -q
release-check:   ## contrôles de version en lecture seule (scripts/release/) sur la base jetable : intégrité financière et catalogue secondaire
	$(DBENV) $(PHP) scripts/release/check_financial_integrity.php > /dev/null
	$(DBENV) $(PHP) scripts/release/check_secondary_catalogue.php > /dev/null
	@echo "release-check : OK"
e2e: db-reset   ## parcours navigateur de la CI (PLAYWRIGHT_MODULE et JIGO_CHROMIUM requis)
	scripts/e2e_browser.sh
dev-db:   ## base de développement avec données réelles : schéma seulement (puis catalogue, scripts/bootstrap_real.py)
	scripts/local_db.sh start
	$(SQLROOT) -e 'DROP DATABASE IF EXISTS jigobourso_v2; CREATE DATABASE jigobourso_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
	$(SQLROOT) jigobourso_v2 < db/schema.sql
