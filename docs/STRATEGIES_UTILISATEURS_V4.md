# Stratégies, personnalisation par utilisateur et Aide (V4)

## Principe
- 7 stratégies **officielles** disponibles pour tous : Croissance rapide, Croissance régulière, Hausse calme, Rebond, Momentum 6 mois, Momentum 12 mois, Momentum ajusté au risque. Une seule entrée chacune (identifiants stables `fast`, `regular`, `calm`, `rebound`, `mom6`, `mom12`, `momrisk`).
- Chaque utilisateur adapte **séparément** les *critères de recherche* et le *calcul des scores*. Les références (code + réglage officiel de l'administration) ne sont jamais modifiées par un utilisateur.
- Statuts : **Officielle** (aucun écart), **Adaptée** (critères ou scores différents de la référence), **Personnelle** (créée par l'utilisateur, privée, dont « Blou »). Revenir exactement aux valeurs officielles supprime l'adaptation : retour automatique à Officielle. Les modifications non enregistrées ne changent pas le statut.

## Stockage (table `settings`, aucune migration de schéma)
| Clé | Contenu |
|---|---|
| `ct_strategies:<uid>` | critères des intégrées (surcharges) et stratégies personnelles de l'utilisateur |
| `scores_profiles_u<uid>` | adaptations de scores de l'utilisateur (nouveau) |
| `scores_profiles` | profils officiels fixés par l'administration (inchangé) |
| `table_layouts:<uid>` | colonnes, ordre, largeurs, tris, filtres initiaux de l'utilisateur (nouveau) ; à défaut, `table_layouts` (défaut commun) |
| `users.prefs_json.help_level` | niveau d'aide Débutant / Expert |

Rien n'est migré ni supprimé : un utilisateur sans entrée personnelle voit les valeurs communes. La configuration de colonnes de l'administration (commit b619ae1) devient le **défaut commun** ; chaque compte la surcharge dans « Mes colonnes et tris ».

## Routes
- Personnelles (connexion requise, toujours limitées au compte) : `strategies/status`, `my/scores`, `my/scores/save|preview|simulate|ranking`, `table-layouts`, `table-layouts/save`, `classement-test/strategies(/save)`, `help/facts`, `auth/prefs`.
- Administration (rôle admin vérifié côté serveur) : `admin/*`, dont `admin/table-layouts*` et `admin/scores*` (références communes).
- Commandes moteur : `strategies-status`, `scores-user-save`, `scores-user-state`, `help-facts`.

## Interface
Menu Explorer : Recherche et résultats, Mes stratégies, Mes critères de recherche, Mes paramètres de scores, Mes colonnes et tris, Mes filtres et catégories. Menu d'administration technique : FinanceDatabase, Yahoo Finance, Actions / ETF, Cron, Journaux, Utilisateurs, Réglages. Page `aide.html` pour tous (rubriques réservées aux administrateurs masquées aux autres).

Composants partagés : `strategies-ui.js` / `.css` (icône par stratégie, badge, fenêtre d'information au clic et au clavier, sélecteur groupé accessible, bandeau). Contenu de l'aide : `help-content.js` (textes) ; les chiffres des fiches viennent du moteur (`help/facts`, `engine/analytics/strategy_docs.py`), jamais recopiés.

## Points à connaître
- Les réglages communs des scores (κ, seuil de couverture, ancrage) restent fixés par l'administration ; ils sont en lecture seule dans « Mes paramètres de scores ».
- Les écrans d'administration des scores et des colonnes ne sont plus dans le menu ; ils restent accessibles par `admin.html#scores` et `admin.html#colonnes` pour fixer les références et le défaut commun.
- Les noms des trois stratégies momentum portent encore « (expérimental) » dans le moteur.
- Croissance rapide n'a pas de seuil de R² dans ses critères (pente seule) ; le R² intervient dans son score complexe.
- Les anciennes notes de Rebond et Hausse calme mentionnaient des seuils d'admission (rendement 6 mois, volatilité, repli) qui n'existent plus dans leurs critères : textes corrigés.

## Tests
`tests/integ/test_user_strategies.py` (isolation, statuts, restaurations, faits), `tests/integ/test_table_layouts.py` (colonnes personnelles), `tests/e2e/strategies-ui.cjs` (deux comptes, menu, permissions, sélecteur, fenêtre d'information, comparaison, restauration, Aide, mobile).
