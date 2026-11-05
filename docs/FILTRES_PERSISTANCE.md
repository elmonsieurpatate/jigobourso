# Filtres secondaires : stockage et chargement

Cette étape conserve les interfaces Administration et Classement test validées. Elle raccorde leurs réglages au serveur PHP/MariaDB ; elle ne raccorde pas le filtrage des résultats boursiers et ne modifie aucun calcul, score, stratégie ou contrôle technique de sélection.

## Stockage unique

La table existante `settings` reçoit seulement deux documents JSON, de schéma 1 :

- `explorer_secondary_filters` : révision, 13 filtres, activation, neuf groupes de mesures éditables et leurs catégories ordonnées (identifiant, nom, explication, couleur, bornes, inclusivité, valeurs d’état, activation, inconnue).
- `explorer_secondary_defaults` : révision indépendante et sélection par défaut pour chaque mesure, ou pour les valeurs d’un filtre catalogue.

`mode: all` inclut toutes les catégories, inconnue comprise, ainsi que celles ajoutées ultérieurement. `mode: custom` conserve une liste explicite d’identifiants ; une liste vide signifie aucune sélection. Les choix de défauts ne modifient pas les définitions.

Les paramètres initiaux sont dans `app/config/explorer_secondary_filters.json`. Ils reprennent les propositions de la maquette, **pas des seuils financiers validés**. Les unités sont inchangées : volatilité quotidienne (%/séance), liquidité (€/jour), volume (titres/séance), proportions affichées en %, rendements par horizon et états distincts pour qualité/fraîcheur. Les mesures de concentration restent séparées.

Il n’y a aucune nouvelle table, migration de schéma, configuration de déploiement ou dépendance. Les clés historiques `explorer_growth`, `catalogue_rules`, `prefilter`, recherches, profils et préférences existants ne sont ni remplacés ni réinitialisés.

## Initialisation et restauration

La première lecture authentifiée initialise ces deux clés dans une transaction. Les lectures suivantes ne modifient ni leurs valeurs, ni leur révision, ni leur date si rien ne manque.

Le complément automatique porte sur les filtres, mesures ou champs structurels absents et leurs sélections initiales. Une liste de catégories existante, même vide, est conservée : **les catégories supprimées ne sont jamais recréées au redémarrage**. Une configuration de schéma incompatible n’est pas remplacée silencieusement.

Les catégories initiales ont des identifiants fixes. Les catégories ajoutées reçoivent un identifiant serveur aléatoire pérenne `cat-…`, renvoyé à l’interface puis conservé lors des éditions et déplacements.

« Restaurer les valeurs proposées » est une action explicite avec confirmation. Elle remet les définitions, l’activation et les défauts du **seul filtre sélectionné** aux propositions ; les autres filtres restent intacts. Pour un filtre catalogue, cela ne change aucune valeur du catalogue. « Tout inclure par défaut » restaure seulement sa sélection, sans toucher aux catégories.

## Routes et contrôle des écritures

- `GET admin/secondary-filters` : tous les filtres, y compris inactifs, avec valeurs catalogue réelles.
- `POST admin/secondary-filters/save` : action `save`, `defaults` ou `restore` ; accès administrateur et contrôle d’origine existant.
- `GET explorer/secondary-filters` : configuration de chargement accessible à l’utilisateur connecté.
- L’ancienne URL `classement-test/categories` délègue au même service, sans autre source de réglages en production.

Les sauvegardes sont transactionnelles, verrouillent les deux documents dans un ordre constant et vérifient une révision optimiste. Un onglet périmé reçoit un 409 au lieu d’écraser un autre enregistrement. L’interface conserve le brouillon et propose « Recharger les réglages ».

Le serveur revalide identifiants, noms, descriptions, types, couleurs, bornes, inconnues, domaines d’état et chevauchements. Les identités des filtres/mesures et les unités ne peuvent pas être changées par le client. Les valeurs des quatre filtres catalogue ne peuvent pas être ajoutées, supprimées ou renommées par cette API.

## Quatre filtres catalogue, en lecture seule

Les listes proviennent du catalogue **stocké**, sans téléchargement ni lancement du moteur :

| Filtre | Source et règle |
|---|---|
| Pays | `instruments.country`, sans en déduire une exposition géographique |
| Secteur | `instruments.category`, avec identifiant et libellé distinguant **secteur d’action** et **catégorie d’ETF** |
| Marché / Place | Valeurs effectivement présentes dans `listings.mic` |
| Type d’actif | Valeurs effectivement présentes dans `instruments.kind` ; le schéma actuel fournit actions/ETF, aucun OPCVM n’est inventé |

La valeur logique « Inconnu » représente l’absence de donnée. Elle n’est pas un pays, secteur, marché ou type synthétique. Les sources sont identiques quel que soit l’état actif du filtre. L’administration garde leur accès ; dans Classement test, chaque filtre actif apparaît une seule fois. Le masquage d’un contrôle ne désactive aucun garde-fou technique.

Les coches « Par défaut » sur ces lignes règlent seulement leur sélection initiale, pas leurs valeurs.

## Chargement dans Explorer et priorité

Le raccordement concerne la page validée `classement-test.html`. L’ancien Explorer et son moteur de classement sont conservés.

1. Charger la configuration serveur et ne présenter que les filtres actifs et catégories actives.
2. Sans choix local, appliquer les défauts administrateur ; initialement, tout est inclus.
3. Si un choix local existe, le conserver sur les identifiants encore disponibles. Une modification de libellé, couleur, description ou borne ne réinitialise pas ce choix.
4. Les nouvelles catégories suivent les défauts administrateur ; celles supprimées ne produisent pas de choix fantômes. Désactiver un filtre ne supprime pas ses préférences locales.

Ces choix utilisent le **localStorage déjà existant** `jigo_classement_test_v1`, sous `secondaryOverridesByUser` (isolés par identifiant d’utilisateur). La sauvegarde automatique des sélections ne sauvegarde pas implicitement les modifications de stratégie non enregistrées. Les sélections restrictives de l’ancienne maquette sont reprises lorsqu’elles peuvent être identifiées par leur mesure et leur libellé.

« Réinitialiser » retire les choix locaux et reprend les défauts administrateur. « Tout afficher » constitue un choix local explicite d’inclure toutes les catégories visibles ; cela n’écrit pas dans les défauts administrateur.

**À ce stade, changer ces sélections ne filtre pas les lignes boursières ni les exemples du tableau et ne modifie aucun score ou rang.** Le panneau le précise. Le compteur de masquage reste donc à zéro. Aucun second contrôle Pays/Place/Type n’a été ajouté dans l’ancien Explorer.

## Vérifications et utilisation locale

Ouvrir les pages servies par PHP, se connecter en administrateur, éditer une catégorie puis recharger. Tester sa désactivation, les coches de défauts et la restauration. Ouvrir Classement test avec une session utilisateur pour vérifier visibilité et priorité des choix locaux. Une base de développement isolée est requise pour ces essais.

L’export HTML autonome reste un **aperçu hors ligne explicitement signalé**, sans serveur ni vraie persistance. Il ne peut pas démontrer une sauvegarde MariaDB.

Tests ajoutés :

- `tests/e2e/secondary-persistence.php` : MariaDB réelle, idempotence, sauvegardes, IDs, ordre, défauts distincts, validation, conflits et conservation de l’existant.
- `tests/integ/test_secondary_filters.py` : intégration de ce scénario dans la suite existante.
- `tests/e2e/secondary-persistence-browser.cjs` : vrai serveur PHP et authentification, autorisations, rechargements, visibilité, catalogue, préférences par utilisateur, restauration et sauvegardes concurrentes ; contrôles visuels clair/sombre à 1280/390/375 px.

Les tests ont été exécutés sur un MariaDB privé sans écoute TCP et deux bases neuves (`jigobourso_filters_it` pour le parcours navigateur, `jigobourso_it` pour la suite d’intégration). Le serveur du parcours navigateur utilise un chemin Python volontairement inexistant : aucun accès au moteur financier n’est nécessaire au fonctionnement de ces réglages.

Aucune donnée de production, aucun push ni déploiement dans cette étape.

## Fichiers de cette étape

| Zone | Fichiers |
|---|---|
| Configuration proposée | `app/config/explorer_secondary_filters.json` |
| Stockage et validation PHP | `app/services/secondary_filters.php` |
| API | `app/routes/secondary_filters.php`, `app/public/api.php`, alias de compatibilité dans `app/routes/explore.php` |
| Administration existante | `app/public/admin-categories-test.html`, `app/public/assets/admin-categories-test.js`, `app/public/assets/admin-categories-test.css` |
| Adaptateur client | `app/public/assets/secondary-filter-store.js` |
| Chargement Explorer | `app/public/assets/classement-test.js`, `app/public/assets/classement-test-filters.js` |
| Export hors ligne | `scripts/export_classement_test.py` |
| Tests de persistance | `tests/e2e/secondary-persistence.php`, `tests/e2e/secondary-persistence-browser.cjs`, `tests/integ/test_secondary_filters.py`, `scripts/test_secondary_filters.sh` |
| Tests des maquettes adaptés | `tests/e2e/admin-categories-test.cjs`, `tests/e2e/classement-test.cjs`, `tests/e2e/classement-test-ranking.cjs`, `tests/e2e/classement-test-secondary.cjs` |
| Documentation | ce fichier, renvois ajoutés à `docs/ADMIN_CATEGORIES_TEST.md` et `docs/CLASSEMENT_TEST.md` |

## Commande de validation autonome

```sh
bash scripts/test_secondary_filters.sh
```

Ce lanceur exige PHP avec PDO MySQL, MariaDB, Node/Playwright, Chromium et Python. Il crée un répertoire temporaire neuf, une base sans écoute TCP et un serveur PHP local sur un port libre. Toutes les variables de connexion sont remplacées ; le fichier de configuration de l’application est ignoré. Il ne réutilise, ne supprime et ne réinitialise aucune base existante. Les services démarrés pour ce test sont arrêtés à la fin ; les rapports et captures sont conservés dans le répertoire temporaire indiqué.

### Résultats obtenus

- `make fast` : **354 tests réussis**, un avertissement de dépendance calendrier.
- Suite `tests/integ` dans la base neuve privée : **188 tests réussis**, avertissements de dépréciation existants.
- Test d’intégration ciblé rejoué avec portefeuille, transaction et cache de score à préserver : **1 réussi**.
- Parcours navigateur réel PHP/MariaDB : sauvegardes/rechargements, catégories/couleurs/descriptions, activation, défauts, préférences locales par utilisateur, restauration, autorisations et douze paires de sauvegardes simultanées (une acceptée, l’autre rejetée en 409 à chaque fois).
- Vérifications navigateur en clair/sombre : **1280, 390 et 375 px**, sans débordement de page.
- Validation PHP/JavaScript de syntaxe et `git diff --check` : réussies.
- Exports hors ligne Administration/Explorer : ouverture vérifiée, aucun appel API.

Aucun fichier de `engine/`, `db/schema.sql` ou `.github/` n’a été modifié par cette étape. Les tests ne constituent pas une validation en production ; aucun déploiement n’a été lancé.

### Incident de concurrence reproduit puis corrigé

Un essai répété a reproduit un interblocage InnoDB (1213) : l’initialisation prenait d’abord des verrous partagés via `INSERT IGNORE` sur les clés existantes, puis tentait de les promouvoir en verrous exclusifs. L’initialisation verrouille désormais les deux lignes directement en exclusif et dans un ordre fixe. Le cas d’une toute première insertion concurrente est repris uniquement après rollback, de façon bornée ; un conflit persistant est signalé en 409, sans remplacement des données.

Après correction : douze paires de sauvegardes concurrentes réelles ont donné chacune 200/409 ; quatre initialisations simultanées, avant création des clés, ont toutes retourné les 13 filtres. Le test d’intégration ciblé a été rejoué après correction. La suite complète de 188 tests avait également réussi avant ce dernier correctif localisé au nouveau service.
