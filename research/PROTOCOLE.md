# Protocole des analyses statistiques (figé avant tout résultat)

Branche `research/analyses-statistiques`. Aucune modification de l'application, d'une stratégie, d'un score, d'un classement ni de la base de production. Lecture seule sur les historiques exportés (`~/tmp-history-long`, 1 553 actions et 1 447 ETF, cours ajustés, volumes).

## 0. Données et limites connues avant de commencer
- Univers : titres **encore cotés en 2026** (biais de survie, très marqué avant 2005 : environ 12 % des titres d'un échantillon sont présents en 1995, 21 % en 2001). Un filtre de liquidité ne le corrige pas.
- Pas de taux de change : les seuils absolus ne s'appliquent qu'aux titres en dollars ; rendements en devise locale ; les devises ne sont jamais mélangées pour simuler un portefeuille réel.
- Pas de secteur dans l'export actuel, pas de capitalisation : la liquidité sert d'approximation de la taille. Robustesse « secteur » : **non calculable** tant que l'univers n'a pas la colonne `category`.
- Seules la clôture, la clôture ajustée et le volume existent : l'exécution est modélisée à la **clôture de la séance suivante** (décalage d'une séance), pas à l'ouverture.
- Les périodes 1993–2015 et 2017–2026 ont déjà été consultées : tout ce qui suit est **exploratoire**, pas une validation vierge.

## 1. Construction commune (point-in-time)
- Dates de décision : toutes les 21 séances du calendrier de référence (≥ 150 titres, seuil de présence 10 %), à partir de 1993-01-01 et de l'indice 126 ; au plus `max(horizon)` séances avant la fin.
- À chaque date, seuls les cours et volumes **connus ce jour-là** servent (420 séances visibles pour le moteur ; liquidité sur les 63 séances **précédant** t, t exclu, couverture ≥ 80 %, titre écarté s'il a un split non ajusté dans la fenêtre).
- Rendement futur : `adjclose` (dividendes et splits inclus). Référence : entrée à la clôture de t (comparable aux travaux précédents) ; **sensibilité** : entrée à la clôture de t+1.
- Horizons : 5, 10, 21, 42, 63, 126 séances. **Principaux : 5, 21, 63.** Les autres sont exploratoires.
- Scénarios de liquidité (actions) : `aucun`, `usd_1M` (cotés en USD, ≥ 1 M$/jour), `relatif_50%` (moitié la plus liquide de chaque devise). **Scénario de référence pour les conclusions : `usd_1M`.** ETF : `aucun` et `usd_1M` seulement.
- Actions et ETF toujours analysés **séparément**.
- Coûts : 10, 30 et 60 points de base par achat ou vente. Sélection conservée N séances (notion 1) : un aller-retour exact. Portefeuille rééquilibré (notion 2) : coût appliqué au **turnover réel** (part des titres remplacés).
- Le classement des profils de l'application est celui du moteur (`strategy.judge`/`rank`) à chaque date ; le filtre de négociabilité s'applique **après** le classement (comme l'Explorer), en gardant l'ordre. Les règles simples (momentum, volatilité…) sont triées sur les titres éligibles.

## 2. Statistiques
- Comparaisons à la **même date, même univers éligible, même horizon, mêmes frais**.
- Intervalles : **bootstrap par blocs mobiles** sur les dates (bloc = max(3, 2 × ⌈h / 21⌉) dates), 2 000 tirages, graine 1. Les actions d'une même date ne sont jamais traitées comme indépendantes (on agrège par date d'abord).
- Dates indépendantes : sous-échantillon espacé de ⌈h / 21⌉ ; l'effectif effectif est toujours affiché.
- Hasard : tirages de même taille dans le même univers éligible, 500 tirages par date, p-valeur sur les dates espacées.
- **Famille principale** (seule soumise à la correction de Bonferroni) : 5 stratégies (Régulière, Rapide, Rebond, Faible volatilité, et le momentum 6-1) × Top 20 × horizons 21 et 63 × scénario `usd_1M` × actions = **10 tests**. Seuil : p < 0,005 (bilatéral 5 % / 10). Tout le reste est **exploratoire** et étiqueté ainsi ; aucun optimum d'horizon ou de taille n'est « retenu ».
- Sous-périodes fixées d'avance : P1 1993–2007, P2 2008–2015, P3 2017–2026 (2016 absent des fichiers précédents ; ici toutes les dates sont gardées et signalées).

## 3. Analyses
1. **Qualité du classement** : Top 1, 5, 10, 20, 50 et tranches 1–5, 6–10, 11–20, 21–50, aux horizons 5, 21, 63. Moyenne, médiane, excès brut et net sur l'univers éligible, part de dates positives, dispersion, IC par blocs, stabilité par sous-période, sensibilité aux frais et à la liquidité, comparaison au hasard. Le Top 1 n'est jamais jugé sur sa moyenne seule (médiane, part de dates positives, contribution de la meilleure date).
2. **Pouvoir prédictif** : corrélation de rang de Spearman à chaque date (IC) entre signal et rendement futur ; moyenne, médiane, dispersion, part de dates positives, t-stat sur dates espacées, IC par blocs ; IC **partiel** après contrôle du momentum 6-1 et de la volatilité ; corrélations de rang entre signaux (redondance). Signaux : pente, R², volatilité (126 séances), momentum 3-1 / 6-1 / 12-1, retournement 1 mois, évolution des volumes, distance au plus haut 12 mois, drawdown 12 mois, écart à la moyenne 200 j.
3. **Déciles** : 10 déciles par date parmi les éligibles, rendement moyen et médian par décile, écart D10−D1, cohérence (corrélation de rang entre décile et rendement), robustesse par tercile de liquidité (substitut de taille).
4. **Risque** : portefeuille chronologique rééquilibré toutes les 21 séances (Top 20 équipondéré, turnover réel), volatilité, drawdown maximal, VaR/CVaR 95 % mensuelles, pires rendements 5/21/63 séances, séries de pertes, récupération, concentration. Les drawdowns ne sont donnés que pour cette simulation.
5. **Horizons** : (a) sélection initiale conservée N séances (courbe d'excès par horizon, tous présentés) ; (b) portefeuille réellement rééquilibré tous les 21 et 63 séances, avec turnover et coûts. Les deux ne sont jamais mélangées.
6. **Candidates** (maximum **6** variantes, définies ci-dessous, seuils fixés) : voir §4.

## 4. Nouvelles stratégies candidates
Déjà testées sous forme voisine dans `backtest_walkforward.py` : `trend_mom` (momentum + au-dessus de la moyenne 200 j), `smooth_mom` (pente × R²), `risk_adj_mom` (momentum / volatilité), `dual_mom` (12-1 positif), `reversal_1m`. Les candidates ci-dessous sont des **filtres sur le Momentum 6-1** (rang par `mom_6_1`, titres éligibles), sans balayage de seuils :

| Id | Hypothèse | Règle fixée |
|---|---|---|
| C1 | Régularité | `mom_6_1` parmi les titres dont le R² (126 séances) est au-dessus de la **médiane** des éligibles |
| C2 | Volatilité | `mom_6_1` parmi les titres dont la volatilité (126 séances) est sous la **médiane** des éligibles |
| C3 | Tendance longue | `mom_6_1` parmi les titres avec `mom_12_1 > 0` |
| C4 | Volumes | `mom_6_1` parmi les titres dont le volume en valeur (21 dernières séances / 63 précédentes, médianes) est au-dessus de la **médiane** des éligibles |
| C5 | Tendance longue + correction modérée | titres avec `mom_12_1 > 0` et rendement 1 mois entre −10 % et 0 %, classés par `mom_12_1` |
| C6 | Rebond confirmé | titres à ≥ 30 % sous leur plus haut 12 mois, `mom_3_1 > 0` et cours > moyenne 50 j, classés par `mom_3_1` |

Comparateurs obligatoires pour chaque candidate : univers éligible, hasard, `mom_6_1` simple, profil existant le plus proche (C1/C2 : « Régulière » ; C5/C6 : « Rebond »).
**Critères de réussite fixés d'avance** (tous requis) : (1) l'excès net (30 pb) de la candidate sur `mom_6_1` simple est positif à 21 **et** 63 séances, scénario `usd_1M`, Top 20 ; (2) l'intervalle de confiance par blocs de cet écart exclut 0 sur l'échantillon complet, avec Bonferroni sur 12 tests (6 variantes × 2 horizons) : seuil p < 0,004 ; (3) le signe est positif dans au moins 2 des 3 sous-périodes ; (4) la CVaR 95 % mensuelle de la candidate n'est pas pire de plus de 10 % que celle de `mom_6_1`. Sinon : « écartée » ou « non concluante », jamais « prometteuse » sur une seule période.

## 5. Journal
`research/JOURNAL.md` : chaque exécution (commit, tâche, paramètres, résultat résumé), y compris les échecs. Aucun résultat n'est retiré.
