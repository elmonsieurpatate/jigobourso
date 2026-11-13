# tests/e2e

Parcours de bout en bout (navigateur ou serveur PHP réel). Trois formes coexistent, par choix de l'outil le plus direct :

| Forme | Rôle |
|---|---|
| `*.cjs` / `*.mjs` | scénarios navigateur (playwright-core) et tests Node de modèles purs (`explorer-model.cjs`) |
| `*.php` | tests de services PHP contre une base jetable (filtres secondaires) |
| `*_seed.py` | données synthétiques injectées avant un scénario |

Point d'entrée : `make e2e` (= `scripts/e2e_browser.sh`) rejoue les trois parcours de la CI (`financial`, `strategies-ui`, `account-navigation`). Les autres scénarios se lancent à la main (`node tests/e2e/<nom>.cjs`, après `make db-reset` et le seed correspondant). Les tests de logique pure sont lancés par `make fast`.
