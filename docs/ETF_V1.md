# Analyse des ETF V1

Information indépendante des scores, de la sélection et du tri. Aucune collecte massive, aucune API payante : historiques existants, profils Yahoo en cache et une requête pour la fiche ouverte.

## Similarité

Méthode **hebdomadaire en EUR** sur 52 semaines (corrélation quotidienne écartée : les places ferment à des heures différentes, VOO / SXR8.DE donne 0,56 en quotidien EUR contre 0,89 en hebdomadaire EUR). Rendements logarithmiques entre deux clôtures du même jour de semaine espacées de 7 jours ; une clôture manquante supprime les deux rendements qui l'utilisent, rien n'est interpolé. Chaque jour de semaine forme une série **sans chevauchement** : cinq corrélations de Pearson indépendantes, dont la moyenne est le coefficient affiché. Au moins **40 semaines** par jour de semaine ; sinon, pas de coefficient.

Un couple est « stable » si l'écart entre les cinq corrélations reste <= 0,15 et si les deux moitiés de la période diffèrent de <= 0,20 ; sinon il est marqué instable et jamais masqué. Paliers fixes : >= 0,97 quasi identiques, >= 0,90 très proches, >= 0,80 proches. Pas de seuil réglé à la volée.

Préparation financière existante réutilisée (splits déclarés, sous-unités, ruptures). Conversion en EUR au taux historique de la date (jamais le taux actuel) ; change absent : observation absente. Cours ajustés non garantis : corrélation de cours, pas de rendements totaux.

Familles : regroupement transitif des paires >= 0,90 (union-find) ; étiquette « Groupe A, B… ». Les paires non comparables (cache ancien, historique insuffisant) sont comptées à part, jamais présentées comme « sans lien ». Une corrélation négative n'est pas une duplication.

Voisins d'un ETF : jusqu'à cinq, coefficient >= 0,80, hors autre cotation du même fonds. Comparaison de jumeaux : frais, liquidité (EUR/jour), place et devise, émetteur, actifs, rendement de distribution, écart de performance sur un an en EUR, chevauchement partiel des lignes (borne basse : seules les lignes dont le poids est connu comptent). Inconnu reste inconnu.

## Pastilles (lecture rapide)

Quatre états : vert, orange, rouge, gris (inconnu). Chaque pastille porte un mot et une explication : la couleur n'est jamais seule. Elles reprennent les critères existants sans rien modifier aux scores ni aux classements : régularité (R2 0,75 / 0,556), risque (1,5 % par séance et repli de 20 %, puis le double), liquidité (minima du préfiltre x4), qualité des données, similarité, concentration des dix premières lignes (40 / 70 %), risques propres (effet de levier, matières premières : détectés par le nom ; « rien détecté » n'est pas « sans risque » et reste gris), part de famille dans un portefeuille (30 / 50 %), part inconnue. Aucune note globale. Au plus trois pastilles par ligne de classement.

## Profils et préchauffage

Ouverture d'une fiche ETF : une requête Yahoo pour cet ETF (profil version 3 : actifs, rendement de distribution). La maintenance récupère progressivement les profils manquants, par passage : au plus 120 profils et 60 secondes, dans cet ordre : ETF détenus et dix premiers de chaque classement, 300 premiers du dernier classement, puis le reste des ETF sélectionnés. Un profil récent n'est jamais redemandé avant 30 jours ; un profil indisponible est réessayé après 1 jour (groupes prioritaires) ou 30 jours (le reste). Arrêt au premier HTTP 429, reprise au passage suivant : aucune API payante, aucun impact sur les cours et devises.

Prétraitement au recalcul existant des mesures / maintenance, matrice par blocs de 32 ETF, pas de matrice N×N permanente. Explorer ne lit que les résumés nécessaires. Portefeuille : petits vecteurs prétraités, aucune lecture des historiques. Cache de plus de trois jours exclu des calculs d'exposition et de similarité des portefeuilles.

## Composition et provenance

Profils en cache ; un seul appel Yahoo pour la fiche ouverte (voir ci-dessus). Date affichée = récupération du profil ; la date effective de composition est inconnue. Profil de plus de 90 jours exclu de la ventilation des montants mais reste consultable avec avertissement. Ancien parseur version 1 : poids nul potentiellement artificiel, rendu inconnu. La somme des dix premières lignes exige dix poids valides ; aucun poids absent n'est converti en zéro.

Les secteurs Yahoo décrivent la poche actions : pour ventiler tout le fonds, leurs poids sont multipliés par la proportion d'actions déclarée. Si cette proportion manque, ventilation monétaire inconnue. Ne pas confondre secteur des participations, domicile du fonds, devise de cotation et pays d'investissement. Les catégories FinanceDatabase ne sont jamais converties en expositions supposées de 100 %.

Le contrôle des concentrations de classement porte sur les dix premiers ETF de la vue, avant pagination, dans l'ordre déjà déterminé. Trois fonds ou plus d'une catégorie couverte déclenchent l'information. La V1 distingue Énergie (actions) et Matières premières (hors actions) ; elle ne prétend pas classifier exhaustivement les secteurs.

Portefeuille : pondération par valeur actuelle en EUR, pas par nombre de parts ni par coût d'achat. Dénominateur = toutes les positions valorisables. Parts manquantes de composition, actions directes non ventilées, profils absents/anciens : inconnus explicites. Une position non valorisable empêche d'afficher un pourcentage global fiable.

## Couverture

`scripts/verify_etf_release.py` ouvre une transaction READ ONLY et mesure deux périmètres : toutes les cotations ETF, puis les ETF sélectionnés et principaux. Compte séparément instruments, cotations, profils, lignes, poids, secteurs, frais ; les motifs sont indépendants et non additionnables. Ne fixe pas 4 676 comme dénominateur : compte la base réelle. Le rapport est un artefact privé de la livraison, conservé un jour, jamais publié sur la branche de statut.

Aucune table utilisateur modifiée. Seule table ajoutée : `etf_analysis`, données dérivées remplaçables. Pas de fournisseur payant.


## Frais, actifs et regroupement (30/10/2026)

- **Frais courants et actifs sous gestion** : lus dans la réponse de cotation Yahoo déjà demandée (`netExpenseRatio`, `netAssets`), sans requête de plus. Ils servent de repli quand le profil détaillé du fonds n'est pas en cache ; une valeur absente reste « inconnue ». Les cotations multiples d'un même fonds donnent le même actif sous gestion.
- **Regroupement des ETF quasi identiques** (toute la page affichée, calculé à la maintenance, aucun calcul de corrélation à l'affichage) : le premier ETF de la page en est le chef ; un membre doit lui être lié DIRECTEMENT (jamais en chaîne), avec une corrélation hebdomadaire en EUR de 0,97 au moins ET le même indice d'après le nom, ou de 0,99 au moins sans nom d'indice commun. Même couverture de change et mêmes marqueurs de stratégie (buffer, levier, ESG, mines, revenus renforcés…) sont exigés. Chaque membre affiche ce qui le rapproche et ce qui le distingue (distribution, devise de cotation, frais). Aucun ETF n'est masqué ; rangs, scores et ordre ne changent pas.
- Une corrélation ne prouve ni la même composition ni les mêmes risques ; le nom d'un indice proche ne rend pas deux fonds interchangeables.
