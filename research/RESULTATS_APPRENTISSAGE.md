# Score appris contre le Momentum 6-1 : résultats (02/11/2026)

Exécution sur Hostinger, lecture seule, commit `ee0976c`, protocole `research/PROTOCOLE_APPRENTISSAGE.md` figé avant résultats. Sortie brute de `scripts/research_ml.py` ci-dessous.

## En bref
- **Aucun des deux modèles ne bat le Momentum 6-1.** Écart net −0,56 (M1) et −0,60 (M2) point par période de 21 séances, non significatif (p ≈ 0,09), négatif en 1993-2007 et 2017-2026.
- **Ils classent mieux l'ensemble des titres** (IC moyen +0,013 / +0,016 contre +0,006 pour le momentum 6-1) **mais moins bien le haut du classement**, là où le Momentum gagne (cf. `RAPPORT.md` §1.2 : l'avantage du Momentum est dans les extrêmes). Une cible en rangs récompense le classement de tout l'univers, pas des 20 premiers.
- **Moins de risque** : CVaR 95 % mensuelle −15 au lieu de −18. Verdict réglé d'avance : « réduit le risque mais coûte du rendement ».
- **Rotation presque doublée** (0,78 contre 0,46) : les frais mangent une partie du rendement.
- Ce que le modèle retient, de façon stable : momentum 12-1 (+), retournement du dernier mois (−), écart à la moyenne 50 j (−), écart à la moyenne 200 j (+). Le momentum 6-1 seul change de signe d'un apprentissage à l'autre (60 %) : il est absorbé par le 12-1 et le 200 j.
- Conséquence : **pas d'intégration dans l'application**. Aucun réglage modifié après lecture des résultats.

---

*Actions négociables, 20 titres, rééquilibrage toutes les 21 séances, entrée à la clôture suivante, frais 30 pb par sens. Le modèle n'apprend que sur des dates passées (fenêtre croissante, écart de 2 dates, réapprentissage tous les 12 dates). Univers des titres encore cotés en 2026 (biais de survie) ; exploratoire.*

## Scénario « usd_1M » (référence des conclusions)

| Modèle | Dates | Rendement net moyen | Réf. mêmes dates | Écart vs référence [IC95 blocs] | Stabilité (1993-2007 / 2008-2015 / 2017-2026) | Rapport rdt/écart-type (réf.) | CVaR 95 % (réf.) | Rotation | IC moyen | 36 dernières dates (réf.) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 score appris linéaire (13 rangs) | 348 (dès 1998-03-11) | +1.27 | +1.83 | -0.56 [-1.22 ; +0.08] p=0.092 | -1.25 / +0.24 / -0.62 | +0.156 (+0.203) | -15.4 (-18.0) | 0.78 (0.46) | +0.0128 | +2.52 (+3.08) | **réduit le risque mais coûte du rendement** |
| M2 score appris courbe (13 rangs + carrés) | 348 (dès 1998-03-11) | +1.24 | +1.83 | -0.60 [-1.29 ; +0.09] p=0.091 | -1.01 / +0.21 / -0.94 | +0.161 (+0.203) | -15.2 (-18.0) | 0.77 (0.46) | +0.0156 | +1.00 (+3.08) | **réduit le risque mais coûte du rendement** |

IC moyen du momentum 6-1 sur les mêmes dates : +0.0063 [-0.0088 ; +0.0198].

Sensibilité aux frais (rendement net moyen, 10 / 30 / 60 pb) : lineaire +1.58/+1.27/+0.80 ; courbe +1.54/+1.24/+0.78

### Ce que M1 a appris (dernier apprentissage, 30 réapprentissages, 203834 lignes)

| Variable | Poids | Même signe qu'au dernier apprentissage |
|---|---|---|
| momentum 6-1 | -0.0205 | 60 % |
| écart à la moyenne 50 j | -0.0196 | 100 % |
| écart à la moyenne 200 j | +0.0175 | 90 % |
| momentum 12-1 | +0.0162 | 100 % |
| rendement du dernier mois (retournement si négatif) | -0.0105 | 97 % |
| régularité (R²) | +0.0082 | 100 % |
| pente de tendance | +0.0076 | 50 % |
| distance au plus haut 12 mois | +0.0042 | 70 % |

### Ce que M2 a appris (dernier apprentissage, 30 réapprentissages, 203834 lignes)

| Variable | Poids | Même signe qu'au dernier apprentissage |
|---|---|---|
| volatilité 6 mois (au carré) | -0.0366 | 90 % |
| distance au plus haut 12 mois (au carré) | -0.0290 | 100 % |
| rendement du dernier mois (au carré) | -0.0239 | 100 % |
| écart à la moyenne 200 j (au carré) | +0.0222 | 100 % |
| momentum 6-1 | -0.0204 | 60 % |
| écart à la moyenne 50 j | -0.0200 | 100 % |
| momentum 3-1 (au carré) | -0.0192 | 100 % |
| momentum 12-1 (au carré) | +0.0181 | 73 % |

## Scénario « relatif_50% » (robustesse)

| Modèle | Dates | Rendement net moyen | Réf. mêmes dates | Écart vs référence [IC95 blocs] | Stabilité (1993-2007 / 2008-2015 / 2017-2026) | Rapport rdt/écart-type (réf.) | CVaR 95 % (réf.) | Rotation | IC moyen | 36 dernières dates (réf.) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 score appris linéaire (13 rangs) | 348 (dès 1998-03-11) | +1.14 | +1.53 | -0.38 [-0.97 ; +0.21] p=0.185 | -0.73 / +0.28 / -0.58 | +0.151 (+0.179) | -14.8 (-17.3) | 0.75 (0.46) | +0.0177 | +2.87 (+2.80) | **réduit le risque mais coûte du rendement** |
| M2 score appris courbe (13 rangs + carrés) | 348 (dès 1998-03-11) | +1.14 | +1.53 | -0.38 [-0.99 ; +0.21] p=0.200 | -0.55 / +0.33 / -0.80 | +0.156 (+0.179) | -14.7 (-17.3) | 0.75 (0.46) | +0.0181 | +1.48 (+2.80) | **réduit le risque mais coûte du rendement** |

IC moyen du momentum 6-1 sur les mêmes dates : +0.0073 [-0.0088 ; +0.0222].

Sensibilité aux frais (10 / 30 / 60 pb) : lineaire +1.44/+1.14/+0.69 ; courbe +1.45/+1.14/+0.69

## Pistes possibles (non testées, à figer dans un nouveau protocole avant tout essai)
1. **Cible centrée sur le haut du classement** (par exemple « le titre finit-il dans le décile supérieur ? », régression logistique) au lieu du rang complet : c'est là que vit l'avantage du Momentum.
2. **Score appris comme filtre** du Momentum (écarter les titres du Top 20 du Momentum que le modèle classe dans la moitié basse) plutôt que comme classement autonome.
3. Rééquilibrage moins fréquent pour réduire la rotation.

## Limites
Biais de survie, pas de change, clôtures seulement, pas de secteur ; périodes déjà consultées par les analyses précédentes (exploratoire).
