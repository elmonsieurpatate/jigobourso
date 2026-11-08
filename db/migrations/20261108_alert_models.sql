-- Modèles d'alerte versionnés (préparation de l'administration future) et traçabilité modèle/version par règle et par position. Ajouts uniquement.
-- alert_models : un modèle = les règles issues d'une stratégie à un instant donné ; une version publiée n'est jamais modifiée.
CREATE TABLE IF NOT EXISTS alert_models (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  strategy_key VARCHAR(40) CHARACTER SET ascii NOT NULL,
  version      INT UNSIGNED NOT NULL,
  status       ENUM('draft','published','archived') NOT NULL DEFAULT 'published',
  rules_json   MEDIUMTEXT NOT NULL,
  digest       CHAR(40) CHARACTER SET ascii NOT NULL,
  created_by   VARCHAR(40) NOT NULL DEFAULT 'system',
  created_at   DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_model_version (strategy_key, version),
  KEY idx_model_digest (strategy_key, digest)
) ENGINE=InnoDB;
ALTER TABLE alert_rules ADD COLUMN why VARCHAR(220) NULL;
ALTER TABLE alert_rules ADD COLUMN model_version INT UNSIGNED NULL;
ALTER TABLE position_watch ADD COLUMN model_version INT UNSIGNED NULL;
