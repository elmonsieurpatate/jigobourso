# Architecture PHP

Quatre rôles, dans cet ordre de dépendance (jamais dans l'autre sens, contrôlé par `tests/fast/test_php_structure.py`).

| Couche | Dossier | Rôle | Interdit |
|---|---|---|---|
| Entrée | `app/public/api.php` | répartition des routes, conversion des erreurs en JSON | logique métier |
| Routes | `app/routes/*.php` | authentification (`require_user`/`require_admin`), méthode (`need_post`), lecture des paramètres (`body()`, `$_GET`), appel d'un cas d'usage | SQL, règles métier |
| Cas d'usage et métier | `app/services/*.php` | opérations complètes, règles (ledger, transactions, validation), SQL propre au domaine ; reçoivent l'utilisateur et un tableau de paramètres | `$_GET`, `body()`, en-têtes, dépendance aux routes |
| Socle | `app/lib/*.php` | HTTP (`http.php`), base (`db.php`), moteur Python (`engine.php`), auth, configuration, unités | dépendance aux services |

Les cas d'usage de portefeuille (`services/portfolios.php`) sont testables sans serveur : `pf_create($user, ['name' => …])`. L'export CSV reste dans sa route, car il écrit directement les en-têtes et le flux.

## Règles

- Chaque fichier charge ce qu'il appelle (`require_once`) ; `test_php_structure.py` vérifie que toute fonction appelée est dans la fermeture des `require_once` du fichier, et qu'aucune fonction globale n'est définie deux fois.
- Propriétaire : toute ressource d'un utilisateur passe par `own_portfolio()` ou `own_transaction()` (404 identique que la ressource soit absente ou à autrui). Les tests HTTP (`tests/integ/test_api.py`, `test_hardening.py`) vérifient les refus entre comptes.
- Aperçu et écriture d'une transaction partagent leurs règles : `tx_fields`, `price_unit`, `historical_fx`, `tx_carry_fx`, `validate_transaction_history`.

## Transactions SQL et verrous

- `tx(callable)` ouvre une transaction ou rejoint celle en cours ; erreur = annulation.
- Écriture du registre : `write_transaction` prend le verrou de ligne du **portefeuille** (`SELECT … FOR UPDATE`), puis celui de ses transactions, relit, applique le changement, valide tout l'historique, commit. Un seul ordre : portefeuille puis transactions.
- Réglages JSON (`settings`) : verrou sur la ligne du réglage ; quand deux réglages sont modifiés ensemble (filtres secondaires : définitions puis valeurs par défaut), toujours dans cet ordre.
- Comptes : utilisateur puis jeton (`account.php`).
- Aucune écriture ne tient un verrou pendant un appel au moteur Python (lent) : le moteur est appelé avant ou après la transaction.

## Contrat PHP ↔ Python (`engine_call`)

- Appel : `python -m engine.cli <commande>`, requête JSON UTF-8 sur stdin, réponse JSON sur stdout, une seule réponse.
- Types : montants et quantités en nombres JSON ; dates `AAAA-MM-JJ` ; identifiants entiers. Une liste vide est `[]`, un objet vide `{}` (côté PHP, `(object)[]` : un tableau vide serait envoyé comme liste). Une valeur absente est `null`, jamais une chaîne vide.
- Erreurs : code de sortie 2 avec `{"error": …}` = demande refusée (HTTP 422, message du moteur) ; autre échec, sortie vide, tronquée ou non objet = HTTP 503 sans détail technique (stderr tronqué dans le journal serveur, avec la référence de requête).
- Délai : `ENGINE_TIMEOUT` 90 s (variable `JIGO_ENGINE_TIMEOUT`) ; au-delà, le processus est arrêté, HTTP 503. Un verrou d'exécution limite les moteurs simultanés (attente 8 s, puis 503 « occupé »).
- Tests : `tests/fast/test_engine_call.py` (fausses sorties du moteur), `tests/integ/test_api.py`.

## Formatage

Aucun formateur PHP n'est installé dans le projet : le style dense existant est conservé et seul `php -l` est imposé (`make lint-php`). Les déplacements de code de l'étape 7 (routes → services) ne changent aucune logique ; les corrections fonctionnelles sont dans des commits distincts (étapes 5 et 6).

## Cas d’usage extraits après audit du 15 novembre

Les routes de compte, recherche, administration, alertes, suivi et portefeuille
ne contiennent plus de requêtes SQL. Les services `auth_actions`, `explore_actions`,
`admin_actions`, `alerts_actions`, `tracking` et `portfolios` reçoivent leurs
paramètres explicitement. Les routes gardent l’authentification et les entrées/sorties
HTTP ; les services gardent le contrôle de propriété et les règles métier. L’export
sépare la lecture de ses données du flux CSV et conserve la protection des cellules.
`services/cron.php` reste un adaptateur historique de cron HTTP (clé/méthode/journal),
pas un cas d’usage appelé par ces nouvelles routes.

Le garde-fou vérifie l’absence de SQL dans ces routes et d’accès à GET/POST/COOKIE/
SERVER ou body/header dans les cas d’usage extraits. Il ne prétend pas prouver toutes
les propriétés de l’application : les tests API vérifient les permissions et les
résultats, notamment sessions et parcours financiers.
