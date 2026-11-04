# Jigobourso V4 — Explorer intégré

Première version fonctionnelle sur `feature/explorer-v4-growth`, sans déploiement
en production. Suite à la clarification utilisateur, les paramètres sont une
base de travail modifiable, pas une calibration financière définitivement validée.
La référence reste l’[audit V1/V2/V3](README_AUDIT_V4.md).

## Utilisation

La page Explorer démarre sur **Croissance rapide**, avec semaine et mois actifs.
Le trimestre reste disponible, désactivé. Chaque période choisie présente deux
réglages : pente minimale en %/séance et R² minimal. L’admission exige les deux
conditions sur toutes les périodes choisies, sur des historiques complets.

Les modifications restent locales jusqu’à **Appliquer**. Changer le mode simple/
avancé ne change pas les calculs appliqués. Les rendements observés jour/semaine/
mois/trimestre sont distincts de la pente du modèle.

Le mode avancé permet des contraintes supplémentaires désactivées initialement :
rendements minimaux, concentrations, volatilité, drawdown, recul, séances
positives, ER, pire séance, volumes, montants et contrôles de moyennes mobiles.
L’opérateur ET/OU porte sur ces contraintes ; il ne permet jamais de contourner
les pentes, R² ou exigences de couverture primaires. Les critères supplémentaires
appliqués sont indiqués dans le résumé et les motifs de ligne.

Les filtres secondaires sont multisélectionnables : OU dans un indicateur, ET
entre indicateurs. Tous les niveaux, **Inconnu compris**, sont inclus au premier
lancement si l’administration n’a pas enregistré d’autres défauts. Ces défauts
restent visibles dans les cases et le résumé. **Tout afficher** réinitialise
uniquement les filtres secondaires ; les exclusions techniques ne disparaissent pas.

Les compteurs distinguent cotations disponibles, hors univers technique, échec de
stratégie, calcul indisponible, retenus, masqués et visibles. Le périmètre est
explicite, avant pagination ; les lignes brutes FinanceDatabase rejetées sont
comptées séparément des cotations. Une recherche d’un symbole connu mais exclu
expose son motif technique, sans lui inventer un score.

Le tableau affiche les scores simple/complexe, pente, R², rendement observé,
couverture et dates des périodes actives. Tris par score, métrique/période ou
indicateur secondaire ; les critères proches sont consultables pour les écartés.
Sur mobile, chaque ligne devient une fiche compacte. Le détail réunit raisons,
décomposition, indicateurs, origine des données, cours et régression.

## Valeurs initiales effectivement retenues

| Période | Activation | Pente min (%/séance) | R² min |
| --- | --- | ---: | ---: |
| Semaine, cinq séances | Oui | 0,08 | 0,65 |
| Mois, 21 séances | Oui | 0,08 | 0,70 |
| Trimestre, 63 séances | Non | 0,08 | 0,75 |

Aucun minimum de rendement observé n’est activé initialement. Couverture primaire :
100 % des N+1 clôtures attendues sur le calendrier de la place, pas 100 % des
jours calendaires. Un jour férié n’est pas une séance manquante.

| Score | Pondérations initiales |
| --- | --- |
| Simple | Force 35 %, régularité 35 %, évolution récente 30 % |
| Complexe | Force 25 %, régularité 25 %, évolution 20 %, risque de trajectoire 20 %, continuité 10 % |

Les trois premières composantes sont communes mais les deux notes sont calculées
indépendamment, sans ajouter le score simple à ses propres composantes.

### Formule `growth-1`

Pour chaque période active, OLS sur `ln(prix)` ; pente `s=100×expm1(b)` en
%/séance, R² `r`, volatilité logarithmique quotidienne `v` en %, drawdown maximal
positif `dd` en %, proportion de séances positives `u`, concentration positive
logarithmique `c` en fraction. Moyennes à poids égaux entre périodes actives.

```text
F = moyenne(100×max(0,s)/(max(0,s)+0,15))
R = moyenne(100×r)
K = moyenne(100/(1+max(v/1,5,dd/20)²))
C = moyenne(100×min(u,clip((1−c)/(1−1/N),0,1)))

Pour chaque paire sélectionnée adjacente court/long :
d = (s_court−s_long)/(abs(s_court)+abs(s_long)), ou 0 si dénominateur nul
q = min(1,(2/N_court)/c)×max(0,(1−c)/(1−1/N_court)), ou 0 si c=0
E = 50+50×moyenne(tanh(2d)×sqrt(r_court×r_long)×q)

Simple   = 0,35F + 0,35R + 0,30E
Complexe = 0,25F + 0,25R + 0,20E + 0,20K + 0,10C
```

Toutes les composantes sont bornées ; aucun percentile. Un pic expliquant toutes
les hausses donne q=0, donc aucun bonus d’accélération. Avec une seule période
volontairement active, E est non applicable : ses poids sont retirés et les
autres renormalisés explicitement. Une donnée nécessaire absente n’est pas
traitée de cette façon : la note concernée devient indisponible.

Une composante de risque manquante ne donne pas artificiellement 100 points au
complexe. Si le simple reste calculable, il conserve sa note. Les scores
n’introduisent pas de nouvelle exclusion : l’admissibilité et la disponibilité
de chaque score sont distinctes. Les données de volume et de liquidité n’entrent
pas dans ces notes, et restent inconnues si elles manquent.

Chaque contribution expose ses entrées par fenêtre, sa normalisation, le poids
initial/effectif, la couverture, les points et la version. Affichage arrondi,
tri sur valeur non arrondie ; départage déterministe par symbole/identifiant.

## Administration et priorités

Accessible depuis **Réglages administrateur** ou `admin.html#explorer` :

1. Stratégie initiale, activation des périodes, seuils et deux jeux de poids.
2. Catégories : noms, bornes ordonnées, libellés et couleurs hexadécimales.
3. Catégories sélectionnées par défaut, indépendantes de leur définition.

Prévisualiser valide sans enregistrer ; restaurer remet les propositions dans le
brouillon ; enregistrer applique explicitement les réglages. Les poids doivent
totaliser 100 %. Les contrôles serveur refusent seuils/poids non finis, pente
nulle, unités incorrectes, bornes désordonnées, couleurs invalides et catégories
inconnues. Aucun champ supplémentaire ne peut cacher un rendement minimal dans
les défauts des deux contrôles primaires.

Les réglages sont conservés dans `settings.explorer_growth`, sans changement de
code pour seuils, poids, bornes, couleurs ou filtres. Les normalisations restent
versionnées dans le moteur ; modifier leurs fonctions exige une nouvelle version.

Priorité : stratégie personnelle chargée > instantané admin lors de sa création >
propositions du code. Les changements admin ne réécrivent pas les stratégies
personnelles. Les catégories utilisent la définition admin commune aux badges
et filtres. Les préférences locales explicites priment sur les filtres admin ;
une recherche complète enregistrée permet aussi de les retrouver via la bibliothèque.

### Catégories initiales

Intervalles : borne basse exclue, borne haute incluse. Chaque ligne comprend aussi
Inconnu, distinct de zéro. Texte/icône accompagnent la couleur.

| Indicateur | Bornes | Catégories successives |
| --- | --- | --- |
| Volatilité %/séance | 1,5 ; 3 ; 5 | Faible, modérée, élevée, très élevée |
| Montant historique €/séance | 1 M ; 2 M ; 4 M | Limité, intermédiaire, important, très important |
| Montant coté Yahoo trois mois €/jour | 1 M ; 2 M ; 4 M | Mêmes libellés, source distincte |
| Volume historique titres/séance | 10 k ; 100 k ; 1 M | Très faible, faible, moyen, important |
| Proportion positive 0–1 | 0,40 ; 0,55 ; 0,70 | Peu fréquente, partagée, fréquente, très fréquente |
| Meilleure séance % | 3 ; 7 ; 15 | Limitée, marquée, forte, très forte |
| Pire séance % | −10 ; −5 ; −2 | Très forte baisse, forte baisse, baisse modérée, baisse limitée |
| Concentration positive log % | 20 ; 40 ; 60 | Répartie, modérée, concentrée, très concentrée |
| Meilleure hausse simple / gain net simple % | 25 ; 50 ; 100 | Limitée, modérée, importante, supérieure au gain net |
| Meilleure hausse log / gain net log % | 25 ; 50 ; 100 | Même échelle, autre définition explicite |
| Drawdown maximal % | 5 ; 10 ; 20 | Faible, modéré, élevé, très élevé |
| Recul actuel % | 3 ; 7 ; 15 | Proche sommet, repli, recul marqué, recul important |
| ER | 0 ; 0,30 ; 0,70 | Négatif/nul, faible, moyen, élevé |
| Rendement observé % | 0 ; 5 ; 15 | Nul/négatif, hausse limitée, marquée, forte |
| Couverture | 0 ; 0,999999 | Absente, partielle, complète |
| Fraîcheur | Code 0 récent, 1 ancien | À jour, ancienne |
| Continuité des données | Code 0 complet, 1 partiel, 2 rupture | Complète, partielle, rupture |

Palette initiale : vert `#166534`, bleu `#1d4ed8`, orange `#9a3412`, rouge
`#b91c1c`, inconnu `#475569`. Sens inversé pour les niveaux où une valeur haute
est favorable. Volume brut : palette neutre `#475569`, `#334155`, `#1e40af`,
`#1e3a8a`. Le volume ne mesure pas à lui seul la négociabilité.

Les catégories de montant sont une échelle informative commune aux actions/ETF.
Leurs pré-filtres techniques restent distincts (défauts actions 1 M€, ETF 250 k€).
Les catégories ne remplacent pas ces garde-fous ni la négociabilité historique.
La durée de référence est la plus longue période primaire choisie, sans arrondi
vers une autre fenêtre. La métadonnée Yahoo trois mois reste étiquetée trois mois.

## Conservation des fonctions existantes

Les sept profils historiques et sauvegardes sont conservés. La bibliothèque
permet création, duplication, modification/remplacement, renommage, archivage,
réactivation, activation, export/import et suppression confirmée des sauvegardes.
Les profils intégrés sont conservés et ne peuvent pas être supprimés.

`explorer_saved.active` garde son sens. La table additive `explorer_states`
conserve les états d’archive et les choix concernant les profils historiques.
L’éditeur historique reste accessible via `index.html?legacy=1`, notamment pour
ses recherches libres, comparaisons, configurations et analyses existantes.
Les liens historiques avec `preset`, `compare`, `library` ou `manage` y conduisent
explicitement. Aucun moteur portefeuille n’a été remplacé.

Les univers historiques comportant des filtres supplémentaires (pays, budget,
capitalisation, encours, etc.) restent utilisables dans cet éditeur. Le parcours
growth-1 expose type/place/recherche et les catégories secondaires ; il refuse
explicitement un filtre historique non pris en charge au lieu de l’ignorer.

## V1 : comparaison et différences connues

Dans chaque fiche, les contrôles V1 stricte sont montrés séparément : jour >0 %,
semaine ≥3 %, mois ≥8 %, R² mois ≥0,60 et meilleur jour log/gain net log ≤45 %.
Ils n’ajoutent aucune condition à V4.

V4 n’est pas une reproduction exacte du classement V1 : nouveaux seuils pente/R²,
deux scores absolus, calendrier et couverture stricts, catalogue FinanceDatabase,
conversions EUR et traitement partagé des trajectoires actions/ETF. V1 utilisait
un univers et des filtres propres, une présélection actions puis un avis /10,
des actualités/résultats, et un score ETF distinct. Sans snapshots correspondants,
on ne peut annoncer la reproduction de ses classements réels.

Sur les séries synthétiques à même rendement trimestriel de 20,8041 % :

| Trajectoire | Admission V4 | Simple | Complexe |
| --- | --- | ---: | ---: |
| Accélération lisse | Oui | 77,1572 | 84,2709 |
| Pente stable | Oui | 73,3450 | 81,6750 |
| Léger ralentissement | Oui | 72,2579 | 80,9008 |
| Plateau final cinq séances | Non : semaine | — | — |
| Pic unique | Non : régularité | — | — |
| Plat | Non : pente | — | — |

Ces exemples vérifient la philosophie, pas la capacité à prévoir un rendement.
Le banc initial sur trois périodes reste un document historique de proposition ;
les chiffres ci-dessus utilisent le moteur intégré semaine/mois.

## Tester et comparer sur de vraies actions

1. Installer la branche dans un environnement de revue avec une base isolée.
   Ne pas réutiliser une configuration ou un dump contenant des données privées
   de production sans autorisation et traitement approprié.
2. Depuis les historiques de marché disponibles dans cet environnement, ouvrir
   une fiche et choisir **Exporter le snapshot de marché**. Le fichier contient
   les clôtures brutes/ajustées stockées, événements, place, référence de date et
   configuration appliquée ; aucune transaction de portefeuille.
3. Rejouer sans base ni réseau :

```bash
.venv/bin/python -m scripts.compare_growth_v4
.venv/bin/python -m scripts.compare_growth_v4 --snapshot TITRE-snapshot.json --json
```

Le JSON donne mesures, seuils, motifs, deux notes et contributions, et comparaison
des conditions de trajectoire V1/V3. Les cours absents restent absents. Un snapshot
exporté est figé : ne pas remplacer sa référence de date par la date du jour.

Pour la validation automatique : `make fast`, `make integ`, puis, avec serveur PHP
et fixtures synthétiques sur base jetable, `tests/e2e/growth-v4.cjs` et les parcours
historiques `explorer-reconstruction.cjs`, `explorer-url.cjs`. Le workflow de revue
PR les exécute et archive les captures ; il ne déploie pas.

## Migration et retour arrière — procédure, pas exécution en production

La migration `20261105_explorer_states.sql` ajoute seulement une table. Les
réglages admin restent absents jusqu’à leur enregistrement explicite : aucune
réécriture destructive de configurations historiques.

Sur une base de revue, sauvegarder puis utiliser la procédure existante :

```bash
.venv/bin/python scripts/migrate.py --check
.venv/bin/python scripts/migrate.py --pending
.venv/bin/python scripts/migrate.py --apply
```

Sur base neuve créée depuis `db/schema.sql`, employer `--record-all` suivant la
procédure existante. Les correctifs P0 sont conservés ; recalculer les métriques
via le traitement existant si l’environnement possède des états précalculés
antérieurs à ces correctifs. Ces commandes ne sont pas une autorisation de les
lancer sur les données réelles.

Retour arrière normal : restaurer l’artefact applicatif précédent en conservant
les tables et configurations ajoutées. Aucun effacement de données requis.
L’outil `scripts/rollback_growth_v4.py --empty-only` ne retire la table que si
aucun état ni réglage admin V4 n’existe ; il refuse sinon. Export et décision
explicite sont nécessaires avant toute opération destructive.

## Qualité, cache et limites

Les correctifs Momentum, MA200, sous-unités et volumes P0 sont conservés. Les
mesures suivent les calendriers, les splits et le choix de base commun du moteur.
Une clôture datée après la référence attendue ne décale pas l’univers de marché :
elle est ignorée et signalée dans les motifs, sans mettre les autres titres en retard.
Les dividendes ne sont pas garantis lorsque les ajustements ne sont pas fournis.
Les trois concentrations ont des champs et unités distincts.

Les notes sont calculées avant filtres/pagination puis mises en cache. La clé
contient la configuration financière ; sa version dépend de l’horloge, des états,
historiques, événements, FX, univers et cotations. Les historiques emploient un
checksum agrégé par date/cours/volume : ce n’est pas une preuve cryptographique
d’identité de chaque historique. Un changement de catégorie ne change pas la clé.
La limite existante de 60 configurations/heure est conservée, avec application
explicite des réglages. Les calculs à froid sont groupés, sans requête de calendrier
par titre. Aucune donnée réseau n’est collectée pour une recherche V4.

Limites : pas de calibration sur un univers réel complet dans cette livraison ;
pas de garantie de parité fournisseur ou de reproduction V1 ; volumes historiques
souvent indisponibles ; jours de calendrier non pris en charge signalés inconnus.
La sensibilité des catégories et des poids devra être affinée sur des snapshots
représentatifs. Les captures et résultats exécutés sont consignés dans le rapport
de validation associé à cette branche.
