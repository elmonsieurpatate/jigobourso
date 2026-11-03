# Portefeuilles V3 — pilotage et conventions financières

## Deux espaces, une période commune

**Mon portefeuille** présente dans cet ordre : portefeuille et période globale, résumé financier, graphique et classement interactif des contributions, tableau compact des positions, détail unique de la sélection. **Historique et gestion** conserve transactions/CSV, ventes, lots et alertes, valeur et mouvements d’argent, allocation géographique, ETF pertinents et paramètres. Le bouton Transaction reste accessible. Il n’y a plus de cartes de positions ni d’onglets d’analyse séparés.

La période démarre à **Depuis le début** à chaque ouverture. Elle pilote un unique instantané (`snapshot`) : résumé de période, graphique, contributions et tableau. La valeur actuelle et le résultat cumulé restent fixes. Les préférences d’unité, de mode de graphique et de tri sont conservées ; un ancien sélecteur de période ne remplace pas ce défaut.

## Résultat personnel et état du titre

La valorisation et les gains restent calculés par `ledger.php`, au **prix moyen pondéré (PMP)**, frais compris et conversions historiques inchangées. Le gain total inclut les ventes. Le pourcentage global = gain / achats cumulés, frais compris. La performance d'une période = gain de la période / (valeur initiale + achats de la période), jamais diminué des produits de vente. Ce ne sont ni des rendements annualisés, ni des TWR/TRI.

L'état du titre décrit séparément les mesures réellement disponibles : tendance sur un mois, momentum 6 mois, moyennes 50/200 séances et volatilité quotidienne sur trois mois. Une plus-value personnelle n'efface pas une tendance défavorable ; une perte ne prouve pas que le marché continue de se dégrader.

Les contributions en euros incluent réalisé et latent et s’additionnent au résultat quand les données sont complètes. Le classement principal utilise les euros, jamais le pourcentage propre au titre. Toutes les contributions, y compris stables, inconnues et titres soldés, restent accessibles à côté du graphique. Les pourcentages de rendement propres aux titres ne s’additionnent pas.

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

## Dates et résultat sur la période

1 semaine = sept jours calendaires ; 1/3/6 mois et 1 an retranchent le nombre de mois, avec ajustement au dernier jour du mois. La borne est la dernière observation disponible au plus tard à cette date. Tous les éléments principaux utilisent **les mêmes indices et dates de `portfolio/history`**. Si le portefeuille est plus récent, la première transaction borne l’historique ; la couverture réelle est affichée. Aucun prix ni gain antérieur à l’acquisition n’est créé. L’historique expose les quantités détenues, dans les unités ajustées des splits déjà employées par le moteur. Les courbes des positions s’interrompent entre une vente totale et un rachat ; le point de sortie et le résultat réalisé restent conservés. Cela n’affecte ni les contributions, ni le registre, ni les rendements calculés.

À la borne de départ, le gain et la valeur sont les états après les transactions datées du jour ; les transactions suivantes contribuent au résultat de la fenêtre. Quand la fenêtre comprend le premier jour enregistré, le calcul inclut les transactions et frais de ce premier jour depuis un portefeuille vide, comme le moteur existant. Les achats pendant la période ne constituent pas un gain ; les ventes ne constituent pas une perte : le résultat cumulé = valeur − achats + ventes nettes de frais. Le dénominateur reste valeur initiale + achats, ou achats cumulés depuis le début, sans déduire les ventes.

En **1 jour**, les données existantes ne reconstituent pas les mouvements intrajournaliers. Le résultat personnel et les contributions de période restent donc indisponibles, la comparaison personnelle et le % sont désactivés. La seule série proposée est la valeur en euros des quantités actuelles sur la dernière séance enregistrée, explicitement nommée ; le résumé cumulé et les positions restent visibles. Le graphique de valeur en gestion suit aussi la même période. Aucun calcul journalier fictif ne remplace une série manquante.

## Graphique, contributions et sélection

Deux modes seulement : **Mon portefeuille** trace le résultat de période, corrigé des achats/ventes hors frais ; **Comparer mes positions** trace le résultat personnel de chaque titre détenu, en € ou en %. Le pourcentage utilise les conventions de période ci-dessus, pas une normalisation des cours à 100. Les séries des titres soldés ne sont ajoutées à la comparaison que lorsqu’ils sont sélectionnés dans les contributions ; leurs gains réalisés restent toujours dans le total.

Le classement adjacent affiche toutes les lignes, pertes décroissantes en euros, gains, stabilité et données insuffisantes. Les deux principales pertes sont identifiées ; la première est sélectionnée automatiquement tant que l’utilisateur n’a pas choisi autrement. Une contribution connue ne permet pas d’inventer le total d’un portefeuille partiellement valorisable. Les étiquettes des courbes portent les tickers à leur extrémité, avec évitement des collisions pour les six positions usuelles. La sélection épaissit le tracé, atténue les autres et le dessine en dernier. Une légende ou un clic sur contribution/tableau sélectionne le titre sans le masquer arbitrairement.

L’option **Courbes séparées** donne une série distincte par position avec échelle propre explicitement indiquée : les superpositions et une position très volatile ne peuvent plus rendre les autres illisibles. Les montants de contribution, toujours en euros, restent comparables et synchronisés. Le même unique tableau sert sur ordinateur et mobile ; sept tris utilisent les valeurs de la période (pertes/gains/impact/%, poids, recul, surveillance).

Le résumé lié à la sélection donne résultat de période, résultat cumulé depuis les achats (ventes comprises), poids et premier achat. La fiche approfondie reste fermée initialement, puis accessible depuis contribution, tableau, alerte ou bouton Détails. Elle réutilise les diagnostics existants, les lots, stratégies et réglages, le suivi des sommets et la fiche du titre. Le tableau prend le **premier achat chronologique**, pas la transaction la plus récente de la liste de gestion triée à l’envers.

Les prix de marché historiques restent dans l’analyse approfondie du titre, y compris avant l’achat, dans leur devise et sans frais/change personnel. Son sélecteur propre ne pilote que cette fiche de marché ; il ne change jamais la période globale ni les montants du portefeuille. Aucun nouveau moteur ni seuil de surveillance n’est ajouté.

## Repères et dates de perte

Les achats viennent du registre authentifié : date/heure, ticker, quantité, prix et devise d’origine, frais en euros, conversion historique. Les unités de la transaction ne sont pas réécrites après un split. Les corrections manuelles de split reconnues ne deviennent pas de faux achats économiques. Les achats à la même date sont regroupés ; sélectionner un titre filtre ses repères. Les repères sont masquables, accessibles au clavier et au toucher. Les achats hors période restent consultables dans la fiche sans être rabattus au début du graphique.

Le détail distingue premier achat et compléments, première perte observée et séquence de perte observée actuelle. Les frais peuvent expliquer une perte dès le premier achat. Une lacune interrompt la séquence ; une dernière valeur inconnue ne permet pas d’affirmer une perte actuelle. Aucun franchissement exact entre deux observations n’est inventé. Le recul garde la référence distincte aux quantités actuellement détenues, depuis le dernier achat encore ouvert.

## Validation reproductible

`make fast`, `make integ` en base locale jetable, puis la fixture `tests/e2e/portfolio_audit_seed.py` avec `JIGO_TEST_DATABASE=1`, `JIGO_DB_HOST=127.0.0.1` et la base locale autorisée. Aucune de ces fixtures ne cible une base de production.

- `tests/e2e/portfolio-cockpit.cjs` vérifie les deux espaces, le défaut Depuis le début, le cas six positions dont deux paires superposées, l’unicité et la synchronisation de la semaine, les dates des achats, le tableau et ses sept tris, les clics/clavier/toucher, les cours approfondis, les réglages par lot et les données partielles/ventes totales à 1280, 390 et 375 px. Il remplace les anciennes suites liées aux quatre onglets (`portfolio-dashboard`, `portfolio-analysis`, `portfolio-focus`).
- `tests/e2e/portfolio-audit.cjs` conserve les six régressions financières : géométrie mobile, dénominateurs après ventes, Momentum, FIFO après split, absence de cours et 1J explicite. La matrice actuelle comporte 75 combinaisons (deux modes × deux unités × six périodes, plus 1J, sur trois largeurs), avec oracles indépendants sur les séries et sommes des contributions.
- `tests/e2e/financial.cjs` vérifie les deux espaces dans le smoke de CI, avec les autres parcours Explorer/ETF/comptes existants.
- Les tests rapides et d’intégration des moteurs PMP/FIFO, frais/devises, splits, données absentes et suivi des sommets restent applicables. Les algorithmes et seuils d’Explorer ne changent pas.
