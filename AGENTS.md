# AGENTS.md — Jigobourso

Aide à la sélection d'actions/ETF et suivi de portefeuilles. PHP 8.1+ (site, API), Python (moteur), MariaDB, front statique sans framework. Répondre en français.

## Carte minimale

- `app/routes/` → `app/services/` (PHP, aucun SQL dans une route) · `app/public/` (pages HTML, `assets/<page>.js`, `api.php`) · `app/styles/` (sources CSS ; `app/public/assets/*.css` est généré).
- `engine/` : `catalogue/`, `market/` (collecte), `analytics/` (`scoring/`, `explorer/`, `series/`, `admin/`, `portfolio/`, `market_views/`), `jobs/`, `shared/`, `cli.py`.
- `db/schema.sql` + `db/migrations/` (additif seulement, schéma et migration modifiés ensemble) · `tests/{fast,integ,php,e2e,seeds}` · `scripts/` (voir `scripts/README.md`) · `ops/` (déploiement).

## Quel document lire (un seul, selon la tâche)

- Comment fonctionne un calcul, un score, une stratégie, une constante : `docs/APPLICATION.md` (629 lignes : lire la section voulue via `grep -n '^#'`, pas en entier).
- Ajouter une fonctionnalité : `docs/AJOUTER_UNE_FONCTIONNALITE.md` (indique où mettre chaque chose et quoi lire ensuite).
- PHP : `docs/ARCHITECTURE_PHP.md`, `docs/API_CONTRACT.md` · Python : `docs/ARCHITECTURE_PYTHON.md` · vue d'ensemble : `docs/ARCHITECTURE.md`.
- Front : `docs/FRONTEND_STRUCTURE.md`, `docs/DESIGN.md`, `docs/DESIGN_HALO.md` (CSS).
- Sécurité : `docs/SECURITE.md` · performance : `docs/PERFORMANCE.md` · livraison/déploiement : `docs/DELIVERY.md`, `docs/DEPLOIEMENT.md`, `docs/RELEASE_ATOMICITY.md`.

## Lecture ciblée

- Chercher avant de lire : `rg -n "symbole"` puis lire la plage utile (`sed -n 120,200p`), pas le fichier entier.
- Ne pas parcourir `app/public/assets/` ni `engine/` en bloc ; ne pas lire `data/`, `logs/`, `audit-results/`, `node_modules/`, `.venv/`, `tests/visual/out/`, `db/schema.sql` en entier.
- Pas d'audit global ni de relecture de toute la documentation pour une petite demande. Si l'information est dans la doc ci-dessus, ne pas la redécouvrir dans le code.

## Tests : le plus petit qui couvre le changement

- Python seul : `.venv/bin/python -m pytest tests/fast/test_xxx.py -q`, puis `make lint` (ruff, format obligatoire : `.venv/bin/ruff format <fichiers>`).
- JS : `make js-check` (format Prettier + syntaxe ; `make js-format` pour corriger) · CSS : `make css-check` après modification de `app/styles/`.
- PHP : `make lint` (php -l) ; tests ciblés dans `tests/php/`.
- SQL/DB : `make integ INTEG_ARGS="tests/integ/test_xxx.py"` (réinitialise la base jetable `jigobourso_it`, port 33307, jamais la production ; utiliser `make integ`, pas pytest nu : il fournit PHP 8.3). Ne jamais lancer deux tâches en parallèle sur cette base.
- Filet avant refactor : `make check` (lint + fast, ~20 s).
- Lourds, seulement en clôture d'une étape ou sur demande : `make fast` complet, `make integ` complet (~5 min), `make e2e` (navigateur : `PLAYWRIGHT_MODULE`, `JIGO_CHROMIUM` requis ; voir `tests/e2e/README.md`).

## Git et production

- Pousser sur `main` déclenche le déploiement Hostinger (`.github/workflows/deploy.yml`). Donc : aucun `git push`, aucun déploiement, aucun workflow dispatch sans accord explicite de l'utilisateur.
- Ne jamais toucher la base réelle ni lancer de collecte/calcul massif ; travailler sur la base jetable `jigobourso_it` (`make db-reset`) ou `jigobourso_v2` (dev).
- Pas de commit sans demande. Commits ne touchant que la doc : suffixe `[skip ci]`. Pas de `reset --hard`, `clean`, `push --force` sans accord ; sauvegarder d'abord (branche ou bundle).
- Aucun secret dans le dépôt (`JIGO_DB_*`, clés cron, `.env*` sont hors Git). Ne pas committer `.agents/` ni `skills-lock.json` sans accord.

## Réponses

- Concises : résultat, fichiers modifiés, commandes lancées et leur issue. Pas de recopie de code ou de doc, pas de plan non demandé.
- Annoncer en une ligne ce qui tourne avant toute commande longue (> 1 min), avec un fichier de log suivi par `tail -f`.
- Petite demande : modifier, vérifier ciblé, s'arrêter. Signaler ce qui n'a pas été testé.
