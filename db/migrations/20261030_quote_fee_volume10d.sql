-- Deux champs déjà présents dans la réponse Yahoo de cotation (aucune requête de plus) :
-- frais courants d'un ETF (en %) et volume moyen sur 10 jours. NULL tant que la prochaine cotation ne les a pas fournis ; l'inconnu reste inconnu.
ALTER TABLE latest_prices ADD COLUMN expense_ratio DECIMAL(6,3) NULL;
ALTER TABLE latest_prices ADD COLUMN avg_volume_10d BIGINT UNSIGNED NULL;
