-- Stocke l'échantillon réellement observé par fenêtre de séances calendaires.
-- Les colonnes restent NULL jusqu'au prochain recalcul nocturne; l'application
-- traite alors ces fenêtres comme non évaluables, jamais comme historiques complets.
ALTER TABLE strategy_metrics ADD COLUMN observations SMALLINT UNSIGNED NULL;
ALTER TABLE strategy_metrics ADD COLUMN expected_closes SMALLINT UNSIGNED NULL;
ALTER TABLE strategy_metrics ADD COLUMN coverage DECIMAL(8,6) NULL;
ALTER TABLE series_state ADD COLUMN coverage_252 DECIMAL(8,6) NULL;
ALTER TABLE series_state ADD COLUMN observed_252 SMALLINT UNSIGNED NULL;
ALTER TABLE series_state ADD COLUMN expected_252 SMALLINT UNSIGNED NULL;
-- Les statuts incomplet / calendrier inconnu sont calculés à la lecture; le ENUM
-- historique est conservé pour éviter une modification destructive de schéma.
