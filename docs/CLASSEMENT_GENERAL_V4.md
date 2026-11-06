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

## Version 3 des scores (2026-11-06)
- **Score simple** = 100 × Dynamique × Régularité, plafonné à 100. Dynamique : note de pente de chaque période (saturation 17 % × (n/5)^0,52), moyenne pondérée par les poids de périodes (renormalisés sur les périodes mesurables). Régularité : R² de chaque période pondéré par min(1, n/21). Pics, séances positives, accélération, volatilité, drawdown et liquidité n'y entrent plus.
- Comparaison sur 2 246 titres réels (avant la bascule) : Spearman 0,998 ; top 50 : 40 titres communs. Médianes par profil, ancienne → nouvelle : croissance régulière 22,1 → 30,9 ; irrégulière 8,2 → 15,2 ; stagnation 0,08 → 0,21 ; baisse 0 → 0. L'ordre est conservé ; l'écart régulière/irrégulière est moins marqué.
- **Score complexe** : sept composantes et poids inchangés (dynamique 40, R² 15, séances positives 5, concentration 7, volatilité 15, drawdown 8, liquidité 10 ; accélération 0).
- **Ancrage récent** (complexe seulement) : note finale = somme pondérée × (1 − λ × (1 − g)), g = min(1, dynamique de la période la plus courte mesurable ÷ 32). λ = 0,5 par défaut, réglable de 0 à 1 dans l'administration (réglage commun), 0 = neutralisé. Il fait partie de la clé de cache des notes.
  - Double comptage : la période courte pèse déjà dans la dynamique (poids 40 × 41,6 %) et amortit cinq composantes via g. Pour une semaine plate, ces deux canaux retirent ~35 % de la note, l'ancrage 0,5 porte la perte à ~68 %. Effet sur le classement réel modéré : Spearman 0,9965 entre λ = 0 et λ = 0,5 (0,846 à λ = 1) ; 93 titres communs sur le top 100 ; seuls 18 titres du top 100 sont pénalisés. Valeur par défaut conservée.
- **Données manquantes** : aucune valeur fictive. La liquidité absente sort du calcul complexe (poids renormalisés, score « partiel »). Sensibilité mesurée : forcer la liquidité absente à 0 ou à 50 modifie peu le classement (Spearman 0,9945 / 0,9586).
- **Complétude** : chaque score expose sa couverture, son statut (complet / incomplet / indisponible), les périodes et composantes utilisées avec leurs poids effectifs (page Simulation).
