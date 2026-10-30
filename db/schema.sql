-- Jigobourso v2 — schéma cible (MariaDB 10.11+/11.8, InnoDB, utf8mb4).
-- Construit dans une base séparée ; aucune table existante n'est touchée.
-- Principes : clé primaire = clé fonctionnelle ; aucun index secondaire sans besoin démontré ;
-- valeurs courtes (ENUM, CHAR ascii) ; une seule génération de tables.

SET NAMES utf8mb4;

-- ───────────── CATALOGUE ─────────────
CREATE TABLE instruments (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  group_key VARCHAR(40) CHARACTER SET ascii NOT NULL,           -- 'isin:…' | 'figi:…' | 'sym:MIC:SYMBOL' : regroupe les cotations d'un même produit
  isin      CHAR(12) CHARACTER SET ascii NULL,
  kind      ENUM('equity','etf') NOT NULL,
  name      VARCHAR(200) NOT NULL,
  country   VARCHAR(40) NULL,                                  -- pays de l'émetteur (nom FinanceDatabase) : place d'origine de la règle R1
  category  VARCHAR(80) NULL,                                   -- secteur (action) / groupe de catégorie (ETF)
  PRIMARY KEY (id),
  UNIQUE KEY uq_instrument_group (group_key),
  KEY ix_instrument_isin (isin)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;

CREATE TABLE listings (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,        -- identifiant propre à la V2 ; la migration rattache les anciennes transactions par (place, symbole)
  instrument_id    INT UNSIGNED NOT NULL,
  mic              CHAR(4) CHARACTER SET ascii NOT NULL,
  symbol           VARCHAR(24) CHARACTER SET ascii NOT NULL,    -- symbole Yahoo
  currency         CHAR(3) CHARACTER SET ascii NULL,
  status           ENUM('excluded','candidate','selected') NOT NULL DEFAULT 'candidate',
  excluded_reason  VARCHAR(120) NULL,                           -- motif principal (obligatoire si excluded)
  is_primary       TINYINT(1) NOT NULL DEFAULT 0,               -- cotation principale de l'instrument (règle R1)
  primary_reason   VARCHAR(20) NULL,                            -- 'home_market' | 'liquidity' | 'single'
  next_daily_check DATE NULL,                                   -- RÉSERVÉ : non utilisé (les splits sont corrigés par corporate_events, voir market/splits.py)
  PRIMARY KEY (id),
  UNIQUE KEY uq_listing_venue_symbol (mic, symbol),
  KEY ix_listing_instrument (instrument_id),
  KEY ix_listing_collect (status, is_primary, mic),
  CONSTRAINT fk_listing_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(id),
  CONSTRAINT ck_excluded_has_reason CHECK (status <> 'excluded' OR excluded_reason IS NOT NULL)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
-- Garantie « exclu ≠ recommandé » : seules les cotations status='selected' ET is_primary=1 entrent dans l'Explorer
-- et les classements. Une cotation détenue (portfolio_transactions) reste collectée et visible dans son portefeuille
-- quel que soit son statut ; elle n'est jamais présentée comme une nouvelle recommandation.

CREATE TABLE catalogue_loads (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_commit CHAR(40) CHARACTER SET ascii NOT NULL,
  loaded_at     DATETIME NOT NULL,
  rows_read     INT UNSIGNED NOT NULL,
  rows_kept     INT UNSIGNED NOT NULL,
  rules_json    JSON NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- ───────────── PRIX ─────────────
CREATE TABLE daily_prices (                                     -- clôtures DÉFINITIVES, 400 séances glissantes
  listing_id   INT UNSIGNED NOT NULL,
  price_date   DATE NOT NULL,
  close_px     DECIMAL(16,6) NOT NULL,
  adj_close_px DECIMAL(16,6) NULL,                              -- RÉSERVÉ : non renseignée (Spark ne fournit pas de cours ajustés des dividendes) ; jamais mélangée à close_px
  volume       BIGINT UNSIGNED NULL,
  PRIMARY KEY (listing_id, price_date),
  CONSTRAINT fk_daily_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;

CREATE TABLE intraday_prices (                                  -- barres de 15 min normalisées sur leur créneau
  listing_id  INT UNSIGNED NOT NULL,
  slot_start  DATETIME NOT NULL,                                -- UTC, multiple de 15 minutes
  close_px    DECIMAL(16,6) NOT NULL,
  is_final    TINYINT(1) NOT NULL DEFAULT 0,                    -- une barre provisoire n'écrase jamais une définitive
  open_px     DECIMAL(16,6) NULL,                               -- bougie complète : renseignée à la consultation d'une fiche (API chart)
  high_px     DECIMAL(16,6) NULL,
  low_px      DECIMAL(16,6) NULL,
  volume      BIGINT UNSIGNED NULL,
  PRIMARY KEY (listing_id, slot_start),
  CONSTRAINT fk_intraday_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;

CREATE TABLE latest_prices (                                    -- une ligne par cotation : ce que l'interface affiche
  listing_id    INT UNSIGNED NOT NULL,
  price         DECIMAL(16,6) NULL,
  price_time    DATETIME NULL,
  source        ENUM('intraday','daily','quote') NOT NULL,
  currency      CHAR(3) CHARACTER SET ascii NULL,
  avg_volume_3m BIGINT UNSIGNED NULL,
  market_cap    BIGINT UNSIGNED NULL,
  quote_at      DATETIME NULL,
  expense_ratio DECIMAL(6,3) NULL,                                -- frais courants d'un ETF, en % (réponse de cotation Yahoo)
  avg_volume_10d BIGINT UNSIGNED NULL,
  analyst_rating VARCHAR(40) NULL,                                -- consensus Yahoo des analystes (actions), texte brut
  net_assets    BIGINT UNSIGNED NULL,                             -- actifs sous gestion d'un ETF (réponse de cotation Yahoo)
  PRIMARY KEY (listing_id),
  CONSTRAINT fk_latest_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;

CREATE TABLE fx_rates (
  currency  CHAR(3) CHARACTER SET ascii NOT NULL,
  rate_date DATE NOT NULL,
  to_eur    DECIMAL(18,8) NOT NULL,
  PRIMARY KEY (currency, rate_date)
) ENGINE=InnoDB;

CREATE TABLE corporate_events (
  listing_id INT UNSIGNED NOT NULL,
  event_date DATE NOT NULL,
  kind       ENUM('split','reverse_split','suspect') NOT NULL,
  ratio      DECIMAL(18,8) NULL,
  PRIMARY KEY (listing_id, event_date, kind),
  CONSTRAINT fk_event_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;

CREATE TABLE price_gaps (                                       -- trous de collecte 15 min par place et séance
  mic          CHAR(4) CHARACTER SET ascii NOT NULL,
  session_date DATE NOT NULL,
  state        ENUM('to_repair','repaired','unrecoverable') NOT NULL,
  detected_at  DATETIME NOT NULL,
  note         VARCHAR(160) NULL,
  PRIMARY KEY (mic, session_date)
) ENGINE=InnoDB;

-- ───────────── ANALYSE ─────────────
-- Les périodes de stratégie ont un nombre de séances réglable (1 à 252) et sept seuils chacune.
-- Les mesures sont donc stockées PAR TITRE ET PAR NOMBRE DE SÉANCES (fenêtre), pas en colonnes fixes.
CREATE TABLE strategy_metrics (
  listing_id   INT UNSIGNED NOT NULL,
  sessions     SMALLINT UNSIGNED NOT NULL,                      -- longueur de la fenêtre (1..252)
  slope        DECIMAL(12,6) NULL,                              -- % par séance = 100·expm1(pente log)
  slope_log    DECIMAL(14,10) NULL,
  r2           DECIMAL(8,6) NULL,
  perf         DECIMAL(12,4) NULL,                              -- rendement % sur la fenêtre
  volatility   DECIMAL(12,6) NULL,                              -- % par séance
  drawdown     DECIMAL(10,4) NULL,
  er           DECIMAL(8,6) NULL,                               -- efficiency ratio
  acceleration DECIMAL(12,6) NULL,                              -- RÉSERVÉ : jamais calculé (toujours NULL)
  observations SMALLINT UNSIGNED NULL,                          -- clôtures observées dans la fenêtre calendaire
  expected_closes SMALLINT UNSIGNED NULL,                       -- clôtures attendues selon le calendrier de la place
  coverage DECIMAL(8,6) NULL,                                   -- observations / expected_closes
  PRIMARY KEY (listing_id, sessions),
  CONSTRAINT fk_metrics_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
-- Les mesures peuvent être NULL alors que coverage et le nombre de clôtures expliquent la fenêtre non évaluable.

CREATE TABLE series_state (                                     -- état de la série et indicateurs techniques, 1 ligne / cotation
  listing_id      INT UNSIGNED NOT NULL,
  computed_at     DATETIME NOT NULL,
  last_close_date DATE NULL,
  closes_count    SMALLINT UNSIGNED NOT NULL,
  close_px        DECIMAL(16,6) NULL,
  ma20            DECIMAL(16,6) NULL,
  ma50            DECIMAL(16,6) NULL,
  ma50_prev       DECIMAL(16,6) NULL,                           -- MA50 cinq séances plus tôt
  daily_change    DECIMAL(10,4) NULL,                           -- % dernière séance
  gap_to_ma20     DECIMAL(10,4) NULL,                           -- % écart au MA20
  break_age       SMALLINT UNSIGNED NULL,                       -- séances écoulées depuis la dernière rupture de cours inexpliquée
  break_dates     VARCHAR(80) NULL,
  coverage_252    DECIMAL(8,6) NULL,                            -- couverture de la fenêtre annuelle calendaire
  observed_252    SMALLINT UNSIGNED NULL,
  expected_252    SMALLINT UNSIGNED NULL,
  risk_score      TINYINT UNSIGNED NULL,                        -- RÉSERVÉ : jamais calculé (toujours NULL)
  quality         ENUM('ok','insufficient','inconsistent_adjustments','stale','break','incomplete','calendar_unknown') NOT NULL DEFAULT 'ok',
  PRIMARY KEY (listing_id),
  CONSTRAINT fk_state_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
-- Statut (retenu/exclu/non évaluable) et rang ne sont jamais stockés : ils dépendent de la configuration
-- de stratégie de l'utilisateur et sont calculés à la demande par le moteur.

-- ───────────── EXPLOITATION ─────────────
CREATE TABLE jobs (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_type    VARCHAR(24) CHARACTER SET ascii NOT NULL,
  trigger_by  ENUM('cron','admin','system') NOT NULL DEFAULT 'cron',
  status      ENUM('queued','running','completed','completed_with_errors','failed','paused','interrupted') NOT NULL,
  started_at  DATETIME NOT NULL,
  finished_at DATETIME NULL,
  items_ok    INT UNSIGNED NULL,
  items_error INT UNSIGNED NOT NULL DEFAULT 0,
  summary     VARCHAR(500) NULL,
  PRIMARY KEY (id),
  KEY ix_jobs_type_start (job_type, started_at)
) ENGINE=InnoDB;

CREATE TABLE job_logs (
  id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id    BIGINT UNSIGNED NOT NULL,
  level     ENUM('warning','error') NOT NULL,
  message   VARCHAR(400) NOT NULL,
  logged_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_job_logs_job (job_id),
  CONSTRAINT fk_log_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE settings (
  name       VARCHAR(64) CHARACTER SET ascii NOT NULL,
  value_json JSON NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (name)
) ENGINE=InnoDB;

-- ───────────── UTILISATEURS ET PORTEFEUILLES ─────────────
-- Repris du DDL réel (auth.php::schema_sql, tools/portfolios/migrate.php), nettoyé.
-- Supprimés : jb_positions (ancien registre, remplacé par portfolio_transactions), jb_notes (vide, D8),
-- jb_pf_backups (sauvegardes JSON d'un ancien format), jb_settings par utilisateur (rejoint users.prefs_json),
-- jb_app_settings (rejoint settings : le mot d'invitation d'inscription y vit).
CREATE TABLE users (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username   VARCHAR(30) NOT NULL,
  email      VARCHAR(190) NULL,
  pass_hash  VARCHAR(255) NOT NULL,
  is_admin   TINYINT(1) NOT NULL DEFAULT 0,
  active     TINYINT(1) NOT NULL DEFAULT 1,
  prefs_json JSON NULL,                                         -- préférences d'affichage (mode Débutant/Avancé, etc.)
  created_at DATETIME NOT NULL,
  last_login DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_name (username),
  UNIQUE KEY uq_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sessions (
  token_hash CHAR(64) CHARACTER SET ascii NOT NULL,
  user_id    INT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL,
  last_seen  DATETIME NOT NULL,
  expires_at DATETIME NOT NULL,
  ip         VARCHAR(45) NULL,
  ua         VARCHAR(190) NULL,
  PRIMARY KEY (token_hash),
  KEY ix_session_user (user_id),
  KEY ix_session_expiry (expires_at),
  CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE login_attempts (
  id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(30) NOT NULL,
  ip       VARCHAR(45) NOT NULL,
  at       DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_attempt_user (username, at),
  KEY ix_attempt_ip (ip, at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE portfolios (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id          INT UNSIGNED NOT NULL,
  name             VARCHAR(100) NOT NULL,
  is_default       TINYINT(1) NOT NULL DEFAULT 0,
  default_user_id  INT UNSIGNED AS (CASE WHEN is_default=1 THEN user_id ELSE NULL END) PERSISTENT,
  strategy_config  JSON NULL,                                   -- configuration de stratégie complète (version 2+)
  created_at       DATETIME NOT NULL,
  updated_at       DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_portfolio_name (user_id, name),
  UNIQUE KEY uq_portfolio_default (default_user_id),
  CONSTRAINT fk_portfolio_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE portfolio_transactions (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  portfolio_id  BIGINT UNSIGNED NOT NULL,
  listing_id    INT UNSIGNED NULL,                              -- NULL = titre saisi à la main, hors catalogue
  symbol        VARCHAR(32) NOT NULL,
  name          VARCHAR(120) NULL,
  isin          CHAR(12) CHARACTER SET ascii NULL,
  side          ENUM('buy','sell') NOT NULL,
  quantity      DECIMAL(24,8) NOT NULL,
  unit_price    DECIMAL(24,8) NOT NULL,
  currency      CHAR(3) CHARACTER SET ascii NULL,
  fx_to_eur     DECIMAL(20,10) NULL,
  fees          DECIMAL(20,8) NULL,
  trade_at      DATETIME NOT NULL,
  note          VARCHAR(500) NULL,
  created_at    DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_tx_portfolio_date (portfolio_id, trade_at, id),
  KEY ix_tx_listing (listing_id),                               -- jeu de collecte : cotations détenues
  CONSTRAINT fk_tx_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
  CONSTRAINT fk_tx_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE etf_profiles (                                     -- fiche pédagogique ETF, mise en cache
  listing_id  INT UNSIGNED NOT NULL,
  fetched_at  DATETIME NOT NULL,
  version     SMALLINT NOT NULL,
  state       VARCHAR(12) NOT NULL,
  data_json   JSON NOT NULL,
  PRIMARY KEY (listing_id),
  CONSTRAINT fk_etf_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ───────────── SUIVI DES CLASSEMENTS ET CACHE ─────────────
CREATE TABLE ranking_snapshots (                                -- meilleurs titres de chaque stratégie, chaque soir (preuve datée)
  snap_date  DATE NOT NULL,                                     -- dernière séance connue au moment du calcul
  preset     VARCHAR(20) CHARACTER SET ascii NOT NULL,
  listing_id INT UNSIGNED NOT NULL,
  grp        ENUM('equity','etf') NOT NULL,
  rank_pos   SMALLINT UNSIGNED NOT NULL,
  score      DECIMAL(6,2) NULL,
  origin     ENUM('live','rebuilt') NOT NULL DEFAULT 'live',    -- rebuilt = reconstitué après coup (biais de survie : univers actuel)
  PRIMARY KEY (snap_date, preset, listing_id),
  CONSTRAINT fk_snap_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;

CREATE TABLE ranking_outcomes (                                 -- rendement (%) d'un titre classé, N séances après le classement
  snap_date  DATE NOT NULL,
  preset     VARCHAR(20) CHARACTER SET ascii NOT NULL,
  listing_id INT UNSIGNED NOT NULL,
  horizon    TINYINT UNSIGNED NOT NULL,
  ret        DECIMAL(9,4) NOT NULL,
  PRIMARY KEY (snap_date, preset, listing_id, horizon)
) ENGINE=InnoDB;

CREATE TABLE universe_outcomes (                                -- référence : rendement médian de tout l'univers recommandable ce jour-là
  snap_date  DATE NOT NULL,
  grp        ENUM('equity','etf') NOT NULL,
  horizon    TINYINT UNSIGNED NOT NULL,
  n          INT UNSIGNED NOT NULL,
  median_ret DECIMAL(9,4) NOT NULL,
  mean_ret   DECIMAL(9,4) NOT NULL,
  PRIMARY KEY (snap_date, grp, horizon)
) ENGINE=InnoDB;

CREATE TABLE result_cache (                                     -- verdicts de l'Explorer par configuration, invalidés par data_version
  cache_key    CHAR(40) CHARACTER SET ascii NOT NULL,
  data_version VARCHAR(80) CHARACTER SET ascii NOT NULL,
  built_at     DATETIME NOT NULL,
  payload      MEDIUMTEXT NOT NULL,
  PRIMARY KEY (cache_key)
) ENGINE=InnoDB;

-- ───────────── JEU DE COLLECTE ─────────────
-- Cotations à rafraîchir : sélectionnées et principales, plus TOUTES les cotations détenues (même non principales ou exclues).
CREATE VIEW v_collect_set AS
  SELECT l.id AS listing_id, l.mic, l.symbol, 0 AS held
    FROM listings l WHERE l.status = 'selected' AND l.is_primary = 1
      AND l.id NOT IN (SELECT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL)
  UNION ALL
  SELECT l.id, l.mic, l.symbol, 1
    FROM listings l WHERE l.id IN (SELECT listing_id FROM portfolio_transactions WHERE listing_id IS NOT NULL);

-- Cotations proposables comme recommandation : jamais une cotation exclue, jamais une cotation non principale.
CREATE VIEW v_recommendable AS
  SELECT l.id AS listing_id FROM listings l WHERE l.status = 'selected' AND l.is_primary = 1;

-- ───────────── Garde-fous par position (ajout du 28/10/2026, additif) ─────────────
CREATE TABLE IF NOT EXISTS position_levels (                    -- « filet de sécurité » (stop) et « objectif » d'une position, dans la devise de la cotation
  portfolio_id BIGINT UNSIGNED NOT NULL,
  listing_id   INT UNSIGNED NOT NULL,
  stop_px      DECIMAL(16,6) NULL,
  target_px    DECIMAL(16,6) NULL,
  updated_at   DATETIME NOT NULL,
  PRIMARY KEY (portfolio_id, listing_id),
  CONSTRAINT fk_levels_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Recherches enregistrées par l'utilisateur : critères + filtres, réutilisables (ajout du 28/10/2026, additif)
CREATE TABLE IF NOT EXISTS saved_searches (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NOT NULL,
  name       VARCHAR(80) NOT NULL,
  config     JSON NOT NULL,
  view       JSON NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_search_name (user_id, name),
  CONSTRAINT fk_search_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ───────────── Pilotage de la chaîne FinanceDatabase → Yahoo → filtrage (ajout du 28/10/2026, additif) ─────────────
CREATE TABLE IF NOT EXISTS catalogue_raw (                       -- données brutes du dernier import FinanceDatabase : permet de réappliquer les règles sans retélécharger
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  kind           ENUM('equity','etf') NOT NULL,
  mic            VARCHAR(12) CHARACTER SET ascii NOT NULL,
  symbol         VARCHAR(64) CHARACTER SET ascii NOT NULL,
  isin           CHAR(12) CHARACTER SET ascii NULL,
  name           VARCHAR(200) NOT NULL,
  country        VARCHAR(60) NULL,
  category       VARCHAR(80) NULL,
  currency       CHAR(3) CHARACTER SET ascii NULL,
  delisted       TINYINT(1) NOT NULL DEFAULT 0,
  group_key      VARCHAR(40) CHARACTER SET ascii NOT NULL,
  removed_step   VARCHAR(16) CHARACTER SET ascii NULL,           -- règle qui a écarté la ligne (NULL = conservée) ; résultat de la dernière application des règles
  removed_reason VARCHAR(80) NULL,
  PRIMARY KEY (id),
  KEY ix_raw_step (removed_step, kind),
  KEY ix_raw_listing (mic, symbol)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;

CREATE TABLE IF NOT EXISTS funnel_steps (                        -- entonnoir d'une exécution : une ligne par étape (avant / écartés / conservés)
  id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id    BIGINT UNSIGNED NULL,
  stage     ENUM('catalogue','yahoo') NOT NULL,
  seq       TINYINT UNSIGNED NOT NULL,
  step_key  VARCHAR(24) CHARACTER SET ascii NOT NULL,
  label     VARCHAR(120) NOT NULL,
  rule_text VARCHAR(400) NULL,
  before_n  INT UNSIGNED NOT NULL,
  removed_n INT UNSIGNED NOT NULL,
  kept_n    INT UNSIGNED NOT NULL,
  info_json JSON NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_funnel_job (job_id, stage, seq)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS job_steps (                           -- étapes chronométrées d'un traitement
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id      BIGINT UNSIGNED NOT NULL,
  seq         TINYINT UNSIGNED NOT NULL,
  name        VARCHAR(80) NOT NULL,
  started_at  DATETIME NOT NULL,
  duration_ms INT UNSIGNED NOT NULL,
  detail      VARCHAR(300) NULL,
  PRIMARY KEY (id),
  KEY ix_job_steps (job_id, seq)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS account_tokens (
 token_hash CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
 user_id INT UNSIGNED NOT NULL,
 purpose ENUM('reset','email') NOT NULL,
 target_email VARCHAR(190) NULL,
 auth_stamp CHAR(64) CHARACTER SET ascii NOT NULL,
 created_at DATETIME NOT NULL,
 expires_at DATETIME NOT NULL,
 used_at DATETIME NULL,
 KEY ix_account_token_user (user_id,purpose),
 CONSTRAINT fk_account_token_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS account_attempts (
 scope_hash CHAR(64) CHARACTER SET ascii NOT NULL,
 at DATETIME NOT NULL,
 KEY ix_account_attempt (scope_hash,at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS session_policies (
 token_hash CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
 persistent TINYINT(1) NOT NULL,
 absolute_expiry DATETIME NOT NULL,
 CONSTRAINT fk_session_policy FOREIGN KEY (token_hash) REFERENCES sessions(token_hash) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS split_log (
  listing_id  INT UNSIGNED NOT NULL,
  event_date  DATE NOT NULL,                                    -- séance qui suit le saut
  price_ratio DECIMAL(18,8) NOT NULL,                           -- cours après / cours avant, observé à la détection
  ratio       DECIMAL(18,8) NOT NULL,                           -- parts nouvelles / anciennes (2 = deux pour un ; 0,1 = regroupement 1 pour 10)
  status      ENUM('detected','confirmed','real_move') NOT NULL DEFAULT 'detected',   -- confirmed : Yahoo a ajusté l'historique ; real_move : le saut persiste
  detected_at DATETIME NOT NULL,
  checked_at  DATETIME NULL,
  PRIMARY KEY (listing_id, event_date),
  CONSTRAINT fk_split_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS etf_analysis (
 listing_id INT UNSIGNED NOT NULL,
 built_at DATETIME NOT NULL,
 payload MEDIUMTEXT NOT NULL,
 returns_json MEDIUMTEXT NOT NULL,
 PRIMARY KEY (listing_id),
 CONSTRAINT fk_etf_analysis_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
