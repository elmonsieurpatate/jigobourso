# Jigobourso v2

Aide à la sélection d'actions et d'ETF (analyse descriptive des cours passés) et suivi de portefeuilles.
PHP 8.1+ (site et API) · Python 3 (moteur : catalogue, collecte, calculs) · MariaDB · front statique sans bundler.
Aucun framework ; une seule dépendance Python d'exécution (PyMySQL).

## Organisation

| Dossier | Contenu |
|---|---|
| `app/` | `public/` (pages HTML, `assets/` JS et CSS, `api.php`), `lib/`, `routes/`, `services/` (PHP) |
| `engine/` | moteur Python : `catalogue/`, `market/`, `analytics/` (admin, explorer, market_views, portfolio, scoring, series, shared), `jobs/`, `shared/`, `cli.py` |
| `db/` | `schema.sql` (schéma unique) et `migrations/` |
| `scripts/` | base locale, migrations, vérifications de version (voir `scripts/README.md`) |
| `ops/` | déploiement et exploitation (`deploy.sh`, rapports, journaux) |
| `tests/` | `fast/` (sans base), `integ/` (MariaDB jetable), `php/` (services PHP), `seeds/` (données), `e2e/` (navigateur, Node) ; voir `tests/e2e/README.md` |
| `docs/` | architecture, méthode, sécurité, déploiement, structure du front |

## Démarrage depuis zéro

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest ruff==0.17.4
.venv/bin/python scripts/check_env.py   # 0 = dépendances conformes à requirements.txt, moteur importable
make dev-db                             # MariaDB locale (docker) + base jigobourso_v2 vide
make check                              # lint + tests rapides
```

Prérequis : Python 3.9+ (le serveur est en 3.9 ; développement testé en 3.12), PHP ≥ 8.1, MariaDB 10.11, Node (formatage et navigateur).
Livraison, restauration et reprise : `docs/DELIVERY.md`.

## Commandes

```
make fast    # tests rapides, sans base ni réseau
make lint    # ruff + php -l
make check   # lint + fast : filet avant tout changement
make integ   # base jetable jigobourso_it (≈ 4 min) : collecte, calcul, API, sécurité
make dev-db  # base de développement vide (jigobourso_v2)
```

Site local : `php -S 127.0.0.1:8090 -t app/public` avec `JIGO_DB_*` et `JIGO_PYTHON`.
Parcours navigateur : `BASE=http://127.0.0.1:8090 USER_NAME=… PASS=… node tests/e2e/smoke.cjs` (variable `PLAYWRIGHT_MODULE` = chemin de playwright-core).

## Configuration

`JIGO_DB_HOST/PORT/NAME/USER/PASSWORD`, `JIGO_PYTHON`, `JIGO_ENGINE_ROOT`, `JIGO_DATA_DIR`. Aucun secret dans le dépôt.

## Production

Un `push` sur `main` lance la CI (contrôles courts, tests complets, puis déploiement Hostinger).
Une seule tâche cron hPanel, toutes les 5 minutes, appelle `api/cron` (en-tête `X-Cron-Key`) ; elle exécute `python -m engine.cli tick`.

## Sécurité du front

CSP stricte, sans `unsafe-inline` : `script-src 'self'`, `style-src 'self'`. Aucun attribut `style=` : les valeurs calculées (couleurs, largeurs) passent par `data-style`, appliqué en CSSOM par `core.js`. Détails : `docs/SECURITE.md`, `docs/FRONTEND_STRUCTURE.md`.
