-- Moyennes mobiles longues et nom du profil d'essai dans le suivi.
ALTER TABLE series_state ADD COLUMN ma200 DECIMAL(16,6) NULL;
ALTER TABLE series_state ADD COLUMN ma200_prev DECIMAL(16,6) NULL;
ALTER TABLE ranking_snapshots ADD COLUMN momentum_risk_profile TINYINT UNSIGNED NULL;
ALTER TABLE ranking_outcomes ADD COLUMN momentum_risk_profile TINYINT UNSIGNED NULL;
