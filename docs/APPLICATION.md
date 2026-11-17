# Application jigobourso : données, méthodes et règles métier

Ce document décrit ce que fait l'application et comment, d'après le code. Il ne contient ni historique ni mesure ponctuelle. Chaque règle renvoie à `fichier:fonction`. Quand le code et ce document divergent, le code fait foi.

Hors périmètre (voir les documents dédiés) : architecture technique, contrat d'API, sécurité, structure du front, charte graphique.

## 1. Vue d'ensemble et vocabulaire

### 1.1 Ce que fait l'application

Application boursière en trois parties :

| Partie | Rôle | Emplacement |
|---|---|---|
| Moteur Python | collecte Yahoo, calendriers, mesures, scores, verdicts, tâches planifiées | `engine/` |
| Site et API PHP | routes JSON, registre des portefeuilles, comptes, réglages | `app/` |
| Front statique | pages HTML et scripts, sans calcul métier de notation | `app/public/` |

Base MariaDB (schéma : `db/schema.sql`, 47 `CREATE TABLE` et 2 vues, plus les migrations de `db/migrations/`). Le moteur écrit les mesures et les scores ; le PHP les lit, gère les portefeuilles et sert l'API.

### 1.2 Principe directeur

Une donnée absente ou douteuse n'est jamais remplacée en silence. Elle donne un statut explicite (indéterminé, partiel, non évaluable, incertain) ou un total nul (`null`), jamais un zéro ni une valeur reconstituée. Voir la section 9.

### 1.3 Vocabulaire

| Terme | Sens |
|---|---|
| Instrument | produit financier (table `instruments`), identifié par ISIN quand il existe |
| Cotation (`listing`) | instrument coté sur une place (MIC) avec un symbole Yahoo ; table `listings` |
| MIC | code de place de marché (ISO 10383) |
| Cotation principale | une seule cotation par instrument, choisie par la règle R1 (§2.3) |
| Séance | jour de bourse du calendrier de la place |
| Fenêtre de n séances | n+1 clôtures consécutives du calendrier de la place |
| Pente | variation moyenne par séance, en % : `100·expm1(b)` où b est la pente de la régression de ln(cours) sur le temps |
| R² | qualité de la droite de régression sur ln(cours) |
| Retenu / exclu / indéterminé | statut d'un titre face aux critères d'une stratégie (V4) |
| Partiel | note calculée avec une partie seulement des périodes attendues |
| Lot | un achat du registre, suivi jusqu'à sa vente (FIFO pour les alertes) |

### 1.4 Deux moteurs de stratégie

| Moteur | Où | Utilisé par |
|---|---|---|
| V4 actuel : scores absolus + statuts de critères + tableau de classement | `engine/analytics/scoring/` | page Classement (Explorer), fiche d'un titre, administration des scores |
| Historique : percentiles parmi les titres retenus, 7 préréglages | `engine/analytics/explorer/strategy.py` | Suivi des classements, alertes et barre de risque, portefeuilles, profils ETF, route `explore` (conservée mais non appelée par le front actuel) |

Le moteur V4 note tous les titres évaluables ; les critères ne donnent qu'un statut et ne modifient ni note ni rang.

## 2. Données

### 2.1 Chaîne de sélection du catalogue

1. Import brut de FinanceDatabase (`engine/jobs/tasks.py:fdb_import`) dans `catalogue_raw`. Rien n'est filtré à ce stade. `JIGO_FDB_REF` épingle une version (commit ou étiquette) pour un catalogue reproductible ; la version importée est notée dans `catalogue_loads`.
2. Filtres FinanceDatabase (`fdb_filter` → `engine/catalogue/rules.py`) puis création des produits et cotations (`loader.sync_listings`).
3. Informations Yahoo (`yahoo_info`) : cotation (prix, devise, volume moyen 3 mois, capitalisation, frais ETF, actifs nets) par lots de 50 (`collect.py:QUOTE_BATCH`), taux de change.
4. Préfiltre Yahoo (`yahoo_filter` → `engine/market/prefilter.py`) puis choix de la cotation principale (`loader.assign_primaries`).
5. Résultat : cotations `status='selected'` et `is_primary=1`. La vue `v_recommendable` expose ces cotations ; `v_collect_set` ajoute les cotations détenues en portefeuille (même hors sélection).

Chaque étape fige un entonnoir (`engine/analytics/explorer/funnel.py`, table `funnel_steps`) : nombre de lignes avant, écartées, conservées.

### 2.2 Règles FinanceDatabase (`engine/catalogue/rules.py`)

| Règle | Effet | Remarque |
|---|---|---|
| `incomplete` | écarte les lignes sans les champs de base | verrouillée |
| `duplicates` | écarte les doublons | verrouillée |
| `types` | types d'instruments admis | réglable |
| `markets` | places admises | `DEFAULT_MARKETS` = 14 places |
| `categories` | catégories admises | désactivée par défaut |
| `delisted` | écarte les titres radiés | |
| `nameless` | écarte les titres sans nom | |
| `warrants`, `spac`, `leveraged` | écartent par expression régulière sur le nom et le symbole | |

### 2.3 Cotation principale (`engine/catalogue/primary.py:choose_primary`, règle R1)

Ordre de départage entre les cotations d'un même instrument :

1. place du marché d'origine du pays (`HOME_MARKET`) ; pour un titre américain, les places de `US_MICS` ;
2. sinon la plus liquide (cours × volume moyen 3 mois converti en euros) ;
3. puis devise EUR ;
4. puis ordre (place, symbole).

Sans aucune liquidité connue, `FALLBACK_ORDER` s'applique. Le motif est stocké dans `listings.primary_reason`.

### 2.4 Préfiltre Yahoo (`engine/market/prefilter.py:decide`)

Une cotation sans information Yahoo n'a pas de décision. Une devise sans taux de change donne le statut `candidate`, pas un rejet.

| Règle | Seuil par défaut | Plage maximale |
|---|---|---|
| `stale` : dernier cours trop ancien | 10 jours | 3650 jours |
| `price` : prix minimal | 2 € | 1000 € |
| `liquidity_equity` : valeur échangée par jour, actions | 1 M€ | 1e9 |
| `liquidity_etf` : idem, ETF | 250 k€ | 1e9 |
| `unknown_volume` : volume inconnu | exclu | |

Valeur échangée = prix × volume moyen 3 mois × taux de change, avec les sous-unités ramenées à l'unité principale (§2.9). Les seuils sont des réglages (`settings`), appliqués par `collect.py:apply_prefilter`.

### 2.5 Calendriers (`engine/market/calendar.py`)

- Source : `exchange_calendars`, avec la table d'alias `_CALENDAR_BY_MIC` (MIC vers calendrier).
- `session_dates` donne les séances attendues d'une place ; `window_calendars` ancre les fenêtres de mesure sur ces séances ; `next_session_dates` donne les séances à venir.
- Un MIC inconnu rend le titre non évaluable (motif `calendar`). Il n'existe aucun repli lundi-vendredi.

Heures de marché (`engine/market/hours.py`) : table `HOURS` par MIC, `SETTLE_MINUTES` = 30 après la clôture, créneaux de `SLOT_MINUTES` = 15 minutes. `expected_last_close` donne la dernière clôture attendue d'une place à un instant donné ; `price_is_stale` juge un prix intraday périmé au-delà de 30 minutes.

Jour férié observé (`collect.py:observed_holiday`) : une place est jugée fériée un jour si moins de 5 % de ses titres ont une clôture alors qu'une collecte passée après la clôture a eu au plus 5 % d'erreurs. `effective_expected_close` remonte alors à la séance précédente (recherche sur 5 jours). `is_holiday` est un test distinct, utilisé par le rattrapage intraday : aucune barre ni clôture pour la place ce jour-là, après une collecte quotidienne passée.

### 2.6 Collecte quotidienne et intraday

| Constante | Valeur | Rôle (`engine/market/collect.py`) |
|---|---|---|
| `DAILY_KEEP_DAYS` | 610 minimum | rétention étendue selon la plus longue fenêtre réellement demandée |
| `FULL_SESSIONS` | 400 minimum | cible de rattrapage étendue selon les périodes actives, sans doublement pour l'accélération |
| `SPARK_BATCH` | 20 | symboles par appel d'historique |
| `QUOTE_BATCH` | 50 | symboles par appel de cotation |
| `FX_HISTORY_DAYS` | 300 | profondeur visée de l'historique de change |

- Clôtures quotidiennes dans `daily_prices` (clôtures définitives, `close_px`, `volume`). La colonne `adj_close_px` est réservée et jamais renseignée ; un cours ajusté n'est jamais mélangé à `close_px`.
- Intraday : barres de 15 minutes dans `intraday_prices`, conservées `retention_sessions` séances (20 par défaut, 5 à 60, plafond `YAHOO_DEPTH_SESSIONS`) ; `prune_intraday` purge le reste. Les trous de collecte sont consignés dans `price_gaps` ; un créneau est jugé troué selon les seuils de `collect.py` (0,4 / 2 créneaux / 0,05 / 0,85).
- `latest_prices` : une ligne par cotation, prix affiché (le plus récent entre cotation et barre intraday, colonne `source`).

Combler les trous (`collect.py:fill_gaps_batch`) :

| Réglage | Valeur |
|---|---|
| titres par passage (`GAP_LIMIT`) | 150 |
| budget de temps (`GAP_BUDGET_S`) | 60 s |
| nouvel essai d'un titre (`GAP_RETRY_DAYS`) | 30 jours |
| cible | titres dont `coverage_252 < 1` |
| écriture | `INSERT IGNORE` : jamais d'écrasement d'une clôture existante |
| arrêt | au premier refus de débit (HTTP 429) |

Volumes quotidiens (`fill_volumes_batch`) : budget 90 s, relecture des 2 dernières séances, nouvel essai après 6 h, relance manuelle reprise après 12 h.

### 2.7 Taux de change

- `collect.py:refresh_fx` : un taux du jour par devise présente dans `latest_prices`, EUR exclue (paire `XXXEUR=X`), sous-unités ramenées à la devise principale.
- `collect.py:backfill_fx` : complète l'historique (clôtures quotidiennes) des devises dont le premier taux est récent ; n'écrase jamais un taux existant ; une devise sans réponse n'est redemandée qu'une fois par semaine.
- Une transaction antérieure au début de l'historique exige un taux saisi à la main (§8.5).

### 2.8 Splits (`engine/market/splits.py`, `split_review.py`)

Un saut de cours est un split suspect ; la table `split_log` suit son statut.

| Étape | Règle |
|---|---|
| Détection (`detect`) | saut compatible avec un ratio usuel (`COMMON_RATIOS`) à `TOLERANCE` 0,08 près |
| Vérification (`verify`) | demande à Yahoo ; accepte un split déclaré dont la date est à ±5 jours et le ratio à ±15 % |
| Revérification (`recheck`) | jusqu'à 3 réponses de Yahoo ; délais 7 puis 14 jours ; fenêtre 60 jours ; 30 titres par passage ; nouvel essai après 3 jours |
| Statuts | `detected` (en attente), `confirmed` (split déclaré, historique ajusté), `real_move` (aucun split déclaré : vrai mouvement) |

Revue manuelle (`split_review.py:decide`) : un administrateur peut appliquer un ratio (`applied`), refuser (`rejected`) ou remettre en attente (`pending`). Appliquer exige une source ou une explication, un ratio qui explique le saut observé (`|price_ratio × ratio − 1|` sous `RATIO_TOLERANCE`) et crée l'événement dans `corporate_events` ; la décision est tracée dans `split_reviews` et `split_review_history` avec une révision optimiste. Un split confirmé déclenche un recalcul des mesures (`split_metrics_pending`).

### 2.9 Unités de prix (`engine/shared/units.py`, miroir PHP `app/lib/units.php` (`unit_split`) et `app/services/ledger.php` (`eur_factor`))

Sous-unités : `GBp` / `GBX` (pence), `ZAc` / `ZAC` (cents), `ILA` (agorot), toutes divisées par 100 pour revenir à la devise principale (GBP, ZAR, ILS). `to_eur_factor` renvoie `None` si le taux manque : la valeur en euros est alors inconnue, jamais approximée.

### 2.10 Tâches planifiées (`engine/jobs/`)

- Un cron appelle `tick` toutes les 5 minutes en production (`schedule.py:CRON_EXPECTED_MINUTES`).
- `tick` lance : l'intraday des places ouvertes ou tout juste fermées (intervalle réglable, 15 minutes par défaut, 5 à 120) ; le quotidien d'une place quand `catchup.daily_due` le demande ; le recalcul `metrics` si un split est en attente ; la `maintenance` si `maintenance_pending` est posé (nouvel essai 30 minutes après un échec) ; le rattrapage.
- Rattrapage (`engine/market/catchup.py`) : contrôle toutes les 10 minutes, nouvel essai quotidien (10, 360) minutes, abandon après 24 h, temps mort de 15 minutes, budget de 150 s, 3 confirmations.
- Un traitement bloqué depuis plus de 90 minutes (`STUCK_MINUTES`) est considéré perdu.
- `tasks.py:maintenance` enchaîne, dans l'ordre : sauvegarde des données utilisateur, cotations, change, historique de change, clôtures manquantes, volumes, détection / vérification / revérification des splits, `compute_all` (§3), profils et similarité ETF, suivi des classements, résultats du suivi, rétention, ménage.
- Sauvegarde : `BACKUP_KEEP` = 14, tables listées dans `BACKUP_TABLES`.
- Ménage (`housekeeping`) : `login_attempts` et `account_attempts` 1 jour, sessions expirées, `account_tokens` 7 jours, `job_steps` et `jobs` 90 jours, collectes automatiques réussies 7 jours.
- Traitements manuels (administration) : `fdb_import`, `fdb_filter`, `yahoo_info`, `yahoo_filter`, `history`, `gaps`, `volumes`.

## 3. Mesures sur une fenêtre

Toutes les mesures se calculent sur ln(cours), sur une fenêtre de n séances (n+1 clôtures). Code : `engine/analytics/series/measures.py`, `series.py`, `compute.py`.

### 3.1 Préparation de la série (`series.py`)

| Étape | Règle |
|---|---|
| `usable_closes` | cours ajusté utilisé seulement si toute la série l'est ; sinon `close_px` |
| `normalize_units` | corrige un changement d'unité (facteur `UNIT_FACTOR` 100, tolérance 6 %) |
| `drop_isolated_spikes` | retire une clôture isolée qui s'écarte de ses deux voisines d'un facteur `SPIKE_FACTOR` 4 alors que les voisines sont à moins de ×1,6 l'une de l'autre |
| `prepare_series` | applique le ratio d'un split confirmé, sauf si l'échelle observée ne le justifie pas ; repère les ruptures (`BREAK_RATIO` = 1,6 entre deux clôtures) |
| `analyze_series` | produit la série et, pour chaque fenêtre manquante, une raison : `calendar`, `break`, `coverage` ou `history` |

### 3.2 Mesures (`measures.py:window_metrics`)

| Mesure | Formule |
|---|---|
| pente | `100·expm1(b)`, b = pente des moindres carrés de ln(cours) |
| R² | `sxy² / (sxx·syy)` |
| performance | `100·expm1(ln fin − ln début)` |
| volatilité | écart-type d'échantillon des Δln, ×100 ; exige au moins 3 variations |
| drawdown | plus forte baisse depuis un sommet de la fenêtre, en % |
| ER (efficiency ratio) | `(ln fin − ln début) / Σ|Δln|` |

Fenêtres techniques de base (`compute.py:BASE_WINDOWS`) : 1, 21 et 252 séances. Les fenêtres de score sont l'union des périodes actives des stratégies, jusqu'à 1 260 séances ; une période personnalisée reste dans sa stratégie. Les périodes prédéfinies comprennent 1, 5, 21, 63, 126, 252, 504, 756 et 1 260 séances.

Fenêtre trouée (`dated_window_metrics`) : acceptée si elle compte au moins `max(3, ceil(0,80 × clôtures attendues))` points. La performance exige les deux bornes. Volatilité, drawdown et ER sont indisponibles dès qu'une clôture manque, car un trou fausse les variations.

### 3.3 Autres mesures

| Mesure | Définition | Code |
|---|---|---|
| momentum 6-1 | rendement de J−126 à J−21 | `series.py:momentum_6_1` |
| momentum 12-1 | rendement de J−252 à J−21 | `series.py:momentum_12_1` |
| MA20, MA50, MA200 | moyennes mobiles ; MA50 d'il y a 5 séances, MA200 précédente | `measures.py:moving_average`, `technical_state` |
| variation du jour, écart à la MA20 | `daily_change`, `gap_to_ma20` | `technical_state` |
| séances positives | part des variations > 0 de la fenêtre | `scoring/score_inputs.py:path_inputs` |
| concentration (`spike_share`) | `ln(1 + plus forte hausse d'une séance) / ln(cours final / cours initial)` ; 1 si la fenêtre ne monte pas | `path_inputs` |
| accélération V4 | pente par séance de la seconde moitié moins celle de la première moitié de la même période ; fiabilité fondée sur leurs R² | `score_inputs.py:window_inputs` |

Pour le Score 2 V4, `score_inputs` utilise désormais deux moitiés successives **internes** à chaque période. L'ancien momentum 6-1/12-1 reste dans `series_state` pour les lecteurs historiques, mais ne contribue plus aux Scores V4.

Une clôture absente rend ces mesures indisponibles : on ne comble jamais un trou.

### 3.4 Liquidité (`series/liquidity.py`)

Fenêtre de `WINDOW` = 20 séances, `MIN_DAYS` = 15 séances au minimum.

- Source `daily` : moyenne des volumes réels de `daily_prices` × cours, convertie en euros avec le dernier taux de change connu.
- Source `estimated` : volume moyen 3 mois de `latest_prices` × prix, quand moins de 15 séances ont un volume valide (`MIN_DAYS`).
- Un volume absent n'est jamais compté comme zéro. Résultat dans `liquidity_state` : valeur en euros, nombre de séances (source `daily` seulement) et source.
- La liquidité du Score 2 est distincte : moyenne des valeurs échangées réelles de chaque période active, dans `score_inputs`, disponible si au moins `max(3, ceil(0,75 × séances))` volumes sont valides ; aucune estimation Yahoo n'entre dans le score.

### 3.5 Calcul et stockage (`compute.py:compute_all`)

Écrit, pour chaque cotation sélectionnée ou détenue : `strategy_metrics` (une ligne par fenêtre : pente, R², performance, volatilité, drawdown, ER, observations, clôtures attendues, couverture), `series_state` (qualité et indicateurs techniques), `score_inputs`, `liquidity_state`. La colonne `strategy_metrics.acceleration` est réservée et toujours nulle ; l'accélération vit dans `score_inputs`.

Qualité de série stockée : `insufficient` si moins de 22 clôtures ; `stale` si la dernière clôture précède la clôture attendue ; `break` si une rupture tombe dans les 252 dernières clôtures ; sinon `ok`. Les états `incomplete` et `calendar_unknown` sont dérivés à la lecture à partir de `coverage_252` et des motifs de manque.

Couverture = observations / clôtures attendues selon le calendrier de la place.

## 4. Scores V4

Code : `engine/analytics/scoring/scores.py` (`VERSION = 5`), profils dans `scores_profiles.py`, service et cache dans `score_service.py`.

Deux notes sur 100 par stratégie : le score simple et le score complexe. Chaque note combine des périodes (par exemple semaine et mois).

### 4.1 Constantes générales

| Constante | Valeur | Sens |
|---|---|---|
| `KAPPA` | 0,7 | exposant des poids automatiques de périodes |
| `COVERAGE_THRESHOLD` | 0,75 | couverture minimale d'une période |
| `MIN_SESSIONS` | 3 | séances minimales d'une période |
| `DAY_SESSIONS` | 1 | longueur de la période Jour |
| `SAT_A` | 17 (plage 5 à 200) | saturation de la dynamique |
| `SAT_B` | 0,52 | exposant de la saturation |
| `ACCEL_REF` | 0,4 (plage 0,05 à 5) | accélération de référence |
| `ACCEL_R2` | 0,6 | R² de pleine confiance de l'accélération |
| `VOL_SLOPE_FLOOR` | 0,3 | plancher de pente pour la volatilité relative |
| saturation du momentum | `SAT_A·((n−e(n))/5)^SAT_B` | même famille que la dynamique, sur la durée réellement mesurée |
| `GATE_FLOOR` | 32 | plancher de la porte de fiabilité |
| `RELIABILITY_SESSIONS` | 21 | séances d'une période pleinement fiable |
| `ANCHOR_LAMBDA` | 0,5 (réglable 0 à 1) | poids de l'ancrage sur la période la plus courte |
| liquidité | 2 M€ → 50 M€ | échelle logarithmique de 0 à 100 |

### 4.2 Poids des périodes

Poids automatiques : `ω ∝ n^(1−κ) − n_prev^(1−κ)` pour une période de n séances qui suit une période de n_prev séances (n_prev = 1 pour la première période). Avec κ = 0,7, semaine puis mois donnent 41,6 % et 58,4 %. Des poids personnalisés (profil) remplacent le calcul automatique ; un poids nul met la période en contexte seulement.

### 4.3 Dynamique d'une période

`saturation = SAT_A · (n/5)^SAT_B`. La pente de la période, rapportée à cette saturation, donne la dynamique de 0 à 1 (plafonnée). La pente est d'abord convertie en croissance composée sur n séances, puis rapportée à la saturation : la croissance cumulée exigée augmente avec n, mais la pente par séance exigée diminue.

### 4.4 Score simple

`score simple = min(100, 100 · D · Q)` où D est la dynamique pondérée par les poids de périodes et Q la moyenne des R² (négatifs ramenés à 0, périodes sans R² écartées), pondérée par le poids effectif de la période × `min(1, n / 21)`.

### 4.5 Score complexe

Moyenne pondérée de notes de composantes, divisée par la somme des poids des composantes disponibles (une composante indisponible ne compte pas comme zéro, son poids sort du dénominateur), puis multipliée par `1 − λ·(1 − porte)` où la porte est celle de la période active la plus courte hors Jour. Avant l'agrégation, la porte de chaque période (dynamique / 32, plafonnée à 1) amortit aussi R², séances positives, concentration, volatilité et drawdown ; dynamique, accélération, momentum, récupération et liquidité n'en ont pas.

Dix composantes (`scores.py:COMPLEX_WEIGHTS`, poids par défaut) :

| Composante | Poids | Note de 0 à 1 |
|---|---|---|
| `dynamics` | 40 | dynamique (§4.3) |
| `r2` | 15 | `(R² − 0,5) / 0,45` |
| `up_days` | 5 | `(part de séances positives − 0,4) / 0,4` |
| `concentration` | 7 | `(0,60 − spike_share) / 0,5` |
| `volatility` | 15 | mode absolu : `(5 − vol) / 4` ; mode relatif : rapport volatilité / pente, 1 donne 100 et 4 donne 0, avec plancher de pente `VOL_SLOPE_FLOOR` |
| `drawdown` | 8 | `(15 − drawdown) / 15` |
| `liquidity` | 10 | par période : valeur échangée moyenne réelle, échelle logarithmique 2 M€ à 50 M€ par jour |
| `acceleration` | 0 | écart des pentes des deux moitiés internes ; référence `saturation(floor(n/2))/floor(n/2) × accel_ref`, fiabilité par les R² |
| `momentum` | 0 | par période : rendement du début à `n−e(n)` séances, `e(n)=max(1,min(21,arrondi(n/12)))`, saturé comme la dynamique sur `n−e(n)` |
| `recovery` | 0 | par période : `100 × fraction du plus grand recul récupérée à la clôture × min(1, profondeur/10 %)`, premier sommet-creux en cas d'égalité ; hausse continue = 0 |

Les bornes de chaque note sont écrêtées entre 0 et 100. Les stratégies donnent des poids différents (§5.2).

### 4.6 Statut et rang

Statut d'une note : `ok` (toutes les périodes), `partiel` (couverture ou séances insuffisantes sur une partie des périodes), `inconnu` (aucune période exploitable, ou aucune régularité ou composante mesurable). Une note partielle reste numérique et classée. `rank_order` et `rank_positions` ordonnent les titres ; le rang du tableau (`ranking_table.py`, via `ranking_support.ordered`) est commun à toutes les cotations notées, actions et ETF confondus ; le rang par groupe (actions / ETF) est celui de `score_service.py:attach`.

### 4.7 Profils et réglages (`scores_profiles.py`)

- `TUNING_DEFAULTS` : `sat_a`, `accel_ref`, `vol_mode` (`absolute` ou `relative`). Le momentum ne possède plus d'horizon fixe indépendant de la stratégie.
- Les poids des composantes d'un profil totalisent 100 (tolérance 0,05).
- Profils enregistrés dans `settings.scores_profiles` (officiel) et `scores_profiles_u<uid>` (personnel). Aucun repli global des poids : un profil incomplet est refusé, sauf `momentum` et `recovery` qui valent 0 par défaut.
- Paramètres globaux κ, seuil de couverture, ancrage : `settings.scores_v4` (validation `explorer/explorer_config.py:validate_scoring` : κ de 0 à 0,95, seuil de 0,1 à 1, ancrage de 0 à 1).
- `apply_profile`, `neutral`, `clean_profile` normalisent les profils.

### 4.8 Service et cache (`score_service.py`)

- `params_for` retire la période Jour si son poids est nul.
- Clé de cache : `scores-v1:` + empreinte SHA-1 des paramètres de notation (sans `required` ni `threshold`, qui n'influent pas sur une note) + `SC.VERSION`. Le cache vit dans `result_cache`.
- Changer un critère ne change jamais une note : les critères n'entrent pas dans la clé.

## 5. Stratégies, critères, verdicts

### 5.1 Les sept stratégies V4 (`scoring/scores_specs.py:V4_STRATEGIES`)

Correspondance avec les anciens identifiants (`CT_BUILTIN`) : `fast` → `growth_v4`, `regular` → `growth_regular`, `calm` → `calm_rise`, `rebound` → `rebound`, `mom6` → `momentum_6m`, `mom12` → `momentum_12m`, `momrisk` → `momentum_risk`.

### 5.2 Réglages par stratégie

| Stratégie | Périodes (poids) | Spécificités |
|---|---|---|
| `growth_v4` | semaine, mois (automatique) | pente très forte, sans seuil de R² |
| `growth_regular` | mois, trimestre | pente modérée, R² flexible, `sat_a` 10 ; poids complexes : dynamique 20, R² 35, séances positives 15, concentration 10, volatilité 5, drawdown 5, liquidité 10 |
| `calm_rise` | mois, trimestre | `sat_a` 10 ; volatilité 35, drawdown 20, dynamique 10, R² 10, séances positives 10, concentration 5, liquidité 10 |
| `rebound` | semaine, mois, semestre (50 / 50 / 0, semestre en contexte) | `accel_ref` 0,25 ; dynamique 15, R² 10, séances positives 5, concentration 5, volatilité 10, drawdown 5, liquidité 5, accélération 20, rebond 25 |
| `momentum_6m` | trimestre, semestre (30 / 70) | momentum 50, dynamique 15, R² 10, volatilité 5, drawdown 10, liquidité 10 |
| `momentum_12m` | semestre, année (30 / 70) | mêmes poids complexes que `momentum_6m` ; momentum calculé sur chaque période |
| `momentum_risk` | semestre, année (40 / 60) | momentum par période 80, volatilité 10, drawdown 10 |

Stratégies personnelles : identifiant `ct:<uid>:<id>`, construites par `_ct_builder` à partir d'un profil de scores et d'un jeu de critères. Au plus 30 par utilisateur (`app/services/ct_strategies.php:CT_MAX_CUSTOM`), enregistrées dans `settings.ct_strategies:<uid>`.

### 5.3 Niveaux de pente et de R² (modes Simple)

Les niveaux de pente viennent de `strategy.py:SLOPE_LEVELS` = `100·expm1(ln 2 / (années·252))` : doubler en 8, 4, 2 ou 1 an(s).

| Niveau de pente | Doublement | Seuil en % par séance |
|---|---|---|
| doux | 8 ans | 0,0344 |
| modéré | 4 ans | 0,0688 |
| fort | 2 ans | 0,1376 |
| très fort | 1 an | 0,2754 |

| Niveau de R² | Seuil |
|---|---|
| flexible | 0,5556 |
| équilibré | 0,75 |
| strict | 0,8889 |

### 5.4 Critères et verdicts (`scoring/criteria.py`)

Un critère compare une mesure d'une période à un seuil. Verdict d'un titre :

| Verdict | Condition |
|---|---|
| `retained` | tous les critères actifs sont satisfaits |
| `excluded` | au moins un critère actif est mesuré et non satisfait |
| `undetermined` | une mesure nécessaire manque (donnée absente ou fenêtre non évaluable) et aucun critère mesuré n'exclut |

Une donnée manquante donne « indéterminé », jamais « exclu ».

Règles de lecture :
- Périodes prédéfinies disponibles (`PERIODS`) : de la séance (1) à cinq ans (1 260 séances), plus les périodes personnalisées propres à chaque stratégie.
- Seuils de pente et de R² pris seulement s'ils sont > 0 ; un seuil à 0 est sans effet.
- La période Jour n'évalue que la performance (critère « return »).
- Volatilité et repli (drawdown) sont lus sur `REFERENCE` = 21 séances.
- Mode Expert : arbre de règles (profondeur 6 au plus), les critères facultatifs sont joints en ET ou en OU.
- Le critère lit les mesures de fenêtres de séances de la cotation (`strategy_metrics`), calculées sur le calendrier de sa place ; il ne reconstitue aucune fenêtre.

### 5.5 Moteur historique (`explorer/strategy.py`, `VERSION = 3`)

Conservé pour le suivi, les alertes et les profils ETF. `preset` définit sept préréglages : `regular`, `fast`, `recovery`, `low_volatility`, `momentum`, `momentum12`, `momentum_risk`.

- Hausse calme : volatilité ≤ 1,5, drawdown ≤ 20, pente douce, R² flexible.
- Rebond (`recovery`) : fenêtre semestre avec `min_slope` −100 et rendement maximal 10.
- `judge` rend `retained`, `rejected` ou `unknown`.
- `rank` : percentiles par groupe parmi les titres retenus ; ex æquo au rang moyen ; un seul titre vaut 50 ; `momentum_risk` combine 35 / 45 / 10 / 10.
- Configuration version 4 (`explorer_config.py`, bornes `BOUNDS`, mode `SCORES_MODE` = `scores`, `configurable_score`) : critères et score pondéré configurables.

## 6. Classement, ordre de la recherche, filtres

### 6.1 Tableau de classement (`scoring/ranking_table.py:table`, route `ranking/table`)

- Toutes les cotations évaluables sont renvoyées avec leurs deux notes, leurs rangs et leur statut de stratégie. Aucune ligne n'est écartée par les critères.
- Tri par défaut : score complexe. Valeurs de référence lues sur 21 séances (`REFERENCE`).
- Rang : parmi toutes les cotations notées (actions et ETF confondus), indépendamment des filtres d'affichage.
- `default_norm` et `norm_of` fournissent les critères normalisés (`criteria.normalize`) appliqués par `verdicts` et `table` ; `verdicts` produit les statuts ; `curves` renvoie les courbes (100 identifiants au plus, route `ranking/curves`).
- Regroupements de métadonnées (pays, place, secteur, type) : `secondary_metadata_groups.json`.
- `ranking_support.py` : `ordered`, `series`, `closes`.

### 6.2 Affichage côté Explorer

La page Classement (`app/public/index.html`, `explorer*.js`) reçoit le tableau complet et applique, dans l'ordre :

1. recherche texte (symbole, nom, ISIN) ;
2. filtres secondaires (affichage seulement) ;
3. onglet Retenues / Exclues / Toutes selon le statut serveur.

Les compteurs portent sur le périmètre après filtres secondaires. « Ignorer les critères » affiche aussi les titres exclus. Aucune de ces étapes ne modifie une note ni un rang.

Deux modes de saisie des critères :

| Mode | Réglages |
|---|---|
| Simple | pente de 0 à 2 % par séance et R² de 0 à 1, par période |
| Expert | arbre de règles ET / OU |

Le statut est toujours calculé par le serveur (moteur `criteria`), identique pour le tableau, la fiche et l'administration.

Stockage local du navigateur : `jigo_classement_test_v1` (état), `jigo_ct_vis_v5` (colonnes visibles), `jigo_ct_ctx:<id>` (contexte passé à la fiche quand les réglages ne sont pas enregistrés) ; accès via `ExplorerStore`. Une fiche sans contexte retrouvable l'indique et ne rend aucun verdict.

### 6.3 Filtres secondaires (`app/config/explorer_secondary_filters.json`)

15 filtres : 11 éditables et 4 de catalogue.

| Type | Filtres |
|---|---|
| éditables (catégories à bornes) | `volatility`, `liquidity`, `volume`, `positive`, `spikes`, `concentration`, `drawdown`, `returns`, `quality`, `score_simple`, `score_complex` |
| catalogue (valeurs) | `country`, `sector`, `market`, `asset` |

Chaque filtre éditable définit des catégories : bornes, bornes incluses ou non, étiquette, couleur, catégorie « donnée indisponible » (`unknown`). Une valeur absente tombe dans la catégorie `unknown`, jamais dans une autre. Un filtre dont toutes les options sont cochées est sans effet.

Réglages en base (`settings`) :

| Clé | Contenu |
|---|---|
| `explorer_secondary_filters` | définitions des filtres |
| `explorer_secondary_defaults` | sélection par défaut, révision optimiste, `FOR UPDATE` |
| `explorer_secondary_user:<uid>` | sélection personnelle |
| `table_layouts`, `table_layouts:<uid>` | mise en page du tableau, commune puis personnelle |
| `ct_strategies:<uid>` | stratégies personnelles |

`scoring/score_categories.py` range une note déjà calculée dans une catégorie (`assign`) sans jamais la modifier ; une note partielle reste numérique et rangée.

### 6.4 Mise en page du tableau (`app/services/table_layouts.php`, `app/config/table_columns.json`)

Tailles de page 25, 50 ou 100 ; largeur de colonne de 48 à 480 ; trois tris au plus ; appareils `desktop` / `mobile` ; onglets `retained` / `excluded` / `all`. `table_columns.json` liste les colonnes des pages explorer et scores.

### 6.5 Ordre de la recherche de l'ancienne voie `explore`

Route `explore` (`engine/analytics/admin/service.py:explore`), conservée mais non appelée par le front actuel : les titres retenus par une stratégie historique sont classés par percentiles parmi les retenus ; des filtres de niveau (régularité, volatilité, négociabilité, `LEVEL_FILTERS`, `level_filtered_rows`) et un masque de négociabilité (`masked_by_tradability`) s'y appliquent. Ces règles ne régissent pas la page Classement actuelle.

## 7. Fiche d'un titre

Code : `engine/analytics/admin/title_sheet.py`, route `sheet`, page `titre.html`.

Contenu : identité, prix et devises, mesures par fenêtre, état technique, scores, verdict de la stratégie choisie avec le détail de chaque critère, courbe, qualité des données, risques propres, similarité, faits de marché.

### 7.1 Pastilles (`engine/analytics/series/signals.py`)

| Pastille | Règle |
|---|---|
| régularité | R² ≥ 0,75 : forte ; R² ≥ 0,556 : moyenne ; sinon faible |
| risque | vert si volatilité ≤ 1,5 % et repli ≤ 20 % ; orange jusqu'à ×2 de ces seuils ; sinon rouge |
| négociabilité | plancher = minimum du préfiltre × 2, confort = ×4 ; données périmées (> 10 jours) : `unknown` |
| top 10 | seuils 40 / 70 |
| famille | seuils 30 / 50 |
| tendance | classe selon `SLOPE_LEVELS` (`trend_class`) |

Négociabilité : fondée sur volume moyen 3 mois × prix (valeur du préfiltre), pas sur la source `daily` de la liquidité des scores.

### 7.2 Appréciation (`signals.py:assessment`)

Cinq niveaux : Très favorable, Favorable, Mitigé, Défavorable, Indéterminé. Hausse extrême : `EXTREME_RISE` = 100 % (avertissement). Contradiction : repli récent ≤ −5 % (sur 21 ou 5 séances) alors que la tendance de fond est ≥ +10 %, ou rebond récent ≥ +10 % dans une baisse de fond ≤ −10 % (`BACKGROUND_MOVE`, `RECENT_DROP`, `RECENT_RISE`).

### 7.3 Qualité des données et risques

`data_quality` résume la série (suffisante, périmée, rupture, incomplète, calendrier inconnu). `specific_risks` liste les risques propres au titre. Une activité récente (10 jours contre 3 mois) hors de l'intervalle [0,67 ; 1,5] est signalée (`title_sheet.py`).

### 7.4 Similarité (`signals.py:similarity`)

Jumeaux : corrélation ≥ 0,97 ; proches : de 0,90 à 0,97.

### 7.5 Faits de marché (`engine/analytics/market_views/market_facts.py`)

- Éligibilité PEA : pays de l'UE plus Islande, Liechtenstein, Norvège (`PEA_COUNTRIES`) et places listées (`PEA_MICS`). Un ETF est toujours « à vérifier ».
- Taille de capitalisation : micro < 300 M€, small < 2 Md€, mid < 10 Md€, large < 200 Md€, mega au-delà. Une capitalisation en pence donne `None`.
- Avis des analystes : donnée Yahoo affichée telle quelle (`analyst_view`).

## 8. Portefeuilles et registre

### 8.1 Registre (`app/services/ledger.php`, `app/services/transactions.php`)

Un portefeuille contient des transactions (`portfolio_transactions` : achat ou vente, quantité, prix unitaire, devise, taux, frais, date). Un titre peut être saisi à la main (`listing_id` nul, hors catalogue).

Valorisation (`ledger.php:portfolio_valuation`) :
- coût moyen pondéré (PMP) par position ;
- splits confirmés pris en compte (`split_events`) ; une lecture impossible des splits renvoie l'erreur 503 ;
- correction manuelle d'un split : un achat à prix nul à partir du jour du split (`free_buy_dates`, `pending_split_ratio`) ;
- prix = le plus récent entre cotation et clôture, converti avec `eur_factor` ;
- position « incertaine » si le change manque ou si les ventes dépassent les achats : elle est exclue des totaux et nommée ;
- valeur, plus-value latente (montant et %) et gain total `null` si une position n'est pas valorisable (`unpriced`) ; coût, réalisé, frais et montants investis restent calculés ;
- `held_listing_ids` : cotations détenues, ajoutées au jeu de collecte.

### 8.2 Écriture d'une transaction (`transactions.php`)

- `write_transaction` verrouille le portefeuille (`FOR UPDATE`), valide l'historique complet (`validate_transaction_history`, `oversold_transactions` : une vente ne peut excéder les achats antérieurs).
- `tx_fields` : date au plus égale à maintenant + 1 jour.
- `price_unit` : l'unité `GBp` est normalisée en `GBX`.
- Les bornes numériques des entrées sont limitées (`app/lib/http.php:NUM_MAX` = 1e12) et la base est en mode strict : valeur hors limites refusée, jamais tronquée.

### 8.3 Change historique (`transactions.php:historical_fx`)

Taux de la date de l'opération, ou le dernier taux antérieur ou égal à la date, à 7 jours au plus ; au-delà, erreur 422 et saisie manuelle du taux.

### 8.4 Lots FIFO (`transactions.php:open_lots`)

Les ventes consomment les achats les plus anciens. Les lots ouverts alimentent les alertes (§8.7) ; `lot_settings`, `lot_origin` portent les réglages et l'origine d'un lot.

### 8.5 Performance et gains

- `engine/analytics/portfolio/performance.py:linked` : performance en Modified Dietz chaînée jour après jour (neutralise les apports).
- Côté page (`app/public/assets/pf-math.js`) : gain d'une période = variation de valeur − apports nets ; pourcentage = gain / (valeur de départ + achats de la période).

### 8.6 Plan de suivi d'une position (`engine/analytics/portfolio/position_plan.py`, `MODEL_VERSION` = 1)

Modèle courant de décision par position.

| Constante | Valeur |
|---|---|
| `SIGMA_WINDOW` | 63 séances |
| `M6_LONG` / `M6_SKIP` | 126 / 21 séances |
| bornes de bande σ63 | 1 ; 1,5 ; 2 ; 3 ; 4 ; 6 ; ∞ |
| niveaux de bande | `low`, `moderate`, `high`, `very_high` |
| repli p90 sur 21 séances par bande | 6,1 / 11,0 / 14,9 / 19,8 / 25,6 / 30,3 / 40,1 |
| `RECUL_COMBINED` | 15 |

Règles : stop, recul, tendance, risque, objectif ; chaque stratégie définit ses supports (`SUPPORT`). Décision par priorité : sortir (`exit`) > réévaluer (`reevaluate`) > surveiller (`watch`) > garder (`keep`). Règles personnelles dans `position_plan_rules` ; niveaux de stop et d'objectif dans `position_levels` (devise de la cotation).

### 8.7 Alertes par lot (`engine/analytics/portfolio/alerts.py`, route `alerts`)

Par défaut : durée de détention `DEFAULT_DAYS` = 182 jours ; chute depuis le plus haut depuis l'achat `DEFAULT_DROP` = 20 %. Les réglages de la stratégie d'origine ou les réglages personnels du lot les remplacent (`rules_for`).

| Alerte | Déclenchement | Niveau |
|---|---|---|
| durée | détenu depuis au moins `days` jours | surveillance |
| chute | chute depuis le plus haut depuis l'achat ≥ seuil ; plus haut mesuré sur la série corrigée des splits (le prix payé n'est pas utilisé) | action si l'action conseillée est « alléger », sinon surveillance |
| momentum | stratégies momentum : momentum 6 mois < 0 | action |
| MA50 | stratégie rebond : cours sous la MA50 | action |
| rang | n'est plus parmi les premiers de sa stratégie | information |

Stratégie « prudent » : durée 365 jours, pas de seuil de chute, action « rééquilibrer ». `alerts/refresh` répond « désactivé » ; `watch.run_all` n'est plus exécuté (les modèles de `watch.py` restent pour les règles).

### 8.8 Barre de risque (`engine/analytics/portfolio/risk.py`)

Utilisée par `alerts.lot_alerts`. Horizons (séances : fenêtre récente / fenêtre longue / horizon du seuil de recul) : `fast` 21/63/10 ; `regular`, `low_volatility`, `recovery`, personnalisé 63/126/21 ; stratégies momentum 126/252/63. `K` = 2, recul de 6 à 30 %, extension au-dessus de la MA50 de 25 %.

Trois signaux (tendance, recul, stabilité) valent 0 à 2 chacun. Niveaux : `ok` (0 à 1), `watch` (2 à 3), `act` (4 ou plus, ou recul au moins égal au seuil) ; `na` si rupture ×1,6 ou historique trop court.

### 8.9 Suivi des classements (`engine/analytics/portfolio/tracking.py`, routes `tracking/*`)

- Chaque jour, `record_snapshot` enregistre les `TOP_N` = 20 meilleurs titres de chaque groupe (actions, ETF) pour chacune des 7 stratégies historiques (`strategy.PRESETS`) dans `ranking_snapshots`.
- Les rendements à `HORIZONS` = 1, 3, 5, 21, 63 séances sont calculés dans `ranking_outcomes`, comparés à la médiane et à la moyenne de l'univers (`universe_outcomes`). Une donnée de plus de `MAX_STALE_DAYS` = 5 jours n'est pas utilisée.
- `summarize` : nombre, moyenne, médiane, part de gagnants, écart à la moyenne de l'univers (`edge`), écart médian (`edge_median`), part qui bat la médiane (`beat_pct`). Les observations d'un même jour ou de jours voisins se chevauchent : `n` ne compte pas autant de cas indépendants que `days`.
- Une règle d'alerte de suivi se règle via `tracking/rules` ; `tracking/strategy` donne les statistiques par stratégie.

### 8.10 ETF (`engine/analytics/market_views/etf.py`, profils `engine/market/etf_profile.py`, `VERSION` = 4 ; analyse de similarité `etf.py`, `VERSION` = 2)

Profil d'un ETF (frais, actifs, composition, secteurs) lu chez Yahoo et mis en cache (`etf_profiles`) ; frais et actifs de repli viennent de la cotation. Profil frais jusqu'à `MAX_PROFILE_DAYS` = 90 jours ; rafraîchissement de `WARM_LIMIT` = 120 fonds par passage, budget `WARM_BUDGET_S` = 60 s, profil rechargé après `PROFILE_FRESH_DAYS` = 30 jours.

Similarité entre ETF (`build`, `correlate`) :
- rendements hebdomadaires en euros sur `WEEKS` = 52 semaines, change daté (dernier taux antérieur, 7 jours au plus), sans remplissage ; un rendement n'existe que si les deux clôtures existent et qu'aucune rupture ne les sépare ;
- corrélation = moyenne de cinq corrélations, une par jour de la semaine ; chaque jour exige `MIN_WEEKS` = 40 semaines et au moins `MIN_PARTITIONS` = 3 jours valides ;
- stabilité : écart entre les cinq corrélations ≤ `SPREAD_LIMIT` 0,15 et écart entre les deux moitiés ≤ `HALF_LIMIT` 0,20 ;
- paliers (`tier`) : ≥ 0,97 quasi identiques ; ≥ 0,90 très proches ; ≥ 0,75 proches ; voisins retenus à partir de 0,80 (5 au plus) ;
- `NEAR_IDENTICAL` 0,97, `IDENTICAL` 0,99, `NEAR_LIMIT` 40 liens compacts par fonds ; autre cotation du même instrument : jamais comptée comme un autre fonds ;
- regroupement d'une page (`page_groups`) : chef direct, même couverture de change et mêmes marqueurs, corrélation ≥ 0,99 ou même indice d'après le nom ;
- concentration (`concentration`) : alerte quand au moins 3 ETF d'une même famille figurent parmi les dix premiers ; `RANKED_DEPTH` = 300 ;
- exposition (`exposure`) : une catégorie du catalogue est une indication qualitative, jamais une pondération.

## 9. Intégrité financière et comportements jamais dégradés en silence

| Cas | Comportement | Code |
|---|---|---|
| Calendrier de la place inconnu | titre non évaluable (`calendar`), pas de repli lundi-vendredi | `calendar.py`, `series.py:analyze_series` |
| Clôture manquante dans une fenêtre | volatilité, drawdown, ER, séances positives, accélération indisponibles ; une couverture incomplète (< 0,999) donne une note partielle, aucune mesure exploitable une note inconnue | `measures.py`, `score_inputs.py` |
| Rupture de série (×1,6) | fenêtre non évaluable (`break`), qualité `break` | `series.py`, `compute.py` |
| Clôture isolée aberrante | retirée de la série | `series.py:drop_isolated_spikes` |
| Split non confirmé | saut tracé (`detected`), non appliqué au registre ; revue manuelle possible | `splits.py`, `split_review.py` |
| Split confirmé non lisible côté registre | erreur 503, pas de valorisation approximative | `ledger.php:split_events` |
| Devise sans taux | `to_eur_factor` renvoie `None` ; valeur en euros inconnue ; préfiltre : `candidate` | `units.py`, `prefilter.py` |
| Taux historique absent (> 7 jours) | saisie refusée (422) tant qu'un taux n'est pas fourni | `transactions.php:historical_fx` |
| Vente supérieure aux achats | position incertaine, exclue des totaux et nommée ; la saisie qui créerait cette situation est refusée | `ledger.php`, `transactions.php` |
| Position non valorisable | totaux dépendant de la valeur (valeur, latente, gain total) `null` (jamais une somme partielle présentée comme complète) | `ledger.php:portfolio_valuation` |
| Volume absent | liquidité estimée ou inconnue, jamais zéro ; préfiltre exclut un volume inconnu | `liquidity.py`, `prefilter.py` |
| Donnée de critère manquante | verdict `undetermined`, jamais `excluded` | `criteria.py` |
| Note sans toutes ses périodes | statut `partiel`, note conservée et marquée | `scores.py` |
| Composante de score indisponible | sort du dénominateur ; jamais comptée comme zéro | `scores.py` (version 5) |
| Prix périmé | pastille négociabilité `unknown` après 10 jours ; prix intraday périmé après 30 minutes | `signals.py`, `hours.py:price_is_stale` |
| Lecture d'un contexte de fiche introuvable | message explicite, aucun verdict | `explorer.js`, `titre` |
| Écriture simultanée de réglages | révision optimiste, refus de l'écrasement | `settings` (`explorer_secondary_defaults`), `split_reviews` |
| Valeur numérique hors limites | refusée (mode SQL strict, `num_in`) | `app/lib/db.php`, `app/lib/http.php` |

## 10. Données et schéma

### 10.1 Tables principales (`db/schema.sql`)

| Groupe | Tables |
|---|---|
| Catalogue | `instruments`, `listings`, `catalogue_loads`, `catalogue_raw`, `funnel_steps` |
| Prix | `daily_prices`, `intraday_prices`, `latest_prices`, `fx_rates`, `corporate_events`, `price_gaps`, `split_log`, `split_reviews`, `split_review_history` |
| Mesures | `strategy_metrics`, `score_inputs`, `liquidity_state`, `series_state`, `result_cache` |
| Traitements | `jobs`, `job_logs`, `job_steps`, `settings` |
| Comptes | `users`, `sessions`, `session_policies`, `login_attempts`, `account_tokens`, `account_attempts` |
| Portefeuilles | `portfolios`, `portfolio_transactions`, `portfolio_targets`, `lot_settings`, `lot_origin`, `position_levels`, `position_watch`, `position_watch_log`, `position_plan_rules`, `alert_rules`, `alert_events`, `alert_models` |
| ETF | `etf_profiles`, `etf_analysis` |
| Suivi | `ranking_snapshots`, `ranking_outcomes`, `universe_outcomes` |
| Divers | `explorer_saved` (bibliothèque historique, encore dans les sauvegardes) |

Vues : `v_collect_set` (cotations sélectionnées principales non détenues, plus cotations détenues), `v_recommendable` (cotations sélectionnées principales).

### 10.2 Conventions

- Le schéma est rejouable : toutes les tables sont en `CREATE TABLE IF NOT EXISTS` (les deux vues en `CREATE VIEW`) ; toute évolution passe par une migration dans `db/migrations/` (appliquée par `scripts/migrate.py`).
- `daily_prices` : table compressée, clé (cotation, date), `close_px` DECIMAL(16,6), `volume` nul si inconnu.
- Heure en base : UTC (`SET time_zone = '+00:00'` à l'ouverture de connexion PHP).
- Quantités de transaction : DECIMAL(24,8) ; taux de change : DECIMAL(20,10).
- Sessions : durée de 30 jours (`app/lib/auth.php:SESSION_DAYS`), 24 h sans « se souvenir de moi » ; jeton stocké haché SHA-256.
- Mots de passe : 10 caractères au moins, 72 octets au plus, hachage `PASSWORD_DEFAULT`.
- Limitation des essais de connexion : fenêtre de 15 minutes ; 5 échecs verrouillent la paire (compte, IP), 30 le compte, 20 l'IP ; demandes de compte (réinitialisation, vérification) limitées sur une heure.
- Réglages (`settings`) : clé, valeur JSON, date de mise à jour ; utilisés pour les profils de scores, filtres, mises en page, préfiltre et réglages de collecte.

## 11. Limites connues

- Le moteur historique et le moteur V4 coexistent ; leurs notes et classements ne sont pas comparables (percentiles parmi les retenus contre scores absolus). Le Suivi des classements mesure les stratégies historiques, pas les scores V4.
- Les cours Yahoo ne sont pas ajustés des dividendes : les mesures sont des rendements de cours.
- Un split n'est reconnu que s'il est détecté, puis confirmé par Yahoo ou par un administrateur ; entre la détection et la confirmation, la série garde une rupture (fenêtres concernées non évaluables).
- La liquidité des scores utilise les volumes quotidiens quand au moins 15 séances sur 20 sont connues ; la pastille de négociabilité et le préfiltre utilisent toujours le volume moyen 3 mois, plus lent à réagir.
- Les jours fériés ne sont connus que par le calendrier ; un jour férié exceptionnel absent du calendrier n'est repéré que par le seuil de 5 % de titres avec clôture.
- Les clôtures manquantes ne sont comblées que par la collecte (jamais interpolées) ; un titre avec un trou reste partiel tant que le trou n'est pas comblé ou sorti de la fenêtre.
- La collecte dépend de Yahoo : un refus de débit (429) arrête le passage en cours, le suivant reprend.
- Les ETF n'ont pas de composition certifiée : l'éligibilité PEA d'un ETF est toujours « à vérifier » ; l'exposition par catégorie est qualitative.
- Le prix de revient (PMP) ne gère que les splits confirmés ; les autres opérations sur titres (dividendes, fusions, scissions) ne sont pas modélisées et se saisissent comme transactions.
- Les alertes de lot, la barre de risque et le plan de suivi sont des aides à la décision à partir de seuils fixes, pas des recommandations ; les constantes ne s'adaptent pas à un titre particulier au-delà des bandes de volatilité.
- Les stratégies personnelles sont limitées à 30 par utilisateur ; les profils de scores doivent totaliser 100.
- Le champ `strategy_metrics.acceleration` est réservé et jamais calculé ; `daily_prices.adj_close_px` est réservé et jamais renseigné.
