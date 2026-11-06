# Dernier jour dans les scores V4 — proposition chiffrée (NON implémentée)

État : **aucune formule modifiée.** Les scores actuels ignorent le dernier jour ; seul le filtre facultatif « dernier jour positif » existe (administration → Profils → mode avancé), indépendant de la notation.

## 1. Ce que V1 faisait réellement
`scan.py` : `force = 0,15 × min(jour, 8 %) + 0,35 × min(semaine, 25 %) + 0,50 × min(mois, 80 %)`, rendements bruts et signés, puis `note = force × régularité × 100`.
Le « 15 % » est un poids **sur l'échelle des rendements**, pas 15 points de note. Comme un jour vaut en moyenne bien moins qu'une semaine ou un mois, l'influence réelle du jour sur la force est faible : sur les titres en hausse semaine + mois de la base de test, **médiane 3 à 7 %** de la force (90e centile 10 à 18 %). Un jour négatif de −1 % coûtait 0,15 point de force sur ~9, soit −1,6 %.

## 2. Solution proposée (un seul indicateur, signé, saturé)
- `r1 = ln(P_t / P_{t−1})` sur la **dernière séance clôturée** du marché du titre (jamais une séance en cours ; sinon indicateur « indisponible », pas 0).
- `D_jour = clamp(r1 / sat(1), −1, +1)` avec `sat(1) = 17 % × (1/5)^0,52 = 7,36 %` (même loi de saturation que les autres granularités ; équivalent du plafond V1 de 8 %). Contrairement aux granularités de tendance (bornées à [0, 1]), il est **signé** : une journée négative peut pénaliser. Pas de R², pas de pente : ce n'est pas une granularité.
- Score simple : `D' = max(0, (1 − λ) × D + λ × D_jour)` puis `score = 100 × D' × Q × f` ; Régularité Q et accélération f inchangées.
- Score complexe : note de dynamique `d' = max(0, (1 − λ) × d + λ × 100 × D_jour)`, contribution `poids_dynamique × d'` ; les autres composantes, la liquidité (comptée une fois) et l'ancrage récent sont inchangés.
- `λ` configurable, `λ = 0` = désactivé (comportement actuel). Un seul paramètre.

## 3. Influence exacte (en points de score, hors saturation)
| λ | simple, par +1 % de jour (Q·f = 0,6) | simple, amplitude max ±7,36 % | complexe, par +1 % | complexe, amplitude max |
|---|---|---|---|---|
| 0,05 | 0,41 | ±3,0 | 0,27 | ±2,0 |
| 0,10 | 0,82 | ±6,0 | 0,54 | ±4,0 |
| 0,15 | 1,22 | ±9,0 | 0,81 | ±6,0 |
Formules : simple `100·Q·f·λ / 7,36` par point de rendement ; complexe `100·w_dyn·λ / 7,36` avec `w_dyn = 0,40`.

## 4. Choix de λ
Pour retrouver l'influence réelle de V1 (et pas son poids nominal), λ doit valoir **environ 0,05** (influence médiane V4 : 4,2 % / 8,6 % / 3,8 % de D sur trois séances, contre 3,1 % / 6,6 % / 2,7 % pour V1). **0,15 appliqué à une note normalisée donne environ 3 fois l'influence de V1.** Recommandation : défaut **λ = 0,05**, préréglage « V1 nominal » λ = 0,15 disponible, désactivable.
Écartés : jour **non signé** « note 0 si ≤ 0 » (baisse quasi uniforme de 15 % de D pour tout titre en baisse, quelle que soit l'ampleur : Δ −0,45 pt si jour négatif contre −0,42 si positif, aucune discrimination) ; jour **normalisé par la volatilité** (déplace trop le classement : Spearman 0,86–0,91 contre 0,93–0,98).

## 5. Effet mesuré sur le classement réel (2 253 titres réels, ¼ de l'univers, dernière séance 2026-11-05)
Corrélation de rang (Spearman) simple / recouvrement du top 100 / décalage de rang des titres du top 100 (médiane, max), selon la séance utilisée comme « dernier jour » (la dernière : médiane −2,2 %, 77 % de titres en baisse ; la précédente : +1,2 % ; la 3e : −0,2 %) :
| λ | dernière | avant-dernière | 3e |
|---|---|---|---|
| 0,05 | 0,982 / 98 / 2, 18 | 0,994 / 97 / 2, 26 | 0,998 / 99 / 2, 17 |
| 0,10 | 0,958 / 95 / 5, 41 | 0,989 / 95 / 3, 54 | 0,993 / 96 / 3, 48 |
| 0,15 | 0,930 / 92 / 7, 68 | 0,986 / 92 / 6, 84 | 0,983 / 92 / 5, 81 |
Score complexe : Spearman ≥ 0,99 pour la dernière séance (0,93–0,96 sur les deux autres), top 100 commun 92–99.

**Croissance régulière avec une seule journée négative** (R² mois ≥ 0,8, ≥ 55 % de séances positives, 4 séances précédentes en hausse, dernière séance négative : 12 titres le 5/11). Rang avant → après :
| titre | jour | rang λ=0,05 | rang λ=0,10 | rang λ=0,15 | note simple 0 → 0,05 → 0,15 |
|---|---|---|---|---|---|
| JLHL | −7,00 % | 1 → 2 | 1 → 2 | 1 → 2 | 61,4 → 55,4 → 43,5 |
| EXR | −0,57 % | 14 → 14 | 14 → 17 | 14 → 19 | 40,3 → 38,0 → 33,3 |
| PSA | −0,66 % | 19 → 20 | 19 → 21 | 19 → 22 | 39,1 → 36,8 → 32,2 |
| EXEL | −5,71 % | 67 → 80 | 67 → 102 | 67 → 133 | 26,5 → 23,0 → 16,2 |
| SPG | −0,86 % | 72 → 74 | 72 → 81 | 72 → 82 | 25,5 → 23,8 → 20,5 |
Moyenne des 12 : rang 161 → 165 (λ=0,05), 172 (0,10), 177 (0,15). Un petit repli (< 1 %) coûte 0 à 3 rangs à λ = 0,05 et une journée à −5/−7 % coûte plusieurs dizaines de rangs à λ = 0,15 : la pénalité est proportionnelle à l'ampleur, jamais une exclusion ni un effet de seuil.
Top 100 actuel : 46 ont un dernier jour négatif ; après λ = 0,05 : 44 ; après 0,15 : 38.

## 6. Limites (à lire avant de valider)
- Échantillon : 2 253 titres (un titre sur quatre) d'une export réel ; trois séances de test seulement, donc trois régimes de marché ; **aucune mesure de pouvoir prédictif** (l'effet sur les rendements futurs n'est pas testé).
- La séance du 05/11 est le dernier point de l'export ; je n'ai pas pu vérifier qu'il s'agit d'une clôture définitive (77 % de titres en baisse, médiane −2,2 %). Le moteur devra recevoir la **dernière clôture définitive** (déjà le cas pour `daily_prices` : clôtures définitives uniquement).
- L'équivalence d'influence avec V1 est estimée avec une approximation de D sur 781 à 1 063 titres en hausse ; ordre de grandeur, pas une identité.
- Aucun code de score modifié : il faudra une nouvelle mesure stockée (`day_change`), le paramètre λ dans le profil et la version de formule (`scores.VERSION`) incrémentée.
