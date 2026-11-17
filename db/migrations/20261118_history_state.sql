-- Registre de la profondeur d'historique (1 260 séances par titre) : distingue un titre trop récent d'un historique incomplet et permet la reprise.
CREATE TABLE IF NOT EXISTS history_state (
  listing_id  INT UNSIGNED NOT NULL,
  status      VARCHAR(12) CHARACTER SET ascii NOT NULL,
  checked_at  DATETIME NOT NULL,
  first_bar   DATE NULL,
  holes       SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  missing     SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  closed_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  added       INT UNSIGNED NOT NULL DEFAULT 0,
  detail      VARCHAR(120) NULL,
  PRIMARY KEY (listing_id),
  KEY ix_history_state_status (status, checked_at),
  CONSTRAINT fk_history_state_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
