# AUDIT GLOBAL : plan directeur de nettoyage et de professionnalisation

Date : 2026-11-12 · Branche d'origine : `chore/frontend-cleanup-20261112` (fusionnée dans `main`)
**Avancement (12/11/2026)** : étapes 0 à 3 faites et déployées en production, base nettoyée (1 536 → 477 Mo). Cases restantes : retrait de `?k=` du cron (étape 1) et alias cron `yahoo-history-cron`, regroupement des scripts de release (étape 3). Étapes 4 à 9 : à faire.
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
- [ ] Regrouper `verify_{etf,financial,momentum}_release.py`, `prepare_financial_release.py` et les `verify_*`/`check_*` PHP dans `scripts/release/` avec un point d'entrée Makefile
- [x] `scripts/test_secondary_filters.sh` : migrer vers `tests/e2e` ou supprimer s'il double `tests/e2e/secondary-*`
- [x] Déplacer ou documenter les `.php` de `scripts/` (`create_user`, `check_*`, `verify_*`) → `ops/`

### 3.3 Frontend
- [x] Supprimer `assets/multiselect.js` (orphelin) ou le brancher s'il est prévu
- [x] Remplacer `alertes.html` et `classement-test.html` (meta refresh) par des redirections 301 `.htaccess`, puis supprimer les pages

Réalisé : routes `searches`, `search/*`, `presets/*`, `explorer/library/legacy`, `explorer_legacy_action` et tables `saved_*` retirées du code et de `schema.sql` (aucune référence active, `git grep`) ; copie des données par `scripts/oneshot/migrate_saved_to_explorer.py` (testé, idempotent) ; sauvegarde quotidienne : `saved_searches` remplacée par `explorer_saved` ; `alerts_mail_pending`, `ALERTS_EXECUTION_ENABLED`, `secondary_setting` supprimés (`ALERT_LABELS` conservée : 3 usages dans `routes/alerts.php`) ; `schema.sql` tout en `CREATE TABLE IF NOT EXISTS` ; F401/F841 nettoyés et réactivés dans `ruff.toml` ; `scripts/README.md` ; `alertes.html`/`classement-test.html` → 301, `multiselect.js` supprimé (le contrôle de déploiement vise désormais `mes-filtres.html`).
**Reste ouvert** : (1) alias cron `yahoo-history-cron` : la tâche hPanel de production l'appelle encore (même chantier que `?k=` de l'Étape 1.1), à retirer après migration vers `api/cron` ; (2) regroupement des `verify_*`/`prepare_*` dans `scripts/release/` : `ops/deploy.sh` et `test_deploy_modes.py` les appellent par chemin, à faire avec le déploiement.
**Déployé le 12/11/2026** (commit `209c06a`). `migrate_saved_to_explorer.py` lancé après le déploiement (le script n'arrive sur le serveur qu'avec lui) : 0 ligne à copier, les deux anciennes tables étaient vides en production. Base de production nettoyée le même jour : 41 tables obsolètes supprimées (34 `codex_*`, 4 `saved_searches`, `saved_presets`, `saved_strategies`), sauvegarde des 37 petites sur le serveur (`~/backup-tables-obsoletes-20261112.sql.gz`). Test navigateur `strategies-ui.cjs` corrigé (menu admin « Splits ») ; les déploiements en `[deploy quick]` ne lancent pas les tests navigateur. Restes de CSS `.ms-*` (app.css) sans usage : à retirer à l'Étape 6.

## Étape 4 : Découpage du moteur `engine/analytics/` (37 fichiers → 7 sous-paquets)

Réalisé le 12/11/2026 : 35 modules déplacés en 6 sous-paquets (`git mv`, historique conservé), imports internes et externes réécrits, **sans shims** (le dossier `series/` et `portfolio/` reprennent le nom des anciens modules, déplacés dans `series/series.py` et `portfolio/portfolio.py`). Fonctions mortes supprimées : `applies`, `session_slope`, `default_selection`. `ops/deploy.sh` mis à jour (chemins du hash du moteur). Chemins relatifs aux fichiers de config corrigés (`ranking_table`, `scores_admin`).
**À l'application en production** : tous les fichiers du moteur ayant changé de chemin, le hash du moteur change, et le déploiement le traite comme un changement du moteur et lance en arrière-plan le traitement `maintenance` (recalcul des données dérivées ; attendu, sans effet visible).

- [x] Créer `series/` : series, compute, history, history_refresh, measures, liquidity, signals
- [x] Créer `scoring/` : scores, score_service, score_inputs, score_categories, configurable_score, criteria, ranking_table
- [x] Créer `explorer/` : explorer_config, explorer_metrics, strategy, strategy_docs, funnel
- [x] Créer `portfolio/` : portfolio, allocation, performance, position_plan, tracking, watch, alerts, risk
- [x] Créer `market_views/` : etf, geography, overview, repository, session
- [x] Créer `admin/` : `adminsvc`, `service`, `scores_admin` déplacés
- [ ] Découper `admin/service.py` (1079 lignes) et `admin/scores_admin.py` (986 lignes) en lecture / écriture : reporté (état partagé entre les deux, de nombreux tests s'appuient sur leurs noms internes)
- [ ] Créer `shared/` : sans objet pour l'instant (le chargeur commun est dans `series/loader.py` ; les `_num`/`_iso` des modules diffèrent légèrement et ne sont pas fusionnés)
- [x] Factoriser le chargement prix/splits (`alerts.py:96-104`, `position_plan.py:310-314`, `compute.py:~48`) → `series/loader.load_bars_and_splits(conn, ids)` : `series/loader.py` (`load_bars`, `load_splits`, `load_bars_and_splits`) utilisé par `alerts`, `position_plan` et `compute` ; `history._load`, `service`, `scores_admin` gardent leur requête (autre forme : volumes, devises, fenêtres)
- [x] Corriger le N+1 `adminsvc.py:184-185` (un `COUNT(*)` par `lid`) → un seul `GROUP BY listing_id` : `_intraday_statuses` (2 requêtes `GROUP BY` par place au lieu de 2 `COUNT` par ligne)
- [x] Confirmer par une lecture plus profonde les doublons/N+1 des modules non lus : balayage automatique des `execute` dans une boucle ; les restes sont soit par lots (`compute`, `explorer_metrics`, `etf`, `_closes`), soit de taille constante (`funnel`) ; à surveiller : `tracking.update_outcomes` (une écriture par ligne, tâche de nuit) et `watch.run_all` (moteur désactivé)
- [x] Retirer les shims, mettre à jour `cli.py`, routes PHP et tests : aucun shim n'a subsisté, tous les imports (`cli.py`, `tasks.py`, scripts, tests, `ops/deploy.sh`) pointent vers les nouveaux chemins

## Étape 5 : Cache-busting et déploiement frontend 🔴

- [ ] Une seule version globale (`BUILD_ID` ou hash de contenu) injectée dans tous les HTML par un script de build/déploiement ; aujourd'hui `app.js` a 6 versions de `?v=` différentes, idem `table-layout.js`, `strategies-ui.js`
- [ ] `.htaccess` : ajouter `Cache-Control: immutable` pour les assets versionnés ; `Expires` pour images, SVG, JSON
- [ ] Revoir `ExpiresByType … "access plus 1 hour"` (`.htaccess:16-18`) une fois la version unifiée

## Étape 6 : Design system CSS 🟠

### 6.1 Tokens et thème
- [x] Fusionner les deux `:root` d'`app.css` (l.2/10 et 183-184)
- [ ] Créer des tokens sémantiques dans `app.css` : `--info`, `--danger`, `--warn`, `--ok` + variantes `-soft` / `-ink`, avec valeurs sombres
- [ ] Refactorer `plan-suivi.css` (≈ 20 hex sombres en dur, l.16-140), `classement-test.css` (l.2,5,45,46, dont code mort), `admin-categories-test.css` (l.2, 88-91), `help.css:38` pour n'utiliser que `var()`

### 6.2 Structure
- [ ] Scinder `app.css` (87 Ko) en `tokens.css`, `base.css`, `components.css` (ou au minimum sections claires) ; sortir les styles de page (portefeuille, `.px-alert` l.529, `.lot-alerts`)
- [ ] Fixer l'ordre de chargement : base → composants → page, identique sur toutes les pages
- [ ] Supprimer les `!important` et `all:unset` (`admin-scores.css:121`)
- [ ] Dédoublonner `.card` (app.css:30, 250) et `th` (l.46, 126)

### 6.3 Composants dupliqués (≈ 15 variantes → ≈ 6 composants)
- [ ] Bouton : `.btn` + variantes `.sm/.md/.icon/.ghost` ; éliminer `.ac .btn`, `.ct … .btn`, `help.css:32`, `admin-scores.css:105`, `.ac-icon-button`, `.ct-slider-row button`, `.ct-segment button`, `.ac-order-buttons button`
- [ ] Carte / panneau : unifier `.card`, `.ct-panel`, `.ac-panel`, `.ac-information`, `.ct-preview`, `.kpi-strip .card` ; vérifier `.sui-*` et `.pf-*`
- [ ] Tableau : unifier `table`, `.table-wrap`, `.table-scroll`, `table.dense`, `table.cmp`, `.ac-table-wrap`, `.ct-table-wrap`, `.as-rktable`
- [ ] Pastille / badge (famille la plus fragmentée) : unifier `.badge`, `.tag`, `.chip`, `.chip-s`, `.pills`, `.pill-ok/-warn`, `.ac-status`, `.ac-count`, `.ac-category-chip`, `.ac-demo-badge`, `.ac-subtle-badge`, `.ct-tag`, `.ct-and`
- [ ] Toast : un seul composant pour `#ct-feedback` et `#ac-feedback` (+ `aria-live`)
- [ ] Onglets / segments : unifier `.ac-tab`, `.ac-mode-tabs`, `.ct-segment`/`.ct-seg`, `.pills`

### 6.4 Renommage des prototypes
- [ ] Renommer les fichiers `-test` / `-demo` en production (`classement-test.*`, `admin-categories-test.*`, `admin-categories-demo.js`) vers des noms définitifs, factoriser reset et composants redéclarés sous `.ct` / `.ac`

## Étape 7 : Noyau JS commun 🟠

- [ ] Remplacer les copies locales de `$` par `J.$` : `classement-test.js:5`, `admin-categories-test.js:6`, `splits.js:5`, `register.js:3`, `admin-scores.js:28`
- [ ] Supprimer les redéfinitions de `esc` (`help-charts.js:4`, `plan-suivi.js:8`, `pf-home.js:16`) au profit de `J.esc`
- [ ] Remplacer les formateurs locaux par `J.num` / `J.pct` / `J.eur` : `fmt` (`classement-test.js:223`, `admin-scores.js:30`, `etf.js:41`, `financial-chart.js:10`, `intraday.js:10`), `pc`/`sg`/`eur` de `pf-home.js`
- [ ] Ajouter `J.store` (get/set/subscribe + localStorage) et `J.dom.h()` ; y intégrer `secondary-filter-store.js`
- [ ] Regrouper les helpers de graphiques (`charts.js`, `financial-chart.js`, `intraday.js`, `help-charts.js`, `pf-math.js`) dans un module commun
- [ ] Découper `admin-categories-demo.js` (2 848 lignes), `classement-test.js` (625), `admin-scores.js` (549)

## Étape 8 : CSP, styles inline et accessibilité 🟠

- [ ] Remplacer les ≈ 270 `style="` générés en JS (`admin.js` 83, `titre.js` 37, `admin-scores.js` 29, `donnees.js` 15, `mes-strategies.js` 12) par des classes utilitaires ou `el.style`, puis retirer `'unsafe-inline'` de `style-src` (`.htaccess:12`)
- [ ] Recenser et remplacer les `onclick=` / `onchange=` (≈ 50, décompte à vérifier) : bloqués par `script-src 'self'`
- [ ] Auditer les `innerHTML` (XSS côté client, non couvert)
- [ ] Focus visible partout : retirer `outline:0` (`help.css:16`, `admin-scores.css:58`), corriger `all:unset`
- [ ] `aria-label` sur les boutons-icônes, `<label>` sur les `<input>` (`admin.js`, `donnees.js`, `titre.js`)
- [ ] Revoir les polices de 9–10 px en `var(--muted)` (contraste)
- [ ] Ajouter `prefers-reduced-motion`, lien « aller au contenu »

## Étape 9 : Finitions

- [ ] Harmoniser le style PHP : espaces, lignes > 250 car. (`lib/auth.php:17-50`, `routes/auth.php:48-60`, `admin.php`, `alerts.php`)
- [ ] Borner la pagination `$page` (`admin.php:91`, `admin/catalogue`) ; lier `$size`/`OFFSET` en paramètres (`admin.php:93`)
- [ ] Revoir `JSON_PARTIAL_OUTPUT_ON_ERROR` (masque les erreurs d'encodage) ; envoyer `send_welcome_mail` après `out_then` plutôt que de façon synchrone
- [x] Fusionner les doublons `.card`/`th` résiduels, nettoyer le CSS mort détecté après les étapes 6–7
- [ ] Unifier la stack de tests e2e (`.cjs`, `.php`, seeds Python : 3 technologies)
- [ ] Mettre à jour README / docs d'architecture (sous-paquets analytics, `scripts/release/`, `scripts/oneshot/`, `ops/`)
- [ ] Rejouer toute la suite de tests et une vérification de déploiement ; supprimer les shims restants

---

## Points positifs à préserver

Requêtes SQL préparées (`ATTR_EMULATE_PREPARES=false`) · sessions hachées SHA-256, cookie `HttpOnly`/`SameSite` · `own_portfolio` systématique · rate-limiting et anti-énumération · neutralisation des formules à l'export CSV · `proc_open` en tableau · secrets lus depuis `JIGO_DB_*` · `GET_LOCK` et groupe COMPUTE exclusif dans les jobs · sauvegardes `mysqldump` en 600/700 avec rotation · aucun `<script>`/`style=` inline dans les HTML · un seul `fetch` dans `app.js` · `lang="fr"` partout.
