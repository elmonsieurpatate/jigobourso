# Architecture Python (engine/)

Dépendances orientées du haut vers le bas, contrôlées par `tests/fast/test_python_dependencies.py` (aucun cycle d'import, imports différés compris).

| Couche | Modules | Règle |
|---|---|---|
| Entrée | `cli.py` | une commande = un appel de cas d'usage ; aucune logique métier |
| Cas d'usage / administration | `analytics/admin/` (`service`, `title_sheet`, `scores_admin`, `scores_ranking`, `adminsvc`, `strategy_docs`) | orchestrent calculs, base et présentation ; seuls à dépendre de l'administration |
| Tâches planifiées | `jobs/` (`tasks`, `runner`, `schedule`) | appellent collecte et calcul ; rien ne dépend de `jobs` |
| Calculs et services d'analyse | `analytics/series`, `analytics/scoring`, `analytics/explorer`, `analytics/market_views`, `analytics/portfolio` | ne dépendent jamais de `analytics/admin` |
| Fournisseurs et marchés | `market/` (`yahoo`, `collect`, `intraday`, `catchup`, `splits`, `etf_profile`, `hours`, `calendar`) | ne dépendent pas des analyses (une exception documentée : `splits` → `series.series`, même ajustement de série) |
| Socle | `shared/` (`db`, `settings`, `units`), `catalogue/` | aucune dépendance vers analyses ni tâches |

Calculs purs (testés sans base ni réseau) : `series.series`, `series.measures`, `scoring.scores`, `scoring.criteria`, `scoring.configurable_score`, `explorer.explorer_config`, `explorer.strategy`, `shared.units` : le test interdit d'y importer la base, Yahoo, un client réseau ou l'administration.

## Cycles résolus à l'étape 8

| Cycle | Résolution |
|---|---|
| scoring ↔ administration (spécifications, profils) | `scores_specs`, `scores_profiles` déplacés dans `scoring/` ; `apply_admin` rejoint les profils (au-dessus de `score_service`) |
| scoring ↔ administration (cache) | sérialisation des résultats dans `scoring/score_cache.py` |
| verdicts d'univers dans l'administration | `universe_verdicts` déplacé dans `explorer/` (utilisé par portefeuille, suivi, scoring) |
| classement des scores ↔ administration | briques communes (`ordered`, `closes`, `series`, `dated_series`) dans `scoring/ranking_support.py` |
| fournisseur ETF ↔ présentation | `market/etf_profile` ne fait que lire et extraire ; normalisation et région dans `market_views/etf.py` |
| collecte ↔ intraday | `slot_of` défini dans `market/hours` |
| planification ↔ rattrapage | `record_cron_error` dans `shared/settings` |
| configuration V4 ↔ stratégie V3 ↔ score configurable | conversion V3→V4 (`upgrade`, `editable`) dans `explorer/legacy_upgrade.py`, au-dessus de `strategy` et `explorer_config` |
| analyses de portefeuille → administration | `downsample` dans `analytics/shared/numbers.py` |

Les anciens chemins et réexports ne sont pas conservés : les appelants (CLI, tâches, scripts, tests, `ops/deploy.sh`) importent les nouveaux emplacements.

## Règles communes

Les règles d'unités de prix sont uniques (`shared/units.py`, miroir PHP testé). Les règles de quantité et de split ont un équivalent PHP (`app/services/ledger.php`) dont la parité des données est contrôlée par le contrôle de release (voir `docs/APPLICATION.md`, § 9).

## Contrôles

`make lint` (ruff, cible Python 3.9 comme la CI), `tests/fast/test_python_dependencies.py`, suites `make fast` / `make integ`. Plafond de longueur des fonctions : 190 lignes après formatage (les plus longues : `explorer/strategy.rank`, `series/history.build`, `market_views/etf.build`, 99–101 lignes ; `history.build` et `admin/service.explore` ont été découpés en `_split_adjusted_series`, `_append_live_quotes`, `_value_day`, `_ordered`, `_etf_page_context`, `_facets`).
