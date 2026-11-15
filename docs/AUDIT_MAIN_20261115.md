# Audit de main — 15 novembre 2026

## Verdict

**La refonte a amélioré le produit et les garde-fous, mais l'architecture n'est
pas entièrement refondue.** L'harmonisation Halo est réelle ; les anciens rôles
CSS ne sont cependant pas complètement séparés. Le moteur Python est mieux
structuré que les contrôleurs JavaScript et certaines routes PHP.

La CI verte ne prouve pas l'absence de défauts : cet audit reproduit deux chemins
qui échappent au délai maximal du moteur, un aperçu qui ne réessaie pas après
une panne, et deux contournements du garde-fou CSS. La restauration accepte aussi
explicitement un cas de dépendances non restaurées sans code d'échec.

**Priorité : corriger la fiabilité, finir la séparation CSS, puis découper les
responsabilités restantes. Une nouvelle réécriture globale n'est pas justifiée.**

## Référence et portée

- Révision examinée : **2bb2cec5292afa95c1073dde7423cb27c03e8c94**.
- `origin/main` rafraîchie et identique au checkout lors de l'audit.
- CI et livraison de cette révision : [run 43718821128](https://github.com/elmonsieurpatate/jigobourso/actions/runs/43718821128), réussite.
- Domaines lus : frontend, passerelle PHP/Python, services et routes PHP,
  architecture Python, traitements, splits/registre, schéma/migrations,
  workflows, restauration et documentation.
- Analyse statique complétée par des reproductions isolées. Aucun changement du
  code applicatif, aucune requête financière de production, aucune modification
  de données, aucun nouveau déploiement pendant cet audit.
- Ce document est la seule modification du dépôt produite par l'audit.

Limites : pas de nouvel inventaire des données réelles, d'`EXPLAIN` en production,
de test de charge Hostinger, de Safari/iPhone physique ni de pentest exhaustif.
Les résultats CI cités concernent exactement la révision ci-dessus ; ils n'ont
pas été présentés comme des milliers de tests nouvellement exécutés pour l'audit.

## Inventaire

| Périmètre | Constat |
|---|---|
| Pages publiques HTML | 19 |
| CSS | 11 feuilles, 11 582 lignes |
| JavaScript applicatif et contenus | 69 fichiers, 18 635 lignes |
| PHP | 47 fichiers, 3 343 lignes |
| Python, scripts et tests compris | 210 fichiers, environ 30 500 lignes |
| Principales feuilles | `base.css` 2 325 lignes ; `halo.css` 2 225 ; `explorer.css` 2 141 |
| Gros contrôleurs JS | `explorer.js` 1 283 lignes ; `admin-scores.js` 865 ; `pf-home.js` 792 |

La taille n'est pas une anomalie en elle-même : les catalogues et chapitres d'aide
sont des données/contenus. Le problème est le mélange des responsabilités et les
contrats non vérifiés, pas un objectif arbitraire de nombre de fichiers.

## Ce qui tient déjà correctement

- **Python** : couches documentées, séparation calculs/fournisseurs/administration,
  garde-fous sur les imports et absence de cycles dans le graphe analysé.
- **Portefeuilles PHP** : cas d'usage extraits ; écritures sérialisées par verrou
  du portefeuille, validation chronologique partagée, contrôle de propriété.
- **Splits et change** : événements confirmés distingués des candidats, absence
  de taux historique signalée, lecture des splits impossible traitée en 503,
  tests de parité et contrôles de release présents.
- **Web** : échappement central, CSP restrictive, contrôles d'origine et taille du
  corps ; protection CSV contre les formules présente. Cela ne remplace pas un pentest.
- **Interface** : tokens clair/sombre, composants communs, galerie, contrôle des
  contrastes, tests clavier/tactiles ; recherche déclenchée par Appliquer dans les
  parcours vérifiés. Le défaut de colonnes de la fiche mobile a été corrigé.
- **Livraison** : CI réelle, sauvegarde et retour arrière automatiques, contrôle
  d'intégrité et configuration BLAS corrigée. Ces acquis sont à conserver.

## Synthèse des constats

P1 = fiabilité à traiter en premier. P2 = architecture, protection ou couverture
à compléter. P3 = entretien. « Risque » ne signifie pas incident observé.

| ID | Priorité | Nature | Constat |
|---|---|---|---|
| A01 | P1 | Défaut reproduit | Le délai moteur ne couvre pas stdin et la fin du processus |
| A02 | P1 | Chemin confirmé par code/test | Restauration pouvant réussir sans restaurer les dépendances requises |
| A03 | P2, lot prioritaire | Défaut reproduit | Échec d'aperçu des poids mémorisé définitivement dans la page |
| A04 | P2 | Architecture constatée | Présentation encore répartie entre base, Halo et feuilles métier |
| A05 | P2 | Contrôle contourné | Le garde-fou CSS laisse passer des surcharges interdites |
| A06 | P2 | Architecture constatée | Extraction des cas d'usage PHP encore partielle |
| A07 | P2 | Organisation constatée | Contrôleurs JS mêlant état, migration, réseau et rendu |
| A08 | P2 | Écart de workflow | Contrôles PR moins complets que ceux de main |
| A09 | P2 | Couverture constatée | Plusieurs parcours métier navigateur restent manuels |
| A10 | P2 | Mesure manquante | Diagnostic de performance réel mobile/Hostinger incomplet |
| A11 | P2 | Risque documenté | Livraison non atomique et dépendances non verrouillées exactement |
| A12 | P3 | Documentation | Contradictions et preuves de clôture trop générales |

### A01 — Le délai maximal n'englobe pas tout l'appel au moteur

**Source :** `app/lib/engine.php:68–85` ; `app/lib/http.php` pour `BODY_MAX` ;
`tests/fast/test_engine_call.py` pour la couverture existante.

L'écriture sur stdin est bloquante, avant la création de la deadline. Une requête
HTTP autorisée peut atteindre 2 Mio, bien plus que la capacité du tube : le
commentaire qui suppose que le corps borné ne bloquera pas ne tient pas.
Après EOF de stdout, `proc_close()` peut également attendre le processus sans
surveiller la deadline.

**Reproductions isolées, PHP 8.2, faux moteur, sans réseau ni base :**

1. Faux moteur dormant 3 s sans lire stdin ; envoi de 128 Kio ; délai configuré
   à 0,1 s : durée mesurée **3 s**, avec avertissement de tube fermé.
2. Faux moteur écrivant un JSON valide, fermant stdout puis dormant 3 s ; délai
   0,1 s : retour réussi `{"ok":true}` après **3 s**.

Les tests actuels envoient une petite requête et testent un moteur dormant qui
garde stdout ouvert : ils ne couvrent ni le gros stdin ni EOF avant terminaison.

**Impact :** workers PHP et emplacements moteur immobilisés au-delà du délai
annoncé ; des timeouts observés ne sont donc pas tous encadrés par la borne 90 s.
Cela n'établit pas que ce défaut explique une lenteur précise en production.

**Correction attendue :** deadline globale démarrant avant les échanges,
écriture non bloquante et complète, surveillance conjointe des flux et de la vie
du processus ; arrêt et nettoyage garantis sur tous les chemins. Ajouter les deux
cas ci-dessus aux tests, sans augmenter le délai pour masquer le problème.

### A02 — Retour arrière : succès possible avec le mauvais environnement

**Source :** `ops/deploy.sh:69–87` ;
`tests/fast/test_environment.py:164–167`.

Si la sauvegarde du venv est absente, le code affiche « vérification manuelle
requise » puis continue. Le contrôle final vérifie seulement que les modules
s'importent ; il ne vérifie pas leur conformité au manifeste restauré. Le test
existant exige explicitement un code zéro dans ce cas.

Sans marqueur de réparation, le script choisit aussi la dernière archive globale
de paquets : aucune association explicite ne prouve qu'elle correspond à une
ancienne sauvegarde de code choisie pour un rollback manuel.

**Impact conditionnel :** un retour arrière peut être annoncé terminé alors que
l'environnement n'est pas celui attendu. Le retour arrière effectivement exécuté
pendant la dernière livraison n'est pas déclaré défectueux par ce constat.

**Correction attendue :** associer chaque sauvegarde de code à son manifeste et à
son environnement ; contrôler la compatibilité après restauration ; si le venv
nécessaire manque, retourner un état dégradé/échec explicite, jamais un succès
complet. Tester une ancienne sauvegarde choisie et une archive absente.

### A03 — L'aperçu des poids ne reprend pas après une erreur

**Source :** `app/public/assets/admin-scores.js:154–176`.

`autoCache['?' + key]` est posé avant l'appel réseau. Le rejet est absorbé par
`.catch(() => {})` et le marqueur n'est jamais retiré. Pour une nouvelle
configuration sans poids disponibles, un échec transitoire laisse le résultat
indisponible pour cette clé pendant la vie de la page.

**Reproduction :** exécution du corps réel de `autoWeights` dans un contexte Node,
premier `J.post` rejeté avec un 503 simulé, puis nouvel appel identique : **un
seul appel réseau au total**, marqueur toujours `true`. Le retour de poids reste
`null` dans le cas sans profil de secours.

**Correction attendue :** distinguer pending/succès/erreur, libérer pending dans
`finally`, montrer l'échec et permettre une reprise explicite ou bornée. Conserver
la déduplication des demandes simultanées.

### A04 — La source visuelle unique reste incomplète

**Sources :** `base.css:112–146`, `halo.css:272–287`, `halo.css:788–820`,
les feuilles `explorer.css`, `filtres.css`, `help.css` et `plan-suivi.css`.

Halo porte réellement les tokens et de nombreux composants. Mais `base.css`
contient encore typographie de KPI, couleurs d'états, spinner et styles métier ;
les feuilles métier ont aussi des déclarations visuelles. Un comptage ciblé
trouve 158 déclarations color/background/border/box-shadow dans base, contre 295
dans Halo : **ce n'est pas un décompte de 158 bugs**, mais la preuve que « base =
structure seule » ne décrit pas le code.

**Impact :** une modification nécessite encore de connaître plusieurs couches de
cascade. `halo.css` chargé en dernier limite certains conflits sans supprimer
leur origine. Onze feuilles CSS ne sont pas le problème ; leur responsabilité l'est.

**Correction attendue :** inventaire par composant, puis déplacement/suppression
des règles remplacées par famille : bouton, champ, carte, tableau, message,
navigation. Garder les grilles métier propres aux pages. Une seule définition
d'apparence par famille, sans nouvelle feuille de « corrections finales ».

### A05 — Le garde-fou CSS ne garantit pas la règle annoncée

**Source :** `scripts/check_halo_css.py:58–105`.

`color` et `border-color` ne font pas partie des propriétés surveillées. Le
traitement des sélecteurs repose sur des expressions régulières qui ne couvrent
pas correctement les pseudo-classes fonctionnelles comme `:is()`.

**Reproduction sur une copie temporaire des 19 pages et 11 CSS, sans modifier le
checkout :** ajout séparé de chacune de ces règles à base :

```css
.btn { color: var(--danger); }
body :is(.title-page .btn) { padding: var(--sp-40); }
```

Dans les deux cas, le garde-fou retourne **0 / succès**. La seconde règle peut
pourtant remplacer l'espacement des boutons. La couleur utilise un token : le
contrôle d'absence de couleur littérale ne la détecte pas non plus.

**Correction attendue :** contrôle structurel des règles/sélecteurs, ou conventions
explicites vérifiables accompagnées de tests négatifs ; intégrer couleurs et
variantes concernées. Ne pas confondre présence de tokens et unicité de définition.

### A06 — Les couches PHP sont partiellement appliquées

**Sources :** `docs/ARCHITECTURE_PHP.md:5–10`, `app/routes/{alerts,admin,explore,auth,tracking}.php`,
`tests/fast/test_php_structure.py:67–74`.

Le document interdit SQL et métier dans les routes. Hors export CSV volontaire,
les cinq groupes cités contiennent **78 appels `q()`** : alerts 21, admin 21,
explore 6, auth 12, tracking 18. Les portefeuilles sont mieux séparés ; cela ne
s'étend pas encore à tous les domaines.

Le test vérifie la direction des dépendances et, pour l'accès HTTP direct,
surtout `services/portfolios.php`. Il ne prouve pas l'interdiction SQL des routes.

**Correction attendue :** extraire les cas d'usage par domaine, commencer par un
petit groupe ; routes limitées à méthode, authentification, paramètres et réponse.
Conserver le contrôle d'origine, la propriété et les limites de transaction.
Étendre les garde-fous à la règle effectivement retenue. Formater PHP séparément,
avec un outil/configuration explicites : `php -l` ne valide que sa syntaxe.

### A07 — Certains contrôleurs frontend restent difficiles à reprendre

**Sources :** `explorer.js`, `admin-scores.js`, `pf-home.js`, `app.js`.

Les modèles et moteurs de tracé déjà extraits sont utiles. Les contrôleurs
restants mêlent encore initialisation, migrations du stockage local, appels API,
état, événements et assemblage HTML. Par exemple, les migrations occupent le
début d'`explorer.js`, qui pilote aussi recherche, colonnes et rendu.

**Correction attendue :** séparer l'état/les transitions, l'orchestration réseau
et le rendu là où ils changent indépendamment ; extraire la migration historique
et les états asynchrones. Garder l'API existante et les modèles purs. Aucun
framework ni bundler ne devient nécessaire du seul fait de ce constat.

### A08 — La PR et main n'appliquent pas la même barrière de qualité

**Sources :** `.github/workflows/pr-validation.yml:35–45` et
`.github/workflows/deploy.yml:38–45,111–118`.

La validation PR lance syntaxe, tests rapides et intégration. Elle n'exécute pas
les mêmes contrôles Ruff/Prettier/Halo et navigateur que le workflow de main.
Une régression peut donc être détectée seulement après fusion/push, avant livraison.

**Correction attendue :** une validation réutilisable et commune, avec distinction
claire entre vérification et déploiement. Conserver les droits minimaux des PR et
ne transmettre aucun secret de production aux jobs PR. Ne pas résoudre l'écart
en supprimant les contrôles de main.

### A09 — « Tests complets » n'exécute pas tous les parcours navigateur métier

**Sources :** workflow de déploiement et `scripts/e2e_browser.sh` ;
`tests/e2e/README.md`.

Cinq parcours principaux sont appelés directement : financial, keyboard,
title-layout, strategies-ui, account-navigation, en plus de la galerie et des
sondes de contrat. D'autres fichiers contiennent des modèles purs déjà couverts
par pytest : ils ne doivent pas être comptés comme des parcours oubliés.

En revanche, les scénarios navigateur `plan-suivi.cjs`, `split-reviews.cjs`,
`portfolio-v5.cjs` et `admin-categories-test.cjs` ne figurent pas dans ce runner.
La documentation indique que les autres scénarios sont manuels. Ce constat ne
signifie pas que leur logique n'a aucun test API/Python.

**Correction attendue :** classer scénarios actifs/obsolètes/modèles purs, préciser
les seeds et l'ordre d'exécution ; intégrer les parcours métier actifs critiques.
Ne pas lancer aveuglément tous les anciens scripts ni assimiler un test de modèle
à une validation des interactions de la page.

### A10 — Les lenteurs réelles restent insuffisamment mesurées

**Source :** `docs/PERFORMANCE.md`, `engine.php`, `explorer.js:1221–1242`.

Les mesures documentées sont utiles mais synthétiques et locales. Elles donnent
notamment environ 10–11 Mo de JSON de classement avant gzip, un pic de 153 Mo et
quatre emplacements moteur. L'interface demande tout le classement avant de
rendre une page ; les courbes sont, elles, limitées aux lignes visibles.

Le raisonnement « le tri local est rapide, donc aucune pagination serveur n'est
justifiée » ne tranche pas le coût CPU/mémoire partagé ni le réseau mobile réel.
Inversement, ces chiffres ne prouvent pas qu'il faut tout paginer immédiatement.

**Action attendue :** mesurer les routes authentifiées sur Hostinger : p50/p95,
attente de slot, démarrage/interpréteur, SQL, sérialisation, mémoire et rendu sur
réseau mobile ; charge concurrente bornée. Choisir ensuite entre payload réduit,
cache, pagination et pré-calcul. Pas d'optimisation à l'aveugle.

### A11 — Livraison et versions reproductibles : garanties encore limitées

**Sources :** `ops/deploy.sh` (rsync avec `--delay-updates`),
`scripts/release/ensure_dependencies.sh:41–45`, `requirements.txt`, `docs/DELIVERY.md`.

Le remplacement différé des fichiers n'est pas une bascule atomique de release :
des requêtes peuvent traverser une transition de fichiers. Cette limite est déjà
documentée. Les dépendances sont bornées, mais non verrouillées exactement avec
leurs dépendances transitives ; le fallback `pip --target` dépend aussi de
l'interpréteur système qui choisit les roues.

**Risque, pas incident prouvé ici :** reconstruction différente ultérieure ou
mélange bref de code pendant le transfert. Le contrôle d'import final ne mesure
pas cette fenêtre et ne suffit pas à garantir une reconstruction identique.

**Action attendue :** version de Python et résolution de dépendances identifiées,
manifestes/sauvegardes associés à la release ; mesurer la fenêtre réelle et étudier
une bascule de répertoire si nécessaire. Éviter un chantier d'infrastructure sans
bénéfice vérifié ; préserver systématiquement données et configuration privées.

### A12 — Documentation et critères de clôture à remettre en cohérence

**Sources :** `README.md:5`, `docs/ARCHITECTURE.md:5–7`,
`docs/ARCHITECTURE_PHP.md`, `docs/PLAN_REFONTE_COMPLET.md`, `tests/e2e/README.md`.

Exemples vérifiables : README annonce une seule dépendance runtime alors que le
manifeste en contient quatre ; le document d'architecture décrit encore une
construction séparée de la production et affirme que Git/GitHub ne sont pas
touchés ; le README e2e n'annonce que trois parcours, le runner en a cinq.

Plusieurs critères de clôture s'appuient sur des preuves globales ou de code :
un contrôle de dialogue partagé ne certifie pas chaque dialogue, pas plus que
l'absence de cycle ne certifie l'ensemble de la séparation des responsabilités.

**Correction attendue :** identifier les documents historiques, une référence
courante par domaine, et une matrice exigence → page/état → test → résultat.
Garder explicites Safari/appareils réels et la profondeur de recette ; ne pas
faire de « toutes cases cochées » un indicateur de qualité à lui seul.

## Décision financière à conserver visible, pas nouveau bug déclaré

`FINANCIAL_INTEGRITY.md:45`, `ledger.php:42–56` et les tests de parité documentent
qu'un achat à prix zéro postérieur à un split vaut correction manuelle implicite.
Le test de regroupement puis achat gratuit attend même une quantité de 105,
conformément à cette décision, plutôt qu'une quantité de 15 correspondant à un
autre sens métier possible.

Un don d'actions et la correction d'un split ne sont donc pas distingués par un
lien explicite à l'événement. Le recensement de release signale ces cas sans les
modifier. **Ce n'est pas une régression nouvellement découverte ni une invitation
à corriger les quantités automatiquement.** À terme, prévoir un type d'opération
et une association explicite après validation métier, surtout pour plusieurs
splits successifs. Aucun historique réel n'a été inspecté ni réparé ici.

## Vérifications de cet audit

| Contrôle | Résultat / provenance |
|---|---|
| Main rafraîchie, état initial propre | `2bb2cec`, aucune divergence |
| Ruff | OK, rejoué |
| Garde-fou Halo, échelles CSS | OK, rejoués ; limites démontrées par A05 |
| Couches Python/PHP et environnement | **24 tests réussis**, rejoués |
| Reproduction des deux délais moteur | 3 s observées pour délai 0,1 s, deux cas distincts |
| Reproduction de l'erreur d'aperçu | 1 requête pour appel initial + tentative de reprise |
| Reproduction des surcharges CSS | 2 règles interdites acceptées, code retour 0 |
| Suite complète de la révision | **719 rapides + 351 intégration + navigateur**, CI verte citée ; non relancée intégralement |
| Production | Livraison de la révision vérifiée au tour précédent ; pas de nouvel essai destructif |

Les sondes utilisent des copies temporaires et un conteneur PHP isolé sans réseau.
Le faux moteur dormant 3 s est volontairement borné ; aucune charge n'a été envoyée
à l'application réelle. La première commande enveloppante Docker a aussi atteint
sa borne externe de 8 s, mais son journal PHP confirme la durée interne de 3 s ;
la seconde reproduction s'est terminée normalement. Les mesures ne sont pas des
benchmarks de performance du site.

## Ordre de travail proposé

1. **Fiabilité : A01, A02, A03.** Trois corrections ciblées avec tests qui
   échouent avant correction ; préserver API et calculs financiers.
2. **CSS : A04 + A05.** Inventaire des définitions puis une famille de composants
   à la fois ; suppression effective des anciennes règles ; galerie et pages réelles.
3. **Architecture et CI : A06 à A09.** Petits lots par domaine, séparation réelle
   et couverture des parcours actifs. Aucune nouvelle direction graphique.
4. **Mesures et exploitation : A10 à A12.** Mesures représentatives avant choix
   d'optimisation, traçabilité des releases et documentation courante.

Pas de réécriture générale, pas de suppression sur simple recherche statique,
pas de modification des données et pas de nouvelle migration de framework par défaut.
