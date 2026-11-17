-- Empreinte des données d'entrée de chaque titre au dernier calcul des indicateurs : seuls les titres dont l'empreinte change sont recalculés.
CREATE TABLE IF NOT EXISTS compute_signatures (
  listing_id  INT UNSIGNED NOT NULL,
  signature   CHAR(32) CHARACTER SET ascii NOT NULL,
  computed_at DATETIME NOT NULL,
  PRIMARY KEY (listing_id),
  CONSTRAINT fk_compute_signature_listing FOREIGN KEY (listing_id) REFERENCES listings(id)
) ENGINE=InnoDB;
