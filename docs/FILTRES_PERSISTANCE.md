# Filtres secondaires : stockage et chargement

Cette étape conserve les interfaces Administration et Classement test validées. Elle raccorde leurs réglages au serveur PHP/MariaDB ; elle ne raccorde pas le filtrage des résultats boursiers et ne modifie aucun calcul, score, stratégie ou contrôle technique de sélection.

## Stockage unique

La table existante `settings` reçoit seulement deux documents JSON, de schéma 1 :

- `explorer_secondary_filters` : révision, 13 filtres, activation, neuf groupes de mesures éditables et leurs catégories ordonnées (identifiant, nom, explication, couleur, bornes, inclusivité, valeurs d’état, champ historique d’activation conservé pour compatibilité, inconnue).
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

Les valeurs brutes du catalogue **stocké** sont affectées à des groupes en lecture seule, décrits dans la section « regroupements v2 » ci-dessous. Aucun téléchargement ni lancement du moteur n’est requis.

| Filtre | Source |
|---|---|
| Zone géographique | `instruments.country`, pas la cotation ni l’exposition du portefeuille |
| Secteur | `instruments.kind` + `instruments.category`, tables distinctes actions/ETF |
| Marché / Place | Codes réellement présents dans `listings.mic` |
| Type d’actif | `instruments.kind` ; deux types pris en charge : actions/ETF |

Inconnu représente une donnée absente/non localisable ; le type d’actif n’a pas de troisième catégorie artificielle. Chaque filtre actif apparaît une seule fois dans Classement test. L’administration conserve les filtres inactifs et le masquage d’un contrôle ne désactive aucun garde-fou technique.

Les coches « Par défaut » sur ces lignes règlent seulement leur sélection initiale, pas leurs valeurs.

## Chargement dans Explorer et priorité

Le raccordement concerne la page validée `classement-test.html`. L’ancien Explorer et son moteur de classement sont conservés.

1. Charger la configuration serveur et ne présenter que les filtres actifs, avec toutes leurs catégories.
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

- `tests/php/secondary-persistence.php` : MariaDB réelle, idempotence, sauvegardes, IDs, ordre, défauts distincts, validation, conflits et conservation de l’existant.
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
| Tests de persistance | `tests/php/secondary-persistence.php`, `tests/e2e/secondary-persistence-browser.cjs`, `tests/integ/test_secondary_filters.py`, `scripts/test_secondary_filters.sh` |
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

## Correction des métadonnées : regroupements v2

Les quatre filtres en lecture seule utilisent désormais des **groupes stables**, pas une liste des valeurs brutes. La définition est dans `app/config/secondary_metadata_groups.json` ; les neuf groupes financiers et leurs personnalisations ne changent pas. Aucun calcul ni filtrage des résultats boursiers n’est raccordé par cette correction.

| Filtre | Groupes / identifiants stables |
|---|---|
| Zone géographique | États-Unis (`country:us`), Europe (`country:europe`), Pays émergents (`country:emerging`), Autres (`country:other`), Inconnue (`unknown`) |
| Secteur | Technologie, Finance, Santé, Industrie, Consommation, Énergie, Matériaux, Services publics, Immobilier, Communication, Autres (`sector:…`), Inconnu (`unknown`) |
| Marché / Place | Marchés américains (`market:us`), européens (`market:europe`), émergents (`market:emerging`), Autres marchés (`market:other`), Inconnu (`unknown`) |
| Type d’actif | Actions (`asset:equity`), ETF (`asset:etf`), uniquement |

Les groupes restent disponibles même si leur effectif est nul. Ce sont des **catégories**, pas des pays, des types ou des cotations inventés. Les effectifs et affectations sont obtenus exclusivement à partir du catalogue stocké. Tous les 13 filtres sont actifs et toutes leurs catégories incluses sur une installation neuve ; une activation ou sélection préexistante n’est jamais réinitialisée.

### Politique géographique explicite

- Source instrument : `instruments.country`, jamais le MIC, la devise ou le symbole. Pour un ETF, le pays stocké est son rattachement/domicile fourni par le catalogue, **pas l’exposition de ses participations**. Les limites de l’import existant ne sont pas corrigées ici.
- Alias de pays : snapshot des 249 entrées ISO 3166-1 fourni par `iso-codes` (noms anglais/français, noms officiels/courants, codes alpha-2/alpha-3), plus alias courants explicites. Aucun appel réseau au chargement. Fichier source de génération local : `/usr/share/iso-codes/json/iso_3166-1.json` et traduction française `iso_3166-1` ; la table générée est versionnée dans le dépôt.
- Ordre : États-Unis, puis **Europe**, puis **émergents**, puis Autres. Europe correspond à l’Europe UN M49, avec Chypre (UE) et Kosovo ajoutés explicitement. Cela inclut Royaume-Uni, Norvège, Suisse et Russie ; cela n’affirme aucune négociabilité.
- La liste émergente de référence est celle des 24 marchés MSCI EM de 2024 : Brésil, Chili, Chine, Colombie, Tchéquie, Égypte, Grèce, Hongrie, Inde, Indonésie, Corée du Sud, Koweït, Malaisie, Mexique, Pérou, Philippines, Pologne, Qatar, Arabie saoudite, Afrique du Sud, Taïwan, Thaïlande, Turquie, Émirats arabes unis. **Tchéquie, Grèce, Hongrie et Pologne sont classées Europe**, par priorité géographique. Cette politique est un regroupement pratique, pas la reproduction d’un indice en temps réel. Canada, Japon, Australie, Hong Kong et Singapour vont dans Autres.
- Un pays non vide et non reconnu va dans Autres avec motif `unmapped-country` et valeur brute conservée. Une absence ou sentinelle explicite (`unknown`, `n/a`, etc.) va dans Inconnue. Aucun pays non vide n’est abandonné.
- Sources documentaires : [ISO 3166](https://www.iso.org/iso-3166-country-codes.html), [UN M49](https://unstats.un.org/unsd/methodology/m49/), [MSCI Market Classification](https://www.msci.com/our-solutions/indexes/market-classification). Référentiels figés pour rendre le résultat déterministe ; pas de prétention à une actualisation automatique.

### Places et secteurs

La table MIC est distincte du pays instrument, fondée sur la localisation de la place ([ISO 10383](https://www.iso20022.org/market-identifier-codes)). Elle couvre notamment **toutes les places nommées dans `engine/catalogue/rules.py::MARKET_NAMES`**. Les affectations utilisent seulement les codes effectivement rencontrés dans `listings.mic` ; on ne déduit jamais un pays d’un préfixe MIC. Exemple : entreprise française cotée sur XNAS → instrument Europe, cotation Marchés américains. XSHG → émergents ; XHKG → Autres marchés. Un MIC absent ou non mappé va dans Inconnu, avec valeur brute et motif `unmapped-mic` conservés ; il n’est pas arbitrairement déclaré américain ou européen.

Pour les actions, la table explicite des grandes familles est proche des 11 familles GICS : `Consumer Cyclical`, `Consumer Defensive`, `Consumer Discretionary` et `Consumer Staples` → Consommation ; `Financial Services`/`Financials` → Finance, etc. Les catégories d’ETF sont traitées par une **autre table**, et non par réutilisation automatique du secteur action. Seuls les libellés sectoriels explicitement reconnus (ex. `Sector Equity Technology`, `Technology`) reçoivent une famille. Un ETF large `Equity`, obligataire `Bond`, ou une catégorie non sectorielle/non reconnue va dans Autres ; l’absence de catégorie va dans Inconnu. Ce regroupement n’invente pas une analyse des participations du fonds.

L’API ajoute `catalogue_mapping` : pour chaque valeur brute rencontrée, type éventuel, effectif, groupe et motif. Les valeurs ambiguës restent ainsi auditables. `metadata_mapping` fournit le même référentiel au migrateur local du navigateur ; les tests vérifient la concordance PHP/JavaScript. Un type d’actif autre que les deux types du schéma est signalé `unsupported`, jamais présenté comme une troisième option.

### Migration contrôlée et préférences

Aucune nouvelle table ni troisième clé `settings`. Les documents conservent leur schéma 1 et reçoivent `metadata_version: 2`.

1. Sous les deux verrous de lignes existants, migrer une seule fois les identités en lecture seule. Conserver leur état actif/inactif et toutes les catégories et valeurs financières.
2. Traduire chaque ancien identifiant de pays, MIC ou secteur vers son groupe. Fusionner les doublons par union. `all` reste `all` ; `custom: []` reste vide. Les nouveaux groupes ne sont pas automatiquement ajoutés à une sélection restrictive.
3. Archiver les anciennes définitions et sélections dans `metadata_migration.previous`, à l’intérieur des deux documents existants. Les changements produisent des `migration_notices` visibles dans la zone d’information administrative existante.
4. L’élargissement France → Europe est inévitable avec les nouvelles catégories : il est **signalé**, sans prétendre conserver une restriction pays par pays. Aucune règle résiduelle cachée « France seulement » n’est conservée.
5. L’ancienne option artificielle de type « unknown » disparaît. Si elle était seule sélectionnée, inclure les deux types pris en charge et signaler la migration ; si des types connus étaient sélectionnés, les conserver. Les anciennes données restent archivées.
6. Migrer aussi les choix locaux **par utilisateur**, prioritaires sur les défauts administrateur. Archiver leurs anciens `selected`/`known` dans `secondaryMetadataPreviousByUser`, dans le même document local existant. Les groupes nouvellement définis sont marqués connus pour éviter qu’ils rejoignent silencieusement une préférence restrictive. L’avis reste présent dans le texte du panneau de filtres ; l’enregistrement du profil conserve l’archive.
7. Après migration, aucun nouveau démarrage/rechargement ne réécrit les choix. La restauration explicite reste ciblée sur le filtre choisi et remet son activation et ses défauts à tout inclus.

Pour examiner les anciennes préférences, consulter ces archives dans les deux documents. Un retour à l’ancien code ne doit pas consommer directement les identifiants regroupés : une restauration de configuration doit rétablir explicitement les anciennes sélections archivées. Aucune restauration automatique ni migration destructive n’est exécutée.

### Validation et limites du catalogue

L’inspection en lecture seule d’une copie jetable de `/workspace/jigo-tools/db` a trouvé **0 instrument dans le catalogue local `jigobourso_v2`**. Aucun accès à la production n’a été utilisé. Il serait donc incorrect d’affirmer avoir validé les valeurs réellement présentes en production. Les codes de places définis dans le dépôt sont tous couverts ; les valeurs brutes absentes de la table sont signalées par le diagnostic plutôt que perdues.

La validation utilise des fixtures déclarées synthétiques (France/XPAR et double cotation XNAS, ETF large, métadonnées absentes), les alias ISO figés et des tests sans réseau. Le catalogue réel devra être contrôlé ultérieurement avec `catalogue_mapping`, en lecture seule et avec autorisation d’accès appropriée. Aucune initialisation ni migration n’a été lancée en production.


### Résultats des commandes exécutées pour cette correction

- `make fast PY=/workspace/jigobourso/.venv/bin/python` : **445 passed**, un avertissement préexistant de calendrier.
- `python -m pytest tests/integ -q`, sur une nouvelle instance MariaDB sans réseau, base jetable `jigobourso_it` : **194 passed**, 958 avertissements de dépréciation préexistants, 161,54 s. Rapport : `/tmp/jigo-metadata-integ.HnTmwN/results.log`.
- `bash scripts/test_secondary_filters.sh` : PHP/MariaDB réel et Chromium, **réussi**. Initialisation complète 13/9/4, migration des quatre métadonnées, archives, activation, défauts, rechargement, restauration, conflits concurrents, maintien des préférences par utilisateur, absence de modification des scores/rangs et doubles cotations.
- Le test rapide `test_secondary_metadata.py` exécute les implémentations PHP et JavaScript sur tous les alias ISO livrés ainsi que 32 cas explicites. Régression couverte : `NA` est bien la Namibie, pas une absence de donnée.
- Navigateur réel : **1280, 390, 375 px**, clair et sombre, aucun débordement horizontal. Captures supplémentaires du filtre géographique en lecture seule : `/tmp/jigo-secondary-tests.zxYZGT/browser/metadata-*.png`. Rapport navigateur : `/tmp/jigo-secondary-tests.zxYZGT/browser/results.json`.
- Aperçu statique : `node tests/e2e/admin-categories-test.cjs` sur serveur local, **8 configurations réussies** (1600/1280/390/375 px, clair/sombre). Il utilise aussi les nouveaux groupes et seulement Actions/ETF.
- `node tests/e2e/classement-test-secondary-logic.cjs`, `node tests/e2e/admin-categories-model.cjs`, `php tests/php/classement-test-categories.php` : **réussis**.
- Syntaxe PHP, JavaScript et `git diff --check` : **réussis**. Comparaison des neuf définitions financières avec le commit de départ : **strictement identiques**.

Lors de ces validations préalables : aucun push, déploiement, changement du moteur financier, des stratégies, des scores ou du schéma SQL. Les migrations de préférences n’ont été exécutées que sur les bases et navigateurs isolés de test.

### Fichiers modifiés / ajoutés

- `app/config/explorer_secondary_filters.json`
- `app/public/admin-categories-test.html`
- `app/public/assets/admin-categories-demo.js`
- `app/public/assets/admin-categories-test.js`
- `app/public/assets/classement-test-filters.js`
- `app/public/assets/classement-test.js`
- `app/public/assets/secondary-filter-store.js`
- `app/services/secondary_filters.php`
- `docs/FILTRES_PERSISTANCE.md`
- `scripts/test_secondary_filters.sh`
- `tests/e2e/admin-categories-model.cjs`
- `tests/e2e/admin-categories-test.cjs`
- `tests/e2e/secondary-persistence-browser.cjs`
- `tests/php/secondary-persistence.php`
- `tests/integ/test_secondary_filters.py`
- `app/config/secondary_metadata_groups.json`
- `app/services/secondary_metadata.php`
- `tests/php/secondary-metadata-persistence.php`
- `tests/e2e/secondary-metadata.cjs`
- `tests/php/secondary-metadata.php`
- `tests/fast/test_secondary_metadata.py`


## Activation des filtres, sélection des catégories

Seul le filtre possède un état actif/inactif. La colonne de statut des catégories et leur commande d’activation ont été retirées. Toutes les catégories restent visibles dans Explorer, y compris celles qui portent un ancien champ `active: false`. Ce champ est conservé uniquement pour la compatibilité des documents historiques ; il ne masque plus rien et ne dispense plus de la validation des bornes.

Les anciennes catégories masquées sont converties une seule fois en catégories visibles mais non sélectionnées dans les défauts administrateur. Cette migration dans `explorer_secondary_defaults` conserve les choix initiaux dans `category_selection_previous`, puis pose `category_selection_version: 1`. Les nouvelles configurations incluent toutes les catégories. Les choix locaux continuent à primer sur les défauts administrateur. Des bornes historiques qui se chevauchent restent conservées et sont signalées pour correction, pas supprimées automatiquement.

Le déploiement Quick conserve les deux menus séparés. `scripts/release/check_secondary_catalogue.php` vérifie en lecture seule les données réellement stockées sur la cible : chaque instrument et chaque cotation doivent recevoir un groupe explicite. Les replis vers Autres/Inconnu sont comptés sans modifier le catalogue ni initialiser les réglages. Le contrôle public des pages et des droits API reste obligatoire.
