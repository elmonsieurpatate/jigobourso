-- Clés étrangères user_id des alertes (la suppression d'un compte supprime ses règles et événements). Échoue sans rien modifier s'il existe des lignes orphelines : à nettoyer à la main avant.
ALTER TABLE alert_rules ADD CONSTRAINT fk_alert_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE alert_events ADD CONSTRAINT fk_event_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
