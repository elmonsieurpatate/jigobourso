# Preuves et limites des corrections du 15 novembre 2026

Référence initiale : `2bb2cec`. Branche : `fix/audit-main-20261115`.
Cette matrice décrit les contrôles exécutés sur la branche, pas les seules cases
d’un plan. Données synthétiques locales uniquement ; aucune réparation financière
ni migration de topologie en production.

| Exigence / état | Preuve | Résultat et portée |
|---|---|---|
| Moteur qui ne lit pas stdin, ferme stdout sans terminer, se bloque ou rend un JSON tronqué | tests/fast/test_engine_call.py | arrêt borné, 422/503 préservés ; durée de phase conservée sur timeout |
| Restauration d’une version choisie et de ses dépendances | tests/fast/test_environment.py | 20 tests ; paire choisie, corruption/manque refusés avant remplacement, réparation sans archive générique, Python de secours incompatible refusé |
| CSS lisible et contrôlé par responsabilités | test_styles_policy, test_css_scale, test_frontend_policy, test_assets et build_styles --check | sources et 11 sorties synchronisées ; budget de 450 000 octets conservé ; surcharges imbriquées et animations testées négativement |
| Apparence conservée | galerie et comparaison avant/après sur le même DOM | 4 contextes de référence inchangés ; 56 pages/contextes sans écart de styles calculés |
| Mobile et thèmes | probe_layout, contrasts, probe_utilities | 120 vues sans défilement horizontal de page ; 196 paires de contraste ; 63 classes / 756 comparaisons ; des éléments internes hors fenêtre ne sont pas assimilés à un débordement de page |
| Routes/services PHP et permissions | test_php_structure et tests/integ | SQL sorti des six domaines ; entrées explicites ; 351 tests d’intégration réussis après les modifications PHP et le verrou runtime |
| Préférences de l’explorateur | explorer-model.cjs via pytest | restauration copiée, migration et cloisonnement par compte sans DOM ni stockage |
| Aperçu Scores indisponible puis rétabli | scores-preview.cjs, API 503 injectée uniquement pour l’aperçu | erreur visible, aucune boucle ; reprise explicite, classement et tri réels, vues simulation et suivi |
| Parcours actifs | e2e_browser.sh | runner complet réussi sur base jetable ; seeds en série, vrais comptes et API ; scénarios historiques classés dans tests/e2e/README.md |
| Suivi et portefeuille | plan-suivi, portfolio-v5 | conseils/règles/protections et graphiques vérifiés ; suivi 320–1440 px, portefeuille 7 largeurs de 320 à 1440 px |
| Splits | split-reviews | mauvais ratio, décision, refus/réexamen, audit, idempotence, rôles et origine ; mobile et bureau |
| Qualité et rapides | validate_quality.sh et test_suite.sh fast | PHP, migrations, ruff, formatage, syntaxe, CSS ; 741 tests rapides réussis ; 739 de ces tests également exécutés dans un environnement Python 3.9 frais sans saut avant les deux dernières régressions PHP |
| CI PR/main | mêmes scripts qualité, pytest et navigateur dans les deux workflows | commandes validées localement ; PR en contents:read, aucun secret de production ; le résultat GitHub du prochain run reste à confirmer |
| Performances Hostinger / appareil réel | measure_search.cjs, Server-Timing, PERFORMANCE.md | outil exercé localement et phases conservées sur erreur ; **mesures authentifiées sur Hostinger, charge concurrente et iPhone physique encore à recueillir** |
| Cohérence pendant la livraison | manifestes verrouillés, sauvegardes appariées, RELEASE_ATOMICITY.md | dépendances et restauration corrigées ; **fenêtre réelle de rsync non mesurée, bascule atomique non implémentée** |

Les avertissements de dépréciation Python observés ne sont pas comptés comme des
tests ratés. Aucun test sauté n’est présenté comme réussi. Les anciens journaux
conservent leurs chiffres et leurs révisions : ils ne sont pas des preuves de
l’état courant. Safari physique et une vraie connexion mobile restent distincts
d’un viewport et d’un réseau simulés dans Chromium.
