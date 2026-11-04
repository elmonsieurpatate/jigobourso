# Validation exécutée — reconstruction Explorer

Date : 4 novembre 2026. Branche `feature/explorer-reconstruction`, base main
`2ba67acc66fb2c1fd6fd07692259102fbf4384fd`.
Tests PHP 8.4, Python 3.12, MariaDB locale et Chromium. Bases jetables
`jigobourso_it` et `jigobourso_explorer_review`, avec données synthétiques uniquement.
Aucune donnée de production modifiée, aucune collecte Yahoo déclenchée par Explorer,
aucune fusion ou mise en production.

## Résultats locaux

| Vérification | Résultat réel |
|---|---|
| `make fast` | **416 réussis**, 1 avertissement exchange_calendars/pandas |
| `make integ` | **192 réussis**, 166,41 s ; avertissements de dépréciation Python/pandas existants |
| `pytest tests/integ/test_explorer_v4.py` après ajout du dernier cas split/FX | **6 réussis**, 2,50 s ; dont 5 déjà inclus ci-dessus et 1 cas supplémentaire |
| Syntaxe PHP, Python, JavaScript | Réussite ; tous les fichiers PHP app/scripts, compilation engine/scripts et JS app/tests CJS |
| Garde des migrations | **11 migrations admissibles**, ajouts uniquement |
| Migration inverse contrôlée | Refus avec sauvegarde présente ; retrait puis recréation testés sur table vide dans la base jetable |
| Benchmark CPU 9 611 titres / 24 contributions | **0,73 s**, sortie compressée 3 182 562 octets ; ne mesure ni SQL ni Hostinger |
| `git diff --check` | Réussite |

Les tests financiers couvrent notamment les conversions réversibles de pente,
la régression logarithmique sur 5/21/63/126/252 séances, les règles en une séance,
R², volatilité, performance, drawdown, continuité, concentrations, volumes absents,
poids nuls/négatifs, percentiles avec ex æquo, normalisation et données absentes.
Les sept méthodes historiques sont comparées numériquement à leur représentation
éditable dans le moteur commun. Les scores de page et de fiche sont comparés aux
contributions de la population complète.

Le dernier cas SQL vérifie un split 2:1 avec cours ajustés constants, volumes bruts
changeant de 10 à 20 titres et conversion USD/EUR datée de 0,5 : le montant moyen
échangé reste **500 €**, sans fausse baisse ni double correction. Un volume manquant
rend les mesures de liquidité indisponibles, sans les remplacer par zéro.

## Parcours navigateur réellement exécutés

`tests/e2e/explorer-reconstruction.cjs`, fenêtres **1280, 390 et 375 px**, avec
cours synthétiques contrôlés :

| Scénario | Résultat |
|---|---|
| A — reproduction exacte V1 sur jeu commun | **Non validé** : scanner V1 inaccessible, voir ci-dessous |
| B — mois/trimestre/semaine, désactivation/réactivation | Valeurs conservées |
| C — modifications sans Appliquer | Aucun appel de recherche ; application groupée vérifiée |
| D — rechargement | État appliqué conservé |
| E — stratégies, copie, suppression, scopes | Réussite ; téléchargement/import JSON effectivement exécutés sur ordinateur |
| F — valeurs d’origine après modification | Valeurs restaurées, appliquées et conservées au rechargement |
| G — débutant/expert et global/période | Valeurs financières conservées |
| H — données manquantes | Historique court identifié, jamais assimilé à zéro |
| I — classement | Somme des contributions cohérente ; fiches et pagination testées avec SQL |
| J — responsive et commandes | Réussite aux trois largeurs ; deux poignées au clavier/souris et entrée tactile sur mobiles |

Le filtre de dernière clôture exclut effectivement une action et un ETF dont le
mois/semaine restent haussiers mais la dernière séance est négative. La régression
détaillée utilise la fenêtre attendue, comporte une courbe tracée et un conteneur
de largeur réelle **supérieure à 230 px sur mobile**, vérifiée par bounding box.
Aucune erreur JavaScript ni débordement horizontal de page sur les parcours.

Captures de la vraie interface par défaut, sans maquette :

- [Ordinateur 1280 px](explorer-v4/1280.png)
- [Mobile 390 px](explorer-v4/390.png)

`explorer-url.cjs` vérifie aussi les liens existants de recherche rapide / Recherche
libre : ils préparent un brouillon, préservent les réglages appliqués et sont consommés
pour ne pas ressusciter après réinitialisation puis rechargement. Résultat : réussite.

## Régressions des fonctions existantes

Les scripts existants ont été adaptés au remplacement de l’interface et à la
persistance demandée ; les anciennes assertions exigeant l’effacement au rechargement
ou le recalcul automatique ont été remplacées par les nouveaux contrats.

- `financial.cjs` : réussite à 375/390/1280 px. Mini-courbes mesurées à **313/328/110 px**,
  fiche du titre, courbes, ajout vers portefeuille, contenu/participations/similarités
  ETF, deux espaces portefeuille, tableau de positions, secteurs ETF et navigation admin.
  Aucun débordement ni erreur JavaScript.
- `tradability.cjs` : masquage contrôlé, compte cohérent, exception de recherche exacte,
  filtres d’univers indépendants et rechargement conservé : réussite.
- `menu.cjs` : réglages, unique bouton Appliquer, recherche/type toujours accessibles,
  conservation des seuils et filtres : réussite à 1280/390/375 px.
- `manage.cjs` : séparation financière/univers, création, renommage, duplication,
  activation, suppression, ancien identifiant conservé et conversion explicitement
  demandée au chargement : réussite.
- `account-navigation.cjs` : navigation/détails/rechargement aux trois largeurs,
  connexion par e-mail, changement des coordonnées, confirmation, récupération et
  changement de mot de passe : réussite avec courrier de test local uniquement.

Les incompatibilités réellement détectées puis corrigées pendant ces parcours :
réponse de validation enveloppée dans `config`, objets JSON vides convertis en listes
par PHP, anciens poids V3 sérialisés en liste vide, et contributions inapplicables
R²/volatilité en une séance lors de la conversion des profils.

## Limites et validations non revendiquées

- La tentative SSH en lecture seule du véritable
  `~/domains/bourse.turnjoy.dev/public_html/scan.py` a retourné **Connection refused**.
  Aucune copie locale trouvée. Les formules exactes V1 et les résultats comparés sur
  GEHC, ROP, VFC, TDOC, EVER et MAX ne sont **pas** validés. Les tests synthétiques ne
  sont pas présentés comme leurs historiques réels.
- L’industrie fine et la réplication ETF ne sont pas dans le catalogue actuel :
  indisponibilité explicitement indiquée ; aucune donnée inventée ni collecte ajoutée.
- Le benchmark 9 611 titres est un benchmark du score en mémoire. La latence froide
  SQL sur les 9 611 historiques réels et les performances Hostinger restent à mesurer
  après revue, sans extrapoler les chiffres locaux.
- Le workflow de PR ajouté ne déploie rien. Son exécution sur GitHub dépend de la
  création effective de la pull request ; les succès ci-dessus sont des validations
  **locales**, pas des statuts GitHub Actions prétendus.

Le résultat exact de la publication de branche/PR est communiqué dans le compte
rendu de livraison. Aucun simple push n’est qualifié de déploiement réussi.
