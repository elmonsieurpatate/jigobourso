# Intégrité financière — correctif du 29 octobre 2026

Les neuf reproductions de l'audit sont conservées dans `tests/fast/test_financial_regressions.py` et `tests/integ/test_financial_regressions.py`. Les cas numériques indépendants sont dans `tests/fast/test_financial_cases.py` et la seconde partie des tests d'intégration : coût moyen pondéré, ventes partielles et totales, frais en euros, change historique, ventes concurrentes et modifications rétroactives.

## Transactions et change

Chaque écriture prend un verrou de ligne sur le portefeuille avant de relire ses transactions. Une seule validation chronologique, par `(trade_at,id)`, intervient avant le commit. L'ajout, la modification et la suppression sont tous annulés si une vente fait passer la quantité détenue sous zéro. Deux ventes concurrentes ne peuvent pas consommer le même stock.

Le taux `fx_to_eur` désigne les euros pour **une unité du prix enregistré**. Il est enregistré à l'écriture, fourni explicitement ou choisi parmi les taux antérieurs ou égaux à la date d'opération, avec sept jours de tolérance maximum (week-end). Aucun taux futur ou courant ne remplace un taux historique absent. Modifier la date dans le dialogue efface le taux prérempli afin d'en choisir un adapté. À date et unité inchangées, un taux historique enregistré est conservé si le client laisse le champ vide.

Les frais sont exprimés en euros : ajoutés au coût des achats, déduits du produit des ventes. Les calculs conservent leur précision ; la présentation arrondit. Le coût moyen restant est réévalué chronologiquement lors de toute modification ancienne.

Une transaction ancienne sans taux confirmé reste inchangée. Les prix de revient et plus-values qui en dépendent sont explicitement indisponibles, avec un avertissement dans le portefeuille et le bilan. Le contrôle CLI ne modifie rien : `php scripts/release/check_financial_integrity.php`.

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

## Étape 6 — splits, unités, parité (2026-11-14)

**Lecture des splits.** `split_events` (ledger.php) lit `split_log` (statut `confirmed` seulement : un simple saut de cours « detected » ou « real_move » ne modifie jamais une quantité). Lecture impossible (base, table absente) = `ApiError` 503 « Événements de split illisibles », jamais une liste vide : valorisation et validation d'écriture échouent explicitement plutôt que de calculer des quantités sans split. Aucun titre demandé = liste vide légitime.

**Règle de quantité unique.** `oversold_transactions()` (transactions.php) est la seule règle « quantité détenue à la date, splits confirmés compris ». La validation des écritures et le contrôle de release (`check_financial_integrity.php`) l'appellent toutes deux : plus de faux diagnostic de vente à découvert après un split valide. Le ratio d'un événement est compté dès le jour du split inclus ; plusieurs splits et regroupements se composent.

**Corrections manuelles (décision).** Un achat à prix zéro daté à partir du jour d'un split vaut correction manuelle de l'utilisateur : le split n'est plus appliqué automatiquement pour ce titre, il n'est jamais corrigé deux fois. Le lien est donc implicite (date et prix zéro), sans migration ni réparation automatique ; l'ambiguïté (don d'actions, ou correction d'un regroupement, un achat ne pouvant pas retirer de parts) est traitée par le recensement : le contrôle de release liste chaque achat à prix zéro (`zero_price_buy_manual_split_or_gift`) pour confirmation par l'utilisateur, sans rien modifier. Les transactions d'origine ne sont jamais réécrites.

**Parité PHP / Python.** Le registre PHP lit `split_log`, le moteur lit `corporate_events` ; les deux sont écrits ensemble à la confirmation (`market/splits.py`, `split_review.py`). Le contrôle de release signale tout split confirmé sans événement correspondant (`confirmed_split_without_corporate_event`).

**Unités de prix.** Source unique côté Python `engine/shared/units.py`, miroir PHP `app/lib/units.php` ; parité testée (`tests/fast/test_units_parity.py`).

| Unité | Devise du taux | Diviseur | Facteur vers l'euro |
|---|---|---|---|
| EUR | EUR | 1 | 1 |
| GBP (livre) | GBP | 1 | taux GBP |
| GBp, GBX (pence) | GBP | 100 | taux GBP / 100 |
| ZAc, ZAC (cents du rand) | ZAR | 100 | taux ZAR / 100 |
| ILA (agorot) | ILS | 100 | taux ILS / 100 |
| autre code ISO | lui-même | 1 | son taux |

Casse : `GBp` (pence) et `GBP` (livre) sont distincts ; les autres codes sont insensibles à la casse. Unité ou taux inconnu : facteur indisponible (`None`/`null`), jamais 1 par défaut. Avant l'étape 6, l'historique des portefeuilles et la saisie historique ne divisaient que les pence : ZAc et ILA étaient 100 fois trop grands.

Les taux historiques enregistrés avec les transactions ne sont jamais recalculés. Aucune migration de données n'est nécessaire à l'étape 6.
