# Périodes et Scores V4 — état final (17 novembre 2026)

Chantier terminé et validé (tests ciblés, E2E, validation manuelle de l'interface). Commit local, non poussé ; **migration non appliquée en production**.

## Fonctionnalités terminées

- **Méthodologie unique** : Score 1 conserve sa formule et agrège les seules périodes actives selon leurs poids. Score 2 calcule ses dix composantes par période, puis agrège avec ces mêmes poids. Une mesure absente reste `None`, sort du dénominateur et réduit la couverture affichée. Les anciens horizons fixes (momentum 6/12 mois, rebond sur 126 séances, liquidité globale, accélération entre deux fenêtres) n'existent plus.
- **Formules par période** : accélération = pente de la seconde moitié moins pente de la première (fiabilité `min(R² des deux moitiés)/0,6`) ; momentum = performance du début à `n−e(n)`, `e(n)=max(1,min(21,arrondi(n/12)))` ; récupération = premier couple sommet/creux de baisse maximale, note `100 × fraction récupérée × min(1, profondeur/10 %)` ; liquidité = moyenne réelle `cours × volume`, au moins `max(3,ceil(75 % × n))` séances valides, échelle logarithmique 2–50 M€/jour.
- **Périodes** : prédéfinies 504, 756 et 1 260 séances ajoutées ; plusieurs périodes personnalisées privées par stratégie (`custom_*`, 3 à 1 260 séances, pas de durée en double parmi les périodes actives).
- **Collecte et calcul** : la profondeur d'historique et de volumes suit la plus longue période active (`engine/shared/period_requests.py`) ; rétention et calendrier adaptés ; aucune lecture au-delà de la plus longue période d'une stratégie.
- **Stockage** : `score_inputs` reçoit `momentum_perf`, `recovery`, `turnover_eur`, `volume_days` (schéma et migration additive `db/migrations/20261117_period_score_inputs.sql`).
- **Site** : configuration PHP/Python, profils, critères, administration, explorateur, fiche titre, aide et `docs/APPLICATION.md` alignés.

## Corrections faites pendant la validation

- Fiche titre : `KeyError: 'two_year'` (liste de libellés fixe) corrigé par `_period_label` dans `engine/analytics/admin/title_sheet.py`.
- Administration > Scores : `HORIZONS is not defined` (export orphelin dans `admin-scores-view.js`) corrigé.
- Mentions obsolètes de « l'horizon de momentum » retirées de l'aide.

## Vérifications réussies

- `make check` : 774 tests rapides, ruff, `php -l` (PHP 8.3). `make js-check` et `git diff --check` propres. `scripts/migrate.py --check` : 18 migrations admissibles.
- Nouveaux tests : formules par période, stratégie 21 + 126 sans lecture au-delà de 126 séances (résultat identique avec 300 séances plus anciennes), isolation des périodes personnalisées, 756 + 1 260 sur 1 261 clôtures.
- PHP 8.3 : `tests/php/ct-periods.php` et `classement-test-categories.php`.
- Intégration (base jetable `jigobourso_it`) : `test_period_scores`, `test_scores_admin`, `test_collect_volumes`, plus migrations, calcul de nuit, collecte, rattrapage, momentum, explorateur, classement, requêtes, stratégies utilisateur, API : tous réussis après correction.
- E2E : `personal-filters`, `scores-preview`, `title-layout`, `strategies-ui`, `financial`, `keyboard`. Modèles Node `explorer-model` et `admin-categories-model`.
- Performance : environ 12 ms par titre avec les neuf périodes jusqu'à 1 260 séances (3 à 4 ms avec trois ou quatre périodes).

## Limites ouvertes

- Les scores déjà stockés n'ont pas de valeurs pour les nouvelles colonnes : un recalcul est nécessaire après déploiement. Les résultats numériques historiques des scores ne sont pas conservés (changement de méthode voulu).
- Activer 756 ou 1 260 séances déclenche, à la collecte suivante, un historique de 5 ans pour toute la liste : coût réseau et temps de calcul plus élevés lors de la première collecte.
- Une période personnalisée n'apparaît dans la courbe de simulation du classement administrateur que lorsqu'elle est active.
- Non exécutés : `make e2e` complet, `make integ` complet, `make visual`.
