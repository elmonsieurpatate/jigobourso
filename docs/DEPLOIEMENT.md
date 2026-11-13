# Déploiement automatique (GitHub Actions)

Chaque push normal sur `main` lance `.github/workflows/deploy.yml` en mode **avec tests** : contrôles de syntaxe PHP/Python/JavaScript, migrations additives, `tests/fast`, `tests/integ` (base jetable du runner), tests navigateur, puis `ops/deploy.sh` sur Hostinger.

Le lancement manuel propose `operation` (`diagnostic`, `deploy`, `rollback`) et `validation` (`full`, `quick`). L’opération par défaut reste `diagnostic` ; la validation par défaut reste `full`. Le déploiement est autorisé uniquement depuis `main`.

| Demande | Choix Actions | Comportement |
|---|---|---|
| Déploiement avec tests | `operation=deploy`, `validation=full` | Syntaxe puis tests complets GitHub, essai isolé Hostinger et vérifications financières/ETF avant mise en service |
| Déploiement rapide | `operation=deploy`, `validation=quick` | Syntaxe/migrations contrôlées ; pas de suites de tests complètes, diagnostic exhaustif des classements, répétition Hostinger ni vérifications exhaustives des calculs/ETF |
| Diagnostic / retour arrière | `operation=diagnostic` ou `rollback` | Contrôles courts, sans relancer les suites CI complètes ; procédure distante habituelle |

Dans **les deux modes de déploiement**, restent obligatoires : sauvegarde du code et des données financières, vérification de la conservation des transactions et comptes, migrations additives, import du moteur et syntaxe PHP distante, contrôles HTTP/version du site et retour arrière automatique du code en cas d’échec. Le recalcul dérivé demandé lorsqu’un moteur/schéma change reste détaché, comme auparavant. Le mode rapide n’a pas de durée garantie : transfert, dépendances ou migrations peuvent encore prendre du temps.

### Lancer le mode choisi

Depuis GitHub : Actions → **Jigobourso — déploiement Hostinger** → Run workflow → branche `main` → opération `deploy` → validation `quick` ou `full`.

Depuis la CLI, pour le commit déjà présent sur `main` :

```sh
# Déploiement rapide
gh workflow run deploy.yml --ref main -f operation=deploy -f validation=quick
# Déploiement avec tests
gh workflow run deploy.yml --ref main -f operation=deploy -f validation=full
```

**Nouveau commit à déployer rapidement :** inclure le marqueur `[deploy quick]` dans le message du commit poussé sur `main`. Le workflow exécute les contrôles courts puis déploie sans lancer les tests complets. Un push sans ce marqueur reste en mode complet. Ne pas utiliser `[skip ci]`, qui empêcherait le workflow de démarrer, et ne pas doubler le push par un lancement manuel.

L’environnement `production`, la concurrence exclusive et `cancel-in-progress: false` restent inchangés : un déploiement commencé n’est pas interrompu par une autre demande. Le résumé Actions indique le mode et si les tests complets ont été exécutés ou ignorés. Un test complet échoué, annulé ou sauté par erreur ne permet pas un déploiement normal ; seul le saut explicitement demandé en mode rapide (manuel ou marqueur de commit) est autorisé pour `deploy`.

Les nouveaux choix deviennent disponibles quand ce workflow est publié sur `main`. Modifier le fichier localement n’effectue aucun déploiement.

- Transmis : `app/ engine/ db/ docs/ scripts/ README.md requirements.txt`. Jamais touchés : `private/` (env, clé cron), `data/`, `logs/`, `.venv`, base de production, tâche cron hPanel.
- **Retour arrière automatique** : avant tout transfert, sauvegarde `tgz` du code distant (`.jigobourso-v2-code-backups/`, 5 dernières). Si une étape échoue après le début du transfert (dépendances, migration, import du moteur, `php -l`, contrôle public), le code est restauré depuis cette sauvegarde (`rsync --delete` sur les seuls dossiers de code) et le site est revérifié. Les données et secrets ne sont jamais concernés.
- **Retour arrière manuel** : Actions › « Jigobourso — déploiement Hostinger » › Run workflow › `rollback` (dernière sauvegarde), ou `ROLLBACK_BACKUP=<fichier>`.
- **Dépendances Python** : si `requirements.txt` change (empreinte `.requirements.sha`), le venv est sauvegardé (3 dernières copies) puis mis à jour. Le venv de production n'a pas `pip` (`ensurepip` indisponible) : le `pip` du système installe dans le venv (`--target`). Échec = retour arrière du code.
- **Schéma SQL** : `db/schema.sql` crée seulement les tables absentes et redéfinit les vues. Toute évolution d'une table existante passe par `db/migrations/AAAAMMJJ_nom.sql` (voir son README) : appliquée une seule fois (`schema_migrations`), ajouts seulement (`ADD COLUMN`, `CREATE INDEX`, `CREATE TABLE IF NOT EXISTS`) ; `DROP`, `DELETE`, `UPDATE`, `MODIFY`… sont refusés par le CI et par `scripts/migrate.py`. Avant une migration, dump complet de la base (`.jigobourso-v2-code-backups/db-*.sql.gz`, 3 dernières). Un retour arrière du code ne défait pas une migration (colonnes ajoutées ignorées par l'ancien code).
- Après transfert : import du moteur, `php -l`, puis contrôle public (accueil 200, version `?v=` servie, `api/auth/me`). Avant le transfert, le marqueur `?v=__BUILD__` de toutes les pages est remplacé par l'identifiant du déploiement. Le fichier `.deployed` (hors web) note commit et date.
- Secret requis : `HOSTINGER_SSH_PRIVATE_KEY` (environnement GitHub `production`). Clé d'hôte épinglée dans le workflow. Résultat publié sans secret sur la branche `deployment-status` (`status.json`, `deployment.log`).
- Lancement manuel : onglet Actions › `diagnostic` (lecture seule), `deploy` ou `rollback`.
- Le nettoyage des anciennes tables (V1, `codex_*`) a été fait à la main le 12/11/2026 (sauvegarde de 37 tables dans `~/backup-tables-obsoletes-20261112.sql.gz` sur le serveur) ; le script `drop_legacy_tables.sh` est retiré (tag `archive/v1-migration`).

# Mise en production et bascule (à exécuter seulement après accord explicite)

Ce document a été exécuté le 28/10/2026 (voir « Bascule effectuée »). Avant cela, la production actuelle (jigobourso.turnjoy.dev, base Hostinger) n'a été touchée qu'en **lecture seule** (export de vos comptes, portefeuilles et transactions).

## Bascule effectuée le 28/10/2026
- **Sauvegardes** (poste local, `migration/private/backup/`, droits 600, jamais versionnées) : dump complet de la base (229 Mo gz, 54 tables, vérifié) et copie de `public_html` (27 Mo).
- **Installation** : `domains/jigobourso.turnjoy.dev/jigobourso-v2/` (code, venv Python 3.9 + PyMySQL, `private/env` et `private/cron.key` en 600, `logs/`). Tables V2 créées à côté des anciennes (80 tables/vues au total, anciennes tables comptées avant/après : intactes). Données : catalogue, amorçage, nightly, tick, suivi reconstitué (30 jours), comptes migrés (1 compte, 2 portefeuilles, 7/7 transactions rattachées, contrôle conforme).
- **Mise en service** : `public_html/v2` est un lien vers `jigobourso-v2/app/public` ; le `.htaccess` racine réécrit toute la racine vers `v2/` (réécriture interne, URL inchangées). L'ancien code et les anciennes données restent sur le disque, non servis.
- **Cron** : la tâche hPanel appelle `api/cron` toutes les 5 minutes avec la clé dans l'en-tête (`wget -q -O /dev/null --header='X-Cron-Key: <clé>' https://…/api/cron`) (mesuré par le battement ; la collecte d'une place reste espacée de 15 minutes) ; V2 répond à cette même URL (même clé, copiée dans `private/cron.key`) et lance `engine.cli tick` en tâche de fond. Un garde-fou évite de refaire une collecte de 15 min si la précédente a moins de 12 minutes. Aucune modification hPanel nécessaire.
- **Retour arrière immédiat** : `cd public_html && cp -p .htaccess.legacy-20261028 .htaccess` (l'ancien site revient, ses tables sont intactes). Les transactions saisies dans V2 après la bascule seraient à reporter à la main.
- **Restent à faire** : observation 2 semaines, puis nettoyage des anciennes tables (après dump et accord) ; changer le mot de passe de test `jigo/jigo` ; retirer dans hPanel d'éventuelles anciennes tâches qui lanceraient `cron_scan.sh` ou `worker.py` (inutiles désormais).

## Répétition générale (faite le 28/10/2026, base jetable neuve)
Rejoue de zéro les étapes 2 à 6 ci-dessous, avec les vraies données Yahoo et votre export (lecture seule). Résultat : **toutes les étapes sans erreur, parcours e2e entièrement vert** (connexion, Explorer, fiche action et ETF, portefeuilles migrés, Suivi, bilan, administration, mobile).

| Étape | Durée mesurée (local) |
|---|---|
| Schéma (26 tables/vues) | 1 s |
| Catalogue (40 654 cotations) | 19 s |
| Amorçage : quotes, préfiltre, 3,9 M clôtures | ≈ 8 min |
| Migration comptes/portefeuilles/transactions (contrôle conforme à l'export) | 1 s |
| Premier `nightly` (métriques, suivi) | ≈ 2,5 min |
| Premier `tick` (clôtures de toutes les places + 15 min) | ≈ 3 min |
| Reconstitution du suivi (10 séances ; 30 séances ≈ 12 min) | ≈ 3 min |
| Base obtenue | ≈ 135 Mo hors 15 min (≈ 260 Mo au régime établi) |

Prérequis du serveur vérifiés en lecture seule : PHP 8.2, Python 3.9, MariaDB 11.8, disque libre très large. Le code est compatible 3.9 et 7.4+.

## Checklist de bascule (historique : V1 est abandonné, la V2 est en production)
Les anciennes tables (V1, `codex_*`) sont supprimées depuis le 12/11/2026 ; la base est descendue de 1 536 à 477 Mo. Cette checklist n'est plus à exécuter.

(Version d'origine, chaque case était réversible jusqu'à l'étape 7.)
Pré-requis : **accord explicite de l'utilisateur**. Durée totale prévue ≈ 45 min, dont ≈ 20 min d'amorçage ; pendant ce temps l'ancien site continue de fonctionner.

1. [ ] **Sauvegarde** : dump complet de la base actuelle vers le poste local (lecture seule), copie de `public_html`. Vérifier taille et ouverture du dump.
2. [ ] **Tables V2 à côté** : exécuter `db/schema.sql` (noms sans préfixe : aucune collision avec `jb_*`, `fdp_*`, `jy_*`). Vérifier : 26 tables/vues créées, anciennes tables intactes (comptage de lignes avant/après).
3. [ ] **Moteur** : copier `engine/` ; venv Python 3.9 avec `PyMySQL` seul ; variables `JIGO_DB_*` dans un fichier hors de la racine web (droits 600).
4. [ ] **Données** : `python -m engine.cli catalogue --source <clone>` ; `python scripts/bootstrap_real.py` ; `python -m engine.cli nightly` ; `python -m engine.cli tick` ; `python -m engine.cli suivi-backfill --sessions 30`. Contrôle : ≈ 40 650 cotations, ≈ 9 400 sélectionnées, ≈ 4 M clôtures, jobs `completed`.
5. [ ] **Vos comptes** : `python scripts/migrate_legacy.py <export>` (script archivé : `git show archive/v1-migration:scripts/migrate_legacy.py`) : contrôle « conforme à l'export », 7/7 transactions rattachées, mots de passe inchangés. Refuse si des comptes existent déjà.
6. [ ] **Site en parallèle** : `app/` sur un sous-domaine de test (même base). Lancer `tests/e2e/smoke.cjs` contre lui ; ouvrir à la main Explorer, une fiche ETF, Portefeuilles, Suivi.
7. [ ] **Bascule** : pointer le domaine sur `app/public` ; remplacer les 3 anciens crons par un seul `python -m engine.cli tick` toutes les 15 min. **Point de non-retour doux** : l'ancien code et l'ancienne base restent en place.
8. [ ] **Après bascule (J+0)** : le tick suivant se déroule (page Administration > Traitements) ; première nuit : nightly 02:00 UTC terminé, un instantané « vécu » dans Suivi.
9. [ ] **Observation 2 semaines**, puis nettoyage des anciennes tables seulement après dump, vérification et accord explicite. Changer le mot de passe de test `jigo/jigo`.

### Retour arrière
Avant l'étape 7 : supprimer les tables V2 (aucune table ancienne modifiée) ; rien d'autre à faire. Après l'étape 7 : remettre le domaine sur l'ancien code et rétablir les 3 anciens crons ; les anciennes données sont intactes. Les saisies faites dans V2 après la bascule (nouvelles transactions) seraient alors à reporter à la main : l'exporter avant (`scripts/export_user_data.py` adapté, ou CSV depuis Portefeuilles).

## Espace disque
Production actuelle : 2 320 Mo sur 3 072 Mo de quota base. V2 mesurée : ≈ 260 Mo au régime établi. Pic pendant la bascule ≈ 2 580 Mo : la marge suffit sans rien supprimer. Si l'espace devenait insuffisant : dump compressé des tables à supprimer vers le poste local (flux direct, rien d'écrit sur le serveur), vérification, puis seulement suppression des tables mortes (`fd_*`, `jb_catalogue_*`).

## Points d'attention
- Le premier `tick` après l'installation exécute les clôtures de toutes les places (≈ 3 min en local).
- Le catalogue se recharge depuis l'Administration (« Recharger le catalogue ») ou `python -m engine.cli catalogue`.
- Les identifiants de cotation changent (nouveaux ids) : la migration rattache les transactions par symbole ; tout titre non retrouvé reste affiché « sans cours » et signalé dans le rapport.
- Mot de passe de test `jigo/jigo` des anciens environnements : à changer (Mon compte).
