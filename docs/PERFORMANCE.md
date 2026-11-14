# Performance et observabilité

Mesures du 2026-11-14 sur **données synthétiques** : 9 600 titres × 400 séances (3,84 millions de cours quotidiens, 57 600 mesures), base MariaDB locale jetable, un seul utilisateur, Chromium 153 sur la même machine. Elles servent à comparer et à repérer les ordres de grandeur ; elles ne prouvent rien sur l'hébergement mutualisé réel (CPU, disque, concurrence).

Reproduction : `scripts/perf_probe.py` (semis, calcul nocturne, commandes du moteur à froid et à chaud, découpage SQL / Python) puis `scripts/perf_browser.cjs` (navigateur). Les deux refusent toute base autre que `jigobourso_perf` sur 127.0.0.1:33307.

## Résultats (volume de production)

| Scénario | Froid | Chaud | JSON | Découpage à chaud |
|---|---|---|---|---|
| Explorer (recherche) | 3,5 s | 0,7 s | 157 Ko | SQL 0,29 s (31 requêtes), Python et sérialisation 0,36 s |
| Classement des scores, sans courbes | 1,9 s | 1,7 s | 11,3 Mo | SQL 0,82 s (12 requêtes), Python 0,77 s, lecture JSON côté client 0,16 s |
| Classement avec courbes de tous les titres | 9,9 s | 8,5 s | 12,6 Mo | SQL 6,96 s (108 requêtes) |
| Fiche d'un titre | 1,5 s | 1,5 s | 41 Ko | SQL 0,36 s (45 requêtes), Python 0,44 s |
| Calcul nocturne (9 600 titres) | | 65 s | | |
| Semis des cours (outil de test) | | 75 s | | |

- **Cache** : l'Explorer passe de 3,5 s (cache `result_cache` froid) à 0,7 s ; le classement n'a pas d'écart notable (0,2 s).
- **Mémoire** : pic de 153 Mo pour le classement, 66 Mo pour l'Explorer.
- **Concurrence** : 4 Explorers simultanés (le nombre d'emplacements du moteur) = 1,1 s au total contre 0,7 s pour un seul ; le cinquième attend jusqu'à 8 s puis reçoit un 503 (`engine_acquire`).
- **Navigateur** (page Classement, après « Appliquer les réglages ») : 3,0 s jusqu'à la première ligne, dont 2,1 s côté serveur ; 50 lignes rendues ; tas JavaScript 15 Mo ; tri d'une colonne 15–19 ms ; recherche : filtre appliqué (9 lignes restantes) en moins de 700 ms, attente de saisie comprise.
- **Les courbes** ne sont demandées que pour la page visible (`ranking/curves`, 9 Ko, 0,2 s) : le coût de 8,5 s des courbes de tout l'univers n'est jamais payé par l'interface.

## Problème mesuré et correction

Le classement renvoie **10,1 Mo de JSON** pour 9 600 titres. Seule correction apportée à l'étape 10 : réponses JSON de plus de 64 Ko compressées en gzip quand le client l'accepte (`json_payload`, `app/lib/http.php`) : 10 143 Ko → 1 151 Ko (÷ 8,8), 94 ms de CPU. Le tri et le filtrage côté client coûtent moins de 20 ms : **aucune pagination serveur, aucun cache, aucun worker, aucun bundler** n'est justifié par ces mesures.

Pistes non retenues faute de problème mesuré : pagination du classement côté serveur (le tri client est rapide ; le coût est le transfert, déjà divisé par neuf) ; cache du classement (écart froid/chaud de 0,2 s).

## Assets

81 fichiers dans `app/public/assets`, tous référencés par au moins une page ou un autre asset, aucun manquant, aucun chargé deux fois (`tests/fast/test_assets.py`). Poids cumulé non compressé des scripts et feuilles de style par page : de 139 Ko (connexion) à 369 Ko (portefeuilles) ; plafond de non-régression à 450 Ko. Les pages d'authentification chargent 140 Ko : non optimisé, aucun problème mesuré.

## Diagnostic des lenteurs et des erreurs

- Chaque réponse porte `Server-Timing` (visible dans l'onglet Réseau) : `app` total PHP, `slot` attente d'un emplacement moteur, `engine` processus Python entier (démarrage, SQL, calcul), `decode` lecture de sa réponse, `gzip` compression.
- Une requête de plus de 3 s (`JIGO_SLOW_MS`) est journalisée : `lent [identifiant] route app;dur=…, engine;dur=…`.
- Les erreurs 500 portent `ref` (identifiant de requête) qu'on retrouve dans le journal serveur ; le moteur journalise ses échecs avec l'identifiant (`docs/API_CONTRACT.md`).
- Le découpage SQL / Python d'une commande se refait avec `scripts/perf_probe.py` (fonction `breakdown`).

## Causes de timeout mesurées

Le délai du moteur est de 90 s ; la commande la plus lente mesurée à l'échelle de production, **sans** les courbes de tout l'univers, dure 1,7 s (classement) et 1,5 s (fiche). Le coût dominant des commandes lentes est SQL (6,96 s sur 9,0 s pour les courbes complètes, 108 requêtes). Un 503 « occupé » vient de la saturation des 4 emplacements, pas d'un moteur lent. Ces proportions viennent d'une base locale : sur l'hébergement, SQL et CPU partagés peuvent multiplier les durées, ce qui n'a pas été mesuré.

## Pannes fournisseur et limitations de débit

Aucun comportement financier n'est corrigé implicitement ; couverts par les tests existants : limitation 429 du fournisseur (`tests/integ/test_catchup.py`, `test_collect_gaps.py`, `test_splits.py`, `test_intraday.py`), données absentes (`test_collect_volumes.py`), reprise et signal de vie des traitements (`test_job_runner.py`, `test_incident.py`), moteur indisponible ou tronqué (`tests/fast/test_engine_call.py`).

## Limites

Données synthétiques sans bruit réel ; un seul utilisateur ; une machine ; pas d'hébergement mutualisé ; pas de réseau lent ni d'appareil mobile mesuré.
