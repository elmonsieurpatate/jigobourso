# Synthèse de l'expérience d'apprentissage (résultat négatif)

*Étude exploratoire sur des survivants sélectionnés aujourd'hui par le catalogue : biais de survie et de sélection non corrigés. Rien ici ne démontre qu'une stratégie aurait réellement surperformé, et l'apprentissage automatique n'a PAS amélioré le classement.*

## Ce que nous avons appris
1. **Les données.** 3 000 titres (1 553 actions, 1 447 ETF), historique quotidien 1993-2026. Les actions ont de la profondeur (70 % au moins 10 ans) ; les ETF sont trop récents (médiane environ 7 ans, 34 % au moins 10 ans) : aucun apprentissage crédible sur les ETF. Actions négociables en USD (>= 1 M de valeur échangée) : 122 en 1995, 421 en 2007, 1 024 en 2026. Avant 1998 les données sont de mauvaise qualité.
2. **Biais non corrigeables.** Titres encore cotés ET retenus aujourd'hui par le catalogue ; aucun taux de change ; frais en hypothèses ; cours ajustés fournis après coup.
3. **Nettoyage.** Une première règle prenait des krachs réels pour des splits (12 des 24 cas : CORT, FENC, VSTM, GOSS, KOD, KRRO, GRAL, NKTR, SVRA…) et aurait effacé leurs pertes : l'amélioration apparente des rendements était artificielle. Règle corrigée (asymétrie hausse/baisse, volume du jour) ; A1 neutralisé plutôt que corrigé. Sur l'univers négociable, le nettoyage touche très peu d'exemples (69 sur 318 575 lignes).
4. **Momentum.** Sur tout l'historique (1993-2026), le Momentum 6-1 est la seule règle significative (excès brut +0,77 à 21 séances, +2,60 à 63 ; net 30 pb +0,17 et +2,00). Sur la fenêtre de validation (2004-2022, actions USD liquides) l'effet est plus faible et non significatif : +0,48 et +1,54 ; le 12-1 à 21 séances donne +0,77 [+0,08 ; +1,48], +0,42 net de 60 pb. Les causes (période, univers USD, grille de dates, biais de survie plus marqué avant 2005) n'ont pas été décomposées.
5. **Le classement porte peu d'information.** Corrélation de rang proche de zéro pour tous les indicateurs ; déciles plats ou en U (à 63 séances le décile le plus bas du momentum rapporte +4,5 %, le plus haut +4,3 %). Le Top 20 du momentum est un pari risqué : CVaR 95 % mensuelle d'environ -20 %.
6. **Apprentissage.** Ridge (V1, V2, cible écrêtée) ne bat aucune référence ; à 63 séances il est significativement pire que le Momentum 6-1 (-2,97 [-5,04 ; -0,91]), dans les trois sous-périodes. Il apprend une relation (volatilité et R² élevés) stable à l'entraînement mais inversée hors échantillon.
7. **Rigueur.** Purge = horizon + 10 séances, période finale protégée (non lue), sensibilités (S1, S3, brut) jamais utilisées pour choisir le modèle, tests sur données synthétiques sans signal.

## Limites de cette expérience
- Les six stratégies actuelles n'ont PAS été rejouées sur les mêmes dates dans cette expérience.
- Univers USD uniquement ; frais en hypothèses ; période déjà consultée dans les analyses précédentes.

## Ce qui peut servir à Jigobourso (sans prétendre que le machine learning a aidé)
- Ne rien changer au classement ; aucun modèle d'apprentissage à intégrer.
- Les Momentum restent « en essai » : l'avantage mesuré concerne les actions liquides, pas les ETF (momentum ETF ≈ 0 dans l'analyse précédente).
- Faible volatilité : outil de réduction du risque (CVaR -10 % à 21 séances contre -21 %), pas de prédiction de performance.
- La rotation pèse sur le net : le 12-1 tourne moins que le 6-1 (29 % contre 45 % à 21 séances).
- Le Suivi accumulera des résultats réels hors échantillon : refaire le point plus tard avec des critères fixés à l'avance.
