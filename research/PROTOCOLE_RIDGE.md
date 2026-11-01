# Protocole Ridge (figé avant tout résultat)

Branche `research/analyses-statistiques`. Étude **exploratoire** : l'univers ne contient que des titres encore cotés et sélectionnés aujourd'hui par le catalogue (biais de survie ET de sélection, non corrigés). Aucun résultat ne prouve qu'une stratégie aurait réellement surperformé. Aucune modification de l'application, des stratégies, de la base.

## Données
- Actions seulement, historiques exportés (`~/tmp-history-long`), **à partir du 1998-01-01** (avant, les données sont de mauvaise qualité : prix quantifiés, volumes nuls).
- Nettoyage v3 (`scripts/research_cleaning_cases.py`, `classify_v3`) : titres A3 écartés ; **A2** (erreur de cotation isolée) masqué dans la série ; **A1** (regroupement d'actions confirmé) **neutralisé** : aucun rendement n'est inventé, les exemples dont la fenêtre d'indicateurs ou l'horizon contient un A1 sont écartés (critère technique, indépendant de la performance) ; **B** (mouvements réels) et **C** (incertains) conservés. Les données d'origine ne sont jamais modifiées ; la variante « brut » n'applique aucun nettoyage.
- Univers négociable à chaque date, avec les seules données antérieures : cotation en USD, valeur échangée médiane (clôture × volume) >= 1 M sur les 63 séances précédentes, volume présent sur >= 80 % d'entre elles. Pas de taux de change : les titres non cotés en USD sont hors de l'univers principal. Aucun seuil de prix nominal.
- Dates de décision : toutes les 21 séances du calendrier de référence (>= 150 titres), au moins 252 séances d'historique par titre. Entrée à la clôture de t ; sensibilité : clôture de t+1.

## Indicateurs (connus à t) et cibles
- Noyau V1 : momentum 6-1, momentum 12-1, pente (log-cours sur 126 séances), R² de régularité, volatilité réalisée (126 séances). Transformés en **rangs par date** (percentiles).
- Variante V2 (définie à l'avance) : V1 + drawdown sur 63 séances + rendement sur 5 séances.
- Cible : rendement à 21 et à 63 séances moins la **médiane des titres négociables à la même date** (rendement relatif, sans indice externe). Variante : écrêtage de la cible d'ENTRAÎNEMENT aux quantiles 1 % et 99 % estimés **sur l'entraînement du pli**. L'évaluation utilise toujours les rendements réels non écrêtés.

## Walk-forward et purge
- Réentraînement annuel (1er janvier 2004, 2005, …, 2022), fenêtre extensible. Les indicateurs ne regardent que le passé, la cible regarde `h` séances devant.
- **Purge = h + 10 séances** (31 pour la cible à 21, 73 pour la cible à 63) : un exemple d'entraînement daté t n'est admis que si t + h + 10 <= date de réentraînement. Raison : (1) sa cible utilise les cours jusqu'à t + h ; (2) la classification d'un événement de nettoyage (A1) utilise les 10 séances qui le suivent ; sans ces 10 séances une correction « apprise » avec des cours postérieurs à la date de réentraînement fuirait dans l'entraînement. Un `assert` du programme vérifie la règle à chaque pli, et que toute date de test est >= à la date de réentraînement.
- Pour un exemple de test daté t : l'A2 n'est masqué dans ses indicateurs que s'il est connu (événement + 2 séances <= t) ; tout événement des 10 dernières séances le marque C (conservé, signalé) ; les cibles utilisent la série nettoyée a posteriori (mesure du vrai rendement).
- λ du Ridge choisi à chaque pli sur les **3 dernières années de l'entraînement** (validation interne purgée), parmi {1e-4, 1e-3, 1e-2, 1e-1, 1}. Aucun réglage n'utilise les dates de test.
- **Période finale : dates de décision >= 2023-01-01, jamais lue en mode `valid`** : les cibles de validation ne débordent pas sur elle (dernière date de test = début 2023 - 63 séances). En mode `final`, le modèle est entraîné une fois (cibles connues au 1er janvier 2023), gelé, et noté sur la période finale. Le mode `final` **refuse de tourner** si le verdict de `valid` n'est pas « prometteur ».

## Évaluation (sur rendements réels)
- Références : Momentum 6-1 seul, Momentum 12-1 seul (+ faible volatilité, R² et pente seuls). Les profils actuels de Jigobourso ne sont pas rejoués dans cette première expérience (leur moteur est lié à d'autres dates de décision) : à ajouter si le Ridge est prometteur.
- Pour chaque modèle : corrélation de rang (IC de Spearman) par date, Top 20 équipondéré, excès sur la moyenne de l'univers, déciles de score, rotation réelle (part des titres remplacés d'une date à la suivante dans la même chaîne de réajustement), rendement net à 10/30/60/100 points de base par achat ou vente, CVaR 95 %, stabilité par sous-période.
- Intervalles : bootstrap circulaire par blocs de 6 dates (graine fixe).

## Règle de décision (par horizon ; « prometteur » si TOUS les critères sont vrais)
1. IC moyen et excès net à 60 pb de Ridge V1 supérieurs à ceux de la meilleure référence (Momentum 6-1 ou 12-1 seul).
2. L'écart d'excès brut Ridge V1 - référence a un intervalle à 98,75 % (deux tests : 21 et 63 séances) strictement positif.
3. Écart positif dans au moins 2 des 3 sous-périodes (2004-2010, 2011-2016, 2017-2022).
4. CVaR 95 % du portefeuille net 60 pb non pire de plus de 10 % que celle de la référence.
5. Écart brut Ridge V1 - Momentum 6-1 positif aussi avec « S1 » (sans exemples touchés par C) et avec les données « brut ».
V2, la cible écrêtée, S1, S3 (borne agressive) et l'entrée à t+1 sont des **sensibilités** : ils ne servent jamais à choisir le modèle. Pas de boosting si Ridge n'apporte aucune amélioration robuste.

## Limites déclarées
Biais de survie et de sélection (catalogue actuel), univers américain en dollars, frais en hypothèses (aucun spread historique), pas de taux de change, cours ajustés fournis après coup par la source, périodes déjà consultées lors d'analyses précédentes (aucune n'est vierge).
