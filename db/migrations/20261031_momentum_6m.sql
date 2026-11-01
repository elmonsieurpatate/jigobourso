-- Stratégie expérimentale « Momentum 6 mois » : variation du cours (en %) entre J−126 et J−21 séances, calculée avec le reste des indicateurs.
-- NULL tant que le prochain calcul des indicateurs ne l'a pas fournie ; l'inconnu reste inconnu (le titre est alors « non évaluable » pour ce profil).
ALTER TABLE series_state ADD COLUMN momentum_6m DECIMAL(12,6) NULL;
