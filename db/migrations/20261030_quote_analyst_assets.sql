-- Deux champs de plus lus dans la réponse de cotation Yahoo déjà demandée (aucune requête de plus) :
-- consensus des analystes (actions, texte brut « 1.8 - Buy ») et actifs sous gestion d'un ETF. NULL tant que le prochain import ne les a pas fournis ; l'inconnu reste inconnu.
ALTER TABLE latest_prices ADD COLUMN analyst_rating VARCHAR(40) NULL;
ALTER TABLE latest_prices ADD COLUMN net_assets BIGINT UNSIGNED NULL;
