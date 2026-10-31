# Protocole : améliorations du Momentum 6-1 (figé avant tout résultat)

Programme : `scripts/research_strategies.py`. Lecture seule sur le panel (`scripts/research_panel.py`). Aucune modification de Jigobourso.

## Pourquoi ces pistes (et pas d'autres)
Les analyses précédentes montrent : un seul avantage mesuré (Momentum 6-1), concentré sur les titres volatils, avec des pertes brutales (jusqu'à −38 % en un mois), des frais qui rongent le gain et un effet de retournement à un mois significatif. Les pistes testées visent donc : (a) mieux choisir la fenêtre de momentum, (b) éviter les cas de retournement, (c) réduire le risque sans perdre l'avantage, (d) réduire les frais. Les pistes qui exigent des données que nous n'avons pas (fondamentaux, secteur, titres disparus) ne sont **pas** testées.

## Construction commune
- Actions négociables (cotées en USD, ≥ 1 M$/jour), scénario de référence `usd_1M` ; robustesse : `relatif_50%`.
- Portefeuille de 20 titres, rééquilibré toutes les 21 séances (dates de décision du panel), entrée à la clôture de la séance suivante (rendement `g21`), frais 30 pb par achat ou vente sur les poids réellement échangés (10 et 60 en sensibilité).
- Comparaison à la même date avec le **Momentum 6-1 simple** (référence) : même univers, mêmes frais, même exécution.

## Huit variantes (aucune de plus ; aucun seuil optimisé)
| Id | Variante | Règle fixée |
|---|---|---|
| V1 | Momentum 12-1 | classement par le rendement de J−252 à J−21 |
| V2 | Momentum composite | moyenne des rangs percentiles du momentum 6-1 et 12-1 |
| V3 | Momentum sans hausse récente | momentum 6-1 en excluant les 10 % des titres ayant le plus monté le dernier mois |
| V4 | Proche du plus haut annuel | classement par la distance au plus haut 12 mois (les plus proches) |
| V5 | Momentum pondéré par l'inverse de la volatilité | mêmes 20 titres que le Momentum 6-1, poids proportionnels à 1 / volatilité 6 mois |
| V6 | Momentum avec filtre de marché | mêmes 20 titres ; investi seulement si le momentum 12-1 médian des titres éligibles est > 0, sinon liquidités (0 %) |
| V7 | Momentum sans volatilité extrême | momentum 6-1 en excluant les 20 % des titres les plus volatils (6 mois) |
| V8 | Rééquilibrage trimestriel | le Momentum 6-1 simple, rééquilibré tous les 63 séances au lieu de 21, comparé au même Momentum rééquilibré chaque mois (rendements composés sur les mêmes 63 séances) |

## Mesures
Rendement net moyen par période, écart-type, rapport rendement/écart-type, baisse maximale, VaR/CVaR 95 %, pire période, rotation, part du temps investi, écart avec la référence (intervalle à 95 % par bootstrap à blocs mobiles, bloc 3 dates), stabilité par sous-période (1993-2007, 2008-2015, 2017-2026).

## Verdict (réglé d'avance, par variante contre la référence ; Bonferroni sur 8 : p < 0,00625)
- **« améliore le rendement »** : écart de rendement net positif, intervalle entièrement positif, p < 0,00625 et signe positif dans au moins 2 sous-périodes sur 3.
- **« meilleur compromis rendement/risque »** : CVaR 95 % améliorée d'au moins 10 %, rapport rendement/écart-type au moins égal à la référence, intervalle de l'écart de rendement contenant 0 ou positif, et écart de signe positif dans au moins 2 sous-périodes sur 3.
- **« réduit le risque mais coûte du rendement »** : CVaR améliorée d'au moins 10 % et rapport rendement/écart-type inférieur à la référence.
- **« pas mieux »** sinon.
Tout verdict favorable reste **exploratoire** (périodes déjà consultées, biais de survie) et devra être confirmé sur de nouvelles observations.
