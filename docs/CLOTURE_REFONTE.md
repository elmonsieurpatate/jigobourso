# Clôture des reliquats de refonte — 15 novembre 2026

## Périmètre et point de départ

Reprise de `origin/main` **7a55926**, sur `chore/cloture-refonte-20261115`.
La branche locale antérieure et ses changements ont été préservés dans leur
worktree. Aucun push, fusion, déploiement ou accès aux données de production.
Le design Halo existant est conservé. Le travail ci-dessous termine les
reliquats concrets signalés ; il ne remplace pas l'audit initial par une
promesse que tout le logiciel est parfait.

## Changements vérifiables

- [x] Palette de données : séries et lignes adaptées au thème dans `halo.css` ;
      jauge centralisée, sens et positions des seuils conservés ; catégories
      personnelles inchangées. Suppression des palettes dupliquées dans les
      deux scripts consommateurs. Voir `DESIGN_HALO.md`.
- [x] Contrastes : navigation claire et lignes de graphiques corrigées ;
      196 paires contrôlées par Chromium en clair/sombre (4,5:1 texte, 3:1 séries).
      Les couleurs personnelles arbitraires restent hors de cette garantie.
- [x] Espacement des sections de carte : primitive `.card-stack`, jeton
      `--card-gap` de 12 px, repris par cartes de splits, suivi et aide latérale
      d'édition. Pas de nouvelle feuille de surcharges. Les espacements propres
      aux lignes d'actions ou grilles ne sont pas artificiellement uniformisés.
- [x] Parité utilitaire : toutes les **63 classes actuellement définies**,
      756 comparaisons navigateur (2 largeurs × 2 thèmes × 3 contextes de cascade).
      La sonde conserve les styles inline préexistants et ne masque plus une
      navigation échouée. Les classes rencontrées dans les vraies pages sont
      comptées séparément ; ce test synthétique n'est pas présenté comme un
      parcours de tous les états dynamiques.
- [x] Police stable et compatible CSP : Space Grotesk et licence OFL locales,
      retrait de l'import Google bloqué par `style-src 'self'`. Captures après
      chargement des polices. Référence visuelle régénérée pour ces changements
      intentionnels, puis comparée sans mise à jour.
- [x] Test SQL fragile : compteur réservé à un utilisateur MariaDB temporaire,
      indépendant des healthchecks et autres clients. Test de non-contamination
      ajouté ; seuils de coût conservés. Configuration et utilisateur restaurés
      dans le nettoyage du fixture.
- [x] Contrôles de clôture intégrés : `make visual` vérifie galerie, contrastes,
      utilitaires ; la CI complète l'exécute. Les parcours clavier, tactile émulé et responsive titre rejoignent les e2e.

- [x] Fiche titre mobile : suppression d'un utilitaire en `!important` qui
      bloquait la colonne unique. Disposition responsive entièrement en CSS,
      y compris après redimensionnement. Test sur 320/390/768/900/901/1280 px,
      clair et sombre. Ancien style JavaScript et utilitaire supprimés.
- [x] Aide : retrait des règles `.hs` redondantes de `base.css`, qui écrasaient
      la couleur des repères numérotés. Encre des icônes adaptée aux fonds pastel.

## Échec CI historique : ce que l'on sait

Run **43674098867**, job **132690412519**, commit `d0c6020` : l'ancien
`--tb=no -rs` a supprimé le nom et la trace du test. La position du `F` dans
l'ordre des 350 tests identifie
`test_query_counts.py::test_portfolio_list_grows_linearly_and_detail_is_bounded`
(265e test d'intégration). Ce test utilisait `SHOW GLOBAL STATUS Questions` :
les requêtes des healthchecks pouvaient donc modifier son résultat. Le défaut
de mesure est corrigé sans relever les plafonds. L'ancienne assertion exacte
n'est pas récupérable ; la cause de ce run ne peut pas être certifiée après coup.
Les runs suivants ont réussi ; `cf791a7` a déjà amélioré les journaux d'échec.

## Portée des critères réconciliés

Les règles permanentes ont été séparées des tâches. Les critères du plan
renvoient à des preuves identifiées (sources, historique de formatage, suites,
captures et sondes). Les captures initiales datent de l'audit `079e40c` ; elles
ne sont pas présentées comme des captures de `7a55926`. La recette courante est
limitée à Chromium et au tactile émulé. Les trois contrôles externes ci-dessous
restent ouverts : leur absence n'est pas effacée pour annoncer « 100 % ».

## Vérification locale de cette reprise

Résultats : **714 tests rapides, 351 tests d'intégration**, e2e et contrôles de
release conformes ; galerie 4 contextes, 196 contrastes et 63 utilitaires OK.
120 vues mesurées, puis 36 vues fiche/aide revérifiées sans débordement de page.
Détail dans le journal du plan et `RECETTE_FINALE.md`.
Python 3.12, PHP 8.2, MariaDB 10.11, Chromium ; données synthétiques dans
`jigobourso_it`. Les environnements et journaux temporaires ne sont pas des
prérequis ajoutés au projet.

Commandes reproductibles dans un environnement équipé :

```sh
make lint js-check css-check fast
make integ
make visual
make e2e
make release-check
scripts/probe_layout.sh --themes --out /tmp/layout.json --shots /tmp/pages
PROBE=scripts/probe_utilities.cjs scripts/probe_layout.sh
```

## Vérifications externes distinctes

- [ ] Appareils et navigateurs réels : Safari/iPhone notamment. Les largeurs
      mobiles et les deux thèmes sont vérifiés sous Chromium émulé.
- [ ] Mesurer la fenêtre de transfert Hostinger et tester une restauration
      réelle sur une cible isolée autorisée. Les répétitions locales ne sont
      pas rebaptisées essais de production ; voir `DELIVERY.md`.
- [ ] Exécuter la CI Python 3.9 sur les nouveaux commits avant livraison.
      La vérification locale Python 3.12 ne remplace pas ce contrôle.

Ces points ne sont pas cochés par suppression de cases ou par référence aux
anciens déploiements. Aucun secret, workflow de diagnostic distant ou accès
à la production n'a été créé pour les contourner.
