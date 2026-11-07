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

## Profils V4 (correction du 06/11)
- Deux profils V4 distincts : **« Croissance rapide — V4 (moteur commun) »** (mode simple : pente et R² par granularité, rien d'autre imposé) et **« Croissance rapide — référence V1 (seuils historiques) »**. Les anciens moteurs sont libellés « … — ancien moteur », séparés, en lecture seule et non migrés.
- **Mode simple** : exactement deux réglages par granularité active (pente minimale, R² minimal). **Mode avancé** : rendement minimal, concentration, volatilité, séances positives, drawdown, filtre facultatif « dernier jour positif », liquidité minimale. Case vide = aucun seuil.
- Préréglages (jamais appliqués sans action) : « valeurs initiales équilibrées » et « référence V1 ».
- **Données et exclusions techniques**, section distincte : historique exigé par période, cours récents, couverture minimale (réglage commun). Un titre non évaluable est « inconnu » ; un titre non conforme garde ses deux scores (aperçu chiffré sur les données réelles dans l'écran).
- **Jour (1 séance)** est une granularité facultative (voir « Granularité Jour » plus bas). Sans poids, le dernier jour n'entre pas dans les notes ; `docs/DERNIER_JOUR_V4.md` reste une proposition abandonnée pour un coefficient implicite.

## Séparation conformité / notation
Les seuils de conformité filtrent ; ils n'entrent jamais dans une note. La clé du cache des scores (`score_service._key`) ne contient que les paramètres de notation (granularités actives, poids, κ, couverture) : changer un seuil ne recalcule rien et ne change aucune note (tests : `tests/fast/test_scores_admin.py`, `tests/integ/test_scores_admin.py`).

## Routes et commandes
`admin/scores` (lecture), `admin/scores/save` (global, profil, `reset` = `global` | `profile` | `all`), `admin/scores/preview` (poids automatiques calculés par le moteur), `admin/scores/simulate`, `admin/scores/monitor` → commandes moteur `scores-state`, `scores-save`, `scores-preview`, `scores-simulate`, `scores-monitor`.

## Limites
- Deux profils utilisent le moteur commun (`growth_v4` et `growth_v1`) ; les stratégies historiques restent en lecture seule, les stratégies enregistrées par les utilisateurs ne sont pas listées.
- Jour (1 séance) ne note que la variation d'une séance (Dynamique) : ni R², ni volatilité, ni repli, ni accélération ; une variation négative vaut une dynamique nulle, comme pour toute période. Il n'a jamais de poids automatique.
- Explorer n'affiche pas encore ces scores. La collecte des volumes quotidiens réels n'est pas codée (liquidité estimée).

## Granularité Jour (1 séance)
- Disponible dans l'administration des scores (liste des granularités, **désactivée et à 0 % pour les sept stratégies intégrées**) et dans l'édition des stratégies du Classement (critère « Variation 1J minimale »).
- **Scores.** `scores.scorable(n)` accepte n ≥ 3 ou n = 1. Pour Jour, `period_components` ne produit que la Dynamique (variation de la séance rapportée à la saturation `A·(1/5)^0,52`) ; r2, up_days, concentration, volatilité, drawdown et accélération restent absents (`None`), le repli de 0 % d'une fenêtre à deux clôtures n'est pas reporté. Les poids automatiques (`resolve_weights`) donnent toujours 0 à Jour et ne déplacent aucun autre poids ; Jour n'a un poids que s'il est saisi en mode « Personnalisé » (total 100 %). `score_service.params_for` retire Jour tant que son poids est nul : mêmes notes, même clé de cache qu'avant l'ajout. Régularité (score simple) : moyenne des R² des seules périodes qui en ont un. Ancrage récent : toujours la plus courte période de plus d'une séance. Fiabilité (couverture) : l'absence de R² / volatilité sur Jour n'est pas une donnée manquante.
- **Critère de recherche.** `criteria.PERIODS['day'] = 1` ; seule la métrique « performance » (variation 1J, `>=`) existe pour Jour ; pente et R² y sont toujours `None` (jamais inventés). Activée sans seuil : aucun critère. Avec un arbre de règles, la règle `return` / `day` de l'arbre fait foi et compte une fois.
- **Compatibilité.** Un profil de scores enregistré sans Jour est lu avec Jour désactivé (un ancien filtre « dernier jour » est repris comme seuil de variation). Une stratégie du Classement enregistrée sans Jour est lue avec Jour désactivé (`ct_config`). Une stratégie personnelle dont seul Jour est actif garde les scores par défaut. Aucun seuil ni poids existant n'est modifié.
- **Colonne « Var. 1J (%) »** (identifiant `change`, inchangé : visibilité, position, largeur et tri enregistrés restent valables) : variation entre les deux dernières séances clôturées (`series_state.daily_change`, calendrier de la place, clôtures réglées uniquement ; une clôture manquante donne « — », jamais 0). Disponible dans Explorer et Scores. Colonne « Dernière clôture » (Explorer, masquée par défaut).
