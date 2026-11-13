# Organisation des tests

Un dossier par technologie, un seul rôle chacun :

| Dossier | Technologie | Rôle |
|---|---|---|
| `tests/fast/`, `tests/integ/` | Python (pytest) | logique, moteur, API ; lancent aussi les tests PHP ci-dessous |
| `tests/php/` | PHP | tests des services PHP contre une base jetable (appelés par pytest ou `scripts/test_secondary_filters.sh`) |
| `tests/seeds/` | Python | données synthétiques injectées avant un scénario navigateur |
| `tests/e2e/` (ici) | Node (`.cjs`, playwright-core) | parcours navigateur et tests de modèles JS purs |

Point d'entrée des parcours navigateur de la CI : `make e2e` (= `scripts/e2e_browser.sh` : `financial`, `strategies-ui`, `account-navigation`).
Les autres scénarios se lancent à la main (`node tests/e2e/<nom>.cjs`, après `make db-reset` et le seed correspondant) ; les tests de logique pure (`core.cjs`, `explorer-model.cjs`…) tournent dans `make fast`.
