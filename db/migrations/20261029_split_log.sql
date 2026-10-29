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
