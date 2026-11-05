> Le chargement persistant des 13 filtres est décrit dans [FILTRES_PERSISTANCE.md](FILTRES_PERSISTANCE.md). Le filtrage des résultats n’est pas raccordé à cette étape ; les descriptions des anciens filtres fictifs ci-dessous concernent l’aperçu hors ligne.

# Classement test — prototype indépendant

Ouvrir `classement-test.html` après connexion, ou l’entrée **Classement test** du menu.
Le prototype réutilise seulement la navigation, l’authentification et le thème communs.
L’Explorer existant, ses préférences, ses appels API et les calculs financiers sont inchangés.

## Interactions

- Simple : sélectionner une période pour voir ses deux réglages ; la case active/désactive cette période sans effacer ses valeurs. Pente exprimée en %/séance, R² entre 0 et 1.
- Expert : véritable constructeur de règles, chaque ligne avec menus indicateur/opérateur/période et valeur numérique. Groupes ET/OU imbriqués (jusqu’à quatre niveaux ajoutables), ajout et suppression de règles et groupes, aperçu de l’expression. Les minimums pente/R² sont synchronisés avec le mode Simple. Une combinaison non représentable (OU entre périodes, opérateur différent, paire incomplète ou doublons) est conservée et signalée ; les curseurs simples sont alors verrouillés pour ne pas réécrire sa logique.
- Changer de profil conserve les réglages déjà édités dans chacun des trois profils de démonstration.
- Filtres secondaires : même bloc compact repliable dans les deux modes ; six indicateurs principaux, autres indicateurs repliés. Chaque indicateur ouvre une liste multisélection recherchable avec bornes en lecture seule, compteur et sélection globale. OU entre catégories, ET entre indicateurs. Toutes les catégories, y compris « inconnu » si configuré, sont initialement incluses. Zéro catégorie sélectionnée signifie aucune catégorie incluse pour ce filtre. Échap ferme la liste et restitue le focus ; les listes passent dans le flux sur mobile.
- Colonnes configurables, 30 lignes fictives explicitement signalées ; tri, pagination, mini-courbes et fiches de démonstration. Aucun accès au moteur ou à des cotations réelles.
- « Appliquer les réglages » confirme uniquement l’état du formulaire, sans calcul ni requête réseau et sans modifier les lignes fictives. « Enregistrer sur cet appareil » sauvegarde explicitement l’état sous `jigo_classement_test_v1` ; aucune configuration serveur ni préférence de l’Explorer n’est écrite.

## Valeurs illustratives

Croissance rapide : semaine et mois actifs, pente 0,08 %/séance. Croissance régulière : mois et trimestre actifs, pente 0,05 %. Croissance calme : mois, trimestre et six mois actifs, pente 0,03 %. R² initial de base respectif 0,65 / 0,80 / 0,85, augmenté de 0,025 par horizon, plafonné à 0,99. Ces profils n’interprètent pas les configurations du moteur.

La pente du prototype est réglable de 0,01 à 2 %/séance et le R² de 0 à 1. Ces limites concernent uniquement ce formulaire. Les catégories ne sont plus définies dans le JavaScript du formulaire : voir la provenance ci-dessous. Elles ne classent aucune donnée réelle à ce stade.

L’illustration SVG suit les valeurs, sans bibliothèque externe ; ce schéma pédagogique ne constitue ni une régression chiffrée réelle ni un historique de marché. Aucun ajout de bibliothèque de règles n’est nécessaire pour ce périmètre limité.

## Validation locale

Servir `app/public` sur `127.0.0.1:18121`, puis lancer :

```sh
node tests/e2e/classement-test.cjs
```

Playwright et Chromium (`/usr/bin/chromium`) sont requis. `PLAYWRIGHT_MODULE`, `BASE` et `AUDIT_OUT` peuvent être précisés. Le test simule seulement les lectures de session et de la navigation des portefeuilles ; aucune base n’est utilisée. Il refuse tout appel API autre que ces lectures.

Scénarios exécutés en 1440, 1280, 1024, 850, 768, 390 et 375 px : valeurs propres à chaque période ; synchronisation dans les deux sens ; activation distincte de la sélection ; conservation des règles avancées ; indépendance des profils ; multisélection ; colonnes ; sauvegarde/rechargement ; largeur du SVG ; absence de débordement de page ; absence de calcul, d’écriture API et de modification des préférences Explorer.

Cette validation couvre l’interface isolée, pas une connexion réelle au serveur PHP ni un classement financier. Aucun déploiement n’est effectué.

## Export sans serveur

```sh
python3 scripts/export_classement_test.py /tmp/classement-test.html
```

Le fichier embarque ses styles et scripts et remplace uniquement la session par une session d’aperçu locale. Aucun appel API, cours ou calcul financier. Dans le constructeur, les menus et les groupes fonctionnent comme dans la page hébergée. Le bouton Backtest est explicitement désactivé ; Gestion des filtres ouvre les filtres secondaires et Requêtes donne accès à la sauvegarde locale, sans simuler des services serveur.

## Catégories : administration en lecture seule

`GET api.php?r=classement-test/categories` (session requise) retourne uniquement les catégories de `settings.explorer_growth`, si ce réglage existe. Aucun réglage n’est écrit, aucun score n’est recalculé. Sur la branche de reprise `2ba67ac`, l’administration V4 n’est pas intégrée : en l’absence du réglage, la source est explicitement « proposée » et utilise `app/config/classement_test_categories.json`, instantané des 17 indicateurs de `growth.defaults()` du commit V4 référencé dans ce JSON. Ce n’est pas une lecture de la production.

Les noms, bornes, unités, couleurs et catégorie inconnue sont repris de cette configuration. Les intervalles respectent sa convention : borne basse exclue, borne haute incluse. Aucune édition de bornes, couleurs ou seuils de catégories dans Explorer. Une configuration fournie invalide est signalée, sans la remplacer silencieusement. Le fichier autonome embarque l’instantané, indiqué « aperçu hors ligne » ; il ne peut pas suivre des modifications de l’administration distante sans nouvel export.

Les sélections personnelles sont sauvegardées avec l’empreinte de la configuration. Si cette dernière change, toutes les catégories sont réincluses pour éviter d’interpréter d’anciens identifiants avec de nouvelles bornes. Les défauts restrictifs éventuels de l’administration ne sont pas appliqués à ce prototype : ouverture initiale « tout inclus », conformément à la demande.

`classement-test-filters.js` contient seulement le masquage de lignes déjà classées. Les tests utilisent des objets gelés et vérifient la conservation des scores, des rangs, de l’ordre et de l’identité des lignes. Depuis la demande de démonstration du classement, 30 lignes fictives sont affichées. Le compteur indique exactement le nombre de ces lignes masquées par les sélections ; il ne représente jamais un univers de marché réel.

## Vérifications complémentaires

```sh
node tests/e2e/classement-test-secondary-logic.cjs
php tests/e2e/classement-test-categories.php
node tests/e2e/classement-test-secondary.cjs
```

Le test PHP porte sur l’adaptateur pur sans connexion DB. Le test navigateur simule la réponse de lecture des catégories administrateur, avec des valeurs différentes de l’instantané pour vérifier leur prise en compte ; il couvre les deux thèmes, les largeurs 1440/1024/390/375 px, les listes et leur recherche, les catégories inconnues, le reset global, la conservation entre modes, l’absence d’éditeur numérique/couleur et de débordement. Le motif répété en thème sombre était causé par l’interaction entre le fond des sélecteurs et leur image SVG ; répétition, taille et position sont désormais explicites, y compris après export autonome. Accents violets, couleurs propres aux catégories conservées telles que configurées.

## Classement fictif interactif

`assets/classement-test-demo.js` fournit 30 lignes déterministes, explicitement fictives, avec des noms de sociétés réelles pour tester la lisibilité. Aucun prix, rendement, score ni tracé ne constitue une donnée de marché. Les mini-courbes, scores et indicateurs sont des illustrations indépendantes, pas les sorties d’une régression financière. Le score n’est pas recalculé à partir des réglages de stratégie.

- Classement initial par score décroissant ; le numéro indique le rang initial et reste stable après filtrage ou tri d’affichage.
- Pagination 10/20/50 lignes avec compteurs exacts sur les 30 exemples, pas un univers artificiel de plusieurs milliers de titres.
- Tris depuis les en-têtes ou le sélecteur, ascendant/descendant, valeurs inconnues en dernier, égalités départagées par le rang initial.
- Colonnes affichables/masquables, identité du titre toujours visible ; vue compacte adaptée au mobile sans défilement horizontal du tableau.
- Détails ouverts par les points de suspension, sans achat, vente ou navigation vers une fiche réelle.
- Filtres secondaires appliqués aux catégories des exemples, selon les bornes de configuration lues ; score, métriques, rang initial et série d’origine restent immuables. Seule la sélection des lignes change.
- Saisie de règles, changement de profil, bouton Appliquer et changement Simple/Expert ne recalculent ni ne reclassent les exemples. Un changement de mode préserve la page de résultats courante.

Validation : `node tests/e2e/classement-test-ranking.cjs`. Ce test vérifie les deux thèmes en 1440/1280/390/375 px, les pages, les tris, les valeurs inconnues, les colonnes, les détails, l’indépendance du formulaire, le masquage et son compteur, la conservation des scores/rangs et le retour depuis une sélection vide. Les seules routes simulées sont les lectures de session, de navigation et de catégories ; aucune donnée de production.
