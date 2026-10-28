# Jigobourso v2

Outil d'aide à la sélection d'actions et d'ETF (analyse descriptive des cours passés) et de suivi de portefeuilles.
PHP (site et API) · Python (moteur : catalogue, collecte, calculs) · MariaDB. Aucun framework ; une seule dépendance Python (PyMySQL).

```
db/schema.sql     schéma unique            engine/   moteur Python (catalogue, market, analytics, jobs, migration)
app/public/       pages, assets, api.php   app/      lib/ routes/ services/ (PHP)
tests/            fast/ integ/ e2e/        scripts/  base locale, amorçage, migration, export
docs/             ARCHITECTURE, METHODE, FONCTIONNALITES, VOLUMETRIE, DEPLOIEMENT
```

## Développer
```
make fast          # tests rapides, sans base ni réseau
make integ         # MariaDB jetable (jigobourso_it) : collecte, calcul, garantie « exclu ≠ recommandé »
make dev-db        # base de développement vide (jigobourso_v2)
python -m engine.cli catalogue --source <clone FinanceDatabase>
python scripts/bootstrap_real.py     # vraies données Yahoo (base locale uniquement)
php -S 127.0.0.1:8090 -t app/public  # site (variables JIGO_DB_* et JIGO_PYTHON)
BASE=http://127.0.0.1:8090 USER_NAME=… PASS=… node tests/e2e/smoke.mjs   # parcours navigateur
```
Variables : `JIGO_DB_HOST/PORT/NAME/USER/PASSWORD`, `JIGO_PYTHON` (interpréteur du moteur), `JIGO_ENGINE_ROOT`, `JIGO_DATA_DIR`.
Planification : une seule tâche cron, toutes les 15 minutes : `python -m engine.cli tick`.
