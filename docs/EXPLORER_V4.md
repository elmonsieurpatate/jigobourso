# Explorer : configuration V4 et reconstruction du classement

Cette reconstruction remplace `index.html` et `assets/explorer.js`. Elle utilise
les services PHP, la CLI Python et `strategy.judge/rank` existants. Elle ne change
ni les collectes FinanceDatabase/Yahoo, ni le calcul nocturne, ni les portefeuilles,
transactions, performances personnelles ou règles d’éligibilité `v_recommendable`.

## État, priorité et application

Un état navigateur versionné, propre à l’utilisateur (`jigo.explorer.v4.<id>`),
contient `applied`, `draft` et `preferences`. Les préférences incluent les panneaux,
le mode débutant/expert, le mode global/par période, les colonnes et la présentation
des résultats. Débutant et expert éditent le même objet, sans conversion de seuils.

1. L’état V4 existant est prioritaire.
2. Sans état V4, le profil d’origine « Croissance régulière » est chargé.
3. L’ancienne clé `jigo_explorer2` est proposée dans la bibliothèque, **sans**
   écraser l’état courant. Une ancienne session n’a plus priorité sur le navigateur.
4. Les anciennes recherches et personnalisations de profils restent en base,
   accessibles sous leurs identifiants historiques. Leur chargement convertit
   explicitement une copie en brouillon V4 ; les originaux ne sont pas réécrits.
5. Les anciennes URL `?library=1` / `?manage=1` ouvrent la bibliothèque. Les anciens
   paramètres `preset` (dont Recherche libre), `q` (recherche de l’en-tête), `kind`,
   `geo_region` et `max_fee` préparent uniquement un brouillon, avec un message
   demandant Appliquer. Ils sont consommés dans l’URL pour ne pas réapparaître au
   rechargement. Le lien Comparer explique la sélection des titres à comparer.
   Aucune URL ne remplace silencieusement l’état financier appliqué.

Changer un profil, une période, un seuil ou un filtre, fermer un panneau, charger
une sauvegarde, réinitialiser : **aucun appel de recherche**. Seul **Appliquer**
valide puis copie le brouillon dans l’état appliqué. Le rechargement recherche avec
cet état appliqué, même si un brouillon différent a été conservé. Un seul bouton
Appliquer existe. Statut, tri et pagination consultent l’état appliqué ; ils ne
valident pas le brouillon. Ils peuvent effectuer une requête de présentation et
lire le classement mis en cache.

Le mode global ne remplace pas les seuils en l’ouvrant : seule la manipulation
explicite d’un contrôle harmonise ce champ sur les périodes actives compatibles.
Une pente globale est une pente **sur chaque période** ; sa conversion interne
est donc différente pour 5 et 21 séances. Les différences préexistantes sont signalées.
Les contraintes propres aux Actions/ETF utilisent le même juge, avec surcharges
explicites ; les résultats indiquent l’existence de ces règles.

## Configuration financière

`version: 4`, `slope_unit: percent_per_session`, six périodes dans l’ordre canonique
jour, semaine, mois, trimestre, semestre, année (1, 5, 21, 63, 126, 252 séances).
L’interface règle les périodes de la plus longue à la plus courte ; leur bandeau
reste unique. Les anciennes fenêtres personnalisées valides sont conservées.

Chaque période possède `enabled`, `require_history` et les bornes listées dans
`explorer_config.BOUNDS`. **null = contrainte inactive ; 0 = seuil réel.** Désactiver
une période conserve ses valeurs et désactive ses critères et contributions.
Une période sans contrainte ni exigence d’historique ne rejette pas un historique
court. Une exigence d’historique demande une mesure de fenêtre disponible ; les
séances manquantes restent signalées. Les statistiques de chemin ne sont pas
calculées à travers des trous. Une couverture partielle ne devient pas complète
par interpolation.

La sélection peut combiner les contraintes par ET ou OU. L’historique explicitement
exigé et la fraîcheur restent obligatoires dans le mode OU. Les données absentes
sont soit « non évaluables », soit explicitement éliminatoires. La politique du
score est séparée : une sélection valide peut rester non évaluable pour le score.

Les champs JSON objets vides sont conservés comme objets par le transport PHP
V4 (`explorer_config_shape`) : `asset_rules: {}` ne doit pas devenir `[]`.
Les tableaux `periods` et `components` restent des listes. Les V3 ne sont pas
réécrites par cette adaptation.

## Mesures et unités

Pour N séances, la fenêtre utilise N+1 clôtures confirmées sur le calendrier de
la place. Le dernier jour compare les deux dernières clôtures attendues, jamais
une cotation intrajournalière. L’historique préparé et les corrections de splits
existants restent la référence commune.

Pour la régression `log(prix_t) = a + b*t` :

- pente interne par séance : `100 * expm1(b)` ;
- pente affichée sur la période : `100 * expm1(N*b)` ;
- conversion inverse du seuil : `100 * expm1(log1p(pente_période/100)/N)` ;
- performance : `100 * (prix_fin/prix_début - 1)` ;
- R² : coefficient de détermination de cette régression ;
- volatilité : écart-type échantillonnal des variations logarithmiques quotidiennes,
  multiplié par 100, **sans annualisation** ;
- drawdown maximal : plus grande baisse depuis un sommet dans la fenêtre ;
- recul actuel : `100 * (1 - prix_fin/max(prix_fenêtre))` ;
- ER : variation logarithmique nette / somme des variations logarithmiques absolues ;
- continuité : nombre de séances de hausse logarithmique stricte (tolérance 1e-12)
  et proportion sur N séances ; les séances stables ne comptent pas comme hausses ;
- concentration des hausses : plus forte hausse logarithmique / somme des hausses
  logarithmiques positives, en %. Zéro en l’absence de hausse ;
- concentration rapportée au gain net : meilleure variation quotidienne simple /
  performance nette positive de la période, en %. Indisponible si celle-ci ≤ 0 ;
- pire/meilleure séance : minimum/maximum des variations quotidiennes simples.

Ces deux concentrations sont des **définitions génériques documentées**, pas des
formules attribuées au scanner V1 non consulté. Elles ne sont pas interchangeables.

Le volume moyen de période exige les N volumes observés. Le montant moyen échangé
en euros utilise le cours historique **brut** × volume historique brut × conversion
EUR datée. Il ne multiplie pas un cours ajusté des splits par un volume non ajusté.
Les taux peuvent être reportés depuis une date antérieure d’au plus 7 jours ; une
conversion manquante rend le montant indisponible. Les pence utilisent la conversion
existante. Un volume absent n’est jamais zéro. Le volume coté moyen 3 mois est un
indicateur distinct, avec son propre libellé.

R², ER et volatilité ne sont pas configurables en une séance. Le graphe de détail
utilise exactement les dates de la fenêtre et la régression logarithmique calculée.
Les trous ne sont pas reliés. Les mini-courbes suivent la plus longue fenêtre active
pour le type du titre, les mêmes clôtures et corrections de splits.

## Score indépendant

Une contribution définit : mesure, période, type Actions/ETF/Tous, activation,
poids, direction, normalisation, transformation et caractère obligatoire éventuel.
Une période inactive et un poids nul n’ont aucun effet sur le score.

- percentile : rang relatif dans la **population complète retenue**, ex æquo au
  rang moyen ; un seul titre vaut 50 ; sens inverse = 100 − percentile ;
- linéaire : bornes fixes, résultat borné entre 0 et 100 ;
- brut : valeur de l’indicateur, avec signe inversé si les petites valeurs sont favorisées ;
- transformations : identité, log(1+x), racine ou puissance signée. Une transformation
  hors domaine/finie devient indisponible, jamais un zéro implicite ;
- moyenne pondérée : somme des `valeur_normalisée * poids / somme(abs(poids))` ;
- somme pondérée : somme des `valeur_normalisée * poids` ;
- poids négatif : pénalité explicite ; poids nul : composant sans effet ;
- données absentes : classement non évaluable ou renormalisation sur les mesures
  présentes. Une contribution marquée obligatoire manque → non évaluable ;
- populations séparées Actions/ETF par défaut, ou combinaison explicitement choisie.

Les valeurs brutes et sommes peuvent dépasser 0–100 : l’interface affiche des
**points**, sans « /100 » trompeur. Un percentile élevé ne décrit pas le risque.
Celui-ci est affiché séparément avec les signaux existants, sans modifier leurs seuils.
Le détail explique chaque contribution ; leur somme égale le score à l’arrondi près.
Le classement est calculé avant pagination. Les fiches reprennent les contributions
de cette population complète, pas celles du seul titre consulté.

Les sept profils d’origine sont disponibles avec leurs formules exposées en composants
éditables. Les méthodes V3 restent disponibles pour compatibilité. Des tests comparent
les scores et rangs de chaque formule d’origine à sa représentation générique. Le
Momentum ajusté du risque conserve 35 % momentum 6 mois, 45 % momentum 12 mois,
10 % stabilité et 10 % faible drawdown, renormalisés si un risque manque ; les deux
momentums actifs restent nécessaires. Les poids et composants sont modifiables dans
la représentation générique. Les Momentum restent expérimentaux, sans garantie.

## Bibliothèque et migration

Une seule bibliothèque et un menu de sauvegarde :

- **Stratégie** : configuration financière, sans univers implicite ;
- **Univers** : filtres uniquement, sans stratégie ;
- **Recherche complète** : combinaison explicite des deux.

Créer, charger, remplacer par le brouillon, dupliquer, renommer, activer/désactiver,
supprimer, exporter/importer JSON sont accessibles. Charger prépare un brouillon.
Le serveur valide la configuration, les noms, les types et la propriété des objets.
L’import ne contient ni code exécutable ni requête vers un fournisseur.

Migration additive `20261104_explorer_saved.sql` : nouvelle table `explorer_saved`,
clé étrangère utilisateur, unicité utilisateur/type/nom, limite 150 objets par compte.
Les anciennes tables `saved_searches` et `saved_presets`, leurs routes et la couche
« historique » de la bibliothèque sont retirées (12/11/2026). Elles étaient vides en
production ; `scripts/oneshot/migrate_saved_to_explorer.py` (idempotent) permet de copier
leur contenu vers `explorer_saved` (kind `search`) sur une base qui en aurait encore.

« Tout remettre à zéro » prépare une configuration vide : aucune période, aucun
seuil, aucune contribution ni filtre d’univers ; aucun score artificiel. La fraîcheur
n’est pas un filtre caché dans ce cas neutre. « Valeurs d’origine » restaure le profil
prédéfini d’origine, sans changer les univers ni les objets sauvegardés. Ces deux
opérations attendent Appliquer.

Les fonctions d’enregistrement pour portefeuille restent dans les API existantes ;
leur ancienne exposition redondante a été retirée d’Explorer. Aucun portefeuille
ni transaction n’est modifié en choisissant ou sauvegardant une stratégie Explorer.

Retour arrière du code : les anciennes tables sont toujours utilisables. Pour
retirer la nouvelle table, le script `rollback_explorer_saved.py --empty-only`
**refuse toute table contenant des sauvegardes**. Exporter et conserver celles-ci
avant un rollback de schéma. Aucun rollback de production n’a été exécuté.

## Performance et frontières

Les indicateurs déjà stockés sont lus en groupe. Les statistiques supplémentaires
sont calculées par lots de 500 titres à partir des cours, volumes, splits et taux
stockés ; aucun appel Yahoo à la recherche ni au détail Explorer. Les mesures de
chemin ont un cache commun indépendant des seuils. Les verdicts et contributions
sont compactés et compressés. Les caches sont invalidés par les calculs, traitements,
changements d’univers et calendrier de clôtures. Les règles utilisant le volume
coté ajoutent une empreinte ordonnée des volumes au cache de verdicts, sans invalider
inutilement les statistiques historiques à chaque cotation.

Les filtres d’univers sont appliqués avant le reclassement de la sélection retenue.
La recherche textuelle et les filtres de présentation de négociabilité masquent
ensuite des résultats ; ils ne redéfinissent pas les percentiles financiers. Une
recherche exacte peut montrer un titre exclu, toujours identifié sans faux score.

Le benchmark `scripts/benchmark_explorer.py` couvre 9 611 titres synthétiques et
24 contributions. Il mesure le moteur de score en mémoire et la taille compressée,
**pas** un temps de réponse SQL complet de 9 611 historiques sur Hostinger.
Les tests d’intégration couvrent SQL/API avec un univers contrôlé plus petit.

## Comparaison V1 : limite explicite

Le véritable fichier demandé était
`~/domains/bourse.turnjoy.dev/public_html/scan.py` sur Hostinger. La tentative SSH
en lecture seule vers le port 65002 a retourné **Connection refused**. Aucune copie
locale de ce scanner n’a été trouvée. Les anciens documents de conception ne sont
pas considérés comme une preuve de ses formules exactes.

La comparaison chiffrée V1/V2 de GEHC, ROP, VFC, TDOC, EVER et MAX sur des historiques
strictement identiques est donc **non validée**. Les formules exactes V1 de continuité,
pics, liquidité et score restent à confronter au scanner et à son jeu de référence.
Aucune équivalence V1 n’est revendiquée et aucune règle spécifique cachée n’a été
ajoutée pour retrouver artificiellement des résultats. Le moteur permet de configurer
manuellement les critères génériques disponibles. Les séries des tests sont explicitement
synthétiques et ne constituent pas les historiques réels des six titres.

Industrie fine et mode de réplication ETF ne sont pas disponibles dans le catalogue
actuel : ils sont signalés comme indisponibles. Les secteurs/catégories, régions,
encours, frais et similarités ETF déjà stockés restent accessibles. Aucun élargissement
de la collecte n’est dissimulé dans cette refonte.

## Validation et livraison

Voir `EXPLORER_V4_VALIDATION.md` pour les résultats exécutés et les limites.
Les scénarios B à J ont des parcours Chromium dans
`tests/e2e/explorer-reconstruction.cjs` (1280, 390 et 375 px, souris, clavier, toucher).
Le scénario A exact V1 reste bloqué pour les raisons ci-dessus. Les autres suites
navigateur conservent les contrôles financiers, ETF, portefeuilles et comptes.

Le workflow `pr-validation.yml` exécute la validation sur pull request, sans
secrets de production ni étape de déploiement. Le workflow Hostinger existant reste
inchangé. Livraison sur branche dédiée et PR vers main ; aucune fusion ni mise en
production autorisée par cette demande.
