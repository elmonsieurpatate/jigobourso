# Protocole : score appris (apprentissage automatique), figé avant tout résultat

Programme : `scripts/research_ml.py`. Lecture seule sur le panel (`scripts/research_panel.py`, `~/tmp-backtest/research/out/panel/panel.pkl.gz`). Aucune modification de Jigobourso, de la base ni des stratégies.

## Question
Un modèle qui apprend, **uniquement sur le passé**, comment combiner les 13 indicateurs du panel fait-il mieux que le Momentum 6-1 simple (seule règle qui a passé le test principal, `research/RAPPORT.md`) ?

## Données et construction (identiques à `PROTOCOLE_STRATEGIES.md`)
- Actions négociables, scénario de référence `usd_1M` (cotées en USD, ≥ 1 M$/jour) ; robustesse : `relatif_50%`. ETF exclus.
- Portefeuille de 20 titres équipondérés, rééquilibré toutes les 21 séances, entrée à la clôture de la séance suivante (`g21`), frais 30 pb par sens sur les poids échangés (10 et 60 en sensibilité).
- Indicateurs (13, ceux du panel, connus à la date t) : `m61 m121 m31 m1 vol126 slope r2 hi mdd252 ma200 ma50 vtr liq`.

## Modèles (deux, aucun de plus ; aucun réglage optimisé)
- Chaque indicateur est remplacé, **à chaque date et parmi les titres éligibles**, par son rang percentile centré (−0,5 à +0,5). Valeur manquante : 0 (la médiane).
- Cible : rang percentile centré de `g21` parmi les titres éligibles de la même date. Le modèle apprend donc à **classer**, pas à prévoir un niveau de marché.
- **M1 linéaire** : régression ridge sur les 13 rangs.
- **M2 courbe** : régression ridge sur les 13 rangs et leurs carrés centrés (rang² − 1/12), pour capter les formes en U vues dans les déciles.
- Pénalité ridge fixée : λ = 0,01 × (nombre de lignes d'entraînement) / 12 (1 % de la variance d'un rang).

## Apprentissage chronologique (aucune information future)
- Fenêtre d'entraînement **croissante** : toutes les dates de décision antérieures d'au moins **2** dates (42 séances) à la date de décision, pour que le rendement cible (22 séances après t) soit entièrement connu.
- Au moins **60 dates** d'entraînement (≈ 5 ans) avant la première décision.
- Le modèle est réappris toutes les **12 dates** (≈ 1 an) ; entre deux, les coefficients ne changent pas.

## Comparaisons et verdict (réglé d'avance)
- Référence : Momentum 6-1 simple, **mêmes dates**, même univers, mêmes frais, même exécution. Écart net par date, intervalle à 95 % par bootstrap à blocs mobiles (bloc 3 dates), p-valeur par blocs.
- Corrélation de rang (IC) du score avec `g21` à chaque date, comparée à celle du momentum 6-1.
- Stabilité : sous-périodes 1993-2007, 2008-2015, 2017-2026 ; signe des coefficients d'un réapprentissage à l'autre.
- Verdicts identiques à `PROTOCOLE_STRATEGIES.md`, Bonferroni sur **2** modèles : p < 0,025.
  - **« améliore le rendement »** : écart net positif, intervalle entièrement positif, p < 0,025, positif dans au moins 2 sous-périodes sur 3.
  - **« meilleur compromis rendement/risque »** : CVaR 95 % améliorée d'au moins 10 %, rapport rendement/écart-type au moins égal, intervalle de l'écart contenant 0 ou positif, 2 sous-périodes sur 3.
  - **« réduit le risque mais coûte du rendement »** / **« pas mieux »** sinon.
- Les 36 dernières dates (≈ 3 ans) sont **aussi** rapportées à part, pour information.

## Limites connues avant de commencer
Univers des titres encore cotés en 2026 (biais de survie) ; pas de change ni de secteur ; clôtures seulement ; périodes déjà consultées par les analyses précédentes (tout reste **exploratoire**). Un verdict favorable ne serait qu'un indice, à confirmer sur de nouvelles observations (le Suivi en production) avant toute intégration dans l'application.
