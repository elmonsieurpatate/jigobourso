# Livraison, restauration et reproductibilité (étape 11)

## Chaîne de validation

| Niveau | Quoi | Où |
|---|---|---|
| Contrôles courts | syntaxe PHP/Python/JS, migrations additives, ruff, formatage JS/CSS, règles Halo | job `syntax` |
| Tests complets | `tests/fast`, `tests/integ` (MariaDB jetable du runner), parcours navigateur sur base synthétique | job `tests` |
| Déploiement | sauvegardes, transfert, dépendances, migrations additives, contrôles financiers, vérification publique, retour arrière automatique | job `hostinger` |

- **Aucun test sauté n'est présenté comme réussi** : la CI lance pytest avec `-rs` et échoue si une seule ligne « skipped » apparaît (rapides comme intégration : une base jetable absente fait échouer, pas passer).
- **Validation complète ou rapide** : push normal = complète. `[deploy quick]` dans le message, ou `workflow_dispatch` avec `validation=quick`, saute les tests complets, l'essai isolé et les vérifications exhaustives, mais garde sauvegardes, contrôle d'intégrité financière, comptes, vérification publique et retour arrière. Le mode est écrit dans le résumé du job.
- Les tests, l'intégration et le navigateur ne tournent jamais contre la production ni la base de développement : base jetable seulement (`JIGO_TEST_DATABASE=1`).

## Dépendances

- `requirements.txt` : chaque dépendance a une borne haute (test `test_every_dependency_is_bounded_for_reproducible_installs`) ; `exchange_calendars` est épinglé (`==4.3`, compatible Python 3.9).
- `scripts/check_env.py` vérifie versions et imports ; la CI l'exécute après l'installation, le README l'indique pour un venv neuf.
- Limite connue : les sous-dépendances (pandas → pytz, dateutil…) ne sont pas figées ; un fichier de verrouillage complet n'est pas fourni (non testé sur Python 3.9 du serveur).

## Cohérence d'une release

- Une seule version pour toutes les pages : `?v=__BUILD__` remplacé par l'horodatage du déploiement ; `tests/fast/test_asset_versions.py` interdit toute version figée et tout fichier référencé absent. Le déploiement échoue si un marqueur reste, puis vérifie que la page servie porte la version attendue.
- Le transfert est un `rsync` unique ; le code PHP/Python et les pages sont remplacés ensemble, les contrôles s'exécutent après transfert et un échec déclenche le retour arrière.
- Limite : le transfert n'est pas atomique (pas de bascule de lien symbolique) ; une requête pendant les quelques secondes du `rsync` peut voir un mélange. Accepté tant que l'hébergement mutualisé n'offre pas de répertoire de release.

## Restauration (code ET dépendances)

`restore_code` (retour arrière automatique ou opération `rollback`) :
1. restaure `app engine db docs scripts README.md requirements.txt` depuis la dernière sauvegarde `code-*.tgz` (5 conservées) ;
2. si l'empreinte de `requirements.txt` restauré ne correspond plus à `.requirements.sha`, remet le venv sauvegardé avant la mise à jour (`site-packages-*.tgz`, 3 conservées) ;
3. vérifie que le moteur et les dépendances s'importent.

Testé localement avec un faux serveur (`tests/fast/test_environment.py`) : restauration, dépendances inchangées, première exécution, sauvegarde absente. Non testé sur l'hébergement réel.
Les données (`private/ data/ logs/`) et la base ne sont jamais restaurées par cette opération ; les migrations sont additives.

## Invalidation et recalcul

- Empreinte du moteur : `scripts/release/engine_hash.sh` (source unique, `engine/` + `db/`, hors les cinq fichiers d'affichage seul). Comparée avant et après transfert ; différente = `maintenance_pending=deploy` puis tâche `maintenance` détachée (recalcul des mesures, verdicts et classements). Identique = aucun recalcul.
- Testé dans `tests/fast/test_environment.py` : exclusions sans effet, code producteur et schéma changent l'empreinte, chaque exclusion désigne un fichier existant (un module déplacé casserait le test).

## Sauvegardes

- Avant tout remplacement : dump `portfolios`, `portfolio_transactions`, `position_levels` (vérifié par `gzip -t`), sauvegarde du code, du venv si les dépendances changent, dump complet de la base si des migrations sont en attente (3 conservés).
- Empreinte financière et comptes comparées avant/après : toute différence fait échouer la livraison.

## Cible isolée

L'essai isolé Hostinger (`sandbox_runner.sh`) exige un secret serveur (`~/tmp-backtest/.sandbox_pw`). Absent, le déploiement le dit (« Essai Hostinger isolé indisponible ») et poursuit avec les validations CI. **Non vérifié ici** : présence du secret, exécution réelle de l'essai.
