-- Battement des traitements (le seuil « périmé » se mesure au dernier battement) et texte complet des journaux (message reste tronqué à 400).
ALTER TABLE jobs ADD COLUMN updated_at DATETIME NULL AFTER started_at;
ALTER TABLE job_logs ADD COLUMN detail TEXT NULL AFTER message;
