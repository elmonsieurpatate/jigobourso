# Méthode de calcul (V2)

## Mesures sur une fenêtre de n séances (n+1 clôtures)
Toutes sur le logarithme du cours : une hausse de 10 % suivie d'une baisse de 10 % ne s'annule pas, et un titre à 5 € se compare à un titre à 500 €.

| Mesure | Définition |
|---|---|
| Pente | pente de la régression de ln(cours) sur le temps, en % par séance : 100·(e^b − 1) |
| R² | part de la variance de ln(cours) expliquée par cette droite (0 à 1). Mesure la **régularité** de la hausse |
| Performance | variation entre la première et la dernière clôture, en % |
| Volatilité | écart-type des variations quotidiennes de ln(cours), en % par séance (≥ 3 séances) |
| Repli maximal | plus forte baisse depuis un sommet de la fenêtre, en % |
| ER (efficacité) | rendement net / distance parcourue, en ln : +1 = montée sans repli, 0 = aller-retour, négatif = baisse |

Abandonné par rapport à l'ancien moteur : **accélération** (définition ambiguë), **exposant k** du classement. Les cours bruts et ajustés ne sont jamais mélangés (ajustés si toute la série en a). Les clôtures viennent de Yahoo Spark, déjà corrigées des splits.

## Données douteuses
Un saut de cours d'une séance à l'autre de plus de ×1,6 (ou ÷1,6), sans split connu, est une **rupture** : aucune fenêtre qui la traverse n'est évaluée, le titre est « non évaluable » sur ces périodes. Série trop courte, dernière clôture plus ancienne que celle de la place : « non évaluable » (jamais « écarté »).

## Verdicts
- **Retenu** : tous les critères actifs de toutes les périodes actives sont satisfaits.
- **Écarté** : au moins un critère mesuré échoue (même si une autre mesure manque).
- **Non évaluable** : rien n'échoue, mais une mesure manque.
- **Exclu** (catalogue/préfiltre, pas la stratégie) : jamais évalué, jamais recommandé.
Chaque verdict conserve la liste de ses raisons (période, critère, valeur, seuil, résultat).

## Classement
Pour chaque période active, percentile du score (pente, performance, régularité ou −volatilité selon le mode) parmi les titres **retenus du même groupe** (actions ou ETF) ; score final = moyenne pondérée des percentiles (0–100). Départage : symbole.

## Stratégies de départ (propositions, modifiables)
Niveaux de pente = temps pour doubler à ce rythme : doux 8 ans (0,034 %/séance), modéré 4 ans (0,069 ≈ +19 %/an), fort 2 ans (0,138), très fort 1 an (0,276 %/séance = 100·(2^(1/252)−1) ≈ +100 %/an). Régularité par résidu de la droite : souple (R² ≥ 0,56), équilibrée (≥ 0,75), stricte (≥ 0,89).
- **Croissance régulière** : mois et trimestre, pente modérée (≥ 0,069 %/séance), R² souple (≥ 0,56). Classement par régularité. → 191 actions et 67 ETF retenus (≈ 4 %).
- **Croissance rapide** : semaine (pente très forte, performance ≥ 0) et mois (pente très forte, performance ≥ 12 %). Classement par performance. → 389 actions, 11 ETF (≈ 8 %).
- **Rebond** : semaine et mois en hausse douce (R² souple) alors que le semestre n'a pas progressé de plus de 10 %. Classement par pente. → 196 actions, 497 ETF.
- **Hausse calme** : mois et trimestre, pente douce, R² souple, volatilité ≤ 1,5 %/séance (≈ 24 % annualisée), repli ≤ 20 %. Classement par stabilité. → 38 actions, 45 ETF.

Calibrage du 28/10/2026 sur 9 700 titres réels. Avec les seuils initiaux, « régulière » ne retenait que 52 actions (R² 0,75 sur deux périodes) et « calme » 4 : trop peu pour offrir un choix. Variantes testées : voir l'historique du calibrage dans ce paragraphe ; les réglages restent modifiables par l'utilisateur.

## Préfiltre de liquidité (réglable en Administration)
Cours ≥ 2 € ; liquidité (cours × volume moyen 3 mois, en euros) ≥ 1 M€/jour pour une action, ≥ 250 k€/jour pour un ETF. Sans cotation Yahoo : pas de décision (le titre n'est ni collecté ni recommandé). Exemple : DVDG.DE, 131 titres/jour à 42 € ≈ 5 520 €/jour → exclu.

## Cotation principale (règle R1)
Place d'origine (pays de l'émetteur) si le produit y est coté ; sinon plus forte liquidité en euros ; départage : devise euro, puis ordre alphabétique. Exemple : SAP → Xetra (SAP.DE).

## Collecte
Tick toutes les 15 minutes : barres de 15 min des places ouvertes (+ dernier créneau), clôtures quotidiennes une fois la séance publiée (30 min après la fermeture). Nuit (02 h UTC) : Quote, taux de change, préfiltre, cotation principale, mesures, détection/réparation des trous, rétention (580 jours / 20 séances). Un jour sans aucune barre pour une place est un jour férié, pas un trou.

## Ordre de la recherche (Explorer et fiche)
1. Univers : toutes les cotations éligibles (`v_recommendable` : sélectionnées et principales). Jamais une cotation exclue, quels que soient les critères ou les filtres.
2. Filtres de l'utilisateur (type, place, pays, catégorie, PEA, détenus, place ouverte, budget, prix, volatilité et repli maximaux, volume, données à jour) : ils déterminent les titres examinés. Les filtres numériques utilisent les mesures de la plus longue période active.
3. Évaluation de ces titres selon la configuration réellement choisie (périodes, seuils, filtres techniques). Un profil prédéfini ne fait que préremplir cette configuration : modifiée, elle est appliquée telle quelle (`name` = `custom`). « Recherche libre » = aucun critère de départ.
4. Classement : rang et score sont des percentiles parmi les titres retenus de la sélection, par groupe (actions / ETF). Changer les filtres change donc le classement ; le score minimum s'applique après.
5. Pagination, uniquement après les étapes précédentes. Les nombres « titres examinés sur N » et « résultats » sont affichés.
La fiche d'un titre reçoit la même configuration et les mêmes filtres (depuis l'Explorer : `titre.html?src=explorer`) ; elle annonce « Verdict calculé selon … » et permet de choisir un profil ou la stratégie d'un portefeuille. Sans configuration transmise, le réglage par défaut est annoncé comme tel.
Recherches enregistrées : critères + filtres + tri (`saved_searches`).
