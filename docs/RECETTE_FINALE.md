# Recette finale et synthèse (étape 12) — 2026-11-14

## Suites rejouées après les derniers changements de code

| Suite | Résultat |
|---|---|
| `make lint` (ruff, format, `php -l`), `js-check`, `css-check` | OK |
| `make visual` (galerie de référence, 4 contextes) | OK au rejeu isolé ; **un échec constaté une fois** lors de l'enchaînement complet (écarts de largeur de quelques pixels), non reproduit seul : sensible à la charge de la machine, cause non identifiée |
| `make fast` | 706 réussis, 0 sauté |
| `make e2e` (parcours navigateur sur base jetable synthétique) | OK |
| `make integ` (MariaDB jetable, 350 tests : financier, API, comptes, migrations, requêtes) | 350 réussis, 0 sauté |
| `make release-check` (intégrité financière et catalogue, base jetable) | OK |
| CI GitHub sur `8d235c0` : contrôles courts, tests complets, déploiement `hostinger` | verte ; le déploiement s'est exécuté sur Hostinger |
| Répétition locale du déploiement (`scripts/rehearse_deploy.sh`, copie d'une base pleine) : `diagnostic`, `ok`, `fail`, `fail-deps` | conformes (a révélé et fait corriger un défaut de retour arrière) |
| Après `ruff format` : fast 707, e2e, integ 350, visual | OK |

## Ce qui est vérifié
- Cas financiers : splits, unités de prix (parité PHP/Python), ventes à découvert, achats à prix zéro, empreinte avant/après livraison, reprise de migration partielle.
- Permissions multi-utilisateurs : propriété des portefeuilles et transactions (`own_portfolio`, `own_transaction`), comptes, navigation (`tests/e2e/account-navigation.cjs`, `tests/integ/test_account.py`).
- Contrat HTTP : 500 avec référence, 413, gzip, `Server-Timing`, réponse illisible côté client.
- Architecture : 0 cycle d'import Python, couches PHP et Python contrôlées par tests, fonctions du moteur ≤ 105 lignes.

## Conservé / remplacé / supprimé / différé

- **Conservé** : règles métier (achat à prix zéro daté d'un split), `legacy_upgrade` (les configurations de stratégie V3 existent encore en base), `collect.fill_daily_gaps` (n'est plus appelé par le moteur ; sert aux tests d'intégration de la collecte — à retirer avec eux si ce chemin séquentiel n'est plus voulu), alias `rules.MARKETS` (noms de marchés, encore utilisé).
- **Remplacé** : empreinte du moteur (trois copies → `scripts/release/engine_hash.sh`), contrôles de release, modules déplacés (`scoring/`, `explorer/`, `admin/`), cas d'usage de portefeuille hors des routes, unités de prix.
- **Supprimé** : `collected_rows`, `score_categories.select`, `rules.exclusion_reason` (aucun appelant hors tests ; références dynamiques vérifiées par recherche sur `engine`, `app`, `scripts`, `ops`, `tests`), réexports et cycles d'import.
- **Vérifié** : voir tableau ci-dessus.
- **Différé / non vérifié** :
  - essai isolé Hostinger : abandonné (secret et script absents), remplacé par la répétition locale ;
  - restauration des dépendances sur l'hébergement réel (testée seulement avec un faux serveur) ;
  - transfert différé mais non atomique, fenêtre non mesurée sur l'hébergement ; sous-dépendances Python libres par décision (voir `docs/DELIVERY.md`) ;
  - recette visuelle manuelle des pages réelles après le dernier changement de code (la galerie automatisée est verte) ;
  - revue case par case du plan par une personne, mise à jour des documents de design hors README ;
  - F07 (états dynamiques) et F08 (53 valeurs fixes dans `data-style` : conversion en classes = changement de spécificité CSS, à juger lors de la recette visuelle humaine). F16 est résolu (formatage).

## Limites de couverture
- Données : bases synthétiques et copie de développement ; mesures de performance à 9 600 titres × 400 séances synthétiques, pas la production.
- Navigateurs : Chromium (Chrome for Testing) uniquement ; ni Firefox ni Safari, ni appareils réels (largeurs 390 et 1280 px émulées).
- Hébergement : Python 3.9 et PHP 8.2 de production non reproduits localement (développement en Python 3.12) ; la CI utilise Python 3.9.
- Volumes réels et charge concurrente non testés.
