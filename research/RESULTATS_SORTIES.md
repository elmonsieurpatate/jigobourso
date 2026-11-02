# Règles de sortie : résultats (02/11/2026)

Exécution sur Hostinger, lecture seule, commit `5c81eeb`, 76 s, protocole `research/PROTOCOLE_SORTIES.md` figé avant résultats. Sortie complète : `~/tmp-backtest/research/out/resultats/sorties.md` (et `.json`) sur l'hébergement.

## En bref
1. **Conserver plus longtemps a toujours rapporté plus**, dans les cinq stratégies : vendre à 21 ou 63 séances fait nettement moins bien que conserver 126 séances (≈ 6 mois). Toutes les règles de sortie coûtent du rendement par rapport à « conserver 126 séances » (intervalles entièrement négatifs). Attention : après une sortie, l'argent reste à 0 % jusqu'à la séance 126 (pas de réinvestissement), ce qui pénalise mécaniquement les sorties précoces.
2. **Toutes réduisent le risque** : la moyenne des 5 % de pires dates (CVaR) et la baisse pendant la détention diminuent. Verdict réglé d'avance : « réduit le risque mais coûte du rendement » presque partout.
3. **Ventes prématurées : 55 à 69 %** des sorties anticipées sont suivies d'une remontée du cours avant la séance 126.
4. Comparées à une **durée fixe de même longueur** (comparaison plus juste) :
   - Momentum 6-1, sortie quand le **momentum 6-1 devient négatif** : +2,12 points [+0,67 ; +3,63] contre une sortie fixe à 63 séances. Seule règle nettement meilleure qu'une durée équivalente.
   - Rebond, sortie **sous la moyenne 50 j** : +0,99 [+0,34 ; +1,75] contre 21 séances.
   - **Stop suiveur −20 %** : ni meilleur ni pire qu'une durée équivalente (≈ 0), mais il coupe fortement les pires positions (Momentum : pire 5 % −25 % au lieu de −47 %).
   - **Sortie du Top 50** : équivalente à une durée fixe courte, sans avantage.

## Momentum 6-1 (404 dates, actions négociables, Top 20)

| Variante | Rendement net | Pire 5 % des positions | CVaR 95 % | Sorties anticipées | Jours détenus | Écart vs 126 s | Écart vs durée équivalente |
|---|---|---|---|---|---|---|---|
| Conserver 21 séances | +1,65 | −23,7 | −16,3 | 100 % | 21 | −10,57 | — |
| Conserver 63 séances | +5,92 | −36,7 | −24,1 | 100 % | 63 | −6,29 | — |
| Conserver 126 séances | +12,21 | −46,8 | −29,8 | 0 % | 126 | — | — |
| Sortie du Top 50 | +6,68 | −34,9 | −18,6 | 83 % | 67 | −5,53 | +0,76 vs 63 s [−0,37 ; +2,06] |
| Momentum négatif | +8,04 | −36,5 | −19,8 | 70 % | 84 | −4,17 | **+2,12 vs 63 s [+0,67 ; +3,63]** |
| Stop suiveur −20 % | +5,80 | −25,3 | −17,0 | 76 % | 67 | −6,41 | −0,13 vs 63 s [−1,29 ; +1,14] |
| Ralentissement (63 s < 0) | +2,78 | −24,3 | −15,3 | 93 % | 40 | −9,43 | +1,14 vs 21 s [+0,01 ; +2,48] |

Autres stratégies (écart vs conserver 126 s ; stop −20 %) : Régulière −2,13 ; Rapide −5,41 ; Rebond −1,63 ; Faible volatilité −0,59.

## Conséquences pour les alertes de Jigobourso (proposées, non démontrées)
- Les alertes servent à **surveiller et réexaminer**, pas à vendre vite : aucune règle n'a battu « conserver ».
- Durée : un rappel « réexaminer » vers **6 mois (126 séances)** plutôt qu'au bout de quelques semaines, y compris pour la croissance rapide.
- Momentum : alerte « vente à envisager » quand le **momentum 6-1 du titre devient négatif** (la meilleure règle testée), plutôt qu'à la sortie du Top 50.
- Chute : **stop suiveur −20 %** comme alerte « surveiller » (ou « alléger »), pour limiter les pires cas, en sachant qu'il coûte du rendement.

## Limites
Biais de survie ; pas de change ; clôtures seulement (un stop peut être exécuté plus bas) ; pas de réinvestissement après une sortie ; périodes déjà consultées (exploratoire).
