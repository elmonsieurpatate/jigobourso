# Jigobourso — Audit préalable à la V4

Date : 4 novembre 2026.

Ce document restitue l’audit du fonctionnement existant demandé avant toute
spécification ou modification de la future V4. Il décrit le code examiné, les
calculs reproduits, les anomalies et les limites de vérification. Il ne constitue
ni une spécification de V4 ni une proposition de correction.

## 1. Périmètre, méthode et versions

| Version désignée | Source examinée | Limites |
| --- | --- | --- |
| V1 | Sources réelles de `domains/bourse.turnjoy.dev/public_html` sur Hostinger | Paramètres du cron et données privées non consultés |
| V2 historique | Instantané Git `afee204`, nommé « Jigobourso V2 » | Ne représente pas nécessairement tous les déploiements V2 |
| V3 / moteur actuel | Code applicatif de `main`, commit `8048982e97a3685b4d265457069e76ba6a2fee57` | Réglages privés de production non interrogés |

Le moteur actuel contient déjà des fichiers et configurations nommés « V4 ».
Il s’agit du schéma de configuration d’Explorer présent avant cet audit, et non
d’une réalisation de la future version produit demandée.

La V1 a été récupérée par un workflow de lecture autorisé sur une branche
d’audit isolée. L’archive publiée est chiffrée. Les sources ont été déchiffrées
pour examen ; aucun scanner n’a été exécuté sur Hostinger.

- Collecte réussie : <https://github.com/elmonsieurpatate/jigobourso/actions/runs/41920464513>.
- SHA-256 de `public_html/scan.py` :
  `99b8d37f4000cecef525622c65dddc369dd542f1a36b543e53ba51c865a516bf`.
- Sources disponibles : scanner Python, API PHP, script de lancement, pages HTML
  et scripts d’interface. Aucun test V1 n’a été identifié dans cette collecte.
- Aucun accès aux données de production, migration ou déploiement pendant l’audit.
- Les seules modifications antérieurement autorisées pour obtenir les sources
  concernaient le workflow d’audit sur sa branche isolée.

### Statut des observations

- **Vérifié** : instruction ou formule directement retrouvée dans le code.
- **Reproduit** : comportement obtenu en exécutant les fonctions concernées sur
  des données synthétiques, sans base ni collecte réseau.
- **À confirmer** : configuration effective, couverture des données ou comportement
  fournisseur que la seule lecture du code ne permet pas d’établir.

Les seuils indiqués sont ceux du code. Ils ne prouvent pas les valeurs actuellement
enregistrées dans les réglages administrateur ou personnels de production.

### Références de code

Les références V1 désignent les fichiers récupérés sur Hostinger. Les références
du moteur actuel sont relatives à la racine du dépôt au commit audité. Les numéros
de lignes correspondent à ces instantanés et pourront changer ultérieurement.

| Abréviation | Fichier, fonctions et lignes utiles |
| --- | --- |
| V1-S | `public_html/scan.py` : univers 46–184 ; collecte 188–338 ; `analyse` 342–369 ; `etf_trend` 373–386 ; `score` 394–398 ; risques 441–497 ; `verdict` 500–541 ; rendu 729–866 ; suivi 900–970 ; `main` 974–1110 |
| V1-J | `public_html/static/app.js` : `apply` 17–39 ; initialisation 232–265 |
| V1-C | `public_html/cron_scan.sh` : lancement et état 11–24 |
| STR | [`engine/analytics/strategy.py`](../engine/analytics/strategy.py) : profils 52–97 ; validation 108–149 ; évaluation 181–267 ; classement 270–393 |
| MES | [`engine/analytics/measures.py`](../engine/analytics/measures.py) : `window_metrics` 23–55 ; fenêtres datées 58–117 ; moyennes mobiles 120–158 |
| SER | [`engine/analytics/series.py`](../engine/analytics/series.py) : préparation des séries ; Momentum 120–158 |
| CFG | [`engine/analytics/explorer_config.py`](../engine/analytics/explorer_config.py) : critères 8–24 ; unités 46–55 ; conversion 58–75 ; validation dès 86 ; profils éditables 185–199 |
| SCORE | [`engine/analytics/configurable_score.py`](../engine/analytics/configurable_score.py) : valeur et transformation 15–36 ; classement et contributions 39–91 |
| PATH | [`engine/analytics/explorer_metrics.py`](../engine/analytics/explorer_metrics.py) : mesures de chemin 15–25 ; historique, volumes et FX 29–59 |
| SVC | [`engine/analytics/service.py`](../engine/analytics/service.py) : univers 138–198 ; proximité 204–220 ; cache 228–299 ; fenêtre de référence 364–367 ; filtres et résultats 388–575 ; fiche dès 734 |
| SIG | [`engine/analytics/signals.py`](../engine/analytics/signals.py) : seuils 13–20 ; risque 61–78 ; liquidité 81–110 ; contradictions 156–167 ; concentration descriptive 268–277 |
| PRE | [`engine/market/prefilter.py`](../engine/market/prefilter.py) : règles 11–38 ; décision 79–97 |
| CAT | [`engine/catalogue/rules.py`](../engine/catalogue/rules.py) : règles et défauts 43–84 |
| UI | [`app/public/assets/explorer.js`](../app/public/assets/explorer.js) : noms et défauts 6–12 ; bibliothèque 92–98 ; application du brouillon dès 98 |
| LIB | [`app/services/explorer_library.php`](../app/services/explorer_library.php) : lecture et sauvegarde 3–27 ; anciennes sauvegardes 30–40 |

## 2. Conclusions principales

1. La V1 ne possède pas une seule note : elle utilise un score de présélection des
   actions, un score ETF et un avis sur 10 intervenant dans le tri final.
2. Les stratégies nommées « Croissance rapide » et « Momentum » appartiennent aux
   générations ultérieures. Elles ne doivent pas être attribuées à la V1 récupérée.
3. Les actions et ETF V1 suivent des branches distinctes. Un ETF non qualifié peut
   néanmoins apparaître parmi les meilleurs disponibles.
4. Une semaine plate peut rester excellente avec « Croissance régulière » actuelle,
   puisque ce profil examine le mois et le trimestre. La sélection stricte V1
   exige au contraire une progression récente.
5. Deux anomalies actuelles ont été reproduites : Momentum classé avec seulement
   3 clôtures sur 127 attendues, et MA200 calculée à tort sur une liste de 55 cours.
6. Les 42 tests ciblés exécutés passent, sans couvrir ces deux anomalies.

## A. Stratégies et parcours de recherche — questions 1 à 6

### 1. Stratégies et valeurs par défaut

#### V1 : trois listes fixes

Les conditions ci-dessous s’appliquent après les contrôles communs de collecte,
d’historique, de prix, de liquidité et de volatilité.

| Liste | Conditions particulières | Sélection et classement |
| --- | --- | --- |
| Globale stricte | Jour > 0 % ; semaine ≥ 3 % ; mois ≥ 8 % ; R² mensuel ≥ 0,60 ; concentration du meilleur jour ≤ 45 % | 30 actions présélectionnées par score, puis tri par avis et score |
| PEA élargie | Suffixe compatible ; jour > −1 % ; semaine ≥ 1 % ; mois ≥ 4 % ; R² ≥ 0,50 ; concentration ≤ 55 % ; pays vérifié si disponible | Présélection de 75, résultat limité à 25 |
| ETF — pente régulière | Qualification si pentes semaine/mois > 1e−10 et R² des deux fenêtres ≥ 0,60 | Qualification puis score ; au plus 30, avec replis non qualifiés possibles |

Références : V1-S, `main` 1018–1067, `etf_trend` 373–390 et tri final 1085–1095.

#### V2 historique et moteur actuel

| Profil | Périodes | Conditions par défaut | Classement |
| --- | --- | --- | --- |
| Croissance régulière `regular` | 21 et 63 séances | Pente modérée ; R² ≥ 5/9 | Régularité |
| Croissance rapide `fast` | 5 et 21 | Pente très forte sur les deux ; rendement semaine ≥ 0 %, mois ≥ 12 % | Performance |
| Rebond `recovery` | 5, 21 et 126 | Semaine/mois : pente douce et R² ≥ 5/9 ; six mois : rendement ≤ 10 % | Tendance |
| Hausse calme `low_volatility` | 21 et 63 | Pente douce ; R² ≥ 5/9 ; volatilité ≤ 1,5 %/séance ; drawdown ≤ 20 % | Faible volatilité |
| Momentum 6 mois | 126 | Aucun seuil de rendement ; dernier mois exclu de la mesure | Momentum 6–1 |
| Momentum 12 mois | 252 | Même principe | Momentum 12–1 |
| Momentum ajusté du risque | 126 et 252 | Cours > MA200 ; MA200 montante | Composite Momentum/risque |

Les quatre premiers profils existent dans l’instantané V2 `afee204`,
`engine/analytics/strategy.py`, `preset`, lignes 48–76. Les trois Momentum sont
présents dans le moteur actuel : STR 52–97 ; CFG 185–199.

La pente minimale est définie par `100 × expm1(ln(2)/(années × 252))` :

| Niveau | Années théoriques de doublement | Seuil en % par séance |
| --- | ---: | ---: |
| Douce | 8 | 0,034388212 |
| Modérée | 4 | 0,068788250 |
| Forte | 2 | 0,137623817 |
| Très forte | 1 | 0,275437038 |

R² flexible = 5/9 ; équilibré = 0,75 ; strict = 8/9. Référence : STR 29–33.
Ces valeurs servent de seuils, pas de prévisions.

### 2. Algorithmes Momentum

Aucun profil nommé Momentum dans la V1 récupérée.

Dans le moteur actuel :

```text
Momentum 6–1  = 100 × (P[J−21] / P[J−126] − 1)
Momentum 12–1 = 100 × (P[J−21] / P[J−252] − 1)
```

Le composite utilise les percentiles : 35 % Momentum six mois, 45 % Momentum
douze mois, 10 % faible volatilité et 10 % faible drawdown. Les Momentum sont
requis dans le profil éditable ; les composantes de risque sont facultatives
avec renormalisation. Les algorithmes diffèrent donc par horizon et composition,
pas seulement par leurs seuils. Unité des rendements : %. Effet : classement,
avec conditions MA200 pour le composite. Références : SER 120–158 ; CFG 189–198.

### 3. Stockage, désactivation et archivage

- V1 : règles codées dans le scanner ; listes et filtres dans le rendu et V1-J.
  Aucun archivage de stratégie identifié.
- Moteur actuel : profils intégrés dans STR ; sauvegardes dans `explorer_saved`,
  `saved_searches`, `saved_presets` ; configuration portefeuille dans
  `portfolios.strategy_config`.
- Les sauvegardes modernes ont `active`, permettant la désactivation sans perte.
  Les anciennes peuvent être désactivées dans les préférences locales du navigateur.
- Aucun état d’archivage métier distinct identifié.

Références : LIB 3–40 ; UI 92–98 ; `db/schema.sql`, tables aux lignes 363, 377, 504.

### 4. Parcours complet

V1 : NasdaqTrader/Wikipedia/Yahoo → exclusions d’univers → présélection Nasdaq →
prélecture Yahoo spark → présélection de prix → téléchargement cours/volumes →
contrôles communs → branche stricte/PEA/ETF → réduction des candidats → pays/ISIN,
actualités et résultats → risque/avis → `rapport.html` → filtres navigateur.

Moteur actuel : FinanceDatabase → règles du catalogue → cotation principale →
informations Yahoo → préfiltre Yahoo → historiques/événements → mesures stockées →
critères → score → filtres d’univers et éventuel reclassement → filtres de
restitution → pagination.

Références : V1-S 46–338 et 974–1104 ; V1-J 17–39 ; CAT ; PRE ;
`engine/jobs/tasks.py` 69–137 ; SVC 138–198 et 388–575.

### 5. Filtres implicites et défauts

| Version / étape | Règle | Effet |
| --- | --- | --- |
| V1 US | Titres de test exclus ; symbole `[A-Z]{1,5}` ; déduplication par symbole | Exclusion de symboles particuliers/classes |
| V1 noms actions | Expressions sur warrants, units, rights, preferred, trust, acquisition corp, ETN, levier, etc. | Exclusion par nom |
| V1 noms ETF | ETN, `[234]x`, ultra, leveraged, inverse, bull, bear, short, daily | Exclusion ; faux positifs possibles |
| V1 Nasdaq | Prix ≥ 5 ; prix × volume ≥ 1,5 M ; capitalisation ≥ 100 M | Présélection actions ; ETF dispensés |
| V1 capitalisation absente | Remplacement par 1 Md dans ce préfiltre | Le manque ne provoque pas de rejet |
| V1 repli Nasdaq | Préfiltre annulé si erreur ou résultat ≤ 500 titres | Univers dépendant du succès fournisseur |
| V1 Europe | Capitalisation > 300 M ; si prix et volume moyen existent : prix ≥ 5 et produit ≥ 800 000 | Présélection partiellement contournable si données absentes |
| V1 prélecture | Jour > −1 %, semaine ≥ 1 %, mois ≥ 4 %, R² ≥ 0,50, concentration ≤ 55 %, volatilité ≤ 7 % | Présélection actions ; ETF dispensés |
| V1 historique | Au moins 40 clôtures positives | Exclusion même pour une courte période |
| V1 fraîcheur | Retard ≤ 4 jours calendaires sur le titre le plus récent du lot | Contrôle relatif, pas absolu |
| V1 limites | 30 actions strictes, 30 ETF ; PEA : 75 présélectionnées puis 25 | Filtres navigateur limités à ces candidats |
| Actuel catalogue | Types/places, radiation, identité, dérivés, SPAC, levier | Exclusion avant stratégie |
| Actuel cotation | `selected` et cotation principale dans `v_recommendable` | Autres cotations hors classement principal |
| Actuel Yahoo | Prix ≥ 2 € ; montant moyen actions ≥ 1 M€/jour, ETF ≥ 250 k€/jour ; cours > 10 jours exclus ; volume inconnu exclu | Défauts administratifs réglables |
| Actuel fraîcheur | Requise dans les profils convertis ; non requise dans une configuration vierge | Inconnu/rejet selon politique |
| Actuel négociabilité | Filtre activé par défaut, masque « limitée » | Masquage après classement ; exception recherche exacte |
| Actuel données | Politique unknown/reject ; composantes requises ou renormalisation | Inconnu, rejet ou score partiel |
| Actuel affichage | Retenus par défaut ; recherche textuelle pouvant montrer les exclus | Visibilité distincte de l’admissibilité |
| Actuel garde-fou | 60 nouvelles configurations calculées par heure, tous utilisateurs confondus | Refus temporaire de calcul |

Références : V1-S 46–147, 236–240 et 1008–1067 ; CAT ; PRE ; UI 11–12 ;
SVC 199–200, 275–310 et 485–535 ; `db/schema.sql:348`.

### 6. Critères propres à Croissance rapide

Ce nom n’existe pas dans le scanner V1. Dans V2/V3, `fast` impose les pentes très
fortes semaine/mois, rendement hebdomadaire ≥ 0 %, mensuel ≥ 12 %, et classe par
performance. Aucun R² minimal ou jour positif n’est requis par défaut.

Activer « Dernier jour » sans seuil ne signifie pas exiger une hausse ce jour-là.
Références : STR 63–66 et 217–233 ; UI, configuration des périodes.

## B. Pente, régularité et périodes — questions 7 à 14

### 7. Pente

V1 : OLS de `ln(clôture)` sur les 22 derniers points ; coefficient `b` en
logarithme par observation. ETF : fenêtres de 6 et 22 points ; affichage
`100 × expm1(b)` en %/séance. Références : V1-S 351–357, 373–386 et 1093.

V2/V3 : même régression logarithmique ; pente interne `100 × expm1(b)` en
%/séance. L’éditeur peut afficher `100 × expm1(Nb)`, progression du modèle sur
N séances, distincte du rendement entre les deux clôtures extrêmes. Rôles :
filtre, score et affichage selon configuration. Références : MES 41–49 ; CFG 46–55.

### 8. R² et cas limites

V1 actions : `1 − Σrésidus²/Σécarts_à_la_moyenne²`, dénominateur nul remplacé par
`1e−12`. Pas de traitement explicite de la série presque constante. Sur 40 cours
constants à 100, résultat reproduit : **0,954545…**, sensible aux résidus numériques.
V1 ETF : variance ≤ `1e−12` → R² = 0. Références : V1-S 355–357 et 380–381.

V3 : formule équivalente par covariances ; variance exactement nulle → R² = 1.
Une séance : R² absent. Deux séances : R² effectivement calculé malgré le
commentaire ; la validation interdit ce critère sous trois séances.
Références : MES 37–54 ; STR 129–132. Unité : sans dimension, 0–1 en usage normal.

### 9. Périodes

V1 : performances sur 1, 5 et 21 intervalles observés ; graphique sur les 66
derniers points environ ; régression du graphique sur 22 points.
V3 : 1/5/21/63/126/252 séances par défaut, personnalisation jusqu’à 252.
Les fenêtres datées utilisent le calendrier du marché, contrairement au comptage
d’observations V1. Références : V1-S 348–351 et 545–566 ; STR 23–26, 123–132 ;
`engine/market/calendar.py`, `window_calendars`, 57–59.

### 10. Calculs indépendants

V1 actions : performances par période mais pente/R² mensuels seulement.
V1 ETF : régressions séparées semaine/mois. V3 : mesures indépendantes par période,
puis agrégation. Certains filtres et pastilles utilisent encore une fenêtre de
référence : la plus longue période active ramenée à la fenêtre stockée la plus
proche. Références : V1-S 342–386 ; STR `rank` ; SVC 364–367.

### 11. Plateaux, accélérations et retournements V1

Aucun détecteur générique comparant les pentes retrouvé. Détections indirectes :
minima jour/semaine ; soupçon de rachat si meilleur jour > 20 % et écart-type des
cinq derniers rendements < 0,4 % ; texte si recul actuel < −5 %.
Références : V1-S 454–466, 530–531 et 1034–1039. Effets : exclusion, risque ou texte.

### 12. Hausse suivie d’une semaine plate

Exemple synthétique exécuté : `P[t] = 100 × 1,02^min(t,58)`, pour `t = 0…63`.

| Fenêtre | Performance | Pente %/séance | R² |
| --- | ---: | ---: | ---: |
| 5 séances | 0 % | 0 % | 1 |
| 21 | +37,2786 % | +1,68684 % | 0,964256 |
| 63 | +215,3624 % | +1,95816 % | 0,997994 |

La V1 stricte rejette une semaine plate ; le PEA aussi. Le profil actuel `regular`
peut la retenir et la classer première puisqu’il n’examine que mois/trimestre.
Avec les trois séries suivantes et `CFG.editable(STR.preset('regular'))` :

```text
PLATEAU[t] = 100 × 1,02^min(t,58)
B[t]       = 100 × exp(0,003t + 0,02 sin(1,3t))
C[t]       = 100 × exp(0,004t + 0,025 sin(1,1t))
t = 0…63
```

Résultats reproduits : tous retenus ; PLATEAU = 100, C = 50, B = 0.
`fast` rejette PLATEAU pour pente hebdomadaire insuffisante.
Références : MES `window_metrics` ; STR `preset` ; SCORE `rank`.

### 13. Comparabilité des pentes

V1 ETF : coefficients log par observation homogènes ; score fondé sur signe et R²,
pas amplitude de pente. V3 : unité interne homogène en %/séance ; les pentes
affichées sur période correspondent à des durées différentes. Les percentiles
sont calculés séparément avant agrégation. Références : V1-S 379–386 ; CFG 46–55 ;
SCORE 26–27 et 69–87.

### 14. Autres règles de régularité

V1 : journées positives, concentration du meilleur jour, volatilité et stabilité
récente pour le rachat. V3 : ER, volatilité, drawdown, journées positives,
concentrations, pire séance, recul et contradiction entre horizons. Aucun comptage
de séquences consécutives de baisse identifié dans le score Explorer.
Références : V1-S 358–369, 397 ; MES 50–54 ; PATH 15–25 ; SIG 156–167.

## C. Indicateurs, seuils et filtres — questions 15 à 26

### 15. Tableau des critères et indicateurs

Notation : `r[t] = P[t]/P[t−1]−1` ; `g[t] = ln(P[t]/P[t−1])`.
Sources : cours et volumes Yahoo ; catalogue actuel FinanceDatabase ; actualités
Google News et calendrier Nasdaq dans la V1.

| Indicateur | Définition / unité / période | Rôle et référence |
| --- | --- | --- |
| Performance V1 | `Pfin/Pdébut−1`, fraction, 1/5/21 intervalles | Filtre, score, tri, affichage ; V1-S 348–350 |
| Performance actuelle | Même formule ×100, %, N séances | Critère/score/affichage ; MES 30 ; CFG |
| Pente | Régression log, voir §7 | Critère/score/affichage ; MES 41–49 |
| R² | Ajustement log, sans unité | Critère/score/pastille ; §8 |
| Régularité composée V1 | R² × pénalité de concentration × facteur de journées positives | Score et affichage ; V1-S 397 |
| Volatilité V1 | Écart-type échantillonnal de 21 rendements simples, fraction/jour | Exclusion, risque ; V1-S 358–363 |
| Volatilité actuelle | Écart-type échantillonnal de g ×100, %/séance | Critère/score/pastille ; MES 50–52 |
| ER | `Σg/Σabs(g)`, −1 à +1 ; 0 si chemin nul | Critère/score ; MES 53–54 |
| Drawdown maximal actuel | `100×max(1−P/sommet antérieur)` | Critère/score/risque ; MES 32–36 |
| Recul actuel V1 | `Pfin/max(21 derniers cours)−1`, négatif | Texte ; V1-S 369 et 530 |
| Recul actuel moderne | `100×(1−Pfin/max(fenêtre))`, positif | Critère/score ; PATH 23 |
| Jours positifs V1 | Part des 21 rendements strictement >0 | Score ; V1-S 359 et 397 |
| Jours positifs modernes | Nombre de g >1e−12 et proportion 0–1 | Critère/score ; PATH 17–20 |
| Concentration V1 | `max(g)/Σg` si gain net positif, sinon 1 | Filtre/score ; V1-S 360–362 |
| Concentration des hausses | `100×max(g positif)/Σg positifs` | Critère/score ; PATH 20 |
| Meilleure hausse / gain net | `100×max(0,rmax)/rendement net` | Critère/score ; PATH 22 |
| Concentration descriptive | `100×max(g)/Σg`, arrondi entier | Affichage ; SIG 268–277 |
| Meilleure/pire séance | Extrêmes des rendements simples en % | Contexte/score et critères disponibles ; PATH 18–22 |
| Volume moyen historique | Moyenne des N volumes, titres/séance | Critère/score ; toutes les valeurs requises ; PATH 24–25 |
| Montant historique V1 | Moyenne cours×volume sur 20 points, devise locale/jour | Filtre/risque ; V1-S 364 |
| Montant historique actuel | Moyenne cours brut×volume×FX daté, €/séance | Critère/score ; PATH 29–59 |
| Volume moyen coté | Champs Yahoo trois mois et dix jours | Préfiltre, négociabilité, contexte ; PRE et SVC |
| MA20/50/200 | Moyenne arithmétique des clôtures, unité du cours | Critères/contexte ; MES 120–158 |
| Tendance des MA | Comparaison avec moyenne cinq séances avant ; MA50 en % possible | Critère/score selon champ ; MES et SCORE 22–23 |
| Écart MA20 | `100×(cours/MA20−1)` | Technique/score ; MES 133–134 |
| Momentum | Rendement hors dernier mois, % | Classement ; SER 120–158 |
| Risque V1 | Somme de pénalités, 1–10 | Avis, filtre et tri ; V1-S 487–497 |
| Avis V1 | Composite régularité/force/risque, actions 1–10 | Tri final ; V1-S 500–508 |
| Écart typique cinq jours V1 | Volatilité quotidienne×√5, ±% | Repère affiché ; V1-S 540 |
| Actualités/résultats V1 | Mots-clés, résultats à 0–7 jours | Risque/plafonds d’avis ; V1-S 441–484 |
| Prix/devise/âge | Dernière cotation et horodatage | Filtres, conversion, qualité |
| Capitalisation | Valeur fournisseur ; catégories actuelles en EUR | Préfiltre US V1 et filtre actions actuel ; SVC vers 863 |
| AUM/frais ETF | Actifs et frais annuels en % | Filtres ETF/contexte ; SVC 450–470 |
| Pays/place/type/PEA | Métadonnées et heuristiques | Univers/affichage ; CAT et SVC |
| Analystes | Donnée Yahoo disponible | Affichage ; SVC vers 849 |
| Similarité ETF | Corrélations de rendements hebdomadaires EUR | Analyse ETF, pas score principal ; `engine/analytics/etf.py` |
| Composition ETF | Poids top 10 et chevauchement de compositions | Vigilance/analyse, pas score principal ; SIG et `etf.py` |

Cet inventaire porte sur Explorer, ses fiches et les analyses ETF associées.
Les métriques comptables des portefeuilles relèvent d’un autre moteur.

### 16. Seuils codés et rôles

Les seuils de profils et d’univers figurent aux questions 1 et 5.

| Version | Valeurs | Effet / référence |
| --- | --- | --- |
| V1 score | Caps jour 8 %, semaine 25 %, mois 80 % ; poids 15/35/50 % | Score ; V1-S 394–398 |
| V1 concentration | Pénalité maximale 50 %, concentration bornée 0–1 pour ce terme | Score ; V1-S 397 |
| V1 volatilité | Exclusion >7 % ; risque >2,5/3,5/5 % par jour | V1-S 1024–1025 et 490 |
| V1 liquidité | Risque : <10 M +2, <30 M +1 ; texte favorable ≥50 M | V1-S 491, 518–519 ; devise locale |
| V1 hausses | Jour >10 % ; semaine >35 % ou mois >100 % | Risque ; V1-S 492–493 |
| V1 rachat | Meilleur jour >20 % et σ cinq jours <0,4 %, ou mots-clés | Risque +3 ; V1-S 454–466, 494 |
| V1 résultats | 0–7 jours | Risque +2 ; avis ≤6 |
| V1 R² | <0,70 | Risque +1 ; V1-S 496 |
| V1 avis | 35 % régularité, 25 % force, 40 % calme ; références de force 40 % mois et 15 % semaine | V1-S 502–503 |
| V1 plafonds | Avis rachat ≤3 ; résultats ≤6 ; bornes actions 1–10 | V1-S 504–508 |
| V1 textes | Régularité 0,40/0,55 ; mois 25 % ; semaine 8 % ; jour 8 % ou semaine 30 % ; recul −5 % | Affichage ; V1-S 510–531 |
| V1 ETF | Pente ±1e−10 ; variance 1e−12 ; qualification R² ≥0,60 | V1-S 381–386 |
| Actuel régularité | 5/9, 0,75, 8/9 | STR 33 ; SIG 13–14 |
| Actuel risque | Volatilité 1,5 %, drawdown 20 % ; orange jusqu’au double | SIG 61–78 |
| Actuel contradictions | Fond ±10 % ; repli récent −5 % ou rebond +10 % | Affichage ; SIG 156–167 et constantes associées |
| Actuel rupture | Ratio >1,6 ou <1/1,6 | Fenêtres indisponibles ; SER |
| Actuel erreur ponctuelle | ≥4× ou ≤¼ des voisins, sous conditions | Nettoyage ; SER |
| Actuel unité | Facteur 100, tolérance 6 %, protection cinq jours calendaires autour des splits | Préparation ; SER |
| Actuel régression trouée | `max(3,ceil(80 %×points attendus))` | Support du calcul ; MES 90 |
| Actuel négociabilité | Plancher 2×, confort 4× minima du préfiltre ; âge maximal dix jours | Couleur/masque ; SIG 81–110 |
| Actuel ETF | Top 10 : 40/70 % ; famille portefeuille : 30/50 % | Vigilance ; SIG 19–20 |
| Actuel similarité | Corrélations 0,90/0,97 ; regroupement sans indice 0,99 | Analyse ; `etf.py` |
| Actuel capitalisation | 300 M, 2 Md, 10 Md, 200 Md EUR | Catégories/filtre ; SVC vers 863 |

Les bornes de validation de CFG 8–24 ne sont pas des filtres actifs : pente
interne −100 à +100 %/séance ; R² 0–1 ; ER −1–1 ; rendement −100 à 10 000 % ;
volatilité/drawdown 0–100 % ; proportion positive 0–1 ; concentration des hausses
0–100 % ; ratio hausse/gain net 0–100 000 % ; volumes 0–1e15 ; montant 0–1e18.

### 17. Volatilité

V1 : σ échantillonnal des rendements simples sur 21 séances. V3 : σ des rendements
logarithmiques sur N séances, ×100. Aucune annualisation dans ces deux mesures.
Références : V1-S 358–363 ; MES 50–52.

### 18. Couleurs V1

Textes : volatilité forte >3,5 %/jour, très forte >5 %. La couleur du risque porte
sur la note composite : 1–3 vert, 4–6 orange, 7–10 rouge. Bandeau sévère →
`risk-bad`, drapeaux → `risk-warn`, sinon `risk-ok`. La volatilité influence
réellement l’avis via le risque. Références : V1-S 446–449, 490, 735, 801, 818.

### 19. Liquidité

V1 : moyenne sur 20 observations de cours×volume, en devise locale malgré le nom
`dollar_vol`. Actuel : cours×volume moyen trois mois×FX EUR pour le préfiltre et
la pastille ; autre mesure historique avec FX daté. Aucun spread utilisé dans ces
formules. Références : V1-S 364 ; PRE 79–97 ; SIG 93–110 ; PATH 48–59.

### 20. Volumes et disponibilité

V1 : séance Nasdaq, moyenne trois mois du screener européen, volumes historiques
du contrôle final. Actuel : trois mois/dix jours cotés et volumes historiques si
présents. Les chemins `collect_daily` et `store_gap_bars` enregistrent les clôtures
sans alimenter les volumes historiques. Impact en production non quantifié.
Références : V1-S 79–83, 111–147, 364 ; `engine/market/collect.py` 197–211,
294–318 ; PATH 24–25.

### 21. Journées positives

V1 : `r>0` sur 21 ; zéro non positif mais inclus au dénominateur ; composante de
score. Actuel PATH : `g>1e−12`, nombre et proportion ; descriptif SIG : `g>0` et
pourcentage arrondi. Rôles modernes : critère/score ou affichage selon champ.
Références : V1-S 359, 397 ; PATH 17–20 ; SIG 273–277.

### 22. Pics

V1 : meilleur jour sur 21 séances et son poids logarithmique ; concentration
éliminatoire, hausse excessive pénalisée, rachat possible. Pas de détecteur
symétrique dédié aux pics de baisse identifié. Actuel : meilleure/pire séance,
concentrations et ruptures de série, avec rôles distincts. Références : V1-S
360–368, 450–457 ; PATH 18–23 ; SER.

### 23. Concentration

Trois définitions coexistent aujourd’hui : meilleur gain log/gain net log
(descriptif, comme V1), meilleur gain log/somme des gains log positifs, meilleure
hausse simple/gain net simple. Elles ne sont pas interchangeables. Les ratios au
gain net peuvent dépasser 100 %. Références : V1-S 360–362 ; PATH 20–22 ; SIG 273–277.

### 24. Risques supplémentaires

V1 : recul actuel, liquidité, volatilité, hausse excessive, résultats et rachat.
Actuel : drawdown maximal, ER, moyennes mobiles, contradictions, qualité des
données et composition ETF. Le recul V1 n’est pas le drawdown maximal.
Les signaux modernes n’entrent pas automatiquement dans le score ; un filtre de
niveaux peut les masquer. Références : V1-S 369, 441–497 ; MES ; SIG ; SVC.

### 25. Performances et rôle

V1 actions : affichage, filtre, score et avis. V1 ETF : performances affichées,
score fondé sur pentes signées et R². Actuel : rôle configurable ; période activée
sans seuil de performance ne signifie pas rendement positif obligatoire.
Références : V1-S 394–398, 1034–1039 ; STR `judge` ; CFG ; SCORE.

### 26. Configurabilité et multi-sélection

V1 : couleurs/seuils codés ; risque maximal scalaire ; marché/liste/type/PEA à
choix simple. Actuel : critères et préfiltre configurables, couleurs de risque
codées dans SIG ; niveaux multi-sélection en OU dans un champ, ET entre champs.
Pays/catégories/devises acceptent plusieurs valeurs séparées par `|` ; tous les
contrôles ne sont pas des composants graphiques multi-sélection.
Références : V1-S 839–850 ; V1-J 17–39 ; SIG 13–20 ; SVC 310, 436–472 ; UI.

## D. Score et classement — questions 27 à 33

### 27. Formules V1 exactes et exemple reproductible

#### Score de présélection des actions

Les rendements sont des fractions : 0,08 signifie 8 %.

```text
F = 0,15×min(jour,0,08)
  + 0,35×min(semaine,0,25)
  + 0,50×min(mois,0,80)

R = max(R²,0)
  × [1 − 0,5×borne(concentration,0,1)]
  × [0,5 + 0,5×proportion_jours_positifs]

S = 100×F×R
```

Référence : V1-S `score`, 394–398. Aucun arrondi dans cette fonction. Ce n’est pas
une note normalisée sur 100 : pour R≤1, le plafond algébrique est 49,95.

#### Risque

```text
r = 1
  + (3 si vol>5 %, sinon 2 si vol>3,5 %, sinon 1 si vol>2,5 %, sinon 0)
  + (2 si montant<10 M, sinon 1 si montant<30 M, sinon 0)
  + 1 si jour>10 %
  + 1 si semaine>35 % ou mois>100 %
  + 3 si rachat probable
  + 2 si résultats imminents
  + 1 si R²<0,70

risque = entier(min(10, round(r)))
```

Référence : V1-S `risk_score`, 487–497. Il ne s’agit pas d’une probabilité calibrée.

#### Avis et tri final

```text
force = min(1, 0,5×mois/0,40 + 0,5×semaine/0,15)
avis_brut = 10×[0,35×R + 0,25×force + 0,40×(1−(risque−1)/9)]
```

Plafond résultats 6, plafond rachat 3 ; bornage 1–10 puis arrondi à une décimale.
Tri final décroissant `(avis, score)`, après troncature initiale par score.
Références : V1-S 500–508, 1041–1044 et 1094–1095.

Exemple réellement exécuté avec les fonctions V1 extraites :

| Entrée | Valeur |
| --- | ---: |
| Jour / semaine / mois | +1 % / +6 % / +20 % |
| R² | 0,90 |
| Jours positifs | 70 % |
| Concentration | 20 % |
| Volatilité | 2 %/jour |
| Montant échangé | 40 M/jour |
| Recul courant | −3 % |
| Rachat / résultats | Non / non |

```text
F = 0,1225
R = 0,6885
S = 8,434125
risque = 1/10
avis = 7,5/10
```

#### Score ETF

Pour chaque fenêtre : q=R² si pente>1e−10, q=−R² si pente<−1e−10, sinon q=0.

```text
score_ETF = 100×[0,5×min(q_semaine,q_mois) + 0,25×(q_semaine+q_mois)]
avis_ETF = round((score_ETF+100)/20, 1)
```

Score de −100 à +100, avis de 0 à 10. L’avis ETF remplace l’avis précédent.
La qualification est prioritaire dans la sélection ; le navigateur ajoute 200 au
score de tri des ETF qualifiés. Références : V1-S 373–390, 750, 1089–1093 ; V1-J 18.

### 28. Normalisation

V1 : plafonds/multiplicateurs fixes pour actions, R² signé pour ETF ; aucune
normalisation par population. V2/V3 historique : percentiles par type et période,
puis moyenne pondérée. Schéma moderne : percentile, linéaire bornée ou brut ;
transformation identité, log1p, racine ou puissance. Références : STR 381–393 ;
SCORE 15–36 et 69–88.

### 29. Compensation des critères

V1 : force et régularité se compensent partiellement dans la note, sans contourner
les seuils stricts ; résultats/rachat plafonnent l’avis. Actuel : critères
éliminatoires en `all`, composantes compensables dans le score ; `any` peut
permettre un succès malgré d’autres échecs non obligatoires. Une période récente
inactive ne pénalise pas un plateau. Références : V1-S 394–398, 500–508, 1034–1035 ;
STR 259–266 ; SCORE 78–88.

### 30. Exclusion, score et information

Un indicateur peut avoir plusieurs rôles : R² V1 filtre/score/risque ; volatilité
V1 exclusion/risque/affichage ; métriques actuelles critère/composante/pastille.
Les pastilles SIG sont informatives au calcul ; les filtres de niveaux peuvent
ensuite masquer des lignes. Références : tableaux 15–16 ; SIG 1–7 ; SVC.

### 31. Incomplets, extrêmes et ex æquo

V1 : historique court exclu ; volume absent remplacé par zéro dans certains
chemins ; informations externes absentes signalées. Pas de départage explicite
par ticker, ni contrôle systématique de finitude dans `analyse`.

Actuel : échec prioritaire sur manque ; composante requise manquante → inconnu ;
renormalisation possible. Ex æquo : moyenne des rangs percentiles ; un seul
élément → 50. Départage : score décroissant, symbole, identifiant. Un score brut
ou à poids négatifs n’est pas forcément entre 0 et 100.
Références : STR 263–266, 381–393 ; SCORE 55–91.

### 32. Poids et stockage

V1 : fixes dans le code. Actuel : poids historiques par période, composants
modernes sauvegardés ; poids autorisés −1 000 à +1 000, au plus 48 composants ;
moyenne ou somme. Références : CFG validation dès 86 ; SCORE 78–88 ; LIB 12–27.

### 33. Explication et reproduction

V1 : explication qualitative, pas décomposition complète du score affichée.
Actuel : motifs `reasons`, détails `score_parts` avec valeur transformée,
normalisation, poids et contribution. Le champ `raw` est déjà transformé.
Une note percentile exige l’univers de comparaison complet, pas seulement le
cours de l’action. Références : V1-S `verdict` ; SCORE 15–36, 84–87 ; SVC 249–255.

## E. Actions, ETF et fournisseurs — questions 34 à 39

### 34. Cause exacte de la séparation V1

Le screener Nasdaq appelé est celui des actions ; les ETF contournent son filtre.
Les ETF ont ensuite un autre algorithme, sans les minima de performance et de
concentration des actions. Aucun champ fondamental manquant n’a été identifié
comme cause nécessaire de cette séparation. La capitalisation sert au préfiltre
actions, pas à leur score final. Références : V1-S 76–85, 1028–1039.

La voie Europe crée des actions par défaut ; aucun catalogue général d’ETF
européens équivalent à l’univers ETF US n’a été identifié dans le scanner.

### 35. Fournisseurs

V1 : NasdaqTrader pour l’univers US ; API Nasdaq pour présélection et résultats ;
Wikipedia pour indices européens ; Yahoo/yfinance pour cours, volumes, pays,
devises et certaines identités ; Google News RSS pour actualités ; Business
Insider pour ISIN approchés. FinanceDatabase absent du scanner V1 récupéré.

Actuel : **FinanceDatabase de JerBouma**, dépôt Git de CSV, pour le catalogue ;
Yahoo pour cours, volumes et profils. Ce n’est pas une API appelée « Financial
Database ». Références : V1-S 46–718 ; `engine/jobs/tasks.py` 27, 69–96 ;
`engine/catalogue/loader.py`.

### 36. Mesures communes actions/ETF

Performance, pente log, R², volatilité, ER, drawdown, recul, jours positifs,
concentration, moyennes et Momentum sont calculables identiquement sur des
historiques de qualité équivalente. C’est le moteur partagé actuel ; la V1 choisit
des scores différents. Références : MES ; SER ; PATH ; V1-S 342–398.

### 37. Données manquantes

| Absence | V1 | Moteur actuel |
| --- | --- | --- |
| Capitalisation | 1 Md de remplacement dans le préfiltre US | Catégorie inconnue ; exclu si filtre de catégorie actif |
| Volume | Zéro dans certains téléchargements ; contrôle Europe parfois contourné | Volume moyen inconnu exclu par défaut ; métriques historiques indisponibles |
| AUM | Non utilisé dans le score examiné | Inconnu ; exclu si filtre AUM actif |
| Frais ETF | Non utilisés dans le score examiné | Inconnu ; exclu si filtre de frais actif |
| Pays | Repli PEA par suffixe | Métadonnée absente et effets des filtres concernés |
| FX | Prix EUR indisponible | Conversion indisponible ; filtres concernés ne peuvent retenir |
| Historique | <40 points : exclusion | Mesures manquantes, politique de statut applicable |
| Actualités | Drapeau non vérifiées | Pas composante générique du score actuel |

Références : V1-S 83, 111–147, téléchargements, 460–461, 1057–1058 ; PRE 79–97 ;
SVC 452–471 ; PATH.

### 38. Traitement des ETF

V1 : autre score et replis non qualifiés possibles ; risque calculé mais avis
remplacé par la formule ETF. Actuel : mêmes mesures, groupes distincts par défaut
ou combinés si configuré ; règles par type possibles ; seuil de liquidité ETF
plus bas, AUM/frais spécifiques et capitalisation réservée aux actions.
Références : V1-S 1085–1093 ; CFG ; SCORE 39–64 ; PRE ; SVC 450–471.

### 39. Identités et doublons

V1 : regex US restrictive, déduplication par symbole, type ETF principalement
NasdaqTrader, devise par place/suffixe, ISIN parfois approché par nom. La recherche
ISIN utilise notamment bonus premier mot +0,2, pénalité ADR −0,3, préférence pays
+0,05, seuil de similarité 0,8 pour premiers mots différents, arrêt à 0,85 et
acceptation finale à 0,5. Effet : identité informative pouvant être incertaine.
Références : V1-S 68–69, `isin_of` 608–673, rendu 737–741.

Actuel : couple place/symbole puis regroupement ISIN, FIGI ou identité dérivée.
Une longueur ISIN de 12 n’est pas une validation complète. Certains collecteurs
indexent par symbole seul : collisions possibles si les identifiants fournisseurs
ne distinguent pas les places. Type issu du catalogue sans revalidation
systématique par `quoteType`. Références : CAT 44–49 ; loader dès 23 ;
`engine/market/collect.py:296`.

## F. Historiques et fiabilité — questions 40 à 47

### 40. Historique minimum

V1 : 40 cours positifs pour toute analyse ; trous non contrôlés par calendrier.
Actuel : N+1 cours pour fenêtre complète ; minimum 80 % arrondi au supérieur et
trois points pour régression trouée ; bornes pour rendement ; chemin complet
pour volatilité/drawdown/ER. Une fenêtre très incomplète peut produire un
dictionnaire vide de mesures plutôt que `None`, contournant une exigence
d’historique Momentum. Références : V1-S 344–346 ; MES 58–117 ; STR 220–229.

### 41. Ajustements

V1 : champ `Close`, repli yfinance avec `auto_adjust=False`. La mention « ajustés
des dividendes » du rendu n’est pas garantie par ces champs. Aucun ajustement
complet des événements ne peut être affirmé. Actuel : ajusté si complet et valide,
sinon brut avec traitement des splits connus. Références : V1-S 243–338, 766 ; SER.

### 42. Événements et données aberrantes

V1 : pas de traitement explicite splits/dividendes identifié dans l’analyse ;
cours non positifs retirés. Actuel : splits déclarés et cohérents corrigés,
ruptures inexpliquées bloquant les fenêtres, changements d’unité et erreurs
ponctuelles corrigés sous conditions ; pas d’invention de clôtures manquantes.
Les dividendes ne constituent un rendement total que si les ajustements
nécessaires sont disponibles. Références : V1-S 344 ; SER ; MES ; calendrier.

### 43. Fraîcheur et fuseaux

V1 : retard relatif maximal quatre jours ; univers entier périmé possible ;
normalisations spark/chart différentes. Actuel : fuseaux par place, clôture
attendue, délai de publication, contrôle intrajournalier 30 minutes, calendriers.
Le secours d’horloge et l’état ouvert ne constituent pas à eux seuls un calendrier
complet de jours fériés/demi-séances. Références : V1-S collecte et 1008–1014 ;
`engine/market/hours.py` 93–126 ; `calendar.py`.

### 44. Devises

V1 : FX récent pour prix EUR/budget, pas pour seuils de montant historique.
Actuel : FX EUR, historique daté avec report maximal sept jours dans PATH.
Le convertisseur général gère des sous-unités, mais PATH ne normalise avant
recherche FX que GBp/GBX vers GBP : ZAc/ILA restent un risque de données absentes.
Performance locale et performance d’un investisseur EUR sont distinctes.
Références : V1-S 364, 709–718 ; PATH 49–58 ; `collect.py`, conversion EUR.

### 45. Recalcul, stockage et caches

V1 : V1-C appelle `scan.py` sans paramètres de stratégie ; génération complète de
`rapport.html`. API : demande ou lancement si autorisé (`api.php` 225–272).
Caches pays/ISIN sans expiration explicite ; suivi conservé 120 jours, horizons
1/3/5 séances. Le script ne prouve pas les horaires du cron réellement installé.

Actuel : `strategy_metrics`, `series_state`, calcul des fenêtres manquantes,
cache par configuration financière/version de données. Nettoyage >3 jours lors
d’une reconstruction, sans TTL strict à chaque lecture ; version issue d’horloge,
états et jobs, sans hash intégral des historiques. Les fenêtres personnalisées
schéma 4 ne sont pas intégrées par `wanted_windows`, encore limité à la version 3 ;
calcul à la demande possible. Références : `compute.py` 16–28 ; SVC 228–299.

### 46. Tests et lacunes

V1 : pas de suite identifiée dans la collecte. Exécution isolée des fonctions
pures `analyse`, `etf_trend`, `score`, `risk_score`, `verdict`, extraites par AST,
sans exécuter le module ou le scanner complet.

Tests actuels exécutés depuis l’environnement virtuel existant :

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -B -m pytest -p no:cacheprovider -s -q \
  tests/fast/test_measures.py \
  tests/fast/test_momentum_strategy.py \
  tests/fast/test_market_session_windows.py
```

Résultat réel : **42 passed, 1 warning**. Avertissement de dépréciation de l’alias
`T` dans `exchange_calendars`. Pas de cache pytest ni bytecode écrit.

Tests présents également sur critères, scores configurables, splits, devises,
classement paginé et montants historiques avec prix bruts. Les tests d’intégration
avec base, migrations et collectes n’ont pas été exécutés pour cet audit.

Lacunes constatées : Momentum avec seules bornes présentes ; MA200 sur liste trop
courte ; alimentation effective des volumes historiques ; comparaison des trois
concentrations ; parité des fournisseurs sur réponses figées.

### 47. Déterminisme

Fonctions pures déterministes à entrées et environnement numérique identiques,
sous réserve des arrondis. Pour reproduire un classement complet, il faut figer
catalogue, cotation principale, univers filtré, historiques, événements, FX, heure,
calendriers, réglages, politiques de manquants, population percentile et versions
des dépendances. V1 : replis fournisseurs et ordre d’entrée peuvent changer le
résultat. Actuel : départage explicite mais percentiles dépendants de l’univers.
Références : V1-S présélection/collecte/tri ; STR 381–393 ; SCORE ; SVC.

## G. Anomalies et incertitudes

### Anomalies et risques classés

| Importance | Constat | Preuve / limites |
| --- | --- | --- |
| Élevée | Momentum retenu avec 3/127 cours, score 50, couverture 2,36 %, 124 manquants | Reproduit avec calendrier synthétique et fonctions réelles |
| Élevée | MA200 = 27,5 avec 55 cours constants à 100 | Reproduit ; fiche de configuration historique fournit 55 dates, SVC 763 ; MES 137–154 |
| Élevée | Critères de volume historique disponibles sans alimentation par les collecteurs quotidiens examinés | Code vérifié ; fréquence en production inconnue |
| Élevée | V1 : seuils de montant en devises locales hétérogènes | Formule vérifiée |
| Élevée | V1 : avis ETF remplace l’avis tenant compte du risque ; non-qualifiés possibles | Branches vérifiées |
| Moyenne | V1 : texte d’ajustement dividendes non garanti par collecte | Incohérence de code |
| Moyenne | V1 : fraîcheur seulement relative | Conséquence du contrôle |
| Moyenne | V1 : risque n/10 affiché aussi n×10 %, sans modèle probabiliste | V1-S 757 |
| Moyenne | V1 : notes actions/ETF/avis non comparables | Formules vérifiées |
| Moyenne | R² constant V1 divergent selon branche, sensible aux arrondis | Reproduit |
| Moyenne | Trois concentrations différentes dans le moteur actuel | Formules vérifiées |
| Moyenne | Dernier jour activé sans seuil n’impose pas une hausse | Moteur vérifié |
| Moyenne | Semaine plate pouvant rester première avec regular | Reproduit, conforme au profil |
| Moyenne | Fenêtre de référence arrondie à une fenêtre stockée ; règles par type non considérées dans ce choix | SVC 364–367 |
| Moyenne | Invalidation cache sans empreinte de tout historique | Code vérifié ; incident non reproduit |
| Faible | Commentaires sur deux séances et bornes de régression en désaccord avec exécution | Code/tests vérifiés |
| Faible | MA200 précédente non datée exige >205 cours au lieu de ≥205 | MES 132 |
| Faible | V1 : seuil PEA 1 M rendu inopérant par seuil commun Europe 2 M | Ordre vérifié |

### Reproduction du Momentum incomplet

Construire 127 dates de jours ouvrés `ds`, à partir du 2 janvier 2026, puis fournir
seulement les cours `(ds[0],100)`, `(ds[105],110)`, `(ds[126],111)`.
Utiliser `CFG.editable(STR.preset('momentum'))`, `evaluate_one` avec
`session_windows={126:ds}`, puis `rank` dans un groupe d’un titre.

```text
status = retained
momentum 6m = 10 %
score = 50
coverage = 3/127
reason = warning, pas missing
```

Les seules bornes du Momentum sont disponibles. La couverture insuffisante ne
devient qu’un avertissement car le dictionnaire de mesures existe.

### Informations nécessaires pour lever les incertitudes

| Élément non confirmé | Donnée nécessaire |
| --- | --- |
| Horaires effectifs V1 | Entrées cron Hostinger, en lecture seule |
| Règles administrateur réellement actives | Export expurgé des règles catalogue/préfiltre |
| Configurations personnelles utilisées | Export ciblé des configurations, sans transactions |
| Volumes et ajustements réellement disponibles | Comptages agrégés de manquants par type/place |
| Écarts spark/chart/yfinance | Réponses figées, mêmes titres/dates/options |
| Reproduction d’anciens classements V1 | Rapport daté et snapshot des entrées |
| Autres variantes V1/V2 | Source ou commit explicitement identifié |
| Unités de frais Yahoo selon endpoint | Réponses et documentation des champs exacts |

## État de livraison

L’audit distingue le fonctionnement établi par le code, les résultats reproduits
et les données encore nécessaires. Il ne certifie ni les réglages privés actuels
ni la qualité de l’ensemble des données de production.

Aucun correctif applicatif ni développement V4 n’est inclus. Aucun nouveau
déploiement n’a été réalisé. Ce README restitue l’audit ; sa création ne vaut pas
autorisation de modifier les moteurs ou les données.
