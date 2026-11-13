# scripts/

Outils hors application. Rien ici n'est appelé par le site ; `ops/deploy.sh` et les tests en appellent certains par leur chemin (ne pas déplacer sans les adapter).

| Fichier | Rôle |
|---|---|
| `migrate.py` | applique les migrations `db/migrations/` (CI : `--check`) |
| `local_db.sh` | MariaDB locale jetable (tests, `make integ`) |
| `test_secondary_filters.sh` | lanceur des tests e2e des filtres secondaires (PHP + Chromium) : base jetable puis `tests/e2e/secondary-*` ; ne les double pas |
| `bootstrap_real.py`, `benchmark_explorer.py`, `explain_current_ranking.py` | amorçage de données réelles locales, benchmark, explication du classement |
| `create_user.php` | crée un compte en ligne de commande (tests e2e, CI) |
| `release/check_financial_integrity.php`, `release/check_secondary_catalogue.php`, `release/verify_account_release.php`, `release/verify_php_bridge.php` | contrôles en lecture seule, appelés par `ops/deploy.sh` |
| `release/prepare_financial_release.py`, `release/verify_etf_release.py`, `release/verify_financial_release.py`, `release/verify_momentum_release.py` | préparation et vérification de version (mode `full` du déploiement) |
| `oneshot/migrate_saved_to_explorer.py` | copie `saved_searches` / `saved_presets` vers `explorer_saved` (une fois en production, puis `DROP TABLE` à la main) |

Migration V1 → V2 terminée : `migrate_legacy.py`, `export_user_data.py`, `drop_legacy_tables.sh` et `engine/migration/` sont retirés, récupérables avec le tag `archive/v1-migration`.
