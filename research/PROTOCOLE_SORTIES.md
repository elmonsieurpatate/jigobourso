# Protocole : règles de sortie et durée de conservation (figé avant tout résultat)

Programme : `scripts/research_exits.py`. Lecture seule sur le panel et les historiques exportés. Aucune modification de Jigobourso. Les résultats ne servent qu'à juger si de futures alertes « Conserver / Surveiller / Vente à envisager » auraient une utilité ; ils ne remplacent pas une validation sur de nouvelles données.

## Sélections et exécution
- Cinq stratégies : Régulière, Rapide, Rebond, Faible volatilité, Momentum 6-1. Actions seulement, négociables (≥ 1 M$/jour, cotées en USD), Top 20 à chaque date de décision du panel (toutes les 21 séances, 1993-2026).
- **Mêmes sélections initiales pour toutes les variantes.** Entrée à la clôture de la séance **suivant** la date de décision. Une position n'est gardée que si ses 126 séances de suivi existent (sinon elle est écartée pour **toutes** les variantes).
- Un signal de sortie est calculé à la clôture du jour *d* avec les seules données jusqu'à *d* ; la vente a lieu à la clôture de la séance *d + 1*. Durée maximale : 126 séances (vente forcée).
- Après une sortie, l'argent reste en liquidités à 0 % jusqu'à la fin de la fenêtre de 126 séances (pas de réinvestissement) : toutes les variantes sont comparées sur la même fenêtre. Un portefeuille réel qui réinvestit aurait un autre profil ; ce n'est pas simulé ici.
- Frais : 30 points de base par achat ou vente (aller-retour 0,6 %), identique pour toutes les variantes (un seul aller-retour par position) ; 10 et 60 points de base en sensibilité.

## Variantes
**Durées fixes (comparateurs)** : vente à 21, 63 et 126 séances.
**Règles générales (cinq stratégies)** :
- **R1 Sortie du Top 50** : à chaque date de décision suivante (toutes les 21 séances), le titre n'est plus parmi les 50 premiers de sa stratégie (parmi les négociables).
- **R2 Momentum négatif** : le momentum 6-1 du titre (variation du cours entre J−126 et J−21) devient négatif.
- **R3 Stop suiveur** : la clôture passe sous 80 % de son plus haut depuis l'entrée (−20 %).
**Règle propre à la stratégie (une seule par stratégie)** :
| Stratégie | Règle | Seuil |
|---|---|---|
| Régulière | perte de régularité | R² sur 63 séances < 0,556 (le seuil « souple » du profil), contrôlé chaque semaine |
| Rapide | ralentissement de la hausse | rendement sur 21 séances < 0 |
| Rebond | fin du rebond | clôture sous la moyenne mobile 50 séances |
| Faible volatilité | augmentation de volatilité | écart-type des variations quotidiennes sur 21 séances > 2,25 % (1,5 × la limite du profil) |
| Momentum 6-1 | ralentissement | rendement sur 63 séances < 0 |

Aucun balayage de seuils : un seul seuil par règle, fixé ici.

## Mesures
Par stratégie et par variante : rendement net moyen sur la fenêtre de 126 séances ; pire 5 % des positions ; CVaR 95 % des dates (moyenne des 5 % de dates les plus mauvaises) ; baisse maximale moyenne de la position pendant sa détention ; part des sorties anticipées ; durée moyenne de détention ; **ventes prématurées** (part des sorties anticipées dont le cours est plus haut à la séance 126 qu'à la vente) ; **gains manqués ou pertes évitées** (variation moyenne du cours entre la vente et la séance 126) ; différence avec la conservation 126 séances et avec la durée fixe de durée moyenne la plus proche, intervalle à 95 % par bootstrap à blocs mobiles sur les dates (bloc 12 dates), stabilité par sous-période (1993-2007, 2008-2015, 2017-2026).

## Verdict (réglé d'avance, par règle, comparé à la conservation 126 séances)
Famille de tests : 5 stratégies × 4 règles = 20 ; seuil de Bonferroni p < 0,0025.
- **« améliore le rendement »** : écart de rendement net > 0 avec intervalle entièrement positif et p < 0,0025.
- **« réduit le risque sans coût détecté »** : CVaR 95 % des dates améliorée d'au moins 10 % **et** l'intervalle de l'écart de rendement contient 0 ou est positif.
- **« réduit le risque mais coûte du rendement »** : CVaR améliorée d'au moins 10 % et l'intervalle de l'écart de rendement entièrement négatif.
- **« pas d'effet détecté »** sinon.
Tout résultat reste exploratoire : les périodes ont déjà été consultées.

## Limites connues
Univers des titres encore cotés en 2026 (biais de survie) ; pas de change ; clôtures seulement (un stop à −20 % peut en réalité être exécuté plus bas) ; positions étudiées une à une, fenêtres de 126 séances qui se chevauchent entre dates (d'où les blocs) ; pas de simulation de portefeuille avec réinvestissement.
