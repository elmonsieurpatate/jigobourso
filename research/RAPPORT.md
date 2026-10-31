# Ce que valent les classements de Jigobourso : rapport des analyses statistiques

Résultats calculés sur vos historiques exportés (1 553 actions et 1 447 ETF, 410 dates de décision espacées de 21 séances, février 1993 à octobre 2026), avec le protocole figé avant tout résultat (`research/PROTOCOLE.md`). Scripts : `scripts/research_panel.py`, `research_analyses.py`, `research_stats.py`. Rien n'a été modifié dans l'application, les stratégies, les scores, les portefeuilles ni la base de production.

**Avertissements valables pour toutes les lignes.** (1) L'univers ne contient que des titres encore cotés en 2026 : les titres disparus manquent, ce qui flatte surtout les titres volatils et les anciens gagnants ; le biais est très marqué avant 2005. (2) Aucun taux de change : les seuils absolus ne s'appliquent qu'aux titres en dollars, les rendements restent en devise locale. (3) Pas de secteur ni de capitalisation. (4) Les périodes ont déjà été consultées : tout est exploratoire, pas une validation vierge. (5) Rendements « par date » : les excès sont exprimés en points de pourcentage sur l'horizon (21 ou 63 séances).

## 1. Résumé exécutif

1. **Une seule règle passe le test principal : le Momentum 6-1.** Sur les 10 tests de la famille principale (5 stratégies × 21 et 63 séances, Top 20, actions négociables ≥ 1 M$/jour, seuil de Bonferroni p < 0,005), seul le Momentum 6-1 est significatif : excès brut de **+0,77** point à 21 séances (intervalle à 95 % par blocs [+0,25 ; +1,32], p = 0,004) et **+2,60** à 63 séances ([+1,31 ; +4,02], p < 0,001). Il est positif dans les trois sous-périodes (1993-2007, 2008-2015, 2017-2026) et ne dépend pas d'une exécution au cours de clôture : l'entrée à la clôture du lendemain donne +0,79 et +2,50. Après 30 points de base de frais avec rotation complète : +0,17 (21 séances) et +2,00 (63 séances).
2. **Pour le Momentum, la position dans le classement porte de l'information.** À 63 séances, l'excès brut décroît avec le rang : Top 5 +4,7 ; Top 10 +3,4 ; Top 20 +2,6 ; Top 50 +1,4 ; et par tranches 6-10 +2,2 ; 11-20 +1,8 ; 21-50 +0,6. Ce n'est donc pas seulement l'appartenance à un groupe de titres. **Mais le Top 1 n'est pas fiable** : moyenne +12,7 portée par quelques cas exceptionnels, médiane +3,9, identique à celle de l'univers.
3. **Les quatre profils existants n'ont pas montré de pouvoir prédictif positif fiable.** Régulière : excès brut proche de zéro. Rebond : négatif à tous les horizons et dans les trois sous-périodes (−0,49 à 21 séances, −0,65 à 63). Faible volatilité : classement inversé, les mieux classés font moins bien (Top 1 −2,0 ; Top 5 −1,7 ; Top 20 −0,8 à 63 séances). Rapide : léger avantage brut (+0,54 et +1,26) mais non établi après prise en compte de la dépendance entre dates (p = 0,075 et 0,066), sans gradient selon le rang (Top 5 +2,0, Top 50 +1,3) : un effet de groupe plus que de position. Après frais, ces quatre profils sont à zéro ou négatifs.
4. **Le Momentum coûte cher en risque.** Perte mensuelle jusqu'à −38 % ; VaR 95 % mensuelle −11,9 % et CVaR 95 % −18,0 % (net, portefeuille de 20 titres rééquilibré tous les 21 séances) ; baisse maximale −55 % contre −47 % pour l'univers ; série de 7 mois perdants ; sélection à 83 % d'un même pays. Plusieurs des pires mois ne coïncident pas avec un marché baissier (par exemple juin 2026 : −37,8 % contre −1,4 % pour l'univers).
5. **Les indicateurs pris un à un prédisent très peu l'ensemble des titres** (|corrélation de rang| ≤ 0,03). Les deux effets les plus nets : le **retournement à un mois** (les titres qui ont le plus monté le dernier mois font légèrement moins bien ensuite : −0,019, significatif) et le **momentum 12-1** (+0,022 après contrôle du momentum 6-1 et de la volatilité, intervalle [+0,011 ; +0,034]). Le R², la pente, la distance aux moyennes mobiles et l'évolution des volumes n'apportent rien de plus.

## 2. Tableau comparatif (actions, Top 20, négociables ≥ 1 M$/jour)

Excès sur l'univers éligible, en points, brut puis après 30 points de base par sens avec rotation complète. Confiance : A = test principal passé ; B = indice exploratoire ; C = pas d'effet détecté ; D = effet négatif constaté.

| Stratégie | Qualité du classement | Excès brut 21 s | Excès brut 63 s | Après frais 63 s | Risque (CVaR 95 % mensuelle) | Stabilité par sous-période | Sensibilité à la liquidité | Confiance |
|---|---|---|---|---|---|---|---|---|
| Régulière | pas de gradient | −0,28 | +0,24 | −0,36 | −13,4 | irrégulière | résultats voisins | C |
| Rapide | effet de groupe, pas de gradient | +0,54 | +1,26 | +0,66 | −18,3 | positive dans 2 périodes sur 3 à 21 s et 3 sur 3 à 63 s | ≈ | B |
| Rebond | négatif | −0,49 | −0,65 | −1,25 | −11,0 | négative partout | négatif partout | D |
| Faible volatilité | inversé (meilleur rang = pire) | −0,26 | −0,81 | −1,41 | −9,7 | plutôt négative | négatif | D |
| **Momentum 6-1** | **gradient net par rang** | **+0,77** | **+2,60** | **+2,00** | **−18,0** | **positive dans les 3 périodes** | **diminue avec la liquidité** | **A** |

## 3. Détail des cinq analyses

**Analyse 1 – qualité du classement (Top 1, 5, 10, 20, 50 et tranches).** Voir §1.2 et §1.3. Les p-valeurs « hasard » du fichier détaillé (tirages au hasard à une même date) sont indicatives : elles ne tiennent pas compte de la dépendance entre dates, seul l'intervalle par blocs fait foi.

**Analyse 2 – pouvoir prédictif (corrélation de rang à chaque date, 410 dates).**
- Momentum 6-1 : +0,004 (21 s) et +0,011 (63 s), non significatifs sur l'ensemble de l'univers. Son avantage est concentré sur les tout premiers rangs.
- Momentum 12-1 : +0,015, et +0,022 [+0,011 ; +0,034] après contrôle du momentum 6-1 et de la volatilité.
- Retournement 1 mois : −0,019 à 21 séances, t = −3,0 ; se maintient après contrôle (−0,022).
- R² : +0,013 à 21 séances, mais +0,003 (non significatif) après contrôle du momentum et de la volatilité : redondant.
- Pente : ≈ 0 ; corrélation de rang de 0,91 avec le momentum 6-1 : mesure la même chose.
- Distance à la moyenne 50 jours : redondante avec le retournement (0,86). Volumes (évolution) : aucun pouvoir. Valeur échangée (taille) : aucun pouvoir.
- Volatilité : corrélation ≈ 0 mais les déciles de volatilité sont parfaitement ordonnés (le décile le plus volatil gagne +1,4 à 21 séances et +4,5 à 63 séances de plus que le moins volatil). C'est un effet de queue, très probablement gonflé par le biais de survie ; il n'est pas exploitable.

**Analyse 3 – déciles.** Momentum 6-1 : forme en U (premier décile +1,6 ; cinquième +1,2 ; dixième +1,9 à 21 s), écart dixième − premier non significatif (+0,24 à 21 s ; +1,69 à 63 s). L'information est dans les extrêmes, pas dans tout le classement. Régularité : progression cohérente (monotonie +0,95). Rapide (parmi les titres retenus, dates avec au moins 100 retenus) : dixième décile bien au-dessus (+6,2 contre +1,5 à 21 s), à confirmer car peu de dates.

**Analyse 4 – risques (simulation chronologique : 20 titres égaux, rééquilibrés tous les 21 séances, frais sur la rotation réelle).** Voir §1.4. Profils « Faible volatilité » : dispersion mensuelle plus faible (3,1 à 3,6 points contre 8,8 pour le Momentum) et CVaR 95 % de −7,6 à −9,7, mais baisse maximale non meilleure que l'univers (−44 à −63 % contre −35 à −49 %) et rendement net inférieur de 0,8 à 1,0 point par mois. C'est un outil de réduction de la variabilité mensuelle, pas de protection contre les krachs. Pires épisodes du Momentum 6-1 : juin 2026 (−37,8 % ; WOLF, VICR, VSH), février 2020 (−35,0 % ; SIG, SGRY, CWH), juin 2022 (−33,0 % ; WTI, SND, CRK), septembre 2008 (−28,1 % ; contre −28,6 % pour l'univers), mars 2025 (−18,9 %) : des paquets de titres d'un même thème qui se retournent ensemble.

**Analyse 5 – horizons.** Sélection conservée N séances (Momentum 6-1, Top 20, négociables) : excès brut +0,10 (5 s), +0,40 (10 s), +0,77 (21 s), +1,61 (42 s), +2,60 (63 s), +5,09 (126 s). Il croît avec la durée ; aucun horizon n'est présenté comme optimal. Rééquilibré toutes les 63 séances : rotation 73 % et excès net +1,86 [+0,35 ; +3,38] (p = 0,015, au-dessus du seuil de Bonferroni : exploratoire). Rééquilibré toutes les 21 séances : rotation 45 %, excès net +0,50 [−0,02 ; +1,05]. Persistance des listes d'un mois sur l'autre : Momentum 55 %, Faible volatilité 25 %, Régulière 16 %, Rapide 8 %, Rebond 4 % ; les quatre profils existants changent donc presque entièrement de sélection chaque mois (rotation de 82 à 99 %), ce qui explique des frais élevés.

**Analyse 6 – nouvelles stratégies candidates (6 variantes, critères fixés d'avance).** **Les six sont écartées.** Aucune ne bat le Momentum 6-1 simple. Momentum + régularité (C1) : −0,23 à 21 s, −0,41 à 63 s. Momentum + faible volatilité (C2) : réduit fortement le risque (CVaR −11,6 % au lieu de −18,0 %) mais détruit l'avantage (−0,88 à 21 s et −2,60 à 63 s, significatif). Momentum + tendance longue (C3) : −0,23 et −0,62. Momentum + volumes (C4) : −0,64 et −1,50. Tendance longue + correction modérée (C5) : −0,43 et −2,15. Rebond confirmé (C6) : seulement 105 dates, très instable (−3,1 en 1993-2007, +0,8 puis +0,5 ensuite). Ce que ça montre : l'avantage du Momentum vit dans les titres les plus volatils, on ne peut pas réduire le risque par ces filtres sans le perdre.

**ETF.** Aucun résultat net : Momentum 6-1 ≈ 0 (−0,03 à 21 s, +0,46 à 63 s, non significatifs), Régulière et Rebond ≈ 0, Faible volatilité négatif. Rapide a un seul résultat positif (+1,98 [+0,24 ; +4,22] à 21 s, sans filtre de liquidité) sur 45 dates seulement : exploratoire.

## 4. Recommandations pour Jigobourso (aucune modification faite)

- **Les classements existants sont-ils prédictifs ?** Pas de façon détectable pour Régulière, Rebond et Faible volatilité sur ces données ; Rapide : un indice d'effet de groupe, non établi. Leur intérêt descriptif (régularité, pente, volatilité) reste distinct et n'est pas remis en cause.
- **Critères utiles :** momentum (6-1, mieux 12-1) et, en sens inverse, le rendement du dernier mois. **Redondants :** pente (≈ momentum 6-1), distance aux moyennes mobiles (≈ rendement du mois), R² (après contrôle). **Sans signal détecté :** évolution des volumes, taille.
- **Le Momentum 6-1 doit-il rester expérimental ?** Oui. Seul résultat positif robuste, mais perte mensuelle jusqu'à −38 %, baisse maximale supérieure à l'univers, 83 % d'un même pays, avantage décroissant avec la liquidité, biais de survie non corrigé.
- **Profils qui limitent le risque plutôt que chercher la performance :** « Faible volatilité » réduit la variabilité mensuelle mais ne protège pas mieux que l'univers en cas de baisse prolongée ; son classement n'a pas de valeur prédictive.
- **Pistes à étudier plus tard (sans les intégrer) :** rééquilibrage trimestriel pour réduire la rotation, momentum 12-1 avec exclusion du dernier mois, listes plus stables, et surtout des données incluant les titres disparus pour mesurer le vrai biais de survie. Toute piste supplémentaire doit être confirmée sur des observations non encore utilisées.

## 5. Ce qui n'a pas pu être calculé de façon fiable
Secteur et taille réelle des titres (absents de l'export) ; conversion de devises ; creux en cours de mois (clôtures seulement) ; exécution à l'ouverture ; titres radiés ; graphiques (non produits à ce stade).
