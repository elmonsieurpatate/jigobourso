-- Revérification bornée des sauts dont Yahoo n'a pas déclaré de split (additif, une seule instruction). Sans ces colonnes, le code ne revérifie rien.
ALTER TABLE split_log ADD COLUMN checks TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER checked_at, ADD COLUMN recheck_after DATE NULL AFTER checks;
