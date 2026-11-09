-- Plan de suivi : réglage individuel des règles d'une position (activation, valeur personnalisée). Ajout uniquement, aucune donnée existante touchée.
-- Le filet de protection et l'objectif personnels restent dans position_levels (stop_px, target_px) ; cette table ne porte que ce qui n'y a pas de place :
-- règle désactivée, seuil de recul personnalisé. Pas de ligne = tout automatique et actif. Les anciennes règles d'alerte (alert_rules) ne sont ni lues ni modifiées.
CREATE TABLE IF NOT EXISTS position_plan_rules (
  portfolio_id BIGINT UNSIGNED NOT NULL,
  listing_id   INT UNSIGNED NOT NULL,
  rule_key     VARCHAR(20) CHARACTER SET ascii NOT NULL,   -- stop | recul | trend | risk | target
  enabled      TINYINT(1) NOT NULL DEFAULT 1,
  custom_value DECIMAL(16,6) NULL,                          -- seuil personnalisé (recul : % depuis le sommet) ; NULL = valeur automatique
  updated_at   DATETIME NOT NULL,
  PRIMARY KEY (portfolio_id, listing_id, rule_key),
  CONSTRAINT fk_plan_rules_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
) ENGINE=InnoDB;
