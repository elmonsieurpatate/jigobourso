-- Mesures de Score 2 confinées à chaque fenêtre, sans reprise des horizons globaux.
ALTER TABLE score_inputs ADD COLUMN momentum_perf DECIMAL(12,4) NULL;
ALTER TABLE score_inputs ADD COLUMN recovery DECIMAL(8,4) NULL;
ALTER TABLE score_inputs ADD COLUMN turnover_eur DECIMAL(20,4) NULL;
ALTER TABLE score_inputs ADD COLUMN volume_days SMALLINT UNSIGNED NULL;
