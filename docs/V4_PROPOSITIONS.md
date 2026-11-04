# Explorer V4 — Propositions à valider avant gel

> Document de la phase préalable/P0. La clarification utilisateur autorise désormais
> l’implémentation avec paramètres provisoires. Voir la version intégrée et les
> défauts semaine/mois dans [README_EXPLORER_V4.md](README_EXPLORER_V4.md).

Date : 4 novembre 2026. Statut : **proposition, non validée par l’utilisateur**.
Ces valeurs ne sont pas les paramètres actifs de l’application. Le banc de calcul
est isolé dans `scripts/preview_growth_v4.py` ; aucun appel applicatif ne l’utilise.

Arbitrage utilisateur : valeurs autorisées **provisoirement** pour examen, sans
validation définitive ni gel. Pente 0,08 ; R² 0,65/0,70/0,75 ; couverture complète ;
poids simples 35/35/30 ; complexes 25/25/20/20/10. Poursuivre les correctifs P0 ;
attendre l’accord sur les formules, catégories et données manquantes avant
intégration finale. Voir le [dossier de revue détaillé](V4_DOSSIER_REVUE.md).

## 1. Admission et couverture proposées

| Période | Séances | Pente minimum en %/séance | R² minimum |
| --- | ---: | ---: | ---: |
| Semaine | 5 | 0,08 | 0,65 |
| Mois | 21 | 0,08 | 0,70 |
| Trimestre | 63 | 0,08 | 0,75 |

Trois fenêtres actives par défaut ; ET entre périodes et entre les deux critères.
Les pentes restent strictement positives et modifiables. 0,08 %/séance correspond
au modèle composé d’environ 0,40 % sur cinq séances, 1,69 % sur 21 et 5,17 % sur
63 ; ce n’est ni un rendement minimum observé ni une prévision. Ce seuil est
supérieur à l’ancien niveau « modéré » (0,0688), nettement inférieur au « très
fort » (0,2754), et commun aux trois horizons pour rester comparable.

R² augmente avec la durée pour demander une tendance durable, en laissant la
semaine plus sensible aux fluctuations. Cette calibration est illustrative et
n’a pas été validée sur un univers représentatif de marché.

Proposition de couverture du **nouveau profil** : 100 % des N+1 clôtures attendues
sur chaque période primaire sélectionnée, bornes comprises. Une séance manquante
produit « calcul indisponible », pas un mauvais score ni une interpolation.
Préserver le support historique de régression à 80 % pour les anciens profils.
Les statistiques de chemin et volumes exigent elles aussi une fenêtre complète.

P0 Momentum : 100 % des 127/253 clôtures calendaires requises, y compris le mois
écarté du rendement. Cela évite qu’une paire de bornes suffise à qualifier un
historique et garde un contrôle cohérent des événements récents.

Cours constant : conserver la convention R²=1 pour une série exactement constante,
avec pente=0, et vérifier les petites erreurs numériques. L’admission reste
impossible car sa pente échoue. L’indication doit dire « cours plat », pas
« croissance régulière ». Cette convention préserve les configurations anciennes.

## 2. Score simple proposé

Normalisation **absolue**, sans percentile : le score ne dépend pas des autres
titres visibles. Moyennes arithmétiques de même poids entre les périodes actives.

| Composante | Poids proposé | Définition |
| --- | ---: | --- |
| Force | 35 % | Moyenne de `100×max(0,s)/(max(0,s)+0,15)` ; s en %/séance |
| Régularité | 35 % | Moyenne de `100×R²` |
| Évolution récente | 30 % | Comparaisons des horizons sélectionnés adjacents, formule ci-dessous |

Le paramètre 0,15 %/séance fixe une demi-saturation de la force ; il n’est pas
un seuil éliminatoire. La fonction récompense une pente forte sans laisser une
hausse extrême dominer sans borne. Les poids, pas la fonction, sont modifiables.

Pour chaque paire courte/longue (semaine/mois et mois/trimestre, ou semaine/
trimestre si le mois est désactivé) :

```text
d = (s_courte − s_longue) / (abs(s_courte) + abs(s_longue))
c = meilleure hausse log / somme des hausses log positives, fenêtre courte
q = min(1, (2/N_court)/c) × max(0,(1−c)/(1−1/N_court))
    si c>0, sinon q=0
a = tanh(2d) × sqrt(R²_court×R²_long) × q
évolution = 50 + 50×moyenne(a)
```

Si le dénominateur des pentes est nul, d=0. Le facteur q vaut zéro lorsqu’une
seule séance explique toutes les hausses : aucun bonus de saut isolé. Il réduit
le bonus lorsque les hausses sont concentrées. Ce frein est continu, sans
exclusion supplémentaire. Les fenêtres sont emboîtées : cette mesure décrit un
changement de tendance, pas une dérivée instantanée ni une preuve causale.

Une seule période sélectionnée : évolution **non applicable**, pas zéro ; poids
force/régularité renormalisés explicitement à 50/50 et détail affiché.
Si plusieurs périodes sont sélectionnées mais une mesure nécessaire manque :
score indisponible, sans bonus ni renormalisation favorable des données manquantes.
Seuls les titres admissibles reçoivent une note et un rang.

## 3. Score complexe proposé

Score distinct, calculé directement à partir des mesures, sans addition du score
simple à ses propres composantes. Pas de capitalisation, de liquidité ou de
qualité de données dans la note : elles sont traitées et expliquées séparément.

| Composante | Poids proposé | Normalisation |
| --- | ---: | --- |
| Force | 25 % | Identique à la composante de force ci-dessus |
| Régularité | 25 % | R² moyen ×100 |
| Évolution | 20 % | Même mesure explicite de changement de pente |
| Risque de trajectoire | 20 % | Moyenne de `100/(1+max(vol/1,5,drawdown/20)²)` |
| Continuité | 10 % | Moyenne de `100×min(proportion_positive, borne((1−c)/(1−1/N),0,1))` |

Volatilité en %/séance ; drawdown positif en %. Utiliser le maximum des deux
ratios évite de sommer deux pénalités fortement liées. La continuité combine
positivité et concentration par le minimum, sans deux poids additionnels.
R² et concentration restent corrélés : ce score n’est pas une mesure statistique
indépendante du risque et n’a pas de validation prédictive.

Une composante requise manquante rend le score complexe **indisponible** ; pas de
renormalisation des manquants. La seule exception est l’évolution non applicable
quand une unique période est volontairement sélectionnée : retirer son poids et
renormaliser les autres, en l’affichant. Les poids administrables non négatifs
doivent totaliser exactement 100 %. Notes bornées 0–100, arrondi d’affichage à
deux décimales, tri sur valeur non arrondie puis symbole et identifiant.

Les deux scores seront versionnés et leurs composantes détaillées (mesure,
transformation, normalisation, poids effectif, contribution, fenêtre, couverture).
Aucune note ne devient un filtre primaire implicite.

## 4. Exemples reproductibles

```bash
.venv/bin/python -m scripts.preview_growth_v4
```

64 clôtures : prix initial 100, puis incréments logarithmiques linéaires sur
63 séances. Les trajectoires accélérée, stable et ralentie ont le même rendement
total de trimestre ; le changement récent, pas ce rendement cumulé, les départage.

| Trajectoire | Incréments log quotidiens | Pentes semaine / mois / trimestre (%/séance) | Admission | Simple | Complexe |
| --- | --- | --- | --- | ---: | ---: |
| Accélération lisse | De 0,0015 à 0,0045 | 0,4413 / 0,4024 / 0,3005 | Oui | 77,539 | 84,448 |
| Stable | 0,003 constant | 0,3005 / 0,3005 / 0,3005 | Oui | 73,345 | 81,675 |
| Léger ralentissement | De 0,0033 à 0,0027 | 0,2723 / 0,2801 / 0,3005 | Oui | 72,157 | 80,844 |
| Plateau cinq séances | 0,003 puis zéro | 0 / 0,2537 / 0,2942 | Non : semaine | — | — |
| Pic unique | 59 cours à 100 puis cinq à 110 | 1,3709 / 0,4585 / 0,0644 | Non : R²/pente | — | — |
| Plat | Cours 100 | 0 / 0 / 0 | Non : pentes | — | — |

Le pic reçoit une évolution neutre de 50, aucun bonus. Le banc compare aussi les
conditions de trajectoire V1 stricte et V3 fast : les trois premières séries sont
écartées par leurs anciens minima de rendement. Il ne rejoue ni le scanner V1,
ni ses volumes/actualités/univers, ni un classement historique réel.

## 5. Catégories proposées

Bornes croissantes ; intervalles `]borne précédente,borne]` (premier et dernier
non bornés). Exception des états de qualité, qui sont catégoriels. Valeurs
manquantes/non finies : catégorie distincte « Inconnu », jamais la pire catégorie.
Toutes les catégories, inconnu compris, sont incluses au premier lancement.

| Indicateur | Bornes proposées | Libellés proposés, du premier au dernier |
| --- | --- | --- |
| Volatilité quotidienne (%) | 1,5 ; 3 ; 5 | Faible / Modérée / Élevée / Très élevée |
| Montant actions (€/jour) | 1 M ; 2 M ; 4 M | Limité / Intermédiaire / Important / Très important |
| Montant ETF (€/jour) | 250 k ; 500 k ; 1 M | Mêmes libellés ; seuils distincts explicites |
| Volume (titres/séance) | 10 k ; 100 k ; 1 M | Très faible / Faible / Moyen / Important |
| Journées positives (0–1) | 0,40 ; 0,55 ; 0,70 | Peu fréquentes / Partagées / Fréquentes / Très fréquentes |
| Meilleure séance (%) | 3 ; 7 ; 15 | Limitée / Marquée / Forte / Très forte |
| Pire séance (%) | −10 ; −5 ; −2 | Très forte baisse / Forte baisse / Baisse modérée / Baisse limitée |
| Concentration positive (%) | 20 ; 40 ; 60 | Répartie / Modérée / Concentrée / Très concentrée |
| Meilleure hausse / gain net simple (%) | 25 ; 50 ; 100 | Limitée / Modérée / Importante / Supérieure au gain net |
| Meilleure hausse log / gain net log (%) | 25 ; 50 ; 100 | Mêmes libellés, nom et formule distincts |
| Drawdown maximal (%) | 5 ; 10 ; 20 | Faible / Modéré / Élevé / Très élevé |
| Recul actuel (%) | 3 ; 7 ; 15 | Proche du sommet / Repli / Recul marqué / Recul important |
| ER (−1 à 1) | 0 ; 0,30 ; 0,70 | Négatif ou nul / Faible / Moyen / Élevé |

Ces découpages ne sont pas des seuils financiers validés. Le volume brut ne dit
pas à lui seul si un titre est liquide. Les concentrations dépendent de la durée
de fenêtre ; afficher cette durée, sans assimiler 20 % sur cinq et 63 séances.
Rendements, R², dates et couverture sont aussi affichés numériquement ; une
catégorie supplémentaire ne doit pas répéter un critère primaire.

Palette initiale proposée : vert `#166534`, bleu `#1d4ed8`, orange `#9a3412`,
rouge `#b91c1c`, inconnu gris `#475569`, avec texte et icône pour ne pas dépendre
de la couleur. Pour un indicateur informatif comme le volume, employer une
palette neutre graduée, pas une équivalence automatique faible=mauvais.

## 6. Priorités des réglages et décision attendue

1. Garde-fous techniques : paramètres admin explicites, valeurs et origine visibles.
2. Stratégie chargée : son instantané versionné prime sur les propositions globales.
3. Nouvelle stratégie : propositions admin courantes, copiées lors de la création.
4. Filtres secondaires : choix personnels explicites s’ils existent ; sinon défauts
   admin, sinon tout inclus. Changer un défaut admin ne réécrit pas les choix
   personnels déjà enregistrés.
5. Catégories : définition admin commune à badges/filtres ; changement de borne
   reclassifie les badges et les masques, sans recalcul financier ou des scores.

**À arbitrer avant intégration finale :** les seuils et couvertures du nouveau
profil, les formules/poids des deux scores et les catégories ci-dessus. Les
correctifs P0 indépendants sont testables sans cet arbitrage. Rien dans ce
document ne vaut approbation utilisateur ni autorisation de production.
