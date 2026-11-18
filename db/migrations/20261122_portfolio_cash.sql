-- Liquidités des portefeuilles (phase 1). Additif : les portefeuilles existants restent en modèle « legacy » (aucune liquidité inventée) jusqu'à une conversion explicite.
ALTER TABLE portfolios ADD COLUMN cash_model ENUM('legacy','cash') NOT NULL DEFAULT 'legacy';
ALTER TABLE portfolios ADD COLUMN kind ENUM('virtual','real') NULL;
ALTER TABLE portfolios ADD COLUMN icon VARCHAR(16) NULL;
ALTER TABLE portfolios ADD COLUMN description VARCHAR(280) NULL;
ALTER TABLE portfolios ADD COLUMN archived_at DATETIME NULL;
ALTER TABLE portfolios ADD COLUMN cash_from DATETIME NULL;
ALTER TABLE portfolios ADD COLUMN cash_converted_at DATETIME NULL;

CREATE TABLE IF NOT EXISTS portfolio_cash_movements (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  portfolio_id    BIGINT UNSIGNED NOT NULL,
  kind            ENUM('initial_capital','deposit','withdrawal','dividend','fee') NOT NULL,
  amount_net      DECIMAL(24,8) NOT NULL,
  currency        CHAR(3) CHARACTER SET ascii NOT NULL DEFAULT 'EUR',
  fx_to_eur       DECIMAL(20,10) NOT NULL DEFAULT 1,
  gross_amount    DECIMAL(24,8) NULL,
  withholding_tax DECIMAL(24,8) NULL,
  listing_id      INT UNSIGNED NULL,
  occurred_at     DATETIME NOT NULL,
  note            VARCHAR(500) NULL,
  source          ENUM('manual','conversion') NOT NULL DEFAULT 'manual',
  created_at      DATETIME NOT NULL,
  updated_at      DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_cash_portfolio_date (portfolio_id, occurred_at, id),
  CONSTRAINT fk_cash_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
  CONSTRAINT fk_cash_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS portfolio_cash_audit (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  portfolio_id BIGINT UNSIGNED NOT NULL,
  movement_id  BIGINT UNSIGNED NULL,
  action       ENUM('edit','remove','convert','undo_convert','reset') NOT NULL,
  before_json  JSON NULL,
  after_json   JSON NULL,
  at           DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_cash_audit_portfolio (portfolio_id, at),
  CONSTRAINT fk_cash_audit_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
