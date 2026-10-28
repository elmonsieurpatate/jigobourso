# Déploiement automatique (GitHub Actions)

Chaque push sur `main` lance `.github/workflows/deploy.yml` : syntaxe PHP/Python, `tests/fast`, `tests/integ` (base jetable du runner), puis `ops/deploy.sh` sur Hostinger.
- Transmis : `app/ engine/ db/ docs/ scripts/ README.md requirements.txt`. Jamais touchés : `private/` (env, clé cron), `data/`, `logs/`, `.venv`, base de production, tâche cron hPanel.
- Avant transfert : sauvegarde `tgz` du code distant (`.jigobourso-v2-code-backups/`, 5 dernières). Le schéma `db/schema.sql` n'est appliqué que s'il est purement additif (`CREATE … IF NOT EXISTS`) ; toute instruction `DROP/ALTER/DELETE…` bloque le déploiement : migration à faire à part, avec sauvegarde.
- Après transfert : dépendances Python si `requirements.txt` a changé, import du moteur, `php -l`, puis contrôle public (accueil 200, version `?v=` servie, `api/auth/me`). Le fichier `.deployed` (hors web) note commit et date.
- Secret requis : `HOSTINGER_SSH_PRIVATE_KEY` (environnement GitHub `production`). Clé d'hôte épinglée dans le workflow. Résultat publié sans secret sur la branche `deployment-status` (`status.json`, `deployment.log`).
- Lancement manuel : onglet Actions › « diagnostic » (lecture seule) ou « deploy ».
- `scripts/drop_legacy_tables.sh` n'est jamais appelé par le déploiement.

# Mise en production et bascule (à exécuter seulement après accord explicite)

Ce document a été exécuté le 28/10/2026 (voir « Bascule effectuée »). Avant cela, la production actuelle (jigobourso.turnjoy.dev, base Hostinger) n'a été touchée qu'en **lecture seule** (export de vos comptes, portefeuilles et transactions).

## Bascule effectuée le 28/10/2026
- **Sauvegardes** (poste local, `migration/private/backup/`, droits 600, jamais versionnées) : dump complet de la base (229 Mo gz, 54 tables, vérifié) et copie de `public_html` (27 Mo).
- **Installation** : `domains/jigobourso.turnjoy.dev/jigobourso-v2/` (code, venv Python 3.9 + PyMySQL, `private/env` et `private/cron.key` en 600, `logs/`). Tables V2 créées à côté des anciennes (80 tables/vues au total, anciennes tables comptées avant/après : intactes). Données : catalogue, amorçage, nightly, tick, suivi reconstitué (30 jours), comptes migrés (1 compte, 2 portefeuilles, 7/7 transactions rattachées, contrôle conforme).
- **Mise en service** : `public_html/v2` est un lien vers `jigobourso-v2/app/public` ; le `.htaccess` racine réécrit toute la racine vers `v2/` (réécriture interne, URL inchangées). L'ancien code et les anciennes données restent sur le disque, non servis.
- **Cron** : la tâche hPanel existante appelle `api/yahoo-history-cron?k=<clé>` toutes les 10 minutes ; V2 répond à cette même URL (même clé, copiée dans `private/cron.key`) et lance `engine.cli tick` en tâche de fond. Un garde-fou évite de refaire une collecte de 15 min si la précédente a moins de 12 minutes. Aucune modification hPanel nécessaire.
- **Retour arrière immédiat** : `cd public_html && cp -p .htaccess.legacy-20261028 .htaccess` (l'ancien site revient, ses tables sont intactes). Les transactions saisies dans V2 après la bascule seraient à reporter à la main.
- **Restent à faire** : observation 2 semaines, puis nettoyage des anciennes tables (après dump et accord) ; changer le mot de passe de test `jigo/jigo` ; retirer dans hPanel d'éventuelles anciennes tâches qui lanceraient `cron_scan.sh` ou `worker.py` (inutiles désormais).

## Répétition générale (faite le 28/10/2026, base jetable neuve, `scripts/rehearsal.sh`)
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

## Checklist de bascule (chaque case est réversible jusqu'à l'étape 7)
Pré-requis : **accord explicite de l'utilisateur**. Durée totale prévue ≈ 45 min, dont ≈ 20 min d'amorçage ; pendant ce temps l'ancien site continue de fonctionner.

1. [ ] **Sauvegarde** : dump complet de la base actuelle vers le poste local (lecture seule), copie de `public_html`. Vérifier taille et ouverture du dump.
2. [ ] **Tables V2 à côté** : exécuter `db/schema.sql` (noms sans préfixe : aucune collision avec `jb_*`, `fdp_*`, `jy_*`). Vérifier : 26 tables/vues créées, anciennes tables intactes (comptage de lignes avant/après).
3. [ ] **Moteur** : copier `engine/` ; venv Python 3.9 avec `PyMySQL` seul ; variables `JIGO_DB_*` dans un fichier hors de la racine web (droits 600).
4. [ ] **Données** : `python -m engine.cli catalogue --source <clone>` ; `python scripts/bootstrap_real.py` ; `python -m engine.cli nightly` ; `python -m engine.cli tick` ; `python -m engine.cli suivi-backfill --sessions 30`. Contrôle : ≈ 40 650 cotations, ≈ 9 400 sélectionnées, ≈ 4 M clôtures, jobs `completed`.
5. [ ] **Vos comptes** : `python scripts/migrate_legacy.py <export>` : contrôle « conforme à l'export », 7/7 transactions rattachées, mots de passe inchangés. Refuse si des comptes existent déjà.
6. [ ] **Site en parallèle** : `app/` sur un sous-domaine de test (même base). Lancer `tests/e2e/smoke.mjs` contre lui ; ouvrir à la main Explorer, une fiche ETF, Portefeuilles, Suivi.
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
