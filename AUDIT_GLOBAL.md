# AUDIT GLOBAL : plan directeur de nettoyage et de professionnalisation

Date : 2026-11-12 · Branche d'origine : `chore/frontend-cleanup-20261112` (fusionnée dans `main`)
**Avancement (13/11/2026)** : étapes 0 à 9 faites. Seules restent deux cases qui dépendent de la tâche cron hPanel de production (action manuelle) : retrait de `?k=` (étape 1.1) et alias `yahoo-history-cron` (étape 3.1).
Audit en lecture seule, aucun code modifié. Sources : 3 sous-agents (Backend/DB, Moteur/scripts, Frontend).

**Limites de l'audit** : les 37 modules `engine/analytics/` n'ont pas été lus en entier (doublons et N+1 à confirmer). `app/services/*` et `tests/` non lus par l'agent Backend. Les `innerHTML` du frontend restent à auditer. Aucun constat critique n'a été relevé nulle part : pas d'injection SQL avérée, pas de secret dans le code.

Légende : 🔴 haute · 🟠 moyenne · 🟢 basse

---

## Étape 0 : Filet de sécurité (avant tout refactor)

- [x] Ajouter un linter Python (`ruff` ou `pyflakes`) au Makefile (aucun n'est installé) et un `php -l` / analyse statique PHP
- [x] Ajouter des tests pour `engine/jobs/runner.py` (stale, verrou concurrent, démarrage en double)
- [x] Ajouter un test d'injection sur `funnel.items`
- [x] Ajouter un test de cohérence `db/schema.sql` ↔ `db/migrations/`
- [x] Vérifier que la suite `tests/fast` passe avant de commencer (baseline)

Réalisé : `ruff.toml` + `make lint` (ruff + `php8.3 -l`, serveur en PHP 8.2), `make check`, `tests/integ/test_job_runner.py`, `tests/integ/test_funnel_injection.py`, `tests/fast/test_schema_migrations.py`. Baseline : `tests/fast` 660 verts (6 tests périmés corrigés), `make integ` 332 verts (php8.3 et venv forcés dans le PATH).
À suivre : la branche `quality` de `funnel.items` est du code mort (F401/F841 de ruff réactivés à l’Étape 3.2).

## Étape 1 : Sécurité et robustesse des fondations 🔴

### 1.1 Backend PHP
- [x] `lib/http.php:44-50` `need_post` : refuser si `Origin` et `Referer` sont absents ; exiger `Content-Type: application/json` dans `body()` (🟠)
- [x] `lib/auth.php:9` `client_ip()` : définir une liste de proxys de confiance ; documenter la confiance accordée à `X-Forwarded-Proto` (🟠)
- [ ] `routes/cron.php:19-22` : retirer la clé via `?k=` (fuite dans les logs d'accès) au profit de l'en-tête, après migration du cron (🟠)
- [x] `routes/admin.php` `admin/system` : masquer ou hacher le code d'invitation renvoyé (🟠)
- [x] `lib/account.php:26,93,100` et `lib/mail.php` : externaliser le domaine codé en dur vers `JIGO_BASE_URL` (🟠)

### 1.2 Moteur Python
- [x] `engine/analytics/explorer/funnel.py:161-170` : remplacer l'interpolation par `.replace()` par une table de colonnes par stage ; passer `LIMIT/OFFSET` en paramètres (🔴)
- [x] Whitelister (assertion explicite) les identifiants SQL dynamiques : `scripts/verify_momentum_release.py:37`, `engine/migration/legacy.py:115`, `engine/analytics/explorer/funnel.py:65` (🔴)
- [x] `engine/jobs/runner.py` : ajouter un heartbeat (`updated_at`) rafraîchi par `progress`/`step`, calculer le stale sur le dernier battement (un job > seuil, ex. `catchup` > 8 min, peut être doublé) (🔴)
- [x] Vérifier le fuseau de `jobs.started_at` vs `utcnow()` ; remplacer `datetime.utcnow()` (déprécié 3.12) (🟠)
- [x] Logs de jobs tronqués à 400 car. (trace à 380) : passer en colonne TEXT ou ajouter un log fichier (🟠)
- [x] Vérifier la fermeture des connexions DB (`connect()` sans `finally conn.close()` visible, `cli.py:119`) ; revoir `read_timeout=900` (🟠)

### 1.3 Base de données
- [x] Ajouter les FK `user_id` sur `alert_rules` (`schema.sql:545`) et `alert_events` (🟠)
- [x] Vérifier qu'une tâche purge `login_attempts`, `account_attempts`, `sessions` expirées (🟠)
- [x] Contrôler par `EXPLAIN` le JOIN `alert_events` sur `rule_id` (`routes/alerts.php:147`) (🟢)

Réalisé : `need_post` exige Origin ou Referer, `body()` exige `application/json` (415) ; `client_ip()`/`https()` ne croient `X-Forwarded-*` que d'un proxy listé dans `JIGO_TRUSTED_PROXIES` ; code d'invitation masqué ; `base_url()` (`JIGO_BASE_URL`, défaut = production) ; `funnel.items` : table de colonnes par stage + `LIMIT/OFFSET` liés, listes blanches explicites ; heartbeat `jobs.updated_at` (stale sur le dernier battement) et `job_logs.detail` TEXT (migrations `20261112_*`) ; `utcnow()` remplacé (reste `etf.py`, dont un test fige l'horloge) ; connexions de `cli.py` toutes fermées ; FK `user_id` sur `alert_rules`/`alert_events` ; purge déjà assurée par `tasks.housekeeping` (test ajouté) ; `EXPLAIN` du JOIN : index `idx_event_user` + `PRIMARY`.
**Reste ouvert** : retrait de `?k=` du cron. Le code accepte déjà `JIGO_CRON_QUERY_KEY=0` pour le refuser, mais la tâche hPanel de production l'utilise encore : migrer vers `X-Cron-Key`, puis activer ce réglage (et changer la clé).
**À l'application en production** : la migration `alert_user_fk` échoue sans rien modifier s'il existe des lignes orphelines ; `read_timeout=900` conservé (requêtes longues volontaires).

## Étape 2 : Architecture backend : terminer le refactor routes → services 🔴

- [x] Déplacer vers `services/` les helpers restés dans les routes :
  - [x] `routes/portfolios.php:9` `tx_fields` → `services/transactions.php`
  - [x] `routes/alerts.php:18-106` (10 helpers `alert_*`) → `services/alerts.php`
  - [x] `routes/tracking.php:18-23` `track_custom_names`, `track_label`
  - [x] `routes/admin.php:3,19` `log_tail`, `system_counts`
  - [x] `routes/cron.php:9-36` `cron_reject`, `cron_presented_key`, `cron_tick`
  - [x] `routes/ct_strategies.php:4` `my_ranking_request` (puis fusionné dans `services/scores.php`)
  - [x] `routes/auth.php:92` `setting_value` → `lib/` ou `services/`
- [x] Ajouter les `require_once` explicites manquants (`lib/mail.php`, `db.php`, `http.php`, `own_portfolio`, `str_in`, `q`) : aujourd'hui dépendance à l'ordre de chargement de `public/api.php`
- [x] Fusionner `admin/scores/ranking` et `my_ranking_request` en un service unique (`user_id` optionnel) ; idem `admin/scores/simulate` / `my/scores/simulate`
- [x] Introduire un helper `tx(callable)` pour remplacer les `beginTransaction/try/rollBack` manuels (`login`, `auth/password`, `portfolios.php:155`)
- [x] Unifier la validation du mot de passe (`admin/user/create` via `str_in` vs `valid_password`) avec `password_input`

## Étape 3 : Élimination du legacy et du code mort

### 3.1 Backend / DB
- [x] Migrer les données `saved_searches` / `saved_presets` vers `explorer_saved`, puis supprimer `routes/explore.php:109-146`, `services/explorer_library.php` (couche legacy) et les deux anciennes tables
- [x] Supprimer `alerts_mail_pending`, `ALERTS_EXECUTION_ENABLED`, `ALERT_LABELS` (si inutilisée ailleurs) dans `routes/alerts.php`
- [x] Supprimer `secondary_setting` (`services/secondary_filters.php:87`)
- [ ] Supprimer l'alias cron legacy `yahoo-history-cron`
- [x] Aligner le style de `schema.sql` (`CREATE TABLE IF NOT EXISTS` mixte) et le rendre cohérent avec `db/migrations/`

### 3.2 Moteur / scripts
- [x] Supprimer les imports inutilisés : `clean_window, find_breaks, usable_closes, window_metrics, technical_state` (`service.py`, `compute.py`, `strategy.py`, `tracking.py`) après vérification qu'aucun appelant ne fait `service.clean_window` ; `cli.py` (`run_job`), `market/intraday.py` (`json`), `watch.py` (`math`), `scripts/explain_current_ranking.py` (`importlib`, `math`, `sys`)
- [x] Uniformiser l'import `__import__('engine.analytics.explorer.strategy_docs', ...)` dans `cli.py:54`
- [x] Archiver les scripts de migration V1→V2 une fois la migration confirmée : `migrate_legacy.py`, `export_user_data.py`, `drop_legacy_tables.sh`, `bootstrap_real.py`, `engine/migration/legacy.py` → supprimés (tag `archive/v1-migration`) ; `drop_legacy_tables.sh` retiré après nettoyage de la base le 12/11/2026 (V1, `codex_*`, `saved_*`, `jb_*` supprimées : 1 536 → 477 Mo) ; `bootstrap_real.py` conservé (`make dev-db`)
- [x] Regrouper `verify_{etf,financial,momentum}_release.py`, `prepare_financial_release.py` et les `verify_*`/`check_*` PHP dans `scripts/release/` avec un point d'entrée Makefile (`make release-check`)
- [x] `scripts/test_secondary_filters.sh` : migrer vers `tests/e2e` ou supprimer s'il double `tests/e2e/secondary-*`
- [x] Déplacer ou documenter les `.php` de `scripts/` (`create_user`, `check_*`, `verify_*`) → `ops/`

### 3.3 Frontend
- [x] Supprimer `assets/multiselect.js` (orphelin) ou le brancher s'il est prévu
- [x] Remplacer `alertes.html` et `classement-test.html` (meta refresh) par des redirections 301 `.htaccess`, puis supprimer les pages

Réalisé : routes `searches`, `search/*`, `presets/*`, `explorer/library/legacy`, `explorer_legacy_action` et tables `saved_*` retirées du code et de `schema.sql` (aucune référence active, `git grep`) ; copie des données par `scripts/oneshot/migrate_saved_to_explorer.py` (testé, idempotent) ; sauvegarde quotidienne : `saved_searches` remplacée par `explorer_saved` ; `alerts_mail_pending`, `ALERTS_EXECUTION_ENABLED`, `secondary_setting` supprimés (`ALERT_LABELS` conservée : 3 usages dans `routes/alerts.php`) ; `schema.sql` tout en `CREATE TABLE IF NOT EXISTS` ; F401/F841 nettoyés et réactivés dans `ruff.toml` ; `scripts/README.md` ; `alertes.html`/`classement-test.html` → 301, `multiselect.js` supprimé (le contrôle de déploiement vise désormais `mes-filtres.html`).
**Reste ouvert** : (1) alias cron `yahoo-history-cron` : la tâche hPanel de production l'appelle encore (même chantier que `?k=` de l'Étape 1.1), à retirer après migration vers `api/cron` ; (2) regroupement des `verify_*`/`prepare_*` dans `scripts/release/` : `ops/deploy.sh` et `test_deploy_modes.py` les appellent par chemin, à faire avec le déploiement.
**Déployé le 12/11/2026** (commit `209c06a`). `migrate_saved_to_explorer.py` lancé après le déploiement (le script n'arrive sur le serveur qu'avec lui) : 0 ligne à copier, les deux anciennes tables étaient vides en production. Base de production nettoyée le même jour : 41 tables obsolètes supprimées (34 `codex_*`, 4 `saved_searches`, `saved_presets`, `saved_strategies`), sauvegarde des 37 petites sur le serveur (`~/backup-tables-obsoletes-20261112.sql.gz`). Test navigateur `strategies-ui.cjs` corrigé (menu admin « Splits ») ; les déploiements en `[deploy quick]` ne lancent pas les tests navigateur. Restes de CSS `.ms-*` (app.css) sans usage : à retirer à l'Étape 6.

## Étape 4 : Découpage du moteur `engine/analytics/` (37 fichiers → 7 sous-paquets)

Réalisé le 12/11/2026 : 35 modules déplacés en 6 sous-paquets (`git mv`, historique conservé), imports internes et externes réécrits, **sans shims** (le dossier `series/` et `portfolio/` reprennent le nom des anciens modules, déplacés dans `series/series.py` et `portfolio/portfolio.py`). Fonctions mortes supprimées : `applies`, `session_slope`, `default_selection`. `ops/deploy.sh` mis à jour (chemins exclus du hash du moteur : `service`, `universe_verdicts`, `title_sheet`, `market_facts`, `signals`). Chemins relatifs aux fichiers de config corrigés (`ranking_table`, `scores_admin`).
**À l'application en production** : tous les fichiers du moteur ayant changé de chemin, le hash du moteur change, et le déploiement le traite comme un changement du moteur et lance en arrière-plan le traitement `maintenance` (recalcul des données dérivées ; attendu, sans effet visible).

- [x] Créer `series/` : series, compute, history, history_refresh, measures, liquidity, signals
- [x] Créer `scoring/` : scores, score_service, score_inputs, score_categories, configurable_score, criteria, ranking_table
- [x] Créer `explorer/` : explorer_config, explorer_metrics, strategy, strategy_docs, funnel
- [x] Créer `portfolio/` : portfolio, allocation, performance, position_plan, tracking, watch, alerts, risk
- [x] Créer `market_views/` : etf, geography, overview, repository, session
- [x] Créer `admin/` : `adminsvc`, `service`, `scores_admin` déplacés
- [x] Découper `admin/service.py` (1079 lignes) et `admin/scores_admin.py` (986 lignes) : `service.py` → `service` (Explorer), `universe_verdicts` (jugement et cache), `title_sheet` (fiche d'un titre), `market_views/market_facts` (PEA, dernière collecte, capitalisations, analystes) ; `scores_admin.py` → `scores_specs` (catalogue des stratégies), `scores_profiles` (profils et configuration), `scores_ranking` (classement, simulation, courbes), `scores_admin` (état, comparaison, enregistrement, couverture). Découpe par cohésion plutôt que par lecture/écriture strictes (les écritures `save`/`user_save`/cache restent à côté des lectures qu'elles prolongent) ; aucun cycle d'imports
- [x] Créer `shared/` : `shared/numbers.finite`, `shared/text.fr`, `shared/dates.iso` remplacent 4 `_num`/`number`, 4 `fr`/`_fr` et 3 `_iso` équivalents ; les `_num`/`_number` de sémantique différente (arrondi, bornes, booléens, infinis) restent locaux
- [x] Factoriser le chargement prix/splits (`alerts.py:96-104`, `position_plan.py:310-314`, `compute.py:~48`) → `series/loader.load_bars_and_splits(conn, ids)` : `series/loader.py` (`load_bars`, `load_splits`, `load_bars_and_splits`) utilisé par `alerts`, `position_plan` et `compute` ; `history._load`, `service`, `scores_admin` gardent leur requête (autre forme : volumes, devises, fenêtres)
- [x] Corriger le N+1 `adminsvc.py:184-185` (un `COUNT(*)` par `lid`) → un seul `GROUP BY listing_id` : `_intraday_statuses` (2 requêtes `GROUP BY` par place au lieu de 2 `COUNT` par ligne)
- [x] Confirmer par une lecture plus profonde les doublons/N+1 des modules non lus : balayage automatique des `execute` dans une boucle ; les restes sont soit par lots (`compute`, `explorer_metrics`, `etf`, `_closes`), soit de taille constante (`funnel`) ; à surveiller : `tracking.update_outcomes` (une écriture par ligne, tâche de nuit) et `watch.run_all` (moteur désactivé)
- [x] Retirer les shims, mettre à jour `cli.py`, routes PHP et tests : aucun shim n'a subsisté, tous les imports (`cli.py`, `tasks.py`, scripts, tests, `ops/deploy.sh`) pointent vers les nouveaux chemins

## Étape 5 : Cache-busting et déploiement frontend 🔴

- [x] Une seule version globale (`BUILD_ID` ou hash de contenu) injectée dans tous les HTML par un script de build/déploiement ; aujourd'hui `app.js` a 6 versions de `?v=` différentes, idem `table-layout.js`, `strategies-ui.js` : 121 références réparties sur 19 pages, 20 versions différentes (`?v=202611060053`, `-nav1`, `-clean1`, `-personal`…) ramenées au seul marqueur `?v=__BUILD__`, remplacé par `ops/deploy.sh` (l'ancien `sed` ne traitait que les versions purement numériques et laissait les suffixes) ; test `tests/fast/test_asset_versions.py`
- [x] `.htaccess` : ajouter `Cache-Control: immutable` pour les assets versionnés ; `Expires` pour images, SVG, JSON : `immutable` (un an) pour tout CSS/JS portant `?v=`, `no-cache` pour les pages HTML, `Expires` d'un mois pour images, SVG, polices ; pas de règle sur le JSON (les réponses de l'API sont du JSON dynamique, aucun fichier JSON statique n'est servi)
- [x] Revoir `ExpiresByType … "access plus 1 hour"` (`.htaccess:16-18`) une fois la version unifiée : règles CSS/JS d'une heure supprimées, remplacées par `immutable` sur les ressources versionnées

Réalisé le 12/11/2026. Chargement vérifié sur une copie servie par PHP après substitution : 19 pages, 121 fichiers en 200, une seule version. **À vérifier après déploiement** (les en-têtes Apache ne se testent pas en local) : `curl -sI 'https://jigobourso.turnjoy.dev/assets/app.js?v=<version>'` doit afficher `Cache-Control: public, max-age=31536000, immutable` ; `curl -sI https://jigobourso.turnjoy.dev/index.html` doit afficher `Cache-Control: no-cache`.

## Étape 6 : Design system CSS 🟠

### 6.1 Tokens et thème
- [x] Fusionner les deux `:root` d'`app.css` (l.2/10 et 183-184)
- [x] Créer des tokens sémantiques dans `assets/tokens.css` : `--info`, `--danger`, `--warn`, `--ok`, `--caution` + variantes `-soft` / `-ink`, avec valeurs sombres (+ `--on-solid`, `--ring`, `--sp-*`, `--radius-*`, `--shadow-pop`, `--chart-*`)
- [x] Refactorer `plan-suivi.css`, `explorer.css` (ex `classement-test.css`), `filtres.css` (ex `admin-categories-test.css`), `help.css` pour n'utiliser que `var()` : plus aucune couleur en dur hors `tokens.css` dans les 10 feuilles. Les violets propres à `.ct`/`.ac` sont remplacés par l'accent commun.

### 6.2 Structure
- [x] Scinder `app.css` (87 Ko) en `tokens.css`, `base.css` (46 Ko après suppression de 446 règles mortes dont `.px-alert` et `.lot-alerts`), `components.css`. Les styles propres à la page Portefeuilles sont dans `pf.css`.
- [x] Fixer l'ordre de chargement : `theme-init.js` → tokens → base → composants → page, identique sur les 19 pages
- [x] Supprimer les `!important` et `all:unset` : `all:unset` 0 ; `!important` 52 → 1 (le reset global `[hidden]`, légitime), les conflits sont résolus par la spécificité
- [x] Dédoublonner `.card` et `th` (une seule définition dans `components.css`)
- [x] Règles CSS à déclarations identiques fusionnées (41 groupes : un jeu de déclarations, plusieurs sélecteurs) ; détecteur : aucun groupe restant de ≥3 déclarations

### 6.3 Composants dupliqués (≈ 15 variantes → ≈ 6 composants)
- [x] Bouton : `.btn` + `.primary/.danger/.ghost/.sm/.icon` ; surcharges de taille retirées partout, `.icon-btn`, `.px-btn`, `.ac-icon-button`, `.ac-order-buttons button`, `.ct-segment button` migrés. `.ct-slider-row button` et `.ct-fold` migrés aussi. Seul `.sui-pick-btn` (sélecteur de stratégie à menu déroulant, pas un bouton d'action) garde sa mise en page propre.
- [x] Carte / panneau : `.card` + `.flush/.tight/.flat/.inset` ; `.ct-panel`, `.ac-panel`, `.ac-information`, `.ct-preview` n'ont plus que leur mise en page ; `.sui-card` supprimé (mort). `.kpi-strip .card` garde sa bordure d'accent.
- [x] Tableau : `table`, `.dense`, `.table-wrap` + `.tall/.boxed` ; `.table-scroll`, `.ac-table-wrap`, `.ct-table-wrap`, `.as-rktable` ramenés dessus. `table.cmp` reste en variante dans `base.css`.
- [x] Pastille / badge : `.badge` + `.ok/.warn/.danger/.info/.accent/.outline/.sm` ; `.tag`, `.chip`, `.chip-s`, `.pill-ok`, `.ac-status`, `.ac-count`, `.ac-demo-badge`, `.ac-subtle-badge`, `.ct-tag`, `.ct-and` migrés (balisage et CSS). `.ps-chip`, `.px-chip`, `.sui-badge` migrés. Seul `.ac-category-chip` garde une règle (couleur de catégorie dynamique, une seule définition).
- [x] Toast : un seul `.toast` (`J.toast`, `#ct-feedback`, `#ac-feedback`, `role=status`)
- [x] Onglets / segments : `.tabs` (`.ac-mode-tabs`, `.ct-builder-tabs`) et `.seg` (`.ct-segment`, `.pills`). `.ac-tab` (mort) supprimé.

### 6.4 Renommage des prototypes
- [x] Renommer les fichiers `-test` / `-demo` : `explorer.{css,js}`, `explorer-filters.js`, `filtres.{css,js}`, `filtres-catalogue.js`, `admin-filtres.html` (redirection 301 de l'ancienne URL). Les routes API `classement-test/*` ne sont pas renommées (backend).
- [x] Factoriser le reset redéclaré sous `.ct` / `.ac` : remonté dans `base.css` (contrôles de formulaire, focus), `.eyebrow` et `h1` communs, modale `<dialog>` dans `components.css`

**Fait en plus (hors liste) :** `theme-init.js` (le thème sombre s'applique enfin sur les pages de connexion, sans flash), mise en page centrée des pages de connexion, 172 `style="margin…"` du JS remplacés par des utilitaires `.mt-*`/`.mb-*` (reste ≈ 130 pour l'étape 8), `docs/DESIGN.md`. Total CSS 223 Ko → 175 Ko.

## Étape 7 : Noyau JS commun 🟠

- [x] Remplacer les copies locales de `$` par `J.$` : `explorer.js`, `filtres.js`, `splits.js`, `register.js`, `admin-scores.js`, `aide.js` (+ `$$`)
- [x] Supprimer les redéfinitions de `esc` (`help-charts.js`, `plan-suivi.js`, `pf-home.js`, et les enveloppes `E` de `admin-columns.js`, `admin-scores.js`, `strategies-ui.js`) au profit de `J.esc`
- [x] Remplacer les formateurs locaux par `J.num` / `J.pct` / `J.eur` : `fmt`, `eur`, `percent`, `num0`, `score1` de `explorer.js` ; `fmt` d'`admin-scores.js` ; `nf` d'`admin.js` ; `num` de `splits.js` ; `eur`/`pc`/`sg`/`pt` de `pf-home.js` et `plan-suivi.js` ; `f1` de `help-charts.js`. Nouveaux : `J.int`, `J.isNum`, `J.numS`/`J.pctS`/`J.eurS` (vrai signe −), `J.dayShort`/`J.dayFull`. Non touchés, volontairement : `etf.js` `fmt` (textes de libellés, pas un formateur de nombre), `intraday.js` `fmt` (fuseaux horaires, `Intl.DateTimeFormat` spécifique), `financial-chart.js` `fmtTime` (déjà basé sur `J.date`), modules testés sans navigateur (`pf-math.js`, `admin-categories-model.js`, `explorer-filters.js`).
- [x] Ajouter `J.store` (get/set/remove/has/subscribe/scope/fn/text, repli mémoire si `localStorage` est indisponible) et `J.dom.h()` ; `secondary-filter-store.js` exposé en `J.store.filters`. Tous les accès à `localStorage` des scripts passent par `J.store` (exceptions : `core.js` et `theme-init.js`, exécuté avant le noyau).
- [x] Nouveau fichier `assets/core.js` (noyau : `$`, `esc`, API, formats, `store`, `dom`), chargé avant `app.js` (coque : navigation, graphiques SVG, dialogues, thème) sur les 19 pages. Tests : `tests/e2e/core-interactions.cjs` (22 vérifications navigateur : thème, menu, classement Simple/Expert, aide, filtres, 9 pages sans erreur JS, toast) et `tests/e2e/core.cjs` (formats, stockage, DOM). Garde-fou : `tests/fast/test_js_core.py` (test Node du noyau `tests/e2e/core.cjs` + interdiction de recréer des copies locales).
- [x] Tableaux : tous les en-têtes passent par `J.table.head` / `headRow` (admin, admin-scores, admin-columns, aide, bilan, donnees, etf, filtres, mes-strategies, pf-home, portefeuilles, suivi, titre). Les trois tableaux triables (explorateur, titres admin, positions du portefeuille, classement des scores) utilisent `button[data-sort]` + `aria-sort` + `J.table.sortRows` / `nextSort` / `onSort`. Les corps de tableau restent propres à chaque page (cellules métier) ; `table-layout.js` (largeurs de colonnes) reste un module à part
- [x] Composants : `seg`, `pills`, `badge` locaux, `J.statusBadge` et `J.insightBadge` passent par `J.seg` / `J.badge` ; `J.tabs` disponible
- [x] Dates et casse : `toLocale…` et `Intl.DateTimeFormat` supprimés des pages (`J.dayFull` / `dayShort` / `dayNumeric` / `dateTimeShort` / `tz` / `fold`). Restent hors noyau : `admin-categories-model.js` (module sans dépendance, volontairement autonome) et les chapitres `help-ch-*`
- [x] `J.dom.h` utilisé par `J.toast`, `J.dialog`, `J.formError`, `J.chartBox`
- [x] Appels API : `J.api` / `J.post` est déjà le seul `fetch` des scripts, rien à fusionner
- [x] Garde-fou `tests/fast/test_js_core.py` étendu (dates, composants, en-têtes) ; `tests/e2e/core.cjs` et `core-interactions.cjs` (tri compris)
- [x] Helpers de graphiques communs : `J.svg`, `J.ticks`, `J.priceDec`, `J.chartBox` dans `core.js` (copies supprimées de `charts.js` et `intraday.js`). `pf-math.js` (calcul de portefeuille) et `help-charts.js` (schémas pédagogiques) n'ont rien en commun avec les graphiques de cours
- [x] `filtres-catalogue.js` (2 848 lignes de données) découpé : un fichier `filtres-catalogue-<id>.js` par filtre (13) + `-indicators`, contenu strictement identique à l'original (vérifié) ; test `admin-categories-model.cjs` adapté
- [x] `explorer.js` (617 → 480 lignes) scindé en `explorer-model.js` (logique pure : profils, arbre de règles, sauvegarde locale, filtres, lignes, tri ; testé sous Node par `tests/e2e/explorer-model.cjs`) et `explorer-view.js` (gabarits HTML purs) ; `admin-scores.js` (547 → 338) scindé en `admin-scores-view.js` (gabarits et libellés, lisant l'état par des accesseurs). Vérifié par des instantanés DOM identiques avant/après sur la base locale réelle (24 pour l'explorateur : Expert, règles, filtres, tri, pages, colonnes, stratégie ; 49 pour les scores : admin et « Mes paramètres », configuration, profils, simulation, suivi). Bug trouvé au passage et corrigé : l'onglet Profils de « Mes paramètres de scores » plantait (`S.personal` absent).

## Étape 8 : CSP, styles inline et accessibilité ✅

- [x] Plus aucun attribut `style=` : les gabarits JS écrivent `data-style`, appliqué par l'API CSSOM (`core.js`, autorisée par la CSP). CSP sans aucun `unsafe-inline` (`style-src 'self'`) ; un test interdit tout `style=` en JS ou en HTML
- [x] `onclick=` / `onchange=` : aucun attribut inline (gestionnaires assignés en JS) ; un test interdit d'en ajouter
- [x] `innerHTML` audités : champs libres échappés via `J.esc` (`REVIEWED_FREE_TEXT`, test `test_free_text_fields_are_escaped_in_templates`) ; un oubli corrigé (`suivi.js`)
- [x] Focus visible rétabli (`help.css`, `admin-scores.css`)
- [x] `aria-label` sur les champs numériques sans libellé (`admin.js`) ; les autres champs sont dans des `<label>`
- [x] Texte 10 px porté à 11 px ; contraste de `--muted` vérifié AA dans les deux thèmes
- [x] `prefers-reduced-motion` et lien « Aller au contenu » (`app.js`, `base.css`)

## Étape 9 : Finitions ✅

- [x] Style PHP : plus aucune ligne > 250 caractères (coupes sur jetons, chaînes interpolées et commentaires vérifiés identiques)
- [x] Pagination `admin/catalogue` : page bornée, `LIMIT`/`OFFSET` liés en paramètres
- [x] `JSON_PARTIAL_OUTPUT_ON_ERROR` retiré : UTF-8 invalide substitué, autre erreur journalisée et signalée
- [x] `send_welcome_mail` envoyé après la réponse (`out_then`) ; l'API renvoie `welcome_mail: 'queued'`
- [x] Doublons `.card`/`th` fusionnés, CSS mort nettoyé
- [x] Tests rangés par technologie : `tests/php/`, `tests/seeds/`, `tests/e2e/` (Node seul, `.mjs` convertis en `.cjs`), point d'entrée `make e2e` ; voir `tests/e2e/README.md`
- [x] README court et docs d'architecture à jour
- [x] Suite complète rejouée : `make check`, `make integ`, `make e2e`, `make release-check`, CSP vérifiée en navigateur (0 violation) ; aucun shim restant

---

## Points positifs à préserver

Requêtes SQL préparées (`ATTR_EMULATE_PREPARES=false`) · sessions hachées SHA-256, cookie `HttpOnly`/`SameSite` · `own_portfolio` systématique · rate-limiting et anti-énumération · neutralisation des formules à l'export CSV · `proc_open` en tableau · secrets lus depuis `JIGO_DB_*` · `GET_LOCK` et groupe COMPUTE exclusif dans les jobs · sauvegardes `mysqldump` en 600/700 avec rotation · aucun `<script>`/`style=` inline dans les HTML · un seul `fetch` dans `app.js` · `lang="fr"` partout.
