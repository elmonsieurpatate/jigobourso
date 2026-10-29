# Lecture du classement demandé — aucun changement de méthode

Données réelles lues sur Hostinger le 29 octobre 2026, clôtures au 28 octobre. Configuration reconstruite d'après la demande : semaine 5 + mois 21, pente très forte sur chacune, aucun minimum de R²/ER, aucun plafond de repli, aucun rendement minimal supplémentaire, classement Performance et poids non personnalisés. Sans filtres pratiques additionnels : **743 actions retenues**. Des filtres ou seuils supplémentaires conservés dans le navigateur peuvent modifier ces effectifs et rangs.

| Action / identité | Place | Rang V2 | Semaine | Mois | Pente 5 séances, %/séance | Pente 21 séances, %/séance | R² semaine / mois | ER semaine / mois |
|---|---|---:|---:|---:|---:|---:|---|---|
| CXM — Sprinklr Inc. | NYSE | 78 | +7,6324 % | +43,3610 % | 1,051937 | 1,717537 | 0,697828 / 0,961728 | 0,891388 / 0,857695 |
| AR — Antero Resources Corporation | NYSE | 79 | +9,3482 % | +25,4394 % | 2,040554 | 1,079823 | 0,938107 / 0,954426 | 1 / 0,685277 |
| DOW — Dow Inc. | NYSE | 65 | +12,3436 % | +23,6146 % | 2,322775 | 1,029396 | 0,874379 / 0,869685 | 0,903757 / 0,631843 |

## Admission : deux conditions séparées

La pente est une régression linéaire des logarithmes des clôtures, avec un pas par séance. Elle est transformée en `100 × (exp(pente_log) − 1)` : même unité de % par séance pour tous les horizons. Cinq séances utilisent six clôtures ; 21 séances en utilisent 22.

« Très forte (~1 an) » signifie un rythme théorique de doublement en 252 séances : **environ 0,2754 % par séance**. La pente doit dépasser ce seuil **sur les deux périodes** : semaine ET mois. La V2 ne moyenne pas deux pentes pour décider de l'admission. Une bonne pente mensuelle ne compense pas une pente hebdomadaire insuffisante.

Sur une droite exponentielle parfaite, cela représenterait environ +1,38 % en cinq séances et +5,95 % en 21. Ce ne sont pas des seuils de rendement réellement imposés : la pente de régression tient compte de toutes les clôtures, contrairement au rendement entre deux extrémités. Ce rythme n'est évidemment pas une prévision de doublement.

Avec régularité « aucune », R² n'est ni un filtre obligatoire ni un poids caché du classement Performance. Même constat pour ER et repli lorsqu'aucun critère correspondant n'est activé. Ces indicateurs restent disponibles pour comprendre les risques.

## Classement Performance : moyenne de deux positions relatives

Après admission, la V2 calcule séparément le percentile du rendement sur 5 séances et celui du rendement sur 21 séances, parmi les titres retenus **du même type** (actions séparées des ETF). Sans poids personnalisés, elle en fait la moyenne : **50 % semaine, 50 % mois**. Ce n'est ni le rendement mensuel seul ni une moyenne de rendements bruts.

| Titre | Percentile semaine | Percentile mois | Score moyen /100 | Rang |
|---|---:|---:|---:|---:|
| CXM | 75,2022 | 95,5526 | 85,3774 | 78 |
| AR | 83,4232 | 87,0620 | 85,2426 | 79 |
| DOW | 89,3531 | 84,6361 | 86,9946 | 65 |

CXM figure très haut sur le mois, mais environ un quart des actions retenues a mieux progressé sur la semaine. DOW a un mois moins fort, mais sa meilleure semaine fait monter son score moyen. AR est plus régulier, notamment sur la semaine, mais le mode Performance ne récompense pas ce R² supérieur. Le percentile réduit l'effet d'une performance mensuelle extrême : être le meilleur du mois ne donne au maximum que 100 sur cette moitié du score.

Les rangs sont calculés avant pagination. Le tri visuel peut aussi être différent du mode de classement stratégique : un tri par performance mensuelle ne change pas l'admission ni le score de stratégie.

## Ancien scanner : deux générations à distinguer

Le dépôt V1 conservé contient deux chemins :

1. Le scanner historique `scan.py` mettait d'abord en avant les titres qualifiés sur 5 et 21 séances, puis un score mêlant force des pentes et régularité R² ; d'autres notes pénalisaient les mouvements concentrés et valorisaient les jours de hausse. Ce n'était donc pas simplement le classement Performance actuel.
2. Le moteur `strategy.py` ajouté ultérieurement en V1 utilisait déjà, en mode Performance, des percentiles de rendements combinés avec des poids. Son mode Tendance utilisait une pente logarithmique pénalisée par `max(ER,0)^k` ; Régularité combinait R² et ER. Il ne faut pas attribuer cette pénalisation au mode Performance, où elle n'intervenait pas.

La V2 Performance ressemble donc beaucoup au **dernier** moteur V1 Performance. Les différences comprennent le périmètre retenu, les sources et dates, les cotations principales, la séparation actions/ETF et les départages d'ex æquo. Un classement est relatif : l'arrivée de nombreux concurrents peut faire reculer un titre dont le cours n'a pas baissé.

Je n'ai pas retrouvé l'instantané complet de l'ancienne session où ces titres étaient 31e–33e, avec son univers, ses dates et ses paramètres. Il serait trompeur de chiffrer une part « marché » et une part « algorithme » sans cet instantané. Les valeurs ci-dessus expliquent le classement actuel ; elles ne démontrent pas que le nouveau scanner est intrinsèquement meilleur ni que tout le recul vient du marché.

## Avis et réglages conseillés, sans les appliquer

Pour comparer une forte progression récente sur deux horizons, le classement Performance est cohérent et transparent. Pour **détecter une hausse régulière suffisamment tôt**, il est insuffisant à lui seul : sans seuil de régularité, il accepte aussi des trajectoires heurtées.

Point de départ à tester : conserver semaine + mois, abaisser la pente à Modérée pour éviter d'attendre une hausse déjà très rapide, exiger une régularité Souple ou Équilibrée sur le mois, et utiliser le mode Tendance ou Régularité plutôt que Performance. Un ER minimal et un plafond de repli peuvent compléter le filtre avancé, avec une tolérance moins stricte sur la semaine, naturellement plus bruitée. Vérifier également l'écart à la MM20 pour identifier une hausse déjà très étendue.

Ce sont des propositions d'exploration, pas des seuils statistiquement validés ni une promesse de meilleur rendement. Détecter plus tôt signifie disposer de moins de preuves de régularité. Comparer les profils sur les mêmes dates et observer leur suivi est plus instructif que chercher à retrouver les anciens rangs.

**Aucun algorithme, seuil, filtre ou préréglage du moteur n'a été modifié pour cette analyse.** Sources : `engine/analytics/strategy.py` (admission et percentiles), `engine/analytics/service.py` (univers et classement avant pagination), anciennes versions V1 conservées dans Git. Le script SELECT-only `scripts/explain_current_ranking.py` reproduit les chiffres de cette note sur la base disponible à son exécution.
