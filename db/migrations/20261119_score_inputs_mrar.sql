-- Rendement ajusté du risque (MRAR, γ = 2) par fenêtre : mois calendaires, cours de prix, NULL sous 252 séances.
ALTER TABLE score_inputs ADD COLUMN mrar DECIMAL(12,4) NULL;
