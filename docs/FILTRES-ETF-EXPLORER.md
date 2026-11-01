# Filtres ETF et zone géographique de l’Explorer

## Les plus gros ETF

Le filtre calcule le décile supérieur des ETF éligibles de `v_recommendable`, avant le classement des résultats et la pagination. Le rang utilise l’encours `netAssets` de Yahoo Finance, converti en euros avec les taux déjà présents dans `fx_rates`. L’encours est la valeur des actifs détenus par le fonds : il ne s’agit ni de sa capitalisation boursière ni de son volume de transactions. Les égalités à la limite du décile sont incluses. Un instrument regroupé sous plusieurs cotations n’est compté qu’une fois. Une valeur absente, non positive ou dont la devise ne peut pas être convertie reste inconnue et n’entre pas dans le calcul du seuil.

Les cotations Yahoo alimentent `latest_prices.net_assets` et leur devise au cours des collectes régulières. Il n’y a pas d’appel Yahoo déclenché par les filtres. Les données AUM les plus récentes sont utilisées ; en l’absence d’un encours collecté, l’ETF n’est pas qualifié de gros. L’encours visible dans les résultats est en euros et n’est affiché que lorsqu’il est connu.

## Zone géographique

Pour les actions, la zone est calculée depuis le pays de rattachement de FinanceDatabase (`instruments.country`) : États-Unis, pays européens, et pays émergents. La place de cotation ne sert pas à déduire la zone. Les pays qui ne relèvent pas de ces trois zones restent inconnus.

Pour les ETF, la seule source utilisée est la catégorie géographique explicite Yahoo/Morningstar (`fundProfile.categoryName`) en cache : catégories « United States Stock », « Europe Stock » et catégories explicites des marchés émergents. Le domicile du fonds, le code de cotation, les dix principales positions et le nom du fonds ne servent pas à attribuer une zone. Les catégories « World », « Global », « International » et ambiguës, comme les réponses sans catégorie, restent inconnues. Ainsi, un ETF mondial n’est jamais classé US simplement parce que les États-Unis pèsent le plus dans ses actifs.

Les profils Yahoo se rafraîchissent par la tâche de maintenance existante, progressivement et avec un budget borné. Le changement de version du parseur les rend à nouveau éligibles à cette actualisation. La classification couvre seulement les fonds pour lesquels Yahoo renvoie un libellé géographique suffisamment précis.

La commande de lecture seule `python -m engine.cli filter-metadata-coverage` donne les dénominateurs et nombres d’instruments recommandables dont l’AUM (en devise convertible), la zone ETF ou le pays d’action sont connus. Les dénominateurs dédoublonnent par instrument. La valeur « Tous » garde les instruments classés et inconnus.
