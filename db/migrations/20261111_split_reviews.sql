-- Décisions manuelles persistantes et journal append-only des splits suspects.
CREATE TABLE IF NOT EXISTS split_reviews (
  listing_id INT UNSIGNED NOT NULL,
  event_date DATE NOT NULL,
  decision ENUM('pending','applied','rejected') NOT NULL,
  ratio DECIMAL(18,8) NULL,
  source_url VARCHAR(1000) NULL,
  note VARCHAR(1000) NOT NULL DEFAULT '',
  actor_id INT UNSIGNED NOT NULL,
  revision INT UNSIGNED NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (listing_id,event_date),
  CONSTRAINT fk_split_review_event FOREIGN KEY (listing_id,event_date) REFERENCES split_log(listing_id,event_date) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS split_review_history (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  listing_id INT UNSIGNED NOT NULL,
  event_date DATE NOT NULL,
  decision ENUM('pending','applied','rejected') NOT NULL,
  ratio DECIMAL(18,8) NULL,
  source_url VARCHAR(1000) NULL,
  note VARCHAR(1000) NOT NULL,
  actor_id INT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_split_review_history (listing_id,event_date,id)
) ENGINE=InnoDB;
