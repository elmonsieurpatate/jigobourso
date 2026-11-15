# Organisation des tests

Les tests Python sont dans `tests/fast` et `tests/integ`, les services PHP dans
`tests/php`, les données synthétiques dans `tests/seeds`. Les `.cjs` ci-dessous
sont soit des parcours Chromium, soit des modèles exécutables sous Node.

## Recette active commune aux PR et à main

Point d’entrée : `scripts/e2e_browser.sh` (`make e2e` initialise d’abord la base
jetable). Aucun de ces scénarios ne doit viser la production. Ils tournent en série,
car les seeds réinitialisent `jigobourso_it`. Le runner conserve un journal par étape.

| Seed / préparation | Parcours | Ce qu’il vérifie |
|---|---|---|
| account_seed, etf_seed, comptes synthétiques | personal-filters | définitions personnelles, options, restauration, indépendance des comptes et des stratégies |
| mêmes données | scores-preview | panne 503 d’aperçu, absence de boucle, reprise explicite et rendu/tri des scores |
| mêmes données | financial, keyboard, title-layout | recherche explicite, fiche, ETF, portefeuille, administration, clavier et disposition mobile |
| mêmes données | strategies-ui | édition, changement et sauvegarde des stratégies |
| mêmes données, en dernier dans ce groupe | account-navigation | inscription, compte, vérification e-mail et récupération ; provoque des refus de connexion volontaires |
| plan_suivi_seed | plan-suivi | conseils et protections chiffrés, règles personnelles, indépendance des positions, thèmes, 320–1440 px |
| split_review_seed | split-reviews | décision, ratio erroné, refus/réexamen, audit, idempotence, droits, mobile |
| portfolio_audit_seed | portfolio-v5 | zones, périodes, graphiques, détail, surveillance, 320–1440 px |

Avant ces parcours : galerie de référence dans quatre contextes, contrastes et
contrats de toutes les classes utilitaires. Ces contrôles ne remplacent pas Safari
ni un appareil physique. Les scénarios simulent le navigateur sur données de test.

## Classement des autres fichiers

- Modèles sans navigateur : `core`, `explorer-model` (inclut restauration/migrations),
  `secondary-metadata` sont appelés par pytest. `admin-categories-model`,
  `classement-test-secondary-logic`, `day-granularity`, `explorer-render` et
  `strategy-status` sont des sondes Node complémentaires ; ce ne sont pas des
  parcours oubliés dans le runner navigateur.
- Anciennes recettes d’interfaces : `classement-apply`, `classement-test`,
  `classement-test-mobile`, `classement-test-secondary`, `columns-admin`,
  `portfolio-audit`, `portfolio-neutral`, `smoke`, `admin`, `core-interactions`.
  Elles ciblent notamment l’ancien explorateur, d’anciens sélecteurs ou des
  démarrages automatiques. Les contrats actifs sont vérifiés par la recette
  ci-dessus et les tests API ; lancer ces anciennes recettes sans adaptation ne
  constitue pas une validation de l’interface actuelle.
- `admin-categories-test` utilise le prototype hors ligne (`JigoSecondaryOffline`)
  et autorise seulement deux routes simulées : il ne valide pas les filtres
  personnels actuels. `secondary-persistence-browser` vise l’ancien éditeur de
  filtres partagés et des comptes de recette distincts. Le parcours actuel de
  définitions personnelles est `personal-filters`, avec API réelle.

Ces scripts historiques restent consultables ; aucune case de validation courante
ne s’appuie sur leur seule présence. Leur suppression exige de conserver les
assertions métier qui ne seraient pas déjà couvertes ailleurs.
