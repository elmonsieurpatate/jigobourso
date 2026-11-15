# Recette finale et synthèse (étape 12)

## Reprise de clôture — 15 novembre 2026

Base `origin/main` : **7a55926**. Voir `CLOTURE_REFONTE.md` pour les changements,
les preuves et les limites. Les résultats ci-dessous concernent cette reprise.

| Contrôle | Résultat |
|---|---|
| Ruff, format Python, syntaxe PHP (47 fichiers), Prettier JS/CSS, syntaxe JS, migrations additives (17), garde-fous Halo et échelles | OK |
| Tests rapides | **714 réussis**, aucun sauté |
| Intégration PHP/Python/MariaDB sur base jetable | **351 réussis**, aucun sauté |
| E2E financier, stratégies, navigation et compte | OK |
| Clavier du dialogue commun et onglets, 4 contextes | OK |
| Tactile émulé, 2 thèmes : sélecteur borné, aucune recherche au changement, un appel au clic, chargement explicite, défilement horizontal | OK |
| Fiche titre, 12 redimensionnements de 320 à 1280 px | OK ; régression de colonne mobile corrigée |
| Galerie, 390/1280 px × clair/sombre | Référence régénérée pour police locale et espacements voulus ; comparaison suivante OK |
| Contraste calculé | **196 paires** conformes ; texte 4,5:1, séries 3:1 |
| Utilitaires | **63/63 classes**, 756 comparaisons de contrat ; vraies pages : 42 classes rencontrées, 326 comparaisons, aucun écart |
| Mise en page | 120 vues initiales ; 36 vues fiche/aide revérifiées après correction ; aucun débordement de page |
| Intégrité financière et catalogue secondaire, base jetable | OK, aucune anomalie financière |

Les éléments hors écran dans un menu fermé ou une zone défilante ne sont pas
assimilés à un débordement de page. Les captures ont été examinées sur la fiche,
l'aide, l'explorateur, les stratégies et l'administration. Les tests portent sur
Chromium, Python 3.12, PHP 8.2 et MariaDB 10.11. CI Python 3.9, appareils réels et
restauration Hostinger réelle restent des vérifications externes explicites.
Aucun push ni déploiement de cette reprise.

Les premières tentatives locales ont révélé deux limites du harnais, corrigées
avant la recette finale : la galerie `file:` est interdite par ce navigateur
(gérée par `GALLERY_URL` HTTP), et l'arrêt du client `docker exec` laissait un
serveur PHP de test vivant avec un ancien répertoire de courrier. Le conteneur
de test a été redémarré avant le rejeu complet. Aucun test de compte n'a été
supprimé ou rendu permissif pour obtenir le résultat ci-dessus.

## Historique des lots précédents (14 novembre)

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
  - F07 et F08 fermés après coup (2026-11-15) : F08 par conversion en classes et sonde de parité (45/66 classes rencontrées, 0 écart) ; la recette visuelle humaine précède cette conversion. F16 est résolu (formatage).

## Limites de couverture
- Données : bases synthétiques et copie de développement ; mesures de performance à 9 600 titres × 400 séances synthétiques, pas la production.
- Navigateurs : Chromium (Chrome for Testing) uniquement ; ni Firefox ni Safari, ni appareils réels (largeurs 390 et 1280 px émulées).
- Hébergement : Python 3.9 et PHP 8.2 de production non reproduits localement (développement en Python 3.12) ; la CI utilise Python 3.9.
- Volumes réels et charge concurrente non testés.

## Livraison — premier passage CI du 15 novembre

Run `43714229168` : syntaxe, 714 tests rapides et 351 tests d’intégration
Python 3.9 réussis. Déploiement bloqué par la galerie : huit écarts sur des
largeurs intrinsèques en `ch` et le rayon natif des radios. Le flottement des
largeurs a ensuite été reproduit localement entre deux exécutions identiques.
Correction du harnais : galerie servie en HTTP local, police chargée explicitement,
largeurs introductives contrôlées contre leur conteneur plutôt que figées en
pixels ; forme native radio exclue, ses dimensions et les autres propriétés
restent contrôlées. Aucun style applicatif modifié ni test métier désactivé.
