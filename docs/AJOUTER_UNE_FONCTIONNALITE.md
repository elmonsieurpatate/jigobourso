# Ajouter une fonctionnalité sans patcher

Cette page dit **où** mettre chaque chose et **quoi lire** avant. Elle ne répète pas les règles : chaque ligne renvoie à la source qui fait foi. Les tests (`make check`) font échouer ce qui sort du cadre.

## Le chemin d'une fonctionnalité, de bas en haut

| Étape | Où | Règle | Source |
|---|---|---|---|
| 1. Données | `db/schema.sql` **et** `db/migrations/AAAAMMJJ_nom.sql` | Une table existante n'évolue que par migration additive (jamais `DROP`, `UPDATE`…). | `db/migrations/README.md`, [DATA_CONTRACT.md](DATA_CONTRACT.md) |
| 2. Calcul | `engine/` (Python) | Mesures pures → critères → classement. Pas d'accès HTTP ni d'état de page. | [ARCHITECTURE_PYTHON.md](ARCHITECTURE_PYTHON.md) |
| 3. API | `app/services/` puis `app/routes/` | **Aucun SQL dans une route** : elle valide l'entrée, appelle un service, renvoie du JSON. SQL toujours préparé. | [ARCHITECTURE_PHP.md](ARCHITECTURE_PHP.md), [API_CONTRACT.md](API_CONTRACT.md) |
| 4. Page | `app/public/*.html` + un seul `assets/<page>.js` | Réutiliser le noyau `J` (`J.api`, `J.esc`, `J.num`, `J.dialog`…) : ne jamais réécrire un format ou un échappement. | [FRONTEND_STRUCTURE.md](FRONTEND_STRUCTURE.md) |
| 5. Style | `app/styles/` (sources) | Couleurs, tailles et espacements **uniquement par variables** ; jamais de `style=` (utiliser `data-style` pour une valeur calculée) ; ne pas éditer à la main `assets/*.css` (générés). | [DESIGN_HALO.md](DESIGN_HALO.md) |

## Les cinq interdits (testés automatiquement)

1. Pas de `style=` ni de `onclick=` dans le HTML ou les gabarits JS (la CSP les bloque, un test les cherche).
2. Pas de couleur ou de `font-size` en dur dans une feuille : tout passe par `tokens.css`.
3. Pas de texte libre dans `innerHTML` sans `J.esc`.
4. Pas de SQL dans `app/routes/`, pas de variable collée dans une requête.
5. Pas de clé ou de secret dans le dépôt ni dans une URL (le cron n'accepte plus que l'en-tête `X-Cron-Key` : la forme `?k=` n'existe plus dans le code ; pas de test dédié, à surveiller en revue).

## Avant de dire « fini »

```
make check     # lint + tests rapides (≈ 20 s)
make integ     # base jetable, API, sécurité (≈ 4 min)
make e2e       # parcours navigateur (PLAYWRIGHT_MODULE et JIGO_CHROMIUM requis)
```

Une modification d'argent (portefeuilles, transactions, alertes) mérite en plus une relecture ciblée : [FINANCIAL_INTEGRITY.md](FINANCIAL_INTEGRITY.md).

## Un fichier devient trop gros ?

Au-delà d'environ 800 lignes, scinder **par responsabilité** (calcul pur / construction HTML / câblage de la page), comme `explorer-model.js` · `explorer-view.js` · `explorer.js`. Ne pas scinder avant d'avoir une raison : on découpe ce qui bouge.
