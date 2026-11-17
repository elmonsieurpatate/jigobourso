-- Empreinte du change et de la cotation, séparée de celle des données : une variation de change ne recalcule plus que la liquidité en euros.
ALTER TABLE compute_signatures ADD COLUMN liquidity_signature CHAR(32) CHARACTER SET ascii NULL AFTER signature;
