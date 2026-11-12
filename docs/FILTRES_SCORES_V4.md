# Filtres « Score simple V4 » et « Score complexe V4 »

Deux filtres numériques ajoutés à l'administration existante « Filtres et catégories » (même mécanisme que la Volatilité : `app/config/explorer_secondary_filters.json` → réglages persistants `explorer_secondary_filters` / `explorer_secondary_defaults`, API `admin/secondary-filters`). Aucune nouvelle interface, aucun système parallèle : visibilité, groupe dans Classement, édition / ajout / suppression / ordre des catégories, plages validées sans chevauchement, inclusion par défaut, restauration et sauvegarde sont ceux des filtres existants.

- Filtres `score_simple` (mesure `score_simple_v4`) et `score_complex` (mesure `score_complex_v4`), unité « /100 », groupe Principal, visibles.
- Les 13 filtres existants et leurs réglages enregistrés ne sont pas touchés : l'initialisation n'ajoute que les deux filtres manquants (testé sur une configuration à 13 filtres).
- Les filtres n'agissent que sur l'affichage : ils ne modifient jamais une note, un rang global ni le calcul. Un score partiel est une note numérique rangée dans sa catégorie ; seule une note indisponible va dans « Inconnu ».
- Raccordement à Explorer : **non fait** (le filtrage des 13 filtres existants n'est pas non plus raccordé à cette étape). `engine/analytics/scoring/score_categories.py` prépare le terme : `assign` (note → catégorie), `select` (lignes retenues, inchangées), `default_selection`. Aucune note n'est simulée.

## Catégories proposées (modifiables)
Convention des filtres existants : ]min ; max]. Extrémités ouvertes (−∞ / +∞) : tout [0 ; 100] est couvert, sans trou ni chevauchement ; « Inconnu » = note indisponible. Toutes incluses par défaut.

| Catégorie | Score simple | Part (9 611 titres, production) | Score complexe | Part |
|---|---|---|---|---|
| Très faible | ≤ 1 | 51,0 % | ≤ 2 | 49,1 % |
| Faible | 1 – 5 | 17,1 % | 2 – 10 | 21,5 % |
| Modéré | 5 – 15 | 17,0 % | 10 – 25 | 14,7 % |
| Élevé | 15 – 30 | 8,8 % | 25 – 45 | 8,7 % |
| Très élevé | > 30 | 5,8 % | > 45 | 5,7 % |
| Inconnu | note indisponible | 0,3 % | note indisponible | 0,3 % |

Bornes choisies sur la distribution réelle (percentiles de la production, 6 novembre 2026) et non sur 20/40/60/80 : 37 % des titres ont une note simple exactement nulle (baisse ou stagnation), la médiane vaut 0,8 et le 90e centile 20,6 ; la note complexe a une médiane de 2,2 et un 90e centile de 32,5. À recalibrer quand la liquidité et les mesures `score_inputs` seront calculées en production (les notes complexes y sont aujourd'hui toutes partielles).
