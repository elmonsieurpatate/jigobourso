# Évolutions du schéma SQL

`db/schema.sql` décrit une installation neuve. Une base DÉJÀ en production n'est jamais recréée : toute évolution d'une table existante passe par un fichier ici.

- Nom : `AAAAMMJJ_description.sql`, appliqué une seule fois dans l'ordre, enregistré dans la table `schema_migrations`.
- Autorisé (jamais de perte de données) : `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX`, `ALTER TABLE … ADD COLUMN | ADD INDEX | ADD KEY`.
- Refusé automatiquement par `scripts/migrate.py` et par le CI : `DROP`, `TRUNCATE`, `DELETE`, `UPDATE`, `INSERT`, `RENAME`, `MODIFY`, `CHANGE`.
  Une transformation de données ou une suppression se fait à la main, avec sauvegarde et accord explicite, jamais par le déploiement.
- Reportez aussi la modification dans `db/schema.sql` (installation neuve), puis exécutez `python scripts/migrate.py --record-all` sur cette base neuve.
- Avant d'appliquer une migration en production, le déploiement sauvegarde toute la base (`mariadb-dump`, 3 dernières copies).
- Un retour arrière du code ne défait pas une migration : les colonnes ajoutées sont simplement ignorées par l'ancien code.
