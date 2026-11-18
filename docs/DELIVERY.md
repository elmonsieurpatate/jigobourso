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

- `requirements.in` conserve les contraintes runtime ; `requirements.txt` verrouille
  les versions directes et transitives, résolues sous Python 3.9 et vérifiées avec
  les tests sous Python 3.9 et 3.12. `requirements-dev.in` et `requirements-dev.txt`
  font de même pour les outils. Une modification des contraintes exige une nouvelle
  résolution puis la recette ; ne pas éditer quelques versions transitives au hasard.
- `scripts/check_env.py` vérifie les versions et imports des 11 paquets runtime.
  Le moteur est importé avant NumPy pour appliquer les limites BLAS.
- `package-lock.json` fixe les outils CSS de développement : `npm ci --ignore-scripts`.
  Les sorties CSS sont déjà commitées ; le serveur de production n’a pas besoin de Node.
- Sans pip dans le venv, le pip système n’est utilisé que si son Python possède
  la même version majeure/mineure que le venv. Un écart arrête la livraison.

## Cohérence d'une release

- Une seule version pour toutes les pages : `?v=__BUILD__` remplacé par l'horodatage du déploiement ; `tests/fast/test_asset_versions.py` interdit toute version figée et tout fichier référencé absent. Le déploiement échoue si un marqueur reste, puis vérifie que la page servie porte la version attendue.
- Le transfert est un `rsync` unique ; le code PHP/Python et les pages sont remplacés ensemble, les contrôles s'exécutent après transfert et un échec déclenche le retour arrière.
- Transfert : `rsync --delay-updates --delete-delay` copie tout sous des noms temporaires puis met les fichiers en place d'un coup en fin de transfert ; la fenêtre de mélange de versions se réduit à la série de renommages finale (quelques centaines de millisecondes, non mesurée sur l'hébergement). Ce n'est pas une bascule atomique de répertoire : l'hébergement mutualisé n'offre pas de répertoire de release. Validé par la répétition locale ; non mesuré sur Hostinger.

## Restauration (code ET dépendances)

`restore_code` (retour arrière automatique ou opération `rollback`) :

1. choisit l’archive de code et son snapshot d’environnement associé ;
2. vérifie avant remplacement les sidecars, checksums, manifeste et version Python ;
3. restaure le code et précisément cet environnement, puis contrôle leurs imports ;
4. valide l’empreinte seulement si les contrôles réussissent.

Chaque sauvegarde du code possède son snapshot, même si requirements.txt n’a pas
changé. Aucun repli vers « le dernier venv disponible » ; aucune réussite si le
snapshot manque. **Les anciennes archives dépourvues d’association sont refusées**
avant de toucher au code actif. Ce changement de contrat impose de conserver une
nouvelle sauvegarde complète valide avant la première livraison de ce mécanisme.
La rétention conserve cinq paires code/environnement et leurs sidecars. La réparation
des dépendances réutilise le snapshot associé, sans nécessiter d’archive générique.

## Invalidation et recalcul

- Empreinte du moteur : `scripts/release/engine_hash.sh` (source unique, `engine/` + `db/`, hors les cinq fichiers d'affichage seul). Comparée avant et après transfert ; différente = `maintenance_pending=deploy` puis tâche `maintenance` détachée (recalcul des mesures, verdicts et classements). Identique = aucun recalcul.
- Testé dans `tests/fast/test_environment.py` : exclusions sans effet, code producteur et schéma changent l'empreinte, chaque exclusion désigne un fichier existant (un module déplacé casserait le test).

## Sauvegardes

- Avant tout remplacement : dump `portfolios`, `portfolio_transactions`, `position_levels` (vérifié par `gzip -t`), sauvegarde appariée du code et du venv, dump complet de la base si des migrations sont en attente (3 conservés).
- Empreinte financière et comptes comparées avant/après : toute différence fait échouer la livraison.

## Cible isolée : répétition locale

L'essai isolé Hostinger (`sandbox_runner.sh`) exige un secret serveur (`~/tmp-backtest/.sandbox_pw`) et un script (`scripts/sandbox_hostinger.sh`) absent du dépôt : il n'a jamais tourné. Décision : il est remplacé par une répétition locale.

`scripts/rehearse_deploy.sh <ok|fail|fail-deps|diagnostic> [commit_en_place]` exécute le **vrai** `ops/deploy.sh` contre un faux serveur (dossier temporaire, venv propre, copie jetable d'une base de développement pleine, `ssh` et `rsync` exécutés en local). Le code en place est par défaut une ancienne version (avant le déplacement des modules). Ni la production ni la base de développement ne sont touchées.

Résultats du 2026-11-15 (base de 3,8 M de prix, 20 transactions) :
- `diagnostic` et `ok` : réussis (migrations, contrôles financiers, comptes, 20 transactions conservées, recalcul déclenché) ;
- `fail` : **a révélé un défaut** (un moteur cassé n'arrêtait pas le déploiement : contrôles écrits `test && echo`, sans effet sous `set -e`). Corrigé dans `ops/deploy.sh`, verrouillé par `test_deploy_checks_never_hide_a_failure_behind_and_echo` ; ensuite le moteur cassé déclenche le retour arrière ;
- `fail-deps` : code **et** dépendances restaurés (paquet ajouté retiré).

Non couvert par la répétition : particularités de l'hébergement (PHP 8.2 réel, droits de fichiers, venv sans pip, SSH, `sendmail` réel — remplacé par un faux).

## Réconciliation du venv à la livraison (15 novembre 2026)

Une empreinte `requirements.txt` identique ne prouve pas que les paquets installés
sont conformes. `scripts/release/ensure_dependencies.sh` vérifie aussi l'environnement
réel ; une dérive suit le chemin normal de sauvegarde et d'installation, sans
modifier les bornes du manifeste. La conformité est contrôlée avant de valider
l'empreinte. Le marqueur `.deployment-venv-backup` conserve la sauvegarde exacte
jusqu'à la réussite de toute la livraison : un échec tardif restaure aussi le venv
quand le manifeste n'a pas changé. Trois tests sur serveur factice couvrent la
réparation, l'absence d'installation inutile et la restauration après échec.

Le contrôleur importe le moteur **avant NumPy/pandas** pour appliquer la limite
BLAS définie dans `engine/__init__.py`. Un arrêt par signal (code >= 128) interrompt
la livraison sans réinstaller les paquets ; il ne doit pas être assimilé à une
version hors bornes. Régression couverte en processus isolé et sur installateur
factice. Le diagnostic ne publie que des catégories d'erreurs, jamais les messages
bruts, chemins privés ou versions des paquets.

## Barrières PR/main après audit

`validate_quality.sh`, `test_suite.sh` (blocs `integ i/n`) et `e2e_browser.sh` (groupes `core|pages|plan|portfolio`) sont les points d’entrée
communs aux deux workflows. Ruff, formatage, construction CSS synchronisée,
frontières Halo, tests non sautés et parcours actifs sont ainsi exécutés avant
fusion. Le workflow PR conserve contents:read et ne reçoit aucun secret de production.
L’exception de déploiement rapide reste explicite dans le workflow de main.

## Limite restant ouverte : publication atomique

Le verrouillage des dépendances et les restaurations appariées ne rendent pas
atomique le rsync actuel. Sa fenêtre de renommages reste possible ; les mesures
locales ne prouvent pas son comportement Hostinger. Une bascule de release doit
préserver les chemins des crons/hPanel, private/data/logs, le venv et les liens
public_html, puis être répétée avec requêtes et tâches concurrentes et retour arrière.
Cette évolution d’hébergement reste ouverte (A11) ; elle n’est pas assimilée à une
correction déjà livrée. Aucune garantie d’atomicité n’est ajoutée à la documentation.

Étude des options et critères de bascule : [RELEASE_ATOMICITY.md](RELEASE_ATOMICITY.md).
