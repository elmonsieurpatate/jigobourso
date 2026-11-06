# Administration des scores V4

Page : **Administration → Scores** (`admin.html#scores`). Un moteur de notation commun (`engine/analytics/scores.py`, formules inchangées) ; l'administration ne règle que des paramètres.

## Quatre espaces
1. **Configuration du moteur** : stratégie V4 choisie, granularités actives (poids automatiques ou personnalisés, total 100 %), score simple (formule et composantes en lecture seule), score complexe (poids du profil, total 100 %), réglages communs (priorité aux périodes courtes = κ, couverture minimale).
2. **Profils de stratégies** : toutes les stratégies avec leur moteur (Scores V4 / historique) ; pour une stratégie V4, seuils de conformité par granularité (pente, R², rendement, historique exigé).
3. **Simulation & exemples** : décomposition des deux scores d'un titre réel, avec ou sans les modifications non enregistrées. Sans données : message explicite, jamais d'exemple fictif.
4. **Suivi des calculs** : titres notés (complets / partiels / inconnus), couverture, fraîcheur, origine de la liquidité (volumes réels / estimés / inconnus), erreurs récentes des traitements.

## Stockage (table `settings`, aucune migration)
- `scores_v4` : `{kappa, threshold}` communs à toutes les stratégies.
- `scores_profiles` : `{<stratégie V4>: {periods, weights_mode, weights, complex_weights}}`.
- Un profil enregistré se superpose à la configuration de base de la stratégie (`scores_admin.apply_profile`) ; une valeur propre à la stratégie différente de la conception l'emporte sur les réglages communs.

## Séparation conformité / notation
Les seuils de conformité filtrent ; ils n'entrent jamais dans une note. La clé du cache des scores (`score_service._key`) ne contient que les paramètres de notation (granularités actives, poids, κ, couverture) : changer un seuil ne recalcule rien et ne change aucune note (tests : `tests/fast/test_scores_admin.py`, `tests/integ/test_scores_admin.py`).

## Routes et commandes
`admin/scores` (lecture), `admin/scores/save` (global, profil, `reset` = `global` | `profile` | `all`), `admin/scores/preview` (poids automatiques calculés par le moteur), `admin/scores/simulate`, `admin/scores/monitor` → commandes moteur `scores-state`, `scores-save`, `scores-preview`, `scores-simulate`, `scores-monitor`.

## Limites
- Une seule stratégie utilise le moteur commun (`growth_v1`, « Croissance rapide (V4) ») ; les stratégies historiques restent en lecture seule, les stratégies enregistrées par les utilisateurs ne sont pas listées.
- Le « dernier jour » n'est pas une granularité de notation (moins de 3 séances : ni R² ni volatilité) : cinq granularités notables au maximum.
- Explorer n'affiche pas encore ces scores. La collecte des volumes quotidiens réels n'est pas codée (liquidité estimée).
