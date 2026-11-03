# Portefeuilles V3 — suivi des investissements

## Quatre espaces

- **Vue d'ensemble** : valeur, gain total brut et net indicatif, capital défini, principaux contributeurs et positions à examiner. Pas de grand graphique avant le résultat.
- **Mes positions** : résultat personnel, poids, prix de revient, résultat sur la période, statut et explications à la demande. Tris par surveillance, pertes, gains, recul et poids.
- **Évolution et analyse** : réutilise les courbes, unités et contributions existantes. La période affichée porte ses dates ; le gain latent depuis les achats garde une référence distincte.
- **Historique et gestion** : transactions/CSV, ventes, réglages regroupés des achats, allocations et secteurs des ETF seulement lorsqu'ils sont détenus. L'ajout de transaction reste accessible indépendamment de l'espace.

Les onglets s'utilisent au clavier (flèches), les détails natifs au clavier/toucher, et les anciens panneaux de gestion avec Entrée/Espace. Les raisons ne dépendent pas d'une couleur ou d'une infobulle de survol.

## Résultat personnel et état du titre

La valorisation et les gains restent calculés par `ledger.php`, au **prix moyen pondéré (PMP)**, frais compris et conversions historiques inchangées. Le gain total inclut les ventes. Le pourcentage global = gain / achats cumulés, frais compris. La performance d'une période = gain de la période / (valeur initiale + achats de la période), jamais diminué des produits de vente. Ce ne sont ni des rendements annualisés, ni des TWR/TRI.

L'état du titre décrit séparément les mesures réellement disponibles : tendance sur un mois, momentum 6 mois, moyennes 50/200 séances et volatilité quotidienne sur trois mois. Une plus-value personnelle n'efface pas une tendance défavorable ; une perte ne prouve pas que le marché continue de se dégrader.

Les contributions en euros incluent réalisé et latent et s'additionnent au résultat quand les données sont complètes. La part relative affichée = valeur absolue d'une contribution / somme des valeurs absolues des contributions de tous les titres. Elle distingue l'impact monétaire du rendement propre et du poids du portefeuille. Les trois principaux contributeurs de chaque signe sont mis en avant ; la vue Analyse conserve la liste complète. Les pourcentages de rendement propres aux titres ne s'additionnent pas.

Le gain net indicatif conserve l'hypothèse précédente : gain brut moins 30 % des gains réalisés positifs par année et du latent positif. Son pourcentage utilise les mêmes achats cumulés. Hors PEA, pertes reportables, dividendes et fiscalité personnelle ; ce n'est pas un montant fiscal personnalisé. Aucune liquidité ni aucun dividende n'est inventé.

## Protection des gains : conventions explicites

### Par achat encore ouvert

Les ventes consomment les quantités FIFO ; le coût historique du lot est diminué proportionnellement à la quantité vendue. Les splits ajustent les quantités sans changer ce coût. Le suivi considère **les seules quantités encore détenues**, sur des clôtures corrigées des splits depuis la date propre à ce lot, converties avec le change connu à la date observée (au plus sept jours d'antériorité). Le cours actuel peut compléter les observations. Il ne s'agit pas du plus haut intraday historique de l'instrument.

Pour un lot de coût restant C et de quantité q :

- gain actuel = q × dernier cours en EUR − C ; rendement = gain / C ;
- meilleur gain observé = maximum des q × cours daté en EUR − C ;
- gain positif rendu (points) = max(0, meilleur rendement) − max(0, rendement actuel), borné à zéro ;
- recul du cours = 100 × (1 − cours actuel en devise / plus haute clôture observée en devise).

Exemple 100 → 108 → 104, sans frais/change : meilleur gain 8 %, actuel 4 %, rendu **4 points**, recul **3,7037 %**. Si le cours finit à 90, les 8 points de gain positif ont été rendus ; les 10 % de perte sont affichés séparément, pas présentés comme 18 points de gains qui auraient existé. En devise étrangère, gain personnel et recul du cours peuvent diverger ; le premier inclut frais et change, le second décrit le titre.

### Position agrégée

Le résultat affiché reste au PMP. Pour éviter de sommer des sommets atteints à des dates différentes ou d'utiliser un achat avant son acquisition, la protection agrégée fixe les quantités **actuellement détenues**, prend le coût PMP actuel comme base et compare les observations à partir du **dernier achat encore ouvert**. Les mesures par lot gardent leur date et leur coût FIFO. Les deux références sont affichées dans le détail ; leurs pourcentages ne sont pas substitués l'un à l'autre.

Les coûts restants FIFO sont des données dérivées en mémoire, sans modification du registre ni nouvelle table. Les références ne changent pas lors d'un changement de stratégie.

### Indisponibilité plutôt que faux sommet

Début d'historique non conservé, séances attendues absentes, calendrier non pris en charge, taux historique absent, coût nul/inconnu ou cours absent rendent le suivi du sommet indisponible. Les observations futures sont exclues. Une correction manuelle de split reconnue garde sa valorisation PMP correcte mais le détail de protection par lot est déclaré non comparable, plutôt que d'attribuer un rendement fictif à un achat gratuit. L'historique réel conservé étant borné, un sommet depuis un achat ancien peut rester indéterminé.

## Surveillance explicable, sans nouveau score

- **Normal** : données fiables, aucun signal notable selon les règles disponibles.
- **À surveiller** : alerte `watch` existante ou contexte de dégradation défini par les indicateurs déjà présents.
- **À examiner** : alerte `act` existante ou filet personnel atteint. Ce n'est pas un ordre de vente.
- **Données insuffisantes** : cotation/indicateurs anciens, qualité non fiable ou mesures nécessaires absentes. Des alertes connues restent expliquées, mais aucun diagnostic rassurant n'est produit.

Les seuils de durée/recul et sorties Momentum/MA50 restent ceux des achats/stratégies existants (`alerts.py`). Le Momentum reste en points de pourcentage. Les critères de volatilité/repli maximal reprennent **les plafonds du profil choisi** (`strategy.preset` ou configuration personnelle), sur leurs fenêtres actives. Aucun plafond universel nouveau n'est appliqué : le plafond 1,5 % de volatilité quotidienne de Hausse calme ne s'applique pas à Croissance rapide.

Le signal préventif de contradiction réutilise `signals.contradiction` : repli récent de 5 % ou plus sur 5/21 séances dans une progression de fond d'au moins 10 %, ou rebond d'au moins 10 % dans une baisse de fond d'au moins 10 %. Le repli appelle une surveillance ; le rebond est informatif. Ces seuils existaient déjà dans le moteur et ne changent aucun classement. Sortie du Top 50 : information seulement. La volatilité est contextualisée, sans inventer un « score de risque » ni un stop optimal prédit.

Les raisons identiques sont regroupées en conservant la sévérité la plus forte ; les rappels communs sont comptés. Les réglages sont regroupés par stratégie et règles effectives dans Gestion. Les réglages individuels restent accessibles. Une surveillance entièrement désactivée est indiquée, pas affichée comme un avis favorable.

La fraîcheur reprend `service.expected_close` et `last_collection`, y compris le cas d'un titre peu échangé dont la collecte est à jour. Une quote récente ne rend pas des indicateurs historiques anciens fiables. Aucune règle n'envoie d'ordre.

## Périodes et corrections conservées

1S = sept jours calendaires ; 1M/3M/6M/1A retranchent le nombre de mois correspondant, avec ajustement au dernier jour du mois lorsque nécessaire. La borne retenue est la dernière observation au plus tard à cette date. Tout part de la première transaction. Les dates réelles sont affichées. En mode Mon investissement, en 1J seule la valeur en euros des quantités actuelles sur la dernière séance disponible est proposée : les autres modes restent explicitement indisponibles, sans rejouer des transactions intrajournalières inexistantes.

Les six régressions de `4b07314` restent couvertes : largeur effective mobile, pourcentages après ventes, unité du Momentum, lots après split, valeurs nulles sans cours et sélecteurs 1J. Les profils, seuils et scores d'Explorer ne sont pas modifiés.

## Validation reproductible

`make fast`, `make integ` exclusivement en base locale jetable, puis `tests/e2e/portfolio-audit.cjs` (93 combinaisons disponibles) et `tests/e2e/portfolio-dashboard.cjs` (navigation, tris, diagnostics, formulaires, clavier/tactile). Les deux scripts utilisent les fixtures locales de `portfolio_audit_seed.py` et les mêmes variables BASE / JIGO_TEST_DATABASE / JIGO_CHROMIUM / PLAYWRIGHT_MODULE / AUDIT_OUT décrites dans METHODE.md. Le smoke financier de CI vérifie aussi les nouveaux onglets et l'absence de débordement des positions.

## Évolution et analyse : cours et investissements

`portfolio/history` fournit désormais deux jeux de données séparés. Les tableaux existants (`dates`, `gain`, `value`, `lines`) gardent leur calcul financier. `market` contient les observations des titres **encore détenus**, depuis le début de l’historique enregistré, même avant leur premier achat. Les ventes totales restent présentes dans le résultat personnel et les contributions, mais ne créent pas une courbe de titre encore détenu.

- **Cours du titre / Base 100** : `100 × cours observé / cours à la date initiale commune`. Aucun changement de quantité, frais ou taux de change personnel n’intervient. Si le prix initial manque, ou si une rupture de série non résolue traverse la fenêtre, la comparaison de ce titre est indisponible. Les cours réels restent consultables dans leur devise ; l’axe numérique ne représente pas un montant global en euros. Les clôtures utilisent `prepare_series`, comme les fiches existantes : corrections de splits et éventuels cours ajustés du fournisseur.
- **Mon investissement / Depuis vos achats** : gain cumulé, réalisé et latent, depuis les transactions initiales ; en %, dénominateur = achats cumulés, frais compris. La période ne fait que découper la partie visible de cette série cumulative.
- **Mon investissement / Sur la période** : conventions de période déjà définies plus haut. Les deux références sont explicitement sélectionnables. Valeur et apports nets conservent leurs montants historiques ; aucune variation de prix n’est présentée comme le rendement personnel.
- **Classement des pertes** : toujours la contribution personnelle **sur la période**, quel que soit le mode du graphique, par euros croissants. Affiche les résultats négatifs calculables, y compris ceux des titres soldés. Le résultat personnel cumulé, le poids actuel et le recul de la position encore ouverte gardent leurs références séparées. Le détail de toutes les contributions conserve les titres positifs et indisponibles. Les données partielles sont signalées ; les rendements propres aux titres ne sont pas additionnés.

Les prix de marché ne sont jamais remplacés par des prix d’achat. Les dates proviennent de vraies observations : le dernier cours conserve sa date réelle, les observations manquantes restent nulles, et une période plus longue que l’historique disponible n’invente pas de séances. Les différentes devises et les dates effectivement affichées sont explicites. En 1J, les cours peuvent être comparés en base 100 ou affichés en devise sur la dernière séance enregistrée. Le résultat personnel intraday conserve la seule vue Valeur/€ et les autres calculs restent explicitement indisponibles.

### Repères et achats

Les repères sont issus des transactions du propriétaire authentifié : identifiant, date/heure enregistrée, quantité et prix **dans les unités de la transaction**, devise, frais en euros et taux de conversion historique. Les splits ne réécrivent pas ces libellés. Les achats gratuits reconnus comme corrections manuelles de split ne deviennent pas de faux achats économiques. Le premier achat et les compléments sont identifiés, même si un premier lot a été vendu.

Un repère hors de la fenêtre ne se rabat jamais sur son premier point. En quotidien, les achats à une même date partagent une verticale et une infobulle détaillant les titres ; une date sans observation est située entre les dates voisines, sans inventer de cours ce jour-là. En 1J, seul un achat dont l’heure enregistrée se trouve dans la séance visible est tracé ; aucune heure n’est attribuée à un achat hors séance. Les heures restent celles du registre et des barres existants. Les repères sont masquables, accessibles au clavier (Échap pour fermer) et consultables au toucher. Un toucher conserve l’infobulle ; toucher le fond du graphique la ferme.

Le récapitulatif regroupe les achats par titre, conserve les premiers achats hors période et replie les compléments. Sélectionner un titre renforce sa courbe et filtre les repères ; « Tous les titres » rétablit l’ensemble. Les compléments ouverts restent ouverts lors d’un changement de période. Les modifications et toutes les ventes restent dans le tableau de gestion existant.

Validation supplémentaire : `tests/e2e/portfolio-analysis.cjs`, après la fixture locale, contrôle les sept périodes, les deux échelles de cours, les repères groupés/hors période/intraday, le clavier/toucher, la mise en évidence, les contributions en euros, les références personnelles, les séries incomplètes et les ventes totales à 1280, 390 et 375 px. Les tests Python contrôlent indépendamment les séries avant acquisition, les frais, devises, splits et ventes partielles, et l’API PHP réelle.
