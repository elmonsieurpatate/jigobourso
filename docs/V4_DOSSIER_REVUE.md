# Explorer V4 — Dossier de revue des paramètres provisoires

Statut : **à examiner, aucun gel et aucune intégration des scores dans l’application**.
Ce dossier répond aux cinq points demandés après la proposition initiale.

Références : [audit](README_AUDIT_V4.md), [plan d’impact](V4_PLAN_IMPACT.md),
[propositions et équations](V4_PROPOSITIONS.md),
[banc exécutable](../scripts/preview_growth_v4.py).

## 1. Mathématiques exactes et normalisations

Pour une fenêtre sélectionnée de N séances, les N+1 cours attendus sont requis.
OLS de `ln(prix)` sur l’indice des séances, et non sur des jours calendaires.
`s_N=100×expm1(b_N)` en %/séance, `r_N=R²_N`, `c_N` meilleure hausse log divisée
par la somme des hausses log positives (fraction), `u_N` proportion de séances
positives (fraction), `v_N` écart-type des rendements log en %/séance,
`dd_N` drawdown maximal en % positif. Aucune valeur n’est annualisée.

Les composantes communes sur les fenêtres actives sont :

```text
F = moyenne_N [100×max(0,s_N)/(max(0,s_N)+0,15)]
R = moyenne_N [100×r_N]
K = moyenne_N [100/(1+max(v_N/1,5, dd_N/20)²)]
C = moyenne_N [100×min(u_N, clip((1−c_N)/(1−1/N),0,1))]
```

Chaque période pèse autant dans la moyenne. Ainsi le trimestre n’a pas 12,6 fois
le poids de la semaine. Pour F, 0,15 %/séance donne 50 points ; 0,30 donne environ
66,67 ; 0,60 donne 80 ; la limite est 100. Ce paramètre appartient à la version
de formule proposée, pas à un seuil d’admission ou à une pondération utilisateur.

Pour les paires d’horizons sélectionnés adjacents, court a et long b :

```text
d_ab = (s_a−s_b)/(abs(s_a)+abs(s_b)), ou 0 si dénominateur nul
q_a = min(1,(2/N_a)/c_a) × max(0,(1−c_a)/(1−1/N_a)), si c_a>0 ; sinon 0
z_ab = tanh(2×d_ab) × sqrt(r_a×r_b) × q_a
E = 50 + 50×moyenne_ab(z_ab)
```

E=50 signifie tendance maintenue, >50 accélération, <50 ralentissement. Les
coefficients sont proposés, sans validation prédictive. R² réduit le crédit
accordé à une évolution peu régulière. Si une seule séance explique toutes les
hausses, c=1 et q=0 : aucun bonus d’accélération. L’absence de pic ne garantit
pas à elle seule la qualité d’une trajectoire.

```text
Score simple   = 0,35F + 0,35R + 0,30E
Score complexe = 0,25F + 0,25R + 0,20E + 0,20K + 0,10C
```

Il n’y a aucun percentile. Modifier les autres titres, la pagination ou les
filtres de présentation ne peut changer ces formules. Les notes sont 0–100 ;
les nombres ci-dessous sont arrondis uniquement pour la présentation.

## 2. Les cinq composantes complexes et leurs limites

| Composante | Poids provisoire | Question traitée | Limite / double comptage |
| --- | ---: | --- | --- |
| F : force | 25 % | À quelle vitesse la tendance monte-t-elle ? | Mesure modélisée, différente du rendement observé ; saturation volontaire |
| R : régularité | 25 % | La trajectoire suit-elle sa tendance ? | R² n’est pas une promesse de maintien ; un cours plat peut avoir R²=1 |
| E : évolution | 20 % | La progression récente accélère-t-elle ? | Fenêtres emboîtées et bruit ; R²/concentration freinent le bonus, sans nouvelle exclusion |
| K : risque de trajectoire | 20 % | Variations et replis sont-ils contenus ? | Prendre le pire ratio vol/drawdown évite d’additionner les deux pénalités ; ce n’est pas une probabilité de perte |
| C : continuité | 10 % | La hausse est-elle partagée entre les séances ? | Minimum positivité/répartition, pas somme de deux récompenses ; corrélation résiduelle avec R² assumée |

La liquidité, la capitalisation et les données manquantes ne donnent pas des
points artificiels. La liquidité a ses garde-fous et catégories distincts. Le
score complexe réutilise les mesures mais n’ajoute pas le score simple à ses
propres composantes, ce qui compterait deux fois F/R/E.

## 3. Catégories, seuils, noms et couleurs proposés

Les bornes numériques sont inclusives à droite : par exemple volatilité faible
`≤1,5`, modérée `]1,5;3]`, élevée `]3;5]`, très élevée `>5`, en %/séance.
Premier/dernier intervalle ouverts vers l’infini ; entrée invalide ou non finie
→ Inconnu, pas une catégorie extrême. Les valeurs impossibles selon le domaine
d’une mesure sont invalides, pas des scores de risque.

Couleurs proposées : vert V=`#166534`, bleu B=`#1d4ed8`, orange O=`#9a3412`,
rouge R=`#b91c1c`, inconnu G=`#475569` ; texte et icônes toujours présents.
Volume brut : palette neutre graduée N1=`#475569`, N2=`#334155`, N3=`#1e40af`,
N4=`#1e3a8a` ; petit volume ne signifie pas automatiquement mauvais investissement.

| Indicateur et unité | Catégorie 1 | Catégorie 2 | Catégorie 3 | Catégorie 4 |
| --- | --- | --- | --- | --- |
| Volatilité (%/séance) | ≤1,5 Faible V | ≤3 Modérée B | ≤5 Élevée O | >5 Très élevée R |
| Montant actions (€/jour) | ≤1 M Limité R | ≤2 M Intermédiaire O | ≤4 M Important B | >4 M Très important V |
| Montant ETF (€/jour) | ≤250 k Limité R | ≤500 k Intermédiaire O | ≤1 M Important B | >1 M Très important V |
| Volume (titres/séance) | ≤10 k Très faible N1 | ≤100 k Faible N2 | ≤1 M Moyen N3 | >1 M Important N4 |
| Jours positifs (0–1) | ≤0,40 Peu fréquents R | ≤0,55 Partagés O | ≤0,70 Fréquents B | >0,70 Très fréquents V |
| Meilleure séance (%) | ≤3 Limitée V | ≤7 Marquée B | ≤15 Forte O | >15 Très forte R |
| Pire séance (%) | ≤−10 Très forte baisse R | ≤−5 Forte baisse O | ≤−2 Baisse modérée B | >−2 Baisse limitée V |
| Concentration hausses positives (%) | ≤20 Répartie V | ≤40 Modérée B | ≤60 Concentrée O | >60 Très concentrée R |
| Meilleure hausse simple / gain net simple (%) | ≤25 Limitée V | ≤50 Modérée B | ≤100 Importante O | >100 Supérieure au gain net R |
| Meilleure hausse log / gain net log (%) | ≤25 Limitée V | ≤50 Modérée B | ≤100 Importante O | >100 Supérieure au gain net R |
| Drawdown maximal (%) | ≤5 Faible V | ≤10 Modéré B | ≤20 Élevé O | >20 Très élevé R |
| Recul actuel (%) | ≤3 Proche du sommet V | ≤7 Repli B | ≤15 Recul marqué O | >15 Recul important R |
| ER (−1 à 1) | ≤0 Négatif ou nul R | ≤0,30 Faible O | ≤0,70 Moyen B | >0,70 Élevé V |
| Rendement observé (%), fenêtre toujours précisée | ≤0 Nul ou négatif R | ≤5 Hausse limitée B | ≤15 Hausse marquée V | >15 Hausse forte O |

Chaque indicateur comprend en plus **Inconnu G**, explicitement sélectionnable.
Tous sont inclus initialement. Le ratio au gain net est inconnu lorsque ce gain
net n’est pas positif. Les deux ratios simple/log restent des champs distincts.

Qualité : complet V, incomplet O, rupture R, calendrier indisponible G.
Fraîcheur : à jour V, ancien O, inconnue G. Couverture : complète V, partielle O,
absente G ; afficher aussi `observés/attendus` et les dates. Pas de fusion entre
couverture, fraîcheur et niveau de risque financier.

Le montant coté trois mois et le montant historique sont affichés avec leur
source et période ; ne pas les substituer silencieusement. Les catégories de
montant proposées ici ne remplacent pas la négociabilité existante : leurs
frontières inclusives et leurs noms sont indépendants, et devront être clairement
nommés dans l’interface. Le rendement et le meilleur jour ne constituent pas
des prévisions. Les bornes de concentration dépendent de la durée ; cette
calibration illustrative nécessite examen sur des snapshots représentatifs.

### Administration prévue, pas encore livrée

Les noms, couleurs, bornes, seuils primaires et pondérations devront être
enregistrés en administration, validés côté serveur et restaurables sans changer
le code. Les fonctions mathématiques resteront versionnées ; l’admin modifie
leurs poids, pas leur définition. Une modification de catégorie ne doit pas
invalider les mesures ou scores. Les sauvegardes personnelles gardent leur
instantané ; les propositions admin ne les écrasent pas.

Le banc emploie des constantes **pour la revue**, pas comme stockage final des
réglages. Aucun écran d’administration V4 n’est annoncé opérationnel à ce stade.

## 4. Résultats détaillés du banc

Les trois trajectoires admises ont toutes le même gain trimestriel : **20,80410 %**.
Chaque fenêtre possède 6/6, 22/22 et 64/64 clôtures synthétiques.

| Trajectoire | R² semaine / mois / trimestre | Rendement semaine / mois / trimestre (%) |
| --- | --- | --- |
| Accélération | 0,9999 / 0,9988 / 0,9826 | 2,22603 / 8,79973 / 20,80410 |
| Stable | 1 / 1 / 1 | 1,51131 / 6,50268 / 20,80410 |
| Ralentissement | 1,0000 / 0,9999 / 0,9993 | 1,36896 / 6,04913 / 20,80410 |

Les différences ne proviennent donc pas de la performance cumulée du trimestre.
Les pentes exactes et la construction des séries figurent dans la proposition.

| Composante normalisée /100 | Accélération | Stable | Ralentissement |
| --- | ---: | ---: | ---: |
| F | 71,39288 | 66,70000 | 65,43419 |
| R | 99,37810 | 100,00000 | 99,97294 |
| E | 59,23210 | 50,00000 | 47,54990 |
| K | 99,86964 | 100,00000 | 99,99477 |
| C | 99,34723 | 100,00000 | 99,82925 |

| Contribution simple en points | Accélération | Stable | Ralentissement |
| --- | ---: | ---: | ---: |
| F ×35 % | 24,9875 | 23,3450 | 22,9020 |
| R ×35 % | 34,7823 | 35,0000 | 34,9905 |
| E ×30 % | 17,7696 | 15,0000 | 14,2650 |
| **Total** | **77,5394** | **73,3450** | **72,1575** |

| Contribution complexe en points | Accélération | Stable | Ralentissement |
| --- | ---: | ---: | ---: |
| F ×25 % | 17,8482 | 16,6750 | 16,3585 |
| R ×25 % | 24,8445 | 25,0000 | 24,9932 |
| E ×20 % | 11,8464 | 10,0000 | 9,5100 |
| K ×20 % | 19,9739 | 20,0000 | 19,9990 |
| C ×10 % | 9,9347 | 10,0000 | 9,9829 |
| **Total** | **84,4477** | **81,6750** | **80,8436** |

Le ralentissement est pénalisé modérément et reste admissible. L’accélération
est récompensée malgré un R² trimestriel légèrement inférieur. Pic unique : E=50,
sans bonus, admission refusée ; plateau semaine : pente=0, refusé si sélectionné.
Période semaine désactivée : le plateau n’est plus éliminé par cette période.

Les totaux peuvent différer de la somme des nombres affichés au dernier chiffre
à cause des arrondis. Le JSON contient les valeurs et contributions non arrondies.

## 5. Données indisponibles et périodes désactivées

| Situation | Admission / score simple | Score complexe | Explication |
| --- | --- | --- | --- |
| Une clôture manque dans une fenêtre primaire | Indisponible, aucune note | Indisponible | Couverture non complète, aucune interpolation |
| Seules les bornes existent | Indisponible | Indisponible | Ne suffit pas à établir la trajectoire |
| R² ou pente requis indisponible | Indisponible | Indisponible | Ne pas assimiler au seuil échoué ou à zéro |
| Une seule période volontairement choisie | F/R renormalisés 50/50 | F/R/K/C renormalisés 31,25/31,25/25/12,5 | E non applicable, annoncé ; pas une donnée manquante |
| Deux périodes choisies | Comparaison de ces deux périodes | Même paire | La période désactivée ne contribue pas |
| Plusieurs périodes actives mais E non calculable | Indisponible | Indisponible | Pas de renormalisation favorable d’un manque |
| Volatilité ou drawdown manquant malgré admission calculable | Simple disponible si ses composantes le sont | Indisponible | Aucun K=100 ou zéro inventé |
| Volume historique ou FX daté manquant | Pas d’effet sur les deux scores proposés | Pas d’effet | Mesure secondaire inconnue, filtre inconnu sélectionnable |
| Volume connu égal à zéro | Pas de substitution | Pas de substitution | Valeur zéro connue, distincte du manque |
| Seuil primaire réellement échoué | Non admis, pas de note de classement | Pas de note | Motif avec mesure/seuil/fenêtre |

Exemple « stable, mois seulement » : simple **83,35000**, complexe **89,59375**.
Ces notes ne se comparent pas aux notes obtenues avec trois périodes : le choix
de stratégie a changé ; l’interface devra afficher le périmètre de calcul.

Le scénario avec un cours manquant deux séances avant la fin produit 5/6 points
hebdomadaires observés et deux scores `null`, jamais 0.

Rejouer : `.venv/bin/python -m scripts.preview_growth_v4`. Le JSON inclut les
cas admis/non admis, les composantes, poids effectifs, contributions, couverture,
un cas manquant et une seule période. Tests du banc :
`tests/fast/test_growth_proposal.py` ; ils vérifient les propriétés de la
proposition et **ne constituent pas une validation utilisateur des paramètres**.
