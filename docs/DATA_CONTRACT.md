# Contrat des données (schéma, migrations, accès SQL)

État vérifié le 2026-11-14, étape 9. Le schéma, les migrations, les accès et les tests décrivent ce même contrat.

## Schéma neuf et base migrée

- `db/schema.sql` décrit une installation neuve (48 tables, InnoDB, 33 clés étrangères) ; `db/migrations/` fait évoluer une base existante, ajouts seulement (`scripts/migrate.py --check` en CI).
- Parité : `tests/fast/test_schema_migrations.py` exige que tout ce qu'une migration ajoute existe dans `schema.sql` ; `tests/integ/test_migrations.py::test_real_migrations_replay_on_a_fresh_schema_without_error` rejoue toutes les migrations réelles sur un schéma neuf (même liste de colonnes avant et après).
- Le déploiement applique `schema.sql` avec `CREATE TABLE IF NOT EXISTS` (aucune table existante modifiée), puis les migrations en attente, après sauvegarde `mariadb-dump`.
- **État requis** : toute base doit avoir `schema_migrations` à jour (`python scripts/migrate.py --pending` vide) avant que le code qui en dépend serve des requêtes. Une base neuve s'enregistre avec `--record-all`.
- **Reprise** : le DDL MariaDB n'est pas transactionnel. Une migration interrompue après sa première instruction est reprise sans blocage : les erreurs « table, colonne, index ou clé étrangère existe déjà » sont ignorées et journalisées, toute autre erreur arrête sans enregistrer la migration (`apply`, test `test_resume_after_a_partially_applied_migration`).

## Clés, index, contraintes

Audit sur la base issue de `schema.sql` : toutes les tables ont une clé primaire sauf `account_attempts` (journal de tentatives, purgé chaque jour, accès uniquement par `scope_hash` + `at` ; aucun besoin démontré, schéma inchangé). Aucune clé étrangère sans index de tête ; aucune table hors InnoDB.

## SQL dynamique

Seuls des fragments issus de constantes du code sont interpolés (jamais une valeur de requête) :

| Lieu | Fragment | Origine |
|---|---|---|
| `IN (%s,…)` partout | marqueurs | générés à partir de la longueur de la liste ; valeurs liées |
| `explorer/funnel.py` | conditions de filtre | table constante `YAHOO_WHERE` et chaînes fixes par étape |
| `admin/adminsvc.py` | `sql_where`, tri | tri par table constante `SORTS` (défaut sûr), valeurs liées |
| `jobs/tasks.py housekeeping` | table et condition | tuple `plan` constant |
| `jobs/tasks.py _count` | table | liste blanche `HISTORY_TABLES`, `ValueError` sinon |
| `catalogue/loader.py` | colonnes | constante `RAW_COLUMNS` |

## N+1

Mesure (`tests/integ/test_query_counts.py`, base jetable) : liste de portefeuilles = 20 requêtes pour 3 portefeuilles, +2 par portefeuille supplémentaire (valorisation) ; détail d'un portefeuille = 38 requêtes à chaud, indépendant du nombre de transactions ; le premier appel d'une session coûte environ dix requêtes de plus. Aucun N+1 par transaction ; la croissance linéaire par portefeuille est connue et plafonnée par le test. Aucune correction nécessaire.

## Comportements financiers jamais dégradés en silence

Lecture illisible des splits : 503 (étape 6). Réglages de plan illisibles (`suivi`) : valeurs par défaut **signalées** (`plan_rules_unavailable`) et journalisées avec l'identifiant de requête. Taux de change historique absent : 422, jamais le taux courant. Le seul `catch` restant en PHP qui ne relance pas concerne l'envoi de messages (échec journalisé) et l'enrichissement d'un achat par une stratégie (`alerts_error` renvoyé).

## Isolation, concurrence, révisions

- Écriture du registre : verrou de ligne du portefeuille, puis de ses transactions, validation de tout l'historique, commit (voir `docs/ARCHITECTURE_PHP.md`).
- Réglages JSON (stratégies, filtres, dispositions) : ligne verrouillée `FOR UPDATE`, champ `revision` : une écriture avec une révision périmée est refusée (409), trois tentatives en cas de verrou occupé.
- Les lectures de contrôle de release utilisent `REPEATABLE READ` en lecture seule.

## Conservation et purge

| Donnée | Règle |
|---|---|
| `sessions`, `login_attempts`, `account_attempts`, `account_tokens`, `job_steps`, `jobs` | `housekeeping` (cron) : expirées, 1 jour, 1 jour, 7 jours, 90 jours, 90 jours |
| `job_logs` | supprimés avec leur traitement (`ON DELETE CASCADE`) |
| `daily_prices`, `intraday_prices` | profondeur fournisseur / `intraday_retention_sessions` |
| `result_cache` | entrées plus anciennes purgées à chaque reconstruction |
| transactions, portefeuilles, comptes | jamais purgés ni réécrits automatiquement |

## Types numériques et arrondis

Quantités `DECIMAL(24,8)`, prix `DECIMAL(24,8)`, change `DECIMAL(20,10)`, frais `DECIMAL(20,8)` ; cours de marché `DECIMAL(16,6)`. PHP et Python calculent en nombres flottants double précision à partir de ces valeurs et ne les arrondissent qu'à la présentation (2 décimales pour les montants en euros, `round(x, 4)` pour les courbes) : aucune valeur arrondie n'est réécrite en base. Bornes à l'écriture : `NUM_MAX = 1e12`, mode SQL strict (une valeur hors limites est refusée, jamais tronquée).

## Pas de changement de schéma à l'étape 9

Aucun besoin démontré : aucune migration ajoutée.
