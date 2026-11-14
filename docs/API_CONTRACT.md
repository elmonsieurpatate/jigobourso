# Contrat de l'API HTTP

Une seule entrée : `app/public/api.php?r=<route>`. Réponses toujours en JSON UTF-8, `Cache-Control: no-store`, et un
en-tête `X-Request-Id` (8 caractères hexadécimaux) repris dans les journaux serveur.

## Forme des réponses

- Succès : statut 2xx, corps JSON propre à la route (objet ou liste).
- Échec : statut ≥ 400, corps `{"error": "message lisible"}`. Une panne interne (500) ajoute `"ref"` : l'identifiant à
  chercher dans le journal serveur (`api [ref] route : message @fichier:ligne`). Les détails techniques (trace, SQL,
  corps de requête, mots de passe) ne sont jamais renvoyés ni journalisés.
- **Jamais de faux succès** : la réponse est encodée avant l'envoi du statut (`json_text`, `http.php`). Une donnée
  inencodable donne 500 avec `ref`, pas 200 avec un message d'erreur.

## Statuts

| Statut | Sens | Exemples |
|---|---|---|
| 400 | validation : champ absent, trop long, non numérique, JSON invalide | `str_in`, `num_in`, `body()` |
| 401 | non connecté (le client redirige vers la connexion) | routes protégées |
| 403 | connecté ou non, mais droit ou origine refusés | `need_post()` (Origin/Referer), routes admin |
| 404 | route ou ressource inconnue | `Route inconnue` |
| 405 | mauvaise méthode | écriture en GET |
| 409 | conflit d'état | doublon, état incompatible |
| 413 | corps de requête > 2 Mio (`BODY_MAX`) | refusé avant lecture si `Content-Length` le dit |
| 415 | corps non `application/json` | formulaire HTML classique |
| 422 | le moteur refuse la demande (paramètres inacceptables) | `engine_call`, code 2 |
| 429 | trop de tentatives | limitation de débit |
| 500 | panne interne inattendue, avec `ref` | exception non prévue |
| 503 | dépendance indisponible : moteur planté, trop long, occupé, réponse tronquée | `engine_call` |

## Client (`J.api`, core.js)

- Statut ≥ 400 : exception portant `error` (ou « Erreur <statut> »).
- Statut 2xx avec corps illisible (tronqué, page HTML d'un proxy) : exception « Réponse illisible du serveur », jamais `null`.
- Délai dépassé et annulation : voir `docs/FRONTEND_STRUCTURE.md`.

## Vérifications

`tests/fast/test_http_contract.py` (encodage, 413, 415/400, identifiant), `tests/fast/test_engine_call.py` (panne,
sortie tronquée, vide, non objet → 503), `tests/e2e/core.cjs` (client), `tests/integ/test_api.py` (statuts sur l'API réelle),
`tests/fast/test_lint_php.py` (garde lint).
