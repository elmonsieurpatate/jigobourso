# Explorer V4 — Validation de la première version intégrée

Branche de revue : `feature/explorer-v4-growth`. Production et `main` inchangés.
Guide, paramètres, limites et procédures : [README_EXPLORER_V4.md](README_EXPLORER_V4.md).

## Périmètre des changements

| Domaine | Fichiers principaux |
| --- | --- |
| Formules et paramètres | `engine/analytics/growth.py`, `explorer_config.py`, `strategy.py` |
| Orchestration/cache | `growth_service.py`, `service.py`, `explorer_metrics.py`, `engine/cli.py` |
| PHP et sauvegardes | `app/lib/engine.php`, `app/routes/explore.php`, `admin.php`, `app/services/explorer_library.php` |
| Interface | `app/public/index.html`, `assets/growth.js`, `assets/explorer.css` |
| Administration | `admin.html`, `assets/admin.js`, `assets/growth-admin.js` |
| Conservation historique | Éditeur `assets/explorer.js`, liens explicites `legacy=1`, tests historiques maintenus |
| Migration additive | `db/migrations/20261105_explorer_states.sql`, `db/schema.sql` |
| Retour arrière sûr | `scripts/rollback_growth_v4.py` |
| Comparaison hors réseau | `scripts/compare_growth_v4.py` |
| Validation PR | `.github/workflows/explorer-review.yml`, sans modification du workflow de déploiement |

Le moteur portefeuille et les transactions n’ont pas été modifiés. Les correctifs
P0 commités précédemment restent présents. Aucun fichier de source V1 privé ni
archive déchiffrée n’est ajouté au dépôt.

## Résultats exécutés

- **470 tests rapides réussis**, sans tests ignorés lorsque le PHP local existant
  est dans le PATH ; avertissement de dépréciation `exchange_calendars`.
- **206 tests d’intégration réussis** sur MariaDB jetable ; avertissements de
  dépréciation Python/dépendances existants. Pas de collecte de marché réseau.
- Après revue finale : **26 tests ciblés réussis**, puis **six tests V4 réussis**
  incluant clôture future signalée, cache froid/chaud identique, pont JSON vide,
  refus de filtres non pris en charge, droits administrateur et retour arrière.
- Vérification de migration : **12 migrations admissibles**, dont la nouvelle
  table d’états ; tests de refus du retour arrière si données présentes.
- PHP lint, compilation Python, contrôles syntaxiques JavaScript et
  `git diff --check` exécutés.
- Tests V4 navigateur aux largeurs **1280, 390, 375 px** avec API PHP réelle et
  MariaDB synthétique ; contrôles de dimensions du graphique et du dialogue,
  absence de débordement de page et d’erreurs JavaScript.
- Parcours historiques rejoués aux trois mêmes largeurs ; test des URL historiques
  et conservation du brouillon/réglage appliqué.
- Export d’un snapshot synthétique depuis le navigateur, relecture effective avec
  `compare_growth_v4 --snapshot ... --json`, sans base ni réseau pour la comparaison.

Les premières passes ont révélé et permis de corriger les limites de taille des
clés du cache existant, la conversion objet/tableau du pont PHP, l’absence de
`ctype` dans le PHP local, le débordement du détail de score mobile et le bouton
d’export qui soumettait le formulaire du dialogue. Les succès indiqués portent
sur les passes réalisées après ces corrections.

## Couverture des scénarios demandés

| Scénario | Validation |
| --- | --- |
| Accélération > stable > ralentissement, même gain trimestriel | Tests numériques du moteur intégré et banc exportable |
| Plateau sélectionné et cours plat | Rejet primaire explicite ; aucun R² élevé ne compense une pente nulle |
| Pic isolé | Pas de bonus d’évolution ; échec de régularité dans le cas reproduit |
| Période désactivée | N’exclut pas ; évolution non applicable explicitement si une seule période |
| Critères avancés facultatifs | Champs vides sans effet ; minimum activé et dernier jour testés |
| ET/OU | Un OU avancé ne contourne pas les critères primaires |
| Catégories toutes incluses / inconnus / zéro | Tests unitaires, API et navigateur |
| Modification de catégories | Classement numérique inchangé, cache financier réutilisé sans évaluation |
| Deux scores | Bornes, somme des contributions, données manquantes et normalisations absolues |
| Pondérations administrateur | Rejet si somme incorrecte ; aperçu sans écriture ; sauvegarde et restauration |
| Actions et ETF | Identité des calculs sur les mêmes séries |
| Archives et profils historiques | États conservés séparément ; activation/réactivation sans modifier les paramètres |
| Momentum, MA200 et volumes | Tests P0 conservés et intégrés à la suite |
| Réparation d’historique sans job | Invalidation du cache et statut inconnu si une clôture active disparaît |
| Recherche d’un exclu | Motif technique ou stratégique consultable, pas de score fictif |
| Pagination | Valeurs des scores identiques à celles de l’univers et de la fiche |
| Édition locale | Aucun appel de calcul au déplacement/édition d’un contrôle ; application explicite |
| Mobile | Modes, filtres, détail, chart, archives et dimensions réelles vérifiés |

## Artefacts de revue

Dans l’environnement cloud :

```text
/workspace/portfolio-audit/v4-review/screens/explorer-1280.png
/workspace/portfolio-audit/v4-review/screens/explorer-390.png
/workspace/portfolio-audit/v4-review/screens/explorer-375.png
/workspace/portfolio-audit/v4-review/screens/detail-375.png
/workspace/portfolio-audit/v4-review/screens/admin-preview.png
/workspace/portfolio-audit/v4-review/screens/results.json
/workspace/portfolio-audit/v4-review/legacy/results.json
/workspace/portfolio-audit/v4-review/integrated-benchmark.json
/workspace/portfolio-audit/v4-review/market-comparison.json
```

Le workflow de revue PR prévoit l’archivage des captures futures ; aucun résultat
GitHub Actions non exécuté n’est présenté comme réussi. Un push de branche n’est
ni un déploiement ni une validation CI distante.

## Limites de cette validation

Pas d’accès aux données réelles de production, pas de nouveau snapshot de marché
réel collecté, pas de calibration prédictive et pas de test de charge sur le
catalogue de production complet. Les cas de marché du navigateur sont synthétiques.
La comparaison V1 se limite aux règles de trajectoire documentées, sans prétendre
rejouer son univers, ses sources externes ou sa note finale.

La première V4 est exploitable en environnement de revue pour importer/rejouer
des snapshots autorisés et affiner les paramètres depuis l’administration.
Toute installation ou action sur la base réelle demande toujours l’autorisation
explicite de l’utilisateur.
