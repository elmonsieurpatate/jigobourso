# Analyse des ETF V1

Information indépendante des scores, de la sélection et du tri. Aucune collecte nouvelle : profils Yahoo déjà en cache et historiques existants seulement.

## Similarité

Six mois calendaires précédant le calcul, rendements logarithmiques quotidiens, Pearson. Au moins **100 rendements communs** : environ 80 % des 126 séances habituelles d'un semestre. C'est un garde-fou de couverture, pas une garantie statistique. Pas de prix interpolé ; même date de départ ET d'arrivée pour les deux fonds ; intervalles de plus de quatre jours écartés. Dernière clôture de plus de sept jours : série non comparable.

Préparation financière existante réutilisée (splits, sous-unités, ruptures). Conversion de chaque clôture en EUR au taux historique disponible à sa date ou antérieur d'au plus sept jours ; jamais le taux actuel appliqué rétroactivement. Change absent : observation absente. Cours ajustés des dividendes non garantis : corrélation de cours, pas de rendements totaux. Horaires différents entre places : biais résiduel explicité.

Cinq voisins positifs par ETF, coefficient >= 0,80 ; instruments identiques exclus des voisins (autre cotation d'un même fonds). Portefeuille : toutes les paires détenues sont examinées, et seules celles >= 0,90 sont signalées. Pas de conclusion d'absence de risque en dessous de ces repères. Une corrélation négative n'est pas présentée comme une duplication.

Prétraitement au recalcul existant des mesures / maintenance, matrice par blocs de 32 ETF, pas de matrice N×N permanente. Explorer ne lit que les résumés nécessaires. Portefeuille : petits vecteurs prétraités, aucune lecture des historiques. Cache de plus de trois jours exclu des calculs d'exposition et de similarité des portefeuilles.

## Composition et provenance

Profils existants, sans requête Yahoo lors de l'ouverture d'une fiche. Date affichée = récupération du profil ; la date effective de composition est inconnue. Profil de plus de 90 jours exclu de la ventilation des montants mais reste consultable avec avertissement. Ancien parseur version 1 : poids nul potentiellement artificiel, rendu inconnu. La somme des dix premières lignes exige dix poids valides ; aucun poids absent n'est converti en zéro.

Les secteurs Yahoo décrivent la poche actions : pour ventiler tout le fonds, leurs poids sont multipliés par la proportion d'actions déclarée. Si cette proportion manque, ventilation monétaire inconnue. Ne pas confondre secteur des participations, domicile du fonds, devise de cotation et pays d'investissement. Les catégories FinanceDatabase ne sont jamais converties en expositions supposées de 100 %.

Le contrôle des concentrations de classement porte sur les dix premiers ETF de la vue, avant pagination, dans l'ordre déjà déterminé. Trois fonds ou plus d'une catégorie couverte déclenchent l'information. La V1 distingue Énergie (actions) et Matières premières (hors actions) ; elle ne prétend pas classifier exhaustivement les secteurs.

Portefeuille : pondération par valeur actuelle en EUR, pas par nombre de parts ni par coût d'achat. Dénominateur = toutes les positions valorisables. Parts manquantes de composition, actions directes non ventilées, profils absents/anciens : inconnus explicites. Une position non valorisable empêche d'afficher un pourcentage global fiable.

## Couverture

`scripts/verify_etf_release.py` ouvre une transaction READ ONLY et mesure deux périmètres : toutes les cotations ETF, puis les ETF sélectionnés et principaux. Compte séparément instruments, cotations, profils, lignes, poids, secteurs, frais ; les motifs sont indépendants et non additionnables. Ne fixe pas 4 676 comme dénominateur : compte la base réelle. Le rapport est un artefact privé de la livraison, conservé un jour, jamais publié sur la branche de statut.

Aucune table utilisateur modifiée. Seule table ajoutée : `etf_analysis`, données dérivées remplaçables. Pas de fournisseur payant.
