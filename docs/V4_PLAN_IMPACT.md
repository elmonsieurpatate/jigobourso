# Explorer V4 — Plan d’impact et avancement

> Document de la phase préalable/P0. La clarification utilisateur autorise désormais
> l’implémentation avec paramètres provisoires. Voir la version intégrée et les
> défauts semaine/mois dans [README_EXPLORER_V4.md](README_EXPLORER_V4.md).

Branche : `feature/explorer-v4-growth`, créée à partir de `main` à `8048982`.
Référence : [audit du 4 novembre 2026](README_AUDIT_V4.md).

## Périmètre et garde-fous

Réutiliser PHP/Python/MariaDB et les composants graphiques existants. Ne pas
modifier les transactions, la V1 Hostinger ou le moteur portefeuille. Pas de
connexion à la production, de migration réelle, de fusion dans main ni de
déploiement. Les propositions chiffrées doivent être validées avant gel.

## Modules et ordre de réalisation

| Étape | Modules réutilisés | Impact prévu |
| --- | --- | --- |
| P0, qualité | `series.py`, `measures.py`, `strategy.py`, `explorer_metrics.py`, `service.py` | Couverture Momentum, fenêtres MA, disponibilité/source des volumes, invalidation des anciens verdicts |
| Configuration | `explorer_config.py`, `strategy.py`, `explorer_library.php` | Nouveau profil explicitement versionné ; conserver les sept profils historiques et leurs paramètres |
| Scores | `configurable_score.py` et module de formules dédié | Deux scores absolus bornés, explications versionnées ; pas de renormalisation par les filtres |
| Service Explorer | `service.py`, `compute.py`, `signals.py`, `prefilter.py` | Séparer exclusions techniques, critères, indisponibilité et présentation ; mesures exactes par période ; compteurs globaux |
| Interface | `app/public/index.html`, `app/public/assets/explorer.js`, composants communs | Simple/avancé, trois périodes, deux contrôles par période, tableau et détails ; édition locale puis Appliquer |
| Administration | Routes et composants admin existants, table `settings` | Stratégies/poids, catégories et filtres par défaut, aperçu et restauration |
| Cycle de vie | `explorer_saved`, bibliothèque, migrations versionnées | Séparer visibilité/activation/archivage ; suppression confirmée ; compatibilité des sauvegardes |
| Validation | `tests/fast`, `tests/integ`, `tests/e2e` | Séries figées, MariaDB jetable exclusivement, desktop/mobile ; aucune collecte réseau de marché nécessaire |

## Contradictions à traiter

1. `scoped_entries` reclasse actuellement après des filtres d’univers. Pour le
   nouveau profil, calculer les deux scores avant présentation ; les catégories
   et leur filtre ne changent ni mesure, ni score, ni univers de normalisation.
   Conserver le comportement des configurations historiques explicitement chargées.
2. Le parcours actuel démarre sur `regular` avec `tradable:true`. Le nouveau
   parcours devra démarrer sur la nouvelle Croissance rapide, sans masque
   secondaire restrictif. Les garde-fous techniques administratifs resteront
   actifs, visibles et comptés séparément.
3. Le nom `fast` désigne déjà un profil historique dont les empreintes sont
   testées. Ne pas remplacer sa formule : créer une identité de nouveau profil
   et proposer une conversion explicite des anciennes configurations.
4. `active` existe pour les sauvegardes. Ajouter un état d’archive distinct,
   conserver son sens actuel et garder une trace réversible des états antérieurs.
5. La présence de colonnes de volume en base ne prouve pas leur alimentation.
   Conserver `NULL`, exposer source/couverture ; ne pas générer un volume historique
   à partir du volume moyen Yahoo.
6. Les valeurs précalculées peuvent avoir été produites avant les correctifs.
   Invalider les caches et prévoir un recalcul explicite lors d’une future
   migration autorisée ; ne pas annoncer qu’un déploiement du code répare la base.

## Livrable intermédiaire

Les correctifs P0 et leurs tests peuvent être réalisés avant arbitrage des poids.
Le banc `scripts/preview_growth_v4.py` ne fait pas partie du moteur applicatif :
il rend la proposition financière vérifiable avant validation.

Les valeurs soumises sont dans [V4_PROPOSITIONS.md](V4_PROPOSITIONS.md). La formule
finale, son intégration, l’interface et l’administration restent à livrer après
cet arbitrage. Ce document ne les présente pas comme terminés.

État après validation technique : correctifs P0 commités dans `e3891fe`,
458 tests rapides et 200 tests d’intégration réussis. Voir
[V4_P0_VALIDATION.md](V4_P0_VALIDATION.md). L’utilisateur autorise les valeurs
provisoires pour examen, sans validation finale ni gel.
