# Classement général V4 (moteur 2) — noter et classer tous les titres évaluables

Décision du 2026-11-06 : V4 ne sélectionne pas un petit groupe conforme, il **note et classe** tous les titres techniquement évaluables.

## Ce qui écartait des titres (avant)
- Seuils de période de la stratégie (pente, R², rendement, concentration, volatilité, séances positives, drawdown), « historique exigé », filtre du dernier jour, liquidité minimale : le verdict `strategy.judge()` les transformait en statut *écarté* / *inconnu*, et la vue par défaut n'affiche que les *retenus*.
- Moteur de notes : période « obligatoire » sans historique ou couverture < 0,75 → les deux notes `None`.

## Maintenant
- Notes : `scores.VERSION = 2`. Aucune note n'est supprimée par un seuil ou par une période obligatoire.
- Données absentes : trois cas. Suffisantes → `ok`. Réduites → note calculée sur les composantes disponibles, poids **renormalisés** (ni bonus ni pénalité), statut `partiel`, couverture et fiabilité fournies. Impossible (aucune période mesurable ; aucune régularité mesurable pour le simple ; aucune composante mesurable pour le complexe) → `inconnu` avec raison.
- Le seuil de couverture 0,75 est un **indicateur de fiabilité** (`reliable`), jamais un filtre ; il n'entre plus dans la clé de cache des notes.
- Filtres : `profil.filters.enabled` (défaut **faux**). Désactivés, la configuration effective n'a aucun seuil ni historique exigé ni filtre du dernier jour ni liquidité minimale (`scores_admin.neutral`). Les valeurs saisies sont conservées dans le profil. Seul le contrôle technique de fraîcheur reste (réglable).
- Le dernier jour n'a aucun coefficient propre (λ = 0,05 abandonné).
- Formules inchangées pour des données complètes (tests de parité conservés).

## Administration
Classement général (titres notés et classés, indisponibles, répartition, dix premiers, effet d'un changement de poids), poids réels des périodes, contributions réelles des composantes (poids effectif après renormalisation), qualité des données ; filtres facultatifs séparés de la notation.
