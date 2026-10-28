# Jigobourso v2 — architecture (refonte totale)

Statut : construction dans `/home/jigo/myProjects/jigobourso-v2/`, séparée de la production et de `bou-fix`.
Aucun ancien fichier n'est conservé par défaut : une fonction n'est reprise que si elle est pertinente **et** testée (voir §6).
Rien n'est déployé ni modifié en production sans accord explicite. Ni Git ni GitHub ne sont touchés.

## 1. Décisions retenues

| # | Décision | Valeur |
|---|---|---|
| D1 | Cotation principale (R1) | place d'origine, puis liquidité (prix × volume moyen 3 mois, en EUR), devise euro puis ordre alphabétique en départage |
| D2 | Historique quotidien | **400 séances** glissantes |
| D3 | Intraday | **barres de 15 min conservées** ; historiques 5 min et 1 h **supprimés** (modification du dossier initial) |
| D4 | Titres collectés | sélectionnés principaux **+ toutes les cotations détenues** |
| D5 | Page Suivi | **faite** : instantanés quotidiens des classements (`ranking_snapshots`) + résultats à 1/3/5 séances (`ranking_outcomes`) comparés à l'univers (`universe_outcomes`) |
| D6 | Noms de tables | anglais explicite |
| D7 | Langages | PHP (web), Python (moteur), MariaDB ; aucun framework |
| D8 | Notes par titre (`jb_notes`) | **supprimées** (table vide, fonction inutilisée) |
| D9 | Anciennes tables | supprimées seulement après observation et accord, avec export préalable |

Hypothèse à confirmer (réglable dans `settings`, pas de décision bloquante) : **rétention du 15 min = 20 séances**, tick toutes les 15 minutes.

## 2. Garanties de conception

1. **Exclu ≠ recommandé.** Seules les cotations `status='selected' AND is_primary=1` (vue `v_recommendable`) entrent dans l'Explorer, les classements et les stratégies. Cause du défaut actuel (DVDG.DE) : le snapshot actuel inclut des « ETF hors préfiltre Quote » (`quote_extra_etfs`) dans l'évaluation. En v2 le moteur évalue uniquement `v_recommendable` ; un test d'intégration échoue si une cotation exclue sort d'un classement, quelle que soit la période.
2. **Titre détenu toujours visible.** Le portefeuille lit `portfolio_transactions` + `latest_prices` et ne dépend ni du statut ni du préfiltre ; il affiche un badge « hors sélection » si la cotation est exclue.
3. **Cotations détenues toujours actualisées.** Le jeu de collecte est la vue `v_collect_set` (sélectionnées principales ∪ détenues) ; un test vérifie qu'une cotation détenue non principale reçoit son tick.
4. **Les quatre stratégies, six périodes et tous les réglages sont reproductibles** : `strategy_metrics` est indexée par `(listing_id, sessions)` (§4) et le moteur calcule à la demande tout nombre de séances 1–252 absent de la table. Test de parité contre l'ancien `strategy.py` sur `tests/fixtures/real/series.json` (§7).
5. **Volumes validés avant toute migration** (§8) sur des données représentatives, en base jetable.

## 3. Modèle de données (`db/schema.sql`, 26 tables/vues)

- **Catalogue** : `instruments`, `listings` (ids = anciens `listing_id`), `catalogue_loads`.
- **Prix** : `daily_prices` (400 séances), `intraday_prices` (15 min), `latest_prices`, `fx_rates`, `corporate_events`, `price_gaps`.
- **Analyse** : `strategy_metrics` (par titre et par fenêtre), `series_state` (indicateurs techniques, ruptures, qualité).
- **Exploitation** : `jobs`, `job_logs`, `settings`, `result_cache` (verdicts de l'Explorer par configuration ; invalidé quand `data_version` change : calcul nocturne, jeu recommandable, traitement terminé ; ≈ 0,25 s au lieu de ≈ 1,5 s).
- **Suivi** : `ranking_snapshots`, `ranking_outcomes`, `universe_outcomes` (`engine/analytics/tracking.py`, alimentées par `nightly`).
- **Utilisateurs** : `users`, `sessions`, `login_attempts`, `portfolios` (`strategy_config` JSON), `portfolio_transactions`, `etf_profiles`.
- **Vues** : `v_collect_set`, `v_recommendable`.

Supprimés par rapport à l'existant : `jb_catalogue_*`, `fd_*`, les copies par run (`jy_run_items`…), `jb_positions`, `jb_notes`, `jb_pf_backups`, `jb_settings`, `jb_app_settings` (fusionnée dans `settings`), barres 5 min et 1 h.

## 4. Stratégies : ce qu'il faut stocker

L'ancien moteur calcule, par période (`day`=1, `week`=5, `month`=21, `quarter`=63, `half`=126, `year`=252 séances **par défaut, réglables de 1 à 252**) : pente (`100·expm1(pente log)`), `slope_log`, R², rendement, volatilité, drawdown, efficiency ratio, accélération (cas particuliers jour/semaine), avec rupture de cours (`break_age`) et cours ajustés/bruts. Sept seuils par période. Quatre profils (`regular`, `fast`, `recovery`, `low_volatility`), niveaux de pente et de régularité, quatre modes de tri (`trend`, `performance`, `regularity`, `stability`), exposant `k`, poids par période, filtres techniques (prix > MA50, MA50 ascendante, variation journalière maximale, écart MA20 maximal).

Le schéma initial (colonnes fixes 5 j / 21 j) ne pouvait **pas** les reproduire. Corrigé :

- `strategy_metrics(listing_id, sessions, slope, slope_log, r2, perf, volatility, drawdown, er, acceleration)` : une ligne par fenêtre. La nuit, le moteur calcule les fenêtres 1, 5, 21, 63, 126, 252 **plus** toutes les fenêtres demandées par une configuration enregistrée. Une fenêtre inédite demandée par l'Explorer est calculée à la volée depuis `daily_prices` (400 séances × 5 510 titres : < 2 s avec numpy).
- `series_state` : MA20, MA50, MA50 précédente, variation journalière, écart MA20, `break_age`, dates de rupture, qualité (`ok`, `insufficient`, `inconsistent_adjustments`, `stale`, `break`).
- Le **statut** (retenu / exclu / non évaluable) et le **rang** ne sont jamais stockés : ils dépendent de la configuration et sont calculés à la demande. Percentiles par groupe `equity` / `etf` séparés (règle R5 conservée).

## 5. Arborescence

```
db/schema.sql            schéma unique
engine/                  Python : catalogue/ market/ analytics/ jobs/ shared/ cli.py
app/                     PHP : public/ (HTML, assets/) routes/ services/ lib/
tests/                   fast/ (sans base) integ/ (MariaDB jetable) fixtures/
scripts/                 local_db.sh, volumetry_test.sql, outils de migration
docs/                    ARCHITECTURE.md, FONCTIONNALITES.md
reference/               extraits de l'ancien code consultés pour la parité (non exécutés en production)
```

Un seul cron : `engine tick` (15 min) décide seul d'ouvrir une collecte intraday, des clôtures, la maintenance de nuit (`nightly` : métriques, rétention) ou le catalogue (`catalogue`, hebdomadaire).

## 6. Reprise de l'ancien code : critères

Reprise seulement par **réécriture propre**, sans l'architecture ni les dépendances d'origine, quand l'algorithme est pertinent et couvert par des tests :
`market_rules.py` (calendriers), `cadence.py` (cadence adaptative), `gaps.py` (trous), `parse_spark`, normalisation des barres (passée de 5 à 15 min), formules de `metrics()`, `window_values`, ruptures de cours, validation de configuration. Tout le reste (`scan.py`, `server.py`, snapshot JSON 107 Mo, catalogue PHP, pilotage par run) est abandonné. Chaque reprise est vérifiée par un test de parité (§7).

## 7. Tests

- `make fast` : pytest sans base ni réseau (séries réelles figées, Yahoo rejoué).
- `make integ` : MariaDB jetable (port 33307, base `jigobourso_v2`), jamais la production.
- Parité : pour chaque profil × période × mode de tri, statuts et rangs du nouveau moteur égaux à ceux de l'ancien sur le jeu de référence (P0).
- Parcours de bout en bout : connexion → Explorer → fiche → achat dans un portefeuille → bilan → administration.

## 8. Volumes (voir `docs/VOLUMETRIE.md`, rempli après mesure)

Estimation avant mesure : `daily_prices` ≈ 60–110 Mo, `intraday_prices` 15 min × 20 séances ≈ 150–250 Mo, reste < 60 Mo. Objectif < 450 Mo contre 2 320 Mo aujourd'hui.

## 9. Plan

P0 jeu de référence + base jetable + volumétrie ; P1 schéma ; P2 catalogue (Python) ; P3 prix et collecte 15 min ; P4 moteur d'analyse + parité ; P5 API PHP ; P6 pages (Explorer, fiches, portefeuilles, bilan) ; P7 administration ; P8 migration des données et bascule contrôlée (hors périmètre sans accord).

## 10. Cap produit : assistant à la décision (hors périmètre V2, prévu dans la conception)

Vision : à terme, aider à identifier des opportunités d'achat et à décider de conserver, renforcer, alléger ou vendre une position. Recommandations toujours **explicables**, fondées sur des données fiables, accompagnées d'une **évaluation du risque**, sans promesse de performance. Priorité V2 inchangée : recherche, analyse, stratégies, classements, portefeuilles.

Points d'accroche prévus dès la V2, pour ne pas reconstruire une troisième fois :
1. **Verdicts structurés.** Toute évaluation (retenu / exclu / non évaluable) renvoie une liste de raisons structurées : critère, valeur mesurée, seuil, résultat, période. Le texte affiché est généré à partir d'elles. Les futures recommandations réutilisent ce format.
2. **Séparation en couches** dans `engine/analytics/` : mesures (pures) → critères → stratégie/classement. Un module `engine/advisor/` pourra s'ajouter au-dessus sans modifier les couches du dessous.
3. **Positions calculées depuis le registre.** Le portefeuille expose par ligne : quantité, prix de revient moyen, durée de détention, poids dans le portefeuille, plus-value latente. Ces données sont le contexte indispensable à une décision de vente ou de renfort.
4. **Qualité des données portée par la donnée.** `series_state.quality` et la fraîcheur des cours sont lues par toute décision : pas de recommandation sur une série douteuse ou périmée.
5. **Risque comme mesure de premier rang** (volatilité, repli maximal, liquidité), calculé et stocké au même titre que la tendance.
6. **Historique des évaluations.** Table additive prévue (`recommendations` : cotation, portefeuille éventuel, date, action, risque, raisons JSON, version des règles) ; elle sera créée avec la fonctionnalité. Elle permet d'auditer et de rejouer une décision passée. Ajout pur, aucune table existante à modifier.
7. **Règles versionnées.** Chaque configuration de stratégie et chaque jeu de règles porte un numéro de version, enregistré avec les résultats.
8. **Aucun conseil personnalisé implicite.** Les formulations produit resteront descriptives (« critères remplis », « risque élevé »), jamais de promesse de rendement.

## Administration : construire le catalogue à la main, le cron l'entretient

Parcours, dans l'ordre, tout est manuel dans l'administration :
**FinanceDatabase → filtres FinanceDatabase → Yahoo Finance → filtres Yahoo → CATALOGUE FINAL → « Importer / mettre à jour les historiques »**.

| Étape | Traitement (`engine/jobs/tasks.py`) | Effet |
|---|---|---|
| Import FinanceDatabase | `fdb_import` | télécharge, stocke les lignes brutes (`catalogue_raw`), ne filtre ni ne supprime rien |
| Filtres FinanceDatabase | `fdb_filter` | applique les règles aux données brutes (sans télécharger), crée/met à jour les cotations |
| Import informations Yahoo | `yahoo_info` | cours, devise, volume moyen des titres issus du filtrage (pas d'historique) |
| Filtres Yahoo | `yahoo_filter` | prix, liquidité, volume sur les informations stockées : le résultat est le catalogue final |
| Historiques | `history` | clôtures manquantes (400 séances) + barres 15 min des deux dernières séances + indicateurs |

- **Règles** : `engine/catalogue/rules.py` (FinanceDatabase) et `engine/market/prefilter.py` (Yahoo) ; valeurs par défaut conservées, tout est modifiable. Les **places de cotation sont libres** : toute place présente dans les données importées est proposable (aucune liste codée en dur ne limite le choix). Une place sans horaires connus (`hours.known`) n'a que les clôtures quotidiennes.
- **Cron** (`tick`) : uniquement `daily:<place>`, `intraday:<place>` puis `maintenance` (cours, indicateurs, suivi, trous, rétention) sur le catalogue final + titres détenus. Il n'importe jamais FinanceDatabase, ne filtre jamais, ne modifie jamais le catalogue. Seul un passage déclenché par le cron compte comme « observé » (`schedule.beat`).
- **Pas de retéléchargement inutile** : `collect.daily_plan` choisit la plus petite fenêtre Yahoo par titre (rien si la dernière clôture publiée est en base) ; `collect.intraday_plan` ne demande que les barres manquantes des deux dernières séances. Un jour n'est « férié » que sans barre ET sans clôture quotidienne après une collecte quotidienne passée (`collect.is_holiday`) : une absence de données Yahoo est rattrapée, pas ignorée. `collect.session_gaps` détecte les vrais trous 15 min par créneau (part des titres de la place comparée au niveau habituel du même créneau), pas par nombre de barres par titre : un titre peu échangé n'a pas de trou.
- **Filtre Yahoo « dernier cours trop ancien »** (`prefilter.py`, règle `stale`, 10 jours par défaut, activable et modifiable) : écarte les titres morts dont le cours figé passait prix et liquidité. Appliqué seulement quand l'administrateur relance « Filtrer » ; la page Yahoo signale « modifié, pas encore appliqué » après l'ajout de la règle.
- **Entonnoirs** (`engine/analytics/funnel.py`) : avant / écartés / conservés à chaque étape, titres consultables, « pourquoi ce titre a disparu » ; figés dans `funnel_steps`.
- **Page Actions / ETF** (`adminsvc.titles`) : tous les titres connus avec statut FinanceDatabase, statut Yahoo, présence dans le catalogue, motif exact, état des historiques.
- **Tables ajoutées** (fin de `db/schema.sql`, additives) : `catalogue_raw`, `funnel_steps`, `job_steps`.
- **Tests** : `make fast`, `make integ` (dont `test_catalogue_flow.py`, parcours complet avec faux Yahoo), e2e navigateur `tests/e2e/smoke.mjs` (général) et `tests/e2e/admin.mjs` (administration).
