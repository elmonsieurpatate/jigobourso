-- Scores V4 : mesures propres aux scores (par fenêtre) et liquidité par titre. Tables nouvelles, aucune donnée existante touchée.
-- score_inputs : séances positives, concentration V1, accélération (pente de la fenêtre moins celle de la fenêtre précédente) ; NULL = indisponible, jamais 0.
CREATE TABLE IF NOT EXISTS score_inputs (
  listing_id   INT UNSIGNED NOT NULL,
  sessions     SMALLINT UNSIGNED NOT NULL,
  up_fraction  DECIMAL(8,6) NULL,
  spike_share  DECIMAL(10,6) NULL,
  accel        DECIMAL(12,6) NULL,
  r2_prev      DECIMAL(8,6) NULL,
  PRIMARY KEY (listing_id, sessions),
  CONSTRAINT fk_score_inputs_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
-- liquidity_state : valeur échangée moyenne par séance, en euros. source 'daily' = volumes quotidiens réels (daily_prices.volume) ;
-- 'estimated' = volume moyen 3 mois × cours (estimation, signalée partout) ; jamais mélangées.
CREATE TABLE IF NOT EXISTS liquidity_state (
  listing_id    INT UNSIGNED NOT NULL,
  turnover_eur  DECIMAL(20,2) NULL,
  days          SMALLINT UNSIGNED NULL,                         -- séances de volume réel utilisées (source 'daily')
  source        ENUM('daily','estimated') NULL,
  computed_at   DATETIME NOT NULL,
  volume_checked_at DATETIME NULL,                              -- dernier passage du collecteur de volumes sur ce titre
  PRIMARY KEY (listing_id),
  CONSTRAINT fk_liquidity_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
