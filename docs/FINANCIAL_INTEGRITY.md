# Intégrité financière — correctif du 29 octobre 2026

Les neuf reproductions de l'audit sont conservées dans `tests/fast/test_financial_regressions.py` et `tests/integ/test_financial_regressions.py`. Les cas numériques indépendants sont dans `tests/fast/test_financial_cases.py` et la seconde partie des tests d'intégration : coût moyen pondéré, ventes partielles et totales, frais en euros, change historique, ventes concurrentes et modifications rétroactives.

## Transactions et change

Chaque écriture prend un verrou de ligne sur le portefeuille avant de relire ses transactions. Une seule validation chronologique, par `(trade_at,id)`, intervient avant le commit. L'ajout, la modification et la suppression sont tous annulés si une vente fait passer la quantité détenue sous zéro. Deux ventes concurrentes ne peuvent pas consommer le même stock.

Le taux `fx_to_eur` désigne les euros pour **une unité du prix enregistré**. Il est enregistré à l'écriture, fourni explicitement ou choisi parmi les taux antérieurs ou égaux à la date d'opération, avec sept jours de tolérance maximum (week-end). Aucun taux futur ou courant ne remplace un taux historique absent. Modifier la date dans le dialogue efface le taux prérempli afin d'en choisir un adapté. À date et unité inchangées, un taux historique enregistré est conservé si le client laisse le champ vide.

Les frais sont exprimés en euros : ajoutés au coût des achats, déduits du produit des ventes. Les calculs conservent leur précision ; la présentation arrondit. Le coût moyen restant est réévalué chronologiquement lors de toute modification ancienne.

Une transaction ancienne sans taux confirmé reste inchangée. Les prix de revient et plus-values qui en dépendent sont explicitement indisponibles, avec un avertissement dans le portefeuille et le bilan. Le contrôle CLI ne modifie rien : `php scripts/check_financial_integrity.php`.

## Livres et pence

`GBP` = livre ; `GBX` = penny (1/100 livre). L'alias Yahoo `GBp` est accepté et enregistré comme `GBX` pour toute nouvelle transaction. Un cours numérique de 100 GBX vaut 1 GBP. Prix et taux utilisent toujours la même unité ; un taux GBP de 1,2 €/GBP devient 0,012 €/GBX. La saisie affiche l'unité, la conserve dans la transaction et permet de saisir un prix en GBP si l'utilisateur sélectionne GBP explicitement. Les affichages monétaires convertissent les pence en livres ; les graphiques restent dans leur unité indiquée.

La sélection de place utilise la devise **du cours**, non celle du catalogue, pour la liquidité. L'import reconnaît GBp/GBX sans convertir silencieusement des montants historiques GBP dont l'unité réelle serait incertaine. Un ancien enregistrement GBP rattaché à un cours GBp est signalé pour confirmation ; le logiciel ne peut pas deviner si son prix a été saisi en livres ou en pence.

## Séries et performances

`prepare_series` et `analyze_series` constituent la préparation commune du calcul nocturne, des fenêtres non standard, de la fiche, des graphiques et des évaluations de stratégie. Les périodes standard sont 1, 5, 21, 63, 126 et 252 séances ; la fiche n'utilise plus une autre durée de mois ou d'année.

Une série ajustée fournisseur complète est prioritaire. Aucun mélange de valeurs ajustées et brutes. Sinon, un split connu utilise le ratio nouvelles parts / anciennes parts pour ajuster les prix antérieurs : split 2:1, prix 100 puis 50 = rendement nul ; 50 puis 55 = +10 %. Le ratio n'est appliqué que lorsque le changement d'échelle observé le justifie : une série brute déjà ajustée ne doit jamais subir un second ajustement. En cas de ratio absent, invalide ou ambigu, une fenêtre traversant l'événement est non évaluable. Les moyennes mobiles ne traversent pas une rupture non résolue. Les cours bruts de la fiche restent accessibles dans `daily_raw` ; `daily` utilise la base commune documentée par `analysis_basis`.

La pente de régression logarithmique, la performance, le R² et la volatilité restent des grandeurs distinctes. Aucune formule de pente ni aucun seuil stratégique n'a été modifié. Les tests utilisent notamment +1 % composé par séance, un rendement attendu de `100*(1.01**21-1)`, R²=1, et des splits/réverses connus. Une série sans métadonnées fiables ne devient pas une preuve d'absence d'opération sur titres.

## Fraîcheur et accès aux résultats

La dernière clôture attendue est dérivée de l'horloge de chaque place, avec délai de publication de 30 minutes, indépendamment de la dernière réponse Yahoo. Une panne de toute la place reste donc détectable. Faute de calendrier certifié des jours fériés, le système est prudent : il peut demander de vérifier une clôture sur un jour férié plutôt que déclarer une panne fournisseur « fraîche ». Pendant l'ouverture, un cours de plus de deux créneaux de 15 minutes est marqué ancien. Le cache change lorsque la séance attendue change.

Les exclus sont paginés comme de véritables éléments, sans réinitialiser leur décalage ; la limite arbitraire de recherche de 50 a été retirée. Le filtre de détention est appliqué même quand la liste des titres détenus est vide, et ne retient que les quantités nettes positives.

## Livraison et conservation

La CI exécute les tests, les syntaxes PHP/JS et une navigation Chrome sur base jetable à 375, 390 et 1 280 px. Avant déploiement : sauvegarde des tables financières hors racine web et empreinte des transactions. Après transfert : recalcul des seules tables dérivées depuis les historiques déjà présents, comparaison des mesures de BOX/BBSI/VOO/UBU5 avec les séries réelles, contrôle de l'empreinte et des effectifs des portefeuilles/transactions, puis contrôle HTTP public. Aucune collecte massive et aucune réécriture des transactions historiques.
